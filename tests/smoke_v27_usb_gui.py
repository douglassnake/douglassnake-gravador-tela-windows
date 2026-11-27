"""Smoke de UI em Xvfb; sem chamar recursos Win32 e sem câmera real."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

class FakeCapture:
    def __enter__(self):
        self.monitors=[
            {'left':0,'top':0,'width':1280,'height':720},
            {'left':0,'top':0,'width':1280,'height':720},
        ]
        return self
    def __exit__(self,*_):pass
sys.modules.setdefault('mss',SimpleNamespace(mss=FakeCapture))
from gravador_tela import App, Screen
from gravador_v27_usb_camera import USB_B_SOURCE, WINDOWS_B_SOURCE
with patch('gravador_tela.enumerate_windows',return_value=[]),patch.object(App,'_refresh_usb_cameras') as refresh:
    app=App()
    try:
        app.dual_enabled_var.set(True)
        app.second_source_var.set(USB_B_SOURCE)
        app._second_area_changed()
        assert app.usb_camera_combo.winfo_manager()=='grid'
        assert app.second_combo.winfo_manager()==''
        refresh.assert_called_once()
        app.usb_camera_devices=['Android Webcam','Integrated Camera']
        app.usb_camera_var.set('Android Webcam')
        app._second_area_changed()
        app.update_idletasks()
        settings=app._settings()
        assert settings.secondary_area is None and settings.usb_camera_b=='Android Webcam'
        assert settings.fps==24
        app.second_source_var.set(WINDOWS_B_SOURCE)
        app.selected_area_b=Screen("Área B",100,100,320,200)
        app.second_var.set("Área personalizada")
        app._second_area_changed()
        assert app.second_combo.winfo_manager()=='grid'
        assert app.usb_camera_combo.winfo_manager()==''
        settings=app._settings()
        assert settings.usb_camera_b is None and settings.secondary_area is not None
        app.dual_enabled_var.set(False)
        app._second_area_changed()
        settings=app._settings()
        assert settings.usb_camera_b is None and settings.secondary_area is None
        print('GUI_USB_AREA_B_OK')
    finally:
        app._on_close()
