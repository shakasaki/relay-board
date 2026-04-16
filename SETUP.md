# USBB-RELAY02 Setup & Usage

## Hardware

- **Board**: USBB-RELAY02 (2-channel HID USB relay)
- **USB ID**: `16c0:05df` (V-USB HID device)
- **Protocol**: HID Feature Reports over `/dev/hidraw*` — NOT serial

## Setup (one-time)

### 1. Install udev rule

This allows your user to access the relay board without `sudo`:

```bash
sudo cp 99-usb-relay.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

Then **unplug and replug** the board.

### 2. Verify the board is detected

```bash
lsusb | grep 16c0:05df
```

You should see:
```
Bus XXX Device XXX: ID 16c0:05df Van Ooijen Technische Informatica HID device ...
```

## Usage

```bash
# Check relay status and board ID
python3 relay_control.py status

# Turn on relay 1
python3 relay_control.py on 1

# Turn off relay 1
python3 relay_control.py off 1

# Turn on relay 2
python3 relay_control.py on 2

# Turn on both relays
python3 relay_control.py on all

# Turn off both relays
python3 relay_control.py off all

# Use a specific hidraw device (if auto-detect fails)
python3 relay_control.py --device /dev/hidraw4 status
```

## Troubleshooting

### Permission denied
If you get a permission error and haven't installed the udev rule, either:
- Install the udev rule (see above), or
- Run with `sudo python3 relay_control.py ...`

### Board not found
1. Check it's plugged in: `lsusb | grep 16c0:05df`
2. Check hidraw devices exist: `ls /dev/hidraw*`
3. Try specifying the device manually: `--device /dev/hidrawN`

## Protocol Reference

The board uses 9-byte HID Feature Reports (report ID `0x00` + 8 data bytes):

| Command | Byte 1 | Byte 2 | Effect |
|---------|--------|--------|--------|
| `0xFF`  | N      | —      | Relay N ON |
| `0xFD`  | N      | —      | Relay N OFF |
| `0xFE`  | `0x00` | —      | All relays ON |
| `0xFC`  | `0x00` | —      | All relays OFF |

Reading the feature report returns the 5-char board ID (bytes 1-5) and relay state bitmask (byte 8, bit 0 = K1, bit 1 = K2).

Reference: https://github.com/pavel-a/usb-relay-hid
