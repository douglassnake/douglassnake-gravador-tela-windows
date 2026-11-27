# -*- coding: utf-8 -*-
"""Layout responsivo e rolável do estúdio; sem alterações no motor de gravação.

A barra vertical pertence somente ao formulário. Os comandos essenciais ficam
fora deste painel, fixos no rodapé da janela principal.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def initial_window_geometry(screen_width: int, screen_height: int) -> tuple[int, int]:
    """Inicia menor que o desktop, com piso funcional para os controles de gravação."""
    width = min(1100, max(900, int(screen_width) - 100))
    height = min(780, max(570, int(screen_height) - 110))
    return width, height


def mousewheel_units(delta: int, linux_button: int | None = None) -> int:
    """Converte ticks Windows/touchpad ou Button-4/5 do X11 em linhas."""
    if linux_button == 4:
        return -3
    if linux_button == 5:
        return 3
    if not delta:
        return 0
    magnitude = max(1, min(6, round(abs(delta) / 120)))
    return -magnitude if delta > 0 else magnitude


class ScrollableSettings(tk.Frame):
    """Painel vertical de Tkinter com scroll region e largura acompanhando a janela.

    A rolagem do mouse é escutada na janela principal (não em todo o processo)
    e só é processada quando o evento vem de dentro do formulário. Não rouba
    scroll de comboboxes, listas ou caixas de texto.
    """

    def __init__(self, parent, *, background: str = '#0c1424'):
        super().__init__(parent, background=background)
        self.canvas = tk.Canvas(
            self, background=background, borderwidth=0, highlightthickness=0,
            relief='flat', takefocus=0,
        )
        self.bar = ttk.Scrollbar(
            self, orient='vertical', command=self.canvas.yview,
            style='Studio.Vertical.TScrollbar',
        )
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.bar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.content = tk.Frame(self.canvas, background=background, padx=22, pady=13)
        self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor='nw')
        self.content.bind('<Configure>', self._content_configured)
        self.canvas.bind('<Configure>', self._canvas_configured)
        self._root = self.winfo_toplevel()
        self._wheel_bindings = (
            ('<MouseWheel>', self._on_mousewheel),
            ('<Button-4>', self._on_mousewheel),
            ('<Button-5>', self._on_mousewheel),
        )
        self._binding_ids = [(name, self._root.bind(name, callback, add='+'))
                             for name, callback in self._wheel_bindings]
        self.bind('<Destroy>', self._cleanup, add='+')

    def _cleanup(self, event) -> None:
        if event.widget is not self:
            return
        if not self._root.winfo_exists():
            return
        for sequence, binding in self._binding_ids:
            if binding:
                try:
                    self._root.unbind(sequence, binding)
                except tk.TclError:
                    pass
        self._binding_ids = []

    def _content_configured(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _canvas_configured(self, event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _inside_form(self, widget) -> bool:
        if isinstance(widget, (ttk.Combobox, tk.Listbox, tk.Text, ttk.Treeview)):
            return False
        current = widget
        while current is not None:
            if current is self.canvas or current is self.content:
                return True
            current = getattr(current, 'master', None)
        return False

    def _on_mousewheel(self, event):
        if not self._inside_form(event.widget):
            return None
        # Na ausência de rolagem real, não consumir o evento.
        lo, hi = self.canvas.yview()
        if lo <= 0.0 and hi >= 1.0:
            return None
        steps = mousewheel_units(getattr(event, 'delta', 0), getattr(event, 'num', None))
        if not steps:
            return None
        self.canvas.yview_scroll(steps, 'units')
        return 'break'
