#!/usr/bin/env python3
"""
Pulse relay(s) ON for a specified duration then turn OFF (USBB-RELAY04).

Usage:
  python3 relay_pulse_04.py 1          # pulse K1 for 2s
  python3 relay_pulse_04.py 3          # pulse K3 for 2s
  python3 relay_pulse_04.py all        # pulse all 4 for 2s
  python3 relay_pulse_04.py 1 -t 5     # pulse K1 for 5s
"""

import argparse
import array
import fcntl
import glob
import os
import sys
import time

VENDOR_ID = 0x16C0
PRODUCT_ID = 0x05DF
NUM_RELAYS = 4
HIDIOCSFEATURE = 0xC0094806

CMD_ON = 0xFF
CMD_OFF = 0xFD
CMD_ALL_ON = 0xFE
CMD_ALL_OFF = 0xFC


def find_relay_hidraw():
    for hidraw in sorted(glob.glob("/dev/hidraw*")):
        num = hidraw.replace("/dev/hidraw", "")
        try:
            with open(f"/sys/class/hidraw/hidraw{num}/device/uevent") as f:
                uevent = f.read()
            for line in uevent.splitlines():
                if line.startswith("HID_ID="):
                    parts = line.split("=")[1].split(":")
                    if int(parts[1], 16) == VENDOR_ID and int(parts[2], 16) == PRODUCT_ID:
                        return hidraw
        except (FileNotFoundError, IndexError, ValueError):
            continue
    return None


def send_cmd(fd, cmd, relay_num=0):
    buf = array.array("B", [0x00, cmd, relay_num, 0, 0, 0, 0, 0, 0])
    fcntl.ioctl(fd, HIDIOCSFEATURE, buf)


def main():
    parser = argparse.ArgumentParser(description="Pulse relay(s) ON then OFF (4-relay board)")
    parser.add_argument("relay", help=f"Relay number (1-{NUM_RELAYS}) or 'all'")
    parser.add_argument("-t", "--time", type=float, default=2.0,
                        help="Duration in seconds (default: 2)")
    parser.add_argument("--device", default=None,
                        help="hidraw device path (auto-detected if omitted)")
    args = parser.parse_args()

    if args.relay != "all":
        try:
            r = int(args.relay)
            if r < 1 or r > NUM_RELAYS:
                parser.error(f"Relay number must be 1-{NUM_RELAYS}")
        except ValueError:
            parser.error(f"Relay must be a number (1-{NUM_RELAYS}) or 'all'")

    device = args.device or find_relay_hidraw()
    if not device:
        print("Error: relay board not found", file=sys.stderr)
        sys.exit(1)

    fd = os.open(device, os.O_RDWR)
    try:
        if args.relay == "all":
            print(f"K1-K{NUM_RELAYS} ON for {args.time}s...")
            send_cmd(fd, CMD_ALL_ON)
            time.sleep(args.time)
            send_cmd(fd, CMD_ALL_OFF)
        else:
            r = int(args.relay)
            print(f"K{r} ON for {args.time}s...")
            send_cmd(fd, CMD_ON, r)
            time.sleep(args.time)
            send_cmd(fd, CMD_OFF, r)
        print("OFF")
    except KeyboardInterrupt:
        # Safety: turn off on Ctrl+C
        if args.relay == "all":
            send_cmd(fd, CMD_ALL_OFF)
        else:
            send_cmd(fd, CMD_OFF, int(args.relay))
        print("\nInterrupted — relay(s) OFF")
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
