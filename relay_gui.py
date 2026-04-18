#!/usr/bin/env python3
"""
GUI for controlling USBB-RELAY04 USB relay board.

Reads relay configuration from config.json (same directory).
Each relay gets a row with: number, name, ON/OFF status, ON button, OFF button, PULSE button.

Requires: tkinter (usually included with Python3).
"""

import json
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox

# Import relay control functions from the existing script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from relay_control_04 import (
    find_relay_hidraw,
    relay_on,
    relay_off,
    read_state,
)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


class RelayGUI:
    def __init__(self, root, config, fd):
        self.root = root
        self.fd = fd
        self.root.title("Relay Control")
        self.root.resizable(False, False)

        self.relays = config["relays"]
        self.status_labels = {}
        self.pulse_buttons = {}
        self.on_buttons = {}
        self.off_buttons = {}

        # Header row
        headers = ["#", "Name", "Status", "", "", ""]
        for col, text in enumerate(headers):
            lbl = tk.Label(root, text=text, font=("sans-serif", 10, "bold"))
            lbl.grid(row=0, column=col, padx=6, pady=(8, 2), sticky="w")

        # One row per relay
        for i, relay_cfg in enumerate(self.relays):
            row = i + 1
            num = relay_cfg["relay"]
            name = relay_cfg.get("name", f"Relay {num}")
            pulse_dur = relay_cfg.get("pulse_duration", 2)

            # Relay number
            tk.Label(root, text=str(num), font=("sans-serif", 11)) \
                .grid(row=row, column=0, padx=6, pady=4, sticky="w")

            # Name
            tk.Label(root, text=name, font=("sans-serif", 11), width=16, anchor="w") \
                .grid(row=row, column=1, padx=6, pady=4, sticky="w")

            # Status
            status_lbl = tk.Label(root, text="--", font=("sans-serif", 11, "bold"), width=4)
            status_lbl.grid(row=row, column=2, padx=6, pady=4)
            self.status_labels[num] = status_lbl

            # ON button
            btn_on = tk.Button(root, text="ON", width=5,
                               command=lambda n=num: self.do_on(n))
            btn_on.grid(row=row, column=3, padx=4, pady=4)
            self.on_buttons[num] = btn_on

            # OFF button
            btn_off = tk.Button(root, text="OFF", width=5,
                                command=lambda n=num: self.do_off(n))
            btn_off.grid(row=row, column=4, padx=4, pady=4)
            self.off_buttons[num] = btn_off

            # PULSE button
            btn_pulse = tk.Button(root, text=f"PULSE ({pulse_dur}s)", width=10,
                                  command=lambda n=num, d=pulse_dur: self.do_pulse(n, d))
            btn_pulse.grid(row=row, column=5, padx=4, pady=4)
            self.pulse_buttons[num] = btn_pulse

        # Quit button
        quit_row = len(self.relays) + 1
        tk.Button(root, text="QUIT", width=10, command=self.quit) \
            .grid(row=quit_row, column=0, columnspan=6, pady=(8, 10))

        self.refresh_status()

    def refresh_status(self):
        try:
            _, state = read_state(self.fd)
        except OSError:
            for num in self.status_labels:
                self.status_labels[num].config(text="ERR", fg="gray")
            return
        for num in self.status_labels:
            bit = (state >> (num - 1)) & 1
            if bit:
                self.status_labels[num].config(text="ON", fg="green")
            else:
                self.status_labels[num].config(text="OFF", fg="red")

    def do_on(self, num):
        try:
            relay_on(self.fd, num)
        except OSError as e:
            messagebox.showerror("Error", str(e))
        self.refresh_status()

    def do_off(self, num):
        try:
            relay_off(self.fd, num)
        except OSError as e:
            messagebox.showerror("Error", str(e))
        self.refresh_status()

    def do_pulse(self, num, duration):
        """Pulse in a background thread so the GUI stays responsive."""
        btn = self.pulse_buttons[num]
        btn.config(state=tk.DISABLED)

        def _pulse():
            try:
                relay_on(self.fd, num)
                self.root.after(0, self.refresh_status)
                threading.Event().wait(duration)
                relay_off(self.fd, num)
            except OSError as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, self.refresh_status)
                self.root.after(0, lambda: btn.config(state=tk.NORMAL))

        threading.Thread(target=_pulse, daemon=True).start()

    def quit(self):
        self.root.destroy()


def main():
    # Load config
    try:
        config = load_config()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {CONFIG_FILE}: {e}", file=sys.stderr)
        sys.exit(1)

    # Find and open relay device
    device = find_relay_hidraw()
    if not device:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Relay Board Not Found",
                             "USB relay board not detected.\n"
                             "Is it plugged in?")
        sys.exit(1)

    try:
        fd = os.open(device, os.O_RDWR)
    except PermissionError:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Permission Denied",
                             f"Cannot open {device}.\n"
                             "Install the udev rule or run with sudo.")
        sys.exit(1)

    root = tk.Tk()
    RelayGUI(root, config, fd)
    root.mainloop()
    os.close(fd)


if __name__ == "__main__":
    main()
