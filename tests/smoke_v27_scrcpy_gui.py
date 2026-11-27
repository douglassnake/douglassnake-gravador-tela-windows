"""UI smoke: new Android USB source, no hardware calls."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tempfile import TemporaryDirectory
class FakeCapture:
    def __enter__(self):
        self.monitors=[{'left':0,'top':0,'width':1280,'height':720}, {'left':0,'top':0,'width':1280,'height':720}]
        return self
    def __exit__(self,*a): pass
sys.modules.setdefault('mss',SimpleNamespace(mss=FakeCapture))
from gravador_tela import App
from gravador_v27_scrcpy import SCRCPY_B_SOURCE
with patch('gravador_tela.enumerate_windows',return_value=[]):
    app=App()
    try:
        app.dual_enabled_var.set(True)
        app.second_source_var.set(SCRCPY_B_SOURCE)
        app._second_area_changed()
        assert app.scrcpy_path_entry.winfo_manager()=='grid'
        assert app.second_combo.winfo_manager()==''
        assert app.usb_camera_combo.winfo_manager()==''
        with TemporaryDirectory() as d:
            directory=Path(d)
            (directory/'scrcpy.exe').write_bytes(b'test')
            (directory/'adb.exe').write_bytes(b'test')
            app.scrcpy_exe_var.set(str(directory/'scrcpy.exe'))
            app.scrcpy_facing_var.set('Traseira')
            app.android_usb_ok=True
            settings=app._settings()
            assert settings.scrcpy_exe_b and settings.scrcpy_facing=='Traseira'
            assert settings.secondary_area is None and settings.usb_camera_b is None
            assert settings.fps==24
        app.dual_enabled_var.set(False)
        app._second_area_changed()
        assert app.scrcpy_path_entry.winfo_manager()==''
        assert app._settings().scrcpy_exe_b is None
        print('GUI_SCRCPY_ANDROID_USB_OK')
    finally:
        app._on_close()
