#!/usr/bin/env bash
# Share the Pi's Wi-Fi internet to a device plugged into eth0, via NetworkManager.
# Usage: share-eth0.sh {on|off|toggle|status}
set -euo pipefail

CON="share-eth0"
IF="eth0"

notify() {
    echo "$1"
    command -v notify-send >/dev/null 2>&1 && notify-send "Internet Sharing (eth0)" "$1" || true
}

ensure_connection() {
    nmcli -t -f NAME connection show | grep -qx "$CON" && return
    # First-time creation needs root; prompts for password in a terminal.
    sudo nmcli connection add type ethernet ifname "$IF" con-name "$CON" \
        ipv4.method shared ipv6.method ignore autoconnect no >/dev/null
}

is_up() { nmcli -t -f NAME connection show --active | grep -qx "$CON"; }

case "${1:-toggle}" in
    on)
        ensure_connection
        is_up || nmcli connection up "$CON" >/dev/null
        notify "ON — NUC should get a lease in 10.42.0.0/24"
        ;;
    off)
        is_up && nmcli connection down "$CON" >/dev/null || true
        notify "OFF"
        ;;
    toggle)
        if is_up; then
            nmcli connection down "$CON" >/dev/null
            notify "OFF"
        else
            ensure_connection
            nmcli connection up "$CON" >/dev/null
            notify "ON — NUC should get a lease in 10.42.0.0/24"
        fi
        ;;
    status)
        if is_up; then
            echo "ON"
            nmcli -g IP4.ADDRESS connection show "$CON"
        else
            echo "OFF"
        fi
        ;;
    *)
        echo "Usage: $0 {on|off|toggle|status}" >&2
        exit 2
        ;;
esac
