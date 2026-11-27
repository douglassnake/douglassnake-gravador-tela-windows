"""Smoke Xvfb: compact app, vertical scrolling and fixed controls, without Windows hardware."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

class FakeCapture:
    def __enter__(self):
        self.monitors = [
            {'left': 0, 'top': 0, 'width': 1280, 'height': 720},
            {'left': 0, 'top': 0, 'width': 1280, 'height': 720},
        ]
        return self
    def __exit__(self,*a):
        pass

sys.modules.setdefault('mss', SimpleNamespace(mss=FakeCapture))
from gravador_tela import App
from gravador_v27_scrcpy import SCRCPY_B_SOURCE

with patch('gravador_tela.enumerate_windows', return_value=[]):
    app = App()
    try:
        app.update()
        assert 'RC5' in app.title(), app.title()
        assert app.winfo_height() <= app.winfo_screenheight(), (app.winfo_height(), app.winfo_screenheight())
        panel = app.scroll_panel
        assert panel.bar.winfo_viewable(), 'scrollbar is not visible'
        assert panel.canvas.winfo_height() < panel.content.winfo_height(), 'content must be vertically scrollable'
        assert app.record_button.winfo_viewable() and app.pause_button.winfo_viewable()
        assert app.record_button.winfo_rooty() + app.record_button.winfo_height() < app.winfo_rooty() + app.winfo_height()
        assert app.record_button.master is not panel.content, 'record button must be in fixed dock'
        # Scrolling changes the canvas but does not reposition the fixed controls.
        button_y = app.record_button.winfo_rooty()
        panel.canvas.yview_moveto(0)
        app.update_idletasks()
        assert panel.canvas.yview()[0] == 0
        child = app.area_label
        event = SimpleNamespace(widget=child, delta=-120, num=0)
        assert panel._on_mousewheel(event) == 'break'
        assert panel.canvas.yview()[0] > 0, 'mouse wheel should advance the form'
        assert app.record_button.winfo_rooty() == button_y, 'dock moved on scroll'
        before = panel.canvas.yview()
        assert panel._on_mousewheel(SimpleNamespace(widget=app.record_button, delta=-120, num=0)) is None
        assert panel.canvas.yview() == before, 'mouse scroll over fixed dock must be ignored'
        # At minimum window size, the controls are still visible.
        app.geometry('900x560')
        app.update()
        assert panel.canvas.winfo_height() > 100
        assert app.record_button.winfo_viewable()
        assert app.recover_button.winfo_viewable()
        assert app.draw_button.winfo_viewable()
        # Backward-compatible scrcpy controls and capture settings remain accessible.
        app.dual_enabled_var.set(True)
        app.second_source_var.set(SCRCPY_B_SOURCE)
        app._second_area_changed()
        assert app.scrcpy_path_entry.winfo_manager() == 'grid'
        assert app.scrcpy_detect_button.winfo_manager() == 'grid'
        with TemporaryDirectory() as d:
            exe = Path(d) / 'scrcpy.exe'
            exe.write_bytes(b'demo')
            (Path(d) / 'adb.exe').write_bytes(b'demo')
            app.scrcpy_exe_var.set(str(exe))
            app.android_usb_ok = True
            settings = app._settings()
            assert settings.scrcpy_exe_b == str(exe) and settings.fps == 24
        app.state = 'recording'
        app._tick()
        assert 'GRAVANDO' in app.header_state_var.get()
        app.state = 'idle'
        app._tick()
        assert 'PRONTO' in app.header_state_var.get()
        print('GUI_RC5_SCROLL_FIXED_DOCK_SCRCPY_OK')
    finally:
        app._on_close()
