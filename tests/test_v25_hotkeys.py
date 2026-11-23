"""Teste RC2: registro de teclas globais, contingência F8 e botão de desenho."""
import queue
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

try:
    import mss
except ImportError:
    sys.modules["mss"] = SimpleNamespace(mss=lambda: None)

from gravador_tela import App, GlobalShortcuts


class GlobalShortcutTests(unittest.TestCase):
    def test_f8_is_alias_of_ctrl_alt_d(self):
        ids = GlobalShortcuts.bindings()
        self.assertEqual(len({row[0] for row in ids}), len(ids))
        draw = [row for row in ids if row[2] == "toggle_draw"]
        self.assertEqual({row[4] for row in draw}, {"Ctrl+Alt+D", "F8"})
        self.assertEqual(next(row for row in draw if row[4] == "F8")[3], 0)

    def test_conflicting_primary_still_registers_f8(self):
        events = queue.Queue()
        shortcuts = GlobalShortcuts(events)
        shortcuts.stop.set()
        api = MagicMock()
        api.RegisterHotKey.side_effect = lambda hwnd, ident, mods, key: ident != 206
        with patch("gravador_tela.ctypes.windll", SimpleNamespace(user32=api), create=True):
            shortcuts._worker()
        event, status = events.get_nowait()
        self.assertEqual(event, "shortcut_status")
        self.assertFalse(status["primary_draw"])
        self.assertTrue(status["fallback_draw"])
        self.assertIn("Ctrl+Alt+D", status["failed"])
        registrations = [c.args[1] for c in api.RegisterHotKey.call_args_list]
        self.assertIn(210, registrations)
        released = [c.args[1] for c in api.UnregisterHotKey.call_args_list]
        self.assertNotIn(206, released)
        self.assertIn(210, released)

    def test_both_taken_other_hotkeys_remain_registered(self):
        events = queue.Queue()
        shortcuts = GlobalShortcuts(events)
        shortcuts.stop.set()
        api = MagicMock()
        api.RegisterHotKey.side_effect = lambda hwnd, ident, mods, key: ident not in (206, 210)
        with patch("gravador_tela.ctypes.windll", SimpleNamespace(user32=api), create=True):
            shortcuts._worker()
        event, status = events.get_nowait()
        self.assertEqual(event, "shortcut_status")
        self.assertFalse(status["primary_draw"])
        self.assertFalse(status["fallback_draw"])
        self.assertIn("F8", status["failed"])


class ButtonTests(unittest.TestCase):
    def test_button_activates_draw_and_returns_to_chrome(self):
        app = MagicMock()
        app.state = "recording"
        app.studio_draw_mode = True
        app.engine.settings.area.hwnd = 12345
        App._manual_draw_action(app)
        app._visual_shortcut.assert_called_once_with("toggle_draw")
        app._prepare_visible_window.assert_called_once_with(12345)

    def test_disabled_while_not_recording(self):
        app = MagicMock()
        app.state = "idle"
        App._manual_draw_action(app)
        app._visual_shortcut.assert_not_called()
        app.studio_status.set.assert_called_once()

    def test_overlay_exception_does_not_leave_drawing_on(self):
        app = MagicMock()
        app.state = "recording"
        app.studio_draw_mode = False
        app.studio_overlay.set_drawing.side_effect = [RuntimeError("layer failed"), None]
        app.highlight_var.get.return_value = False
        app.clicks_var.get.return_value = False
        app.zoom_var.get.return_value = False
        App._visual_shortcut(app, "toggle_draw")
        self.assertFalse(app.studio_draw_mode)
        self.assertEqual(app.studio_overlay.set_drawing.call_count, 2)
        self.assertIn("Falha", app.studio_status.set.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
