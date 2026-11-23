"""Testa barra real Tk em Xvfb; não exige Windows, GPU ou webcam."""
import tkinter as tk
from gravador_v23_overlay import StudioOverlay, CaptureBounds
from gravador_v24_history import AnnotationHistory

root = tk.Tk(); root.withdraw()
o = StudioOverlay.__new__(StudioOverlay)
o.parent=root;o.bounds=CaptureBounds(0,0,1280,720)
o.closed=False;o.visible=True;o.drawing=True
o.tool='Caneta';o.color_name='Amarelo';o.stroke_width=4
o.on_tool_changed=None;o.history=AnnotationHistory()
o.toolbar_window=None;o.toolbar_position=None;o.toolbar_drag_anchor=None;o.toolbar_buttons={}
o.text_value='Guarda-Mor';o.text_entry=None;o.font_sizes={};o.pending_erase=set()
o._show_toolbar();root.update()
assert o.toolbar_window.winfo_viewable()
assert len(o.toolbar_buttons)>=18,len(o.toolbar_buttons)
assert 'tool:Texto' in o.toolbar_buttons
assert 'tool:Borracha' in o.toolbar_buttons
assert 'save' in o.toolbar_buttons
assert o.text_entry is not None
o.text_entry.delete(0,'end');o.text_entry.insert(0,'Novo texto')
o._text_changed()
assert o.text_value=='Novo texto'
o._hide_toolbar();root.destroy()
print('GUI_TOOLBAR_V25_OK')
