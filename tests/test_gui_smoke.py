import sys,types
class FakeMSS:
    monitors = [{'left':0,'top':0,'width':1920,'height':1080}, {'left':0,'top':0,'width':1920,'height':1080}]
    def __enter__(self):return self
    def __exit__(self,*args):return False
sys.modules.setdefault('mss',types.SimpleNamespace(mss=FakeMSS))
from gravador_tela import App, CAMERA_OFF
app=App()
app.update_idletasks()
assert app.webcam_var.get()==CAMERA_OFF
assert app.separate_tracks_var.get() is False
cfg=app._settings()
assert cfg.webcam_device is None and not cfg.separate_audio_tracks
assert app.highlight_var.get() is False
assert app.clicks_var.get() is False
assert app.zoom_var.get() is False
assert app.studio_overlay is None
app.destroy()
print('GUI smoke OK')
