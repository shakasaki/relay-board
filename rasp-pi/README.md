# rasp-pi / LAN sharing

Share a Raspberry Pi's Wi-Fi internet over its Ethernet port, so a device
plugged into `eth0` (e.g. a NUC with no Wi-Fi / flaky Wi-Fi) gets internet.
Uses NetworkManager's built-in *shared* mode on Pi OS Bookworm — no manual
`iptables`/`dnsmasq` setup.

When enabled:
- Pi sits at `10.42.0.1/24` on `eth0`
- Runs DHCP + DNS for anything plugged in
- NATs traffic out through `wlan0`

## Files

| File                | Role                                                 |
|---------------------|------------------------------------------------------|
| `share-eth0.sh`     | CLI toggle: `on` / `off` / `toggle` / `status`       |
| `share-eth0-gui.py` | Tk GUI with a single *Share LAN* switch + live status |
| `share-eth0.desktop`| Launcher for the GUI (double-click icon / menu entry) |

Both tools drive the same NetworkManager connection (`share-eth0`), so
state stays consistent between them.

## Install (on the Pi)

```bash
# CLI on PATH
sudo install -m 755 share-eth0.sh     /usr/local/bin/share-eth0
# GUI on PATH
sudo install -m 755 share-eth0-gui.py /usr/local/bin/share-eth0-gui

# Desktop icon + menu entry
mkdir -p ~/.local/share/applications
cp share-eth0.desktop ~/.local/share/applications/
cp share-eth0.desktop ~/Desktop/
chmod +x ~/Desktop/share-eth0.desktop
```

First run of `share-eth0 on` (or first click of the GUI checkbox) creates
the NetworkManager connection — requires a sudo / polkit password once.
After that, toggling is password-less.

## Use

```bash
share-eth0 on       # enable sharing
share-eth0 off      # disable
share-eth0 status   # ON / OFF (+ IP when on)
share-eth0-gui      # launch GUI
```

## Verify (without a client plugged in)

```bash
ip -br addr show eth0                                   # 10.42.0.1/24, UP or NO-CARRIER
sysctl net.ipv4.ip_forward                              # 1
sudo nft list ruleset | grep -iE 'masquerade|nm-shared' # masquerade rule
sudo ss -ulnp | grep -E ':(53|67)\b'                    # dnsmasq on DNS + DHCP
```

`NO-CARRIER` just means no cable is plugged in — the config is live and
ready the moment a device is attached.

## Watch a client connect

```bash
sudo journalctl -u NetworkManager -f | grep -i dhcp
```

Shows the `DHCPDISCOVER → OFFER → ACK` exchange when the NUC boots with
the cable in.

## Tear down

```bash
share-eth0 off
sudo nmcli connection delete share-eth0   # remove the NM connection entirely
```
