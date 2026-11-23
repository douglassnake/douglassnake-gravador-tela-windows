"""Teste Tk simulado da barra de ferramentas v2.6."""
import tkinter as tk
from gravador_v23_overlay import StudioOverlay, CaptureBounds
from gravador_v24_history import AnnotationHistory
root=tk.Tk();root.withdraw()
o=StudioOverlay.__new__(StudioOverlay)
o.parent=root;o.bounds=CaptureBounds(0,0,1280,720)
o.closed=False;o.visible=True;o.drawing=True
o.tool='Caneta';o.color_name='Amarelo';o.stroke_width=4
o.on_tool_changed=None;o.history=AnnotationHistory()
o.toolbar_window=None;o.toolbar_position=None;o.toolbar_drag_anchor=None;o.toolbar_buttons={}
o.text_value='Teste';o.text_entry=None;o.selection_label=None;o.selected_text_id=None
o.font_sizes={};o.pending_erase=set()
o._show_toolbar();root.update()
assert o.toolbar_window.winfo_viewable()
assert 'saveproj' in o.toolbar_buttons
assert 'openproj' in o.toolbar_buttons
assert 'edittext' in o.toolbar_buttons
assert str(o.toolbar_buttons['edittext']['state'])=='disabled'
assert o.toolbar_window.winfo_width()==760
o._hide_toolbar();root.destroy();print('GUI_TOOLBAR_V26_OK')
