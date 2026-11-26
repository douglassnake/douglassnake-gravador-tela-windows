"""Optional display smoke test: run via xvfb-run -a python tests/smoke_v27_gui.py."""
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class Mon:
    monitors = [
        {'left':0,'top':0,'width':2560,'height':1080},
        {'left':0,'top':0,'width':1280,'height':1080},
        {'left':1280,'top':0,'width':1280,'height':1080},
    ]
    def __enter__(self):return self
    def __exit__(self,*args):return None
sys.modules.setdefault('mss',SimpleNamespace(mss=lambda: Mon()))
from gravador_tela import App
app=App()
app.update_idletasks()
assert app.dual_enabled_var.get() is False
print('DEBUG',repr(app.second_combo.cget('state')),type(app.second_combo.cget('state')));assert str(app.second_combo.cget('state'))=='disabled'
app.dual_enabled_var.set(True)
app._second_area_changed()
assert str(app.second_combo.cget('state'))=='readonly'
assert app.second_var.get()=='Monitor 2'
settings=app._settings()
assert settings.secondary_area.name=='Monitor 2'
assert settings.area.name=='Monitor 1'
app.dual_enabled_var.set(False)
app._second_area_changed()
assert app._settings().secondary_area is None
app._on_close()
print('GUI v2.7 smoke OK')
