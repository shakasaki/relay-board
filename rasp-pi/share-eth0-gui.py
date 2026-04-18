#!/usr/bin/env python3
"""Simple Tk GUI to toggle NetworkManager 'shared' mode on eth0."""
import subprocess
import tkinter as tk
from tkinter import messagebox

CON = "share-eth0"
IFACE = "eth0"


def nmcli(*args, elevate=False):
    cmd = (["pkexec"] if elevate else []) + ["nmcli", *args]
    return subprocess.run(cmd, capture_output=True, text=True)


def connection_exists():
    return CON in nmcli("-t", "-f", "NAME", "connection", "show").stdout.splitlines()


def is_active():
    return CON in nmcli("-t", "-f", "NAME", "connection", "show", "--active").stdout.splitlines()


def shared_address():
    r = nmcli("-g", "IP4.ADDRESS", "connection", "show", CON)
    return r.stdout.strip() if r.returncode == 0 else ""


def ensure_connection():
    if connection_exists():
        return True, ""
    r = nmcli("connection", "add", "type", "ethernet", "ifname", IFACE,
              "con-name", CON, "ipv4.method", "shared",
              "ipv6.method", "ignore", "autoconnect", "no", elevate=True)
    return r.returncode == 0, r.stderr.strip()


def set_sharing(on):
    if on:
        ok, err = ensure_connection()
        if not ok:
            return False, err or "Could not create connection"
        r = nmcli("connection", "up", CON)
    else:
        r = nmcli("connection", "down", CON)
    return r.returncode == 0, r.stderr.strip()


class App:
    REFRESH_MS = 2000

    def __init__(self, root):
        self.root = root
        root.title("LAN Sharing")
        root.geometry("280x150")
        root.resizable(False, False)

        self.status_var = tk.StringVar(value="...")
        self.status_label = tk.Label(root, textvariable=self.status_var,
                                     font=("Sans", 13, "bold"))
        self.status_label.pack(pady=(18, 4))

        self.detail_var = tk.StringVar(value="")
        tk.Label(root, textvariable=self.detail_var,
                 font=("Sans", 9), fg="#666").pack()

        self.switch = tk.BooleanVar()
        tk.Checkbutton(root, text="Share LAN (eth0)", variable=self.switch,
                       command=self.on_toggle, font=("Sans", 11)).pack(pady=12)

        self.refresh()

    def on_toggle(self):
        want = self.switch.get()
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        ok, err = set_sharing(want)
        self.root.config(cursor="")
        if not ok:
            messagebox.showerror("Sharing error", err or "nmcli failed")
        self.refresh()

    def refresh(self):
        active = is_active()
        self.switch.set(active)
        if active:
            self.status_var.set("Sharing: ON")
            self.status_label.config(fg="#2a7a2a")
            self.detail_var.set(f"eth0  {shared_address() or '10.42.0.1/24'}")
        else:
            self.status_var.set("Sharing: OFF")
            self.status_label.config(fg="#888")
            self.detail_var.set("no DHCP, no NAT")
        self.root.after(self.REFRESH_MS, self.refresh)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
