#!/usr/bin/env python3
"""
Control script for USBB-RELAY04 (16c0:05df) HID USB relay board.

This board uses V-USB HID Feature Reports via ioctl, NOT serial or regular writes.
Protocol (9-byte feature reports: 1 byte report ID + 8 data bytes):
  - Relay N ON:   [0x00, 0xFF, N, 0, 0, 0, 0, 0, 0]
  - Relay N OFF:  [0x00, 0xFD, N, 0, 0, 0, 0, 0, 0]
  - All ON:       [0x00, 0xFE, 0, 0, 0, 0, 0, 0, 0]
  - All OFF:      [0x00, 0xFC, 0, 0, 0, 0, 0, 0, 0]
  - Read state:   get feature report -> byte[8] = relay state bitmask
  - Board ID:     get feature report -> bytes[1:6] = 5-char ASCII ID

Reference: https://github.com/pavel-a/usb-relay-hid

Usage:
  python3 relay_control_04.py status
  python3 relay_control_04.py on 1
  python3 relay_control_04.py off 3
  python3 relay_control_04.py on all
  python3 relay_control_04.py off all

Requires: udev rule or sudo for /dev/hidraw access.
"""

import argparse
import array
import fcntl
import glob
import os
import sys

VENDOR_ID = 0x16C0
PRODUCT_ID = 0x05DF
NUM_RELAYS = 4
REPORT_LEN = 9  # 1 byte report ID + 8 bytes data

# ioctl constants for HID feature reports
# HIDIOCSFEATURE(9) = _IOC(_IOC_WRITE|_IOC_READ, 'H', 0x06, 9)
# HIDIOCGFEATURE(9) = _IOC(_IOC_WRITE|_IOC_READ, 'H', 0x07, 9)
HIDIOCSFEATURE = 0xC0094806
HIDIOCGFEATURE = 0xC0094807

CMD_ON = 0xFF
CMD_OFF = 0xFD
CMD_ALL_ON = 0xFE
CMD_ALL_OFF = 0xFC


def find_relay_hidraw() -> str | None:
    """Find the hidraw device node for the USB relay board."""
    for hidraw in sorted(glob.glob("/dev/hidraw*")):
        num = hidraw.replace("/dev/hidraw", "")
        sysfs = f"/sys/class/hidraw/hidraw{num}/device"
        try:
            with open(os.path.join(sysfs, "uevent")) as f:
                uevent = f.read()
            # Look for HID_ID=0003:000016C0:000005DF
            for line in uevent.splitlines():
                if line.startswith("HID_ID="):
                    parts = line.split("=")[1].split(":")
                    vid = int(parts[1], 16)
                    pid = int(parts[2], 16)
                    if vid == VENDOR_ID and pid == PRODUCT_ID:
                        return hidraw
        except (FileNotFoundError, IndexError, ValueError):
            continue
    return None


def send_feature_report(fd, data: list[int]):
    """Send a HID feature report (report ID 0x00 + 8 bytes)."""
    buf = array.array("B", [0x00] + data + [0] * (8 - len(data)))
    fcntl.ioctl(fd, HIDIOCSFEATURE, buf)


def get_feature_report(fd) -> bytes:
    """Read a HID feature report. Returns 9 bytes (report ID + 8 data)."""
    buf = array.array("B", [0x00] * REPORT_LEN)
    fcntl.ioctl(fd, HIDIOCGFEATURE, buf)
    return buf.tobytes()


def relay_on(fd, relay_num: int):
    """Turn a relay ON (1-based)."""
    send_feature_report(fd, [CMD_ON, relay_num])


def relay_off(fd, relay_num: int):
    """Turn a relay OFF (1-based)."""
    send_feature_report(fd, [CMD_OFF, relay_num])


def all_on(fd):
    """Turn all relays ON."""
    send_feature_report(fd, [CMD_ALL_ON])


def all_off(fd):
    """Turn all relays OFF."""
    send_feature_report(fd, [CMD_ALL_OFF])


def read_state(fd) -> tuple[str, int]:
    """Read board ID and relay state. Returns (board_id, state_bitmask)."""
    data = get_feature_report(fd)
    board_id = data[1:6].decode("ascii", errors="replace").rstrip("\x00")
    state = data[8]
    return board_id, state


def print_status(board_id: str, state: int):
    """Print human-readable relay status."""
    print(f"Board ID: {board_id}")
    print("Relay status:")
    for i in range(1, NUM_RELAYS + 1):
        bit = (state >> (i - 1)) & 1
        status = "ON" if bit else "OFF"
        print(f"  K{i}: {status}")


def main():
    parser = argparse.ArgumentParser(description="USBB-RELAY04 control")
    parser.add_argument("action", choices=["on", "off", "status"],
                        help="Action to perform")
    parser.add_argument("relay", nargs="?", default=None,
                        help="Relay number (1-4) or 'all'")
    parser.add_argument("--device", default=None,
                        help="hidraw device path (auto-detected if omitted)")
    args = parser.parse_args()

    # Find device
    device = args.device or find_relay_hidraw()
    if not device:
        print("Error: USB relay board not found. Is it plugged in?", file=sys.stderr)
        sys.exit(1)

    print(f"Using device: {device}")

    # Validate relay argument for on/off
    if args.action in ("on", "off"):
        if args.relay is None:
            parser.error(f"on/off requires a relay number (1-{NUM_RELAYS}, or 'all')")
        if args.relay != "all":
            try:
                r = int(args.relay)
                if r < 1 or r > NUM_RELAYS:
                    parser.error(f"Relay number must be 1-{NUM_RELAYS}")
            except ValueError:
                parser.error("Relay must be a number or 'all'")

    # Open device
    try:
        fd = os.open(device, os.O_RDWR)
    except PermissionError:
        print(f"Error: Permission denied on {device}.", file=sys.stderr)
        print("Run with sudo, or install the udev rule:", file=sys.stderr)
        print("  sudo cp 99-usb-relay.rules /etc/udev/rules.d/", file=sys.stderr)
        print("  sudo udevadm control --reload-rules", file=sys.stderr)
        print("  # then unplug and replug the board", file=sys.stderr)
        sys.exit(1)

    try:
        if args.action == "status":
            board_id, state = read_state(fd)
            print_status(board_id, state)

        elif args.action == "on":
            if args.relay == "all":
                all_on(fd)
                print("All relays: ON")
            else:
                r = int(args.relay)
                relay_on(fd, r)
                print(f"K{r}: ON")

        elif args.action == "off":
            if args.relay == "all":
                all_off(fd)
                print("All relays: OFF")
            else:
                r = int(args.relay)
                relay_off(fd, r)
                print(f"K{r}: OFF")
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
