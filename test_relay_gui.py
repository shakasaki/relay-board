#!/usr/bin/env python3
"""Tests for relay_gui.py — mocks all hardware access."""

import json
import os
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import relay_gui


class TestLoadConfig(unittest.TestCase):
    def test_loads_valid_config(self):
        cfg = {"relays": [{"relay": 1, "name": "Test", "pulse_duration": 3}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            f.flush()
            with patch.object(relay_gui, "CONFIG_FILE", f.name):
                result = relay_gui.load_config()
        os.unlink(f.name)
        self.assertEqual(result, cfg)

    def test_missing_file_raises(self):
        with patch.object(relay_gui, "CONFIG_FILE", "/nonexistent.json"):
            with self.assertRaises(FileNotFoundError):
                relay_gui.load_config()

    def test_invalid_json_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json{{{")
            f.flush()
            with patch.object(relay_gui, "CONFIG_FILE", f.name):
                with self.assertRaises(json.JSONDecodeError):
                    relay_gui.load_config()
        os.unlink(f.name)


class TestRelayGUI(unittest.TestCase):
    """Tests that exercise the GUI class with mocked hardware."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError:
            raise unittest.SkipTest("No display available for tkinter tests")

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.config = {
            "relays": [
                {"relay": 1, "name": "Pump", "pulse_duration": 2},
                {"relay": 2, "name": "Valve", "pulse_duration": 5},
                {"relay": 3, "name": "Light", "pulse_duration": 2},
                {"relay": 4, "name": "Fan", "pulse_duration": 3},
            ]
        }
        self.fake_fd = 99
        # Patch read_state so constructor's refresh_status doesn't hit hardware
        patcher = patch.object(relay_gui, "read_state", return_value=("ABCDE", 0))
        self.mock_read_state = patcher.start()
        self.addCleanup(patcher.stop)

        self.gui = relay_gui.RelayGUI(self.root, self.config, self.fake_fd)

    def test_all_relay_rows_created(self):
        self.assertEqual(set(self.gui.status_labels.keys()), {1, 2, 3, 4})
        self.assertEqual(set(self.gui.on_buttons.keys()), {1, 2, 3, 4})
        self.assertEqual(set(self.gui.off_buttons.keys()), {1, 2, 3, 4})
        self.assertEqual(set(self.gui.pulse_buttons.keys()), {1, 2, 3, 4})

    def test_refresh_status_all_off(self):
        self.mock_read_state.return_value = ("ABCDE", 0b0000)
        self.gui.refresh_status()
        for num in (1, 2, 3, 4):
            self.assertEqual(self.gui.status_labels[num].cget("text"), "OFF")

    def test_refresh_status_all_on(self):
        self.mock_read_state.return_value = ("ABCDE", 0b1111)
        self.gui.refresh_status()
        for num in (1, 2, 3, 4):
            self.assertEqual(self.gui.status_labels[num].cget("text"), "ON")

    def test_refresh_status_mixed(self):
        # K1 ON, K2 OFF, K3 ON, K4 OFF  -> bitmask 0b0101 = 5
        self.mock_read_state.return_value = ("ABCDE", 0b0101)
        self.gui.refresh_status()
        self.assertEqual(self.gui.status_labels[1].cget("text"), "ON")
        self.assertEqual(self.gui.status_labels[2].cget("text"), "OFF")
        self.assertEqual(self.gui.status_labels[3].cget("text"), "ON")
        self.assertEqual(self.gui.status_labels[4].cget("text"), "OFF")

    def test_refresh_status_oserror(self):
        self.mock_read_state.side_effect = OSError("device gone")
        self.gui.refresh_status()
        for num in (1, 2, 3, 4):
            self.assertEqual(self.gui.status_labels[num].cget("text"), "ERR")

    @patch.object(relay_gui, "relay_on")
    def test_do_on_calls_relay_on(self, mock_on):
        self.gui.do_on(2)
        mock_on.assert_called_once_with(self.fake_fd, 2)

    @patch.object(relay_gui, "relay_off")
    def test_do_off_calls_relay_off(self, mock_off):
        self.gui.do_off(3)
        mock_off.assert_called_once_with(self.fake_fd, 3)

    @patch.object(relay_gui, "relay_off")
    @patch.object(relay_gui, "relay_on")
    def test_do_pulse_calls_on_then_off(self, mock_on, mock_off):
        # Collect root.after callbacks instead of posting to tk event loop
        after_calls = []
        self.gui.root.after = lambda ms, fn: after_calls.append(fn)
        self.gui.do_pulse(1, 0.05)
        import time
        time.sleep(0.3)
        mock_on.assert_called_once_with(self.fake_fd, 1)
        mock_off.assert_called_once_with(self.fake_fd, 1)

    @patch.object(relay_gui, "relay_off")
    @patch.object(relay_gui, "relay_on")
    def test_pulse_button_re_enabled_after_pulse(self, mock_on, mock_off):
        # Collect root.after callbacks and run them manually
        after_calls = []
        self.gui.root.after = lambda ms, fn: after_calls.append(fn)
        self.gui.do_pulse(2, 0.05)
        self.assertEqual(str(self.gui.pulse_buttons[2].cget("state")), "disabled")
        import time
        time.sleep(0.3)
        # Run the queued tk callbacks (refresh_status, re-enable button)
        for fn in after_calls:
            fn()
        self.assertEqual(str(self.gui.pulse_buttons[2].cget("state")), "normal")

    def test_pulse_button_labels(self):
        self.assertEqual(self.gui.pulse_buttons[1].cget("text"), "PULSE (2s)")
        self.assertEqual(self.gui.pulse_buttons[2].cget("text"), "PULSE (5s)")
        self.assertEqual(self.gui.pulse_buttons[4].cget("text"), "PULSE (3s)")

    def test_config_defaults(self):
        """Relay with no name/pulse_duration gets defaults."""
        config = {"relays": [{"relay": 1}]}
        self.mock_read_state.return_value = ("ABCDE", 0)
        gui = relay_gui.RelayGUI(self.root, config, self.fake_fd)
        self.assertEqual(gui.pulse_buttons[1].cget("text"), "PULSE (2s)")


if __name__ == "__main__":
    unittest.main()
