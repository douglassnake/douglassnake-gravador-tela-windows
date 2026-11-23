# -*- coding: utf-8 -*-
"""Estúdio 2.4: efeitos, anotações reversíveis e barra de ferramentas.

Este módulo só cria janelas quando explicitamente ativado. Sem hook de teclado,
acesso remoto ou instalação de drivers. O Windows é a única plataforma suportada
para o efeito transparente/click-through.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import tkinter as tk
from dataclasses import dataclass
from PIL import ImageGrab, ImageTk
from tkinter import filedialog, messagebox
from gravador_v25_export import export_annotations
from gravador_v24_history import (
    AnnotationHistory, HistoryChange, ANNOTATION_COLORS, STROKE_WIDTHS,
)

TRANSPARENT = '#ff00ff'
# Camada de entrada minimamente visível: alpha > 0 permite hit-test no Windows.
# A camada de desenho propriamente dita preserva suas cores/opacity originais.
INPUT_LAYER_BG = '#101820'
INPUT_LAYER_ALPHA = 0.05
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
GWL_EXSTYLE = -20
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1
ANNOTATION_TOOLS = ('Caneta', 'Seta', 'Retângulo', 'Borracha', 'Texto')


@dataclass(frozen=True)
class CaptureBounds:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self):
        if self.width < 64 or self.height < 64:
            raise ValueError('A área de gravação é pequena demais para os efeitos.')


def cursor_relative(bounds: CaptureBounds, x: int, y: int) -> tuple[int, int] | None:
    """Coordenada local; respeita monitores com origem negativa."""
    if bounds.x <= x < bounds.x + bounds.width and bounds.y <= y < bounds.y + bounds.height:
        return x - bounds.x, y - bounds.y
    return None


def zoom_crop(bounds: CaptureBounds, x: int, y: int, width: int = 160,
              height: int = 100) -> tuple[int, int, int, int] | None:
    """Recorte limitado à área gravada. Não mostra pixels fora do enquadramento."""
    local = cursor_relative(bounds, x, y)
    if local is None:
        return None
    width = min(max(1, width), bounds.width)
    height = min(max(1, height), bounds.height)
    left = min(max(x - width // 2, bounds.x), bounds.x + bounds.width - width)
    top = min(max(y - height // 2, bounds.y), bounds.y + bounds.height - height)
    return left, top, left + width, top + height


def zoom_placement(bounds: CaptureBounds, x: int, y: int,
                   width: int = 256, height: int = 168) -> tuple[int, int]:
    """Lupa no canto mais distante do ponteiro para reduzir sobreposição."""
    width = min(width, bounds.width)
    height = min(height, bounds.height)
    pad = min(14, max(0, (bounds.width - width) // 2),
              max(0, (bounds.height - height) // 2))
    local = cursor_relative(bounds, x, y) or (0, 0)
    left = pad if local[0] > bounds.width / 2 else bounds.width - width - pad
    top = pad if local[1] > bounds.height / 2 else bounds.height - height - pad
    return max(0, left), max(0, top)


def _cursor() -> tuple[int, int] | None:
    if sys.platform != 'win32':
        return None
    pos = wintypes.POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pos)):
        return None
    return pos.x, pos.y


def _left_button_pressed() -> bool:
    return sys.platform == 'win32' and bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)


class StudioOverlay:
    """Uma única janela sobreposta, não interativa salvo no modo anotação.

    Os comandos Tk devem ser executados exclusivamente na thread principal.
    O FFmpeg gdigrab registra o desktop visível; os efeitos ficam nessa camada
    e não exigem recomprimir vídeo ou adicionar um filtro pesado.
    """
    def __init__(self, parent: tk.Tk, bounds: CaptureBounds, *,
                 highlight: bool = False, clicks: bool = False,
                 zoom: bool = False, tool: str = 'Caneta',
                 color: str = 'Amarelo', stroke_width: int = 4,
                 on_tool_changed=None):
        if sys.platform != 'win32':
            raise RuntimeError('Efeitos visuais disponíveis apenas no Windows')
        if tool not in ANNOTATION_TOOLS:
            raise ValueError('Ferramenta de anotação inválida')
        self.parent = parent
        self.bounds = bounds
        self.highlight = bool(highlight)
        self.clicks = bool(clicks)
        self.zoom = bool(zoom)
        self.tool = tool
        self.color_name = color if color in ANNOTATION_COLORS else 'Amarelo'
        self.stroke_width = stroke_width if stroke_width in STROKE_WIDTHS else 4
        self.on_tool_changed = on_tool_changed
        self.active_tool: str | None = None
        self.pending_erase: set[int] = set()
        self.text_value = 'Texto'
        self.text_entry: tk.Entry | None = None
        self.font_sizes: dict[int, int] = {}
        self.history = AnnotationHistory()
        self.toolbar_window: tk.Toplevel | None = None
        self.toolbar_buttons: dict[str, tk.Button] = {}
        self.toolbar_position: tuple[int, int] | None = None
        self.toolbar_drag_anchor: tuple[int, int] | None = None
        self.drawing = False
        self.visible = True
        self.closed = False
        self.prev_down = False
        self.click_age = 0
        self.anchor: tuple[int, int] | None = None
        self.active_item: int | None = None
        self.zoom_image: ImageTk.PhotoImage | None = None
        self.zoom_item: int | None = None
        self.zoom_frame: int | None = None
        self.zoom_caption: int | None = None
        self.input_window: tk.Toplevel | None = None
        self.input_canvas: tk.Canvas | None = None
        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.configure(bg=TRANSPARENT)
        self.window.wm_attributes('-transparentcolor', TRANSPARENT)
        self.window.wm_attributes('-topmost', True)
        self.window.geometry(f'{bounds.width}x{bounds.height}+0+0')
        self.canvas = tk.Canvas(self.window, bg=TRANSPARENT, highlightthickness=0,
                                bd=0, width=bounds.width, height=bounds.height)
        self.canvas.pack(fill='both', expand=True)
        self.halo = self.canvas.create_oval(0, 0, 0, 0,
                                            outline='#00d8ff', width=3, state='hidden')
        self.ring = self.canvas.create_oval(0, 0, 0, 0,
                                            outline='#ffbb00', width=4, state='hidden')
        self.mode_text = self.canvas.create_text(18, 18, anchor='nw',
            fill='#faff7c', font=('Segoe UI', 14, 'bold'),
            text='DESENHO ATIVO — Ctrl+Alt+D para sair', state='hidden')
        self.canvas.bind('<ButtonPress-1>', self._press)
        self.canvas.bind('<B1-Motion>', self._drag)
        self.canvas.bind('<ButtonRelease-1>', self._release)
        self.window.update_idletasks()
        self.window.deiconify()
        self._set_pass_through(True)
        self._place()
        self.window.after(60, self._poll)
        self.window.after(300, self._refresh_zoom)

    def _hwnd(self) -> int:
        # Tk pode criar uma janela wrapper; a flag WS_EX_TRANSPARENT precisa
        # ser aplicada no HWND superior, não no filho Canvas.
        api = ctypes.windll.user32
        api.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
        api.GetAncestor.restype = wintypes.HWND
        raw = int(self.window.winfo_id())
        return int(api.GetAncestor(wintypes.HWND(raw), 2) or raw)

    def _place(self) -> None:
        # SetWindowPos usa coordenadas ABSOLUTAS do desktop (incluindo x negativos).
        hwnd = self._hwnd()
        ctypes.windll.user32.SetWindowPos(
            wintypes.HWND(hwnd), wintypes.HWND(HWND_TOPMOST),
            int(self.bounds.x), int(self.bounds.y),
            int(self.bounds.width), int(self.bounds.height),
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )

    def _set_pass_through(self, yes: bool) -> None:
        hwnd = self._hwnd()
        api = ctypes.windll.user32
        getter = getattr(api, 'GetWindowLongPtrW', api.GetWindowLongW)
        setter = getattr(api, 'SetWindowLongPtrW', api.SetWindowLongW)
        getter.argtypes = [wintypes.HWND, ctypes.c_int]
        getter.restype = ctypes.c_ssize_t
        setter.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        setter.restype = ctypes.c_ssize_t
        current = getter(wintypes.HWND(hwnd), GWL_EXSTYLE)
        base = current | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        updated = base | WS_EX_TRANSPARENT if yes else base & ~WS_EX_TRANSPARENT
        setter(wintypes.HWND(hwnd), GWL_EXSTYLE, updated)
        self._place()

    def _show_input_layer(self) -> None:
        """Captura arrasto numa camada com alpha > 0, sem apagar o vídeo.

        A camada visual usa -transparentcolor (colorkey); pixels transparentes
        NÃO participam do hit-test do Windows mesmo sem WS_EX_TRANSPARENT.
        Um escudo separado com alpha mínimo recebe os cliques e encaminha
        coordenadas ao Canvas visual sem reduzir a opacidade dos desenhos.
        """
        if self.closed or not self.visible or self.input_window is not None:
            return
        shield = tk.Toplevel(self.parent)
        shield.withdraw()
        shield.overrideredirect(True)
        shield.configure(bg=INPUT_LAYER_BG)
        shield.wm_attributes('-topmost', True)
        # Não usar -transparentcolor: isso causava o bug dos cliques ignorados.
        shield.wm_attributes('-alpha', INPUT_LAYER_ALPHA)
        shield.geometry(f'{self.bounds.width}x{self.bounds.height}+0+0')
        surface = tk.Canvas(shield, bg=INPUT_LAYER_BG, highlightthickness=0,
                            bd=0, cursor='crosshair', width=self.bounds.width,
                            height=self.bounds.height)
        surface.pack(fill='both', expand=True)
        surface.bind('<ButtonPress-1>', self._press)
        surface.bind('<B1-Motion>', self._drag)
        surface.bind('<ButtonRelease-1>', self._release)
        shield.bind('<Escape>', lambda _: self.set_drawing(False))
        shield.update_idletasks()
        shield.deiconify()
        # Evita confusão com coordenadas relativas em desktops multimonitor.
        self._position_input_layer(shield)
        self.input_window = shield
        self.input_canvas = surface
        # O overlay visual deve ficar em cima do escudo e permanecer click-through.
        self._place()
        self._show_toolbar()

    def _position_input_layer(self, shield: tk.Toplevel) -> None:
        api = ctypes.windll.user32
        api.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
        api.GetAncestor.restype = wintypes.HWND
        raw = int(shield.winfo_id())
        hwnd = int(api.GetAncestor(wintypes.HWND(raw), 2) or raw)
        api.SetWindowPos(wintypes.HWND(hwnd), wintypes.HWND(HWND_TOPMOST),
                         int(self.bounds.x), int(self.bounds.y),
                         int(self.bounds.width), int(self.bounds.height),
                         SWP_NOACTIVATE | SWP_SHOWWINDOW)

    def _hide_input_layer(self) -> None:
        self._hide_toolbar()
        window = self.input_window
        self.input_window = None
        self.input_canvas = None
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

    def set_highlight(self, enabled: bool) -> None:
        self.highlight = bool(enabled)
        if not enabled:
            self.canvas.itemconfigure(self.halo, state='hidden')

    def set_clicks(self, enabled: bool) -> None:
        self.clicks = bool(enabled)
        if not enabled:
            self.canvas.itemconfigure(self.ring, state='hidden')

    def set_zoom(self, enabled: bool) -> None:
        self.zoom = bool(enabled)
        if not enabled:
            self._remove_zoom()

    def set_tool(self, name: str) -> None:
        if name not in ANNOTATION_TOOLS:
            raise ValueError('Ferramenta de anotação inválida')
        self.tool = name
        if self.on_tool_changed is not None:
            self.on_tool_changed(name)
        self._refresh_toolbar_buttons()

    def set_color(self, name: str) -> None:
        if name not in ANNOTATION_COLORS:
            raise ValueError('Cor de anotação inválida')
        self.color_name = name
        self._refresh_toolbar_buttons()

    def set_stroke_width(self, value: int) -> None:
        if value not in STROKE_WIDTHS:
            raise ValueError('Espessura de anotação inválida')
        self.stroke_width = value
        self._refresh_toolbar_buttons()

    def _text_changed(self, _event=None) -> None:
        if self.text_entry is not None:
            self.text_value = self.text_entry.get()[:240]

    def _finish_erase(self) -> None:
        pending = getattr(self, 'pending_erase', set())
        if pending:
            self._apply_history(self.history.erase(tuple(pending)))
            pending.clear()

    def _erase_at(self, x: float, y: float) -> None:
        """Borracha por objeto: remove a anotação atingida, não o fundo gravado."""
        radius = max(8, self.stroke_width * 2)
        pending = getattr(self, 'pending_erase', set())
        hits = self.canvas.find_overlapping(x-radius, y-radius, x+radius, y+radius)
        for item in hits:
            if item in self.history.visible and item not in pending:
                self.canvas.itemconfigure(item, state='hidden')
                pending.add(item)

    def _annotation_records(self) -> list[dict]:
        """Coleta só elementos do usuário; nunca inclui webcam/tela/halo/lupa."""
        records = []
        visible = self.history.visible
        for item in self.canvas.find_all():
            if item not in visible:
                continue
            kind = self.canvas.type(item)
            points = [float(x) for x in self.canvas.coords(item)]
            if kind == 'text':
                records.append({'tipo': 'Texto', 'pontos': points,
                                'cor': self.canvas.itemcget(item, 'fill'),
                                'espessura': 2, 'texto': self.canvas.itemcget(item, 'text'),
                                'fonte_px': self.font_sizes.get(item, 22)})
            elif kind == 'rectangle':
                records.append({'tipo': 'Retângulo', 'pontos': points,
                                'cor': self.canvas.itemcget(item, 'outline'),
                                'espessura': int(float(self.canvas.itemcget(item, 'width')))})
            elif kind == 'line':
                tool = 'Seta' if self.canvas.itemcget(item, 'arrow') == 'last' else 'Caneta'
                records.append({'tipo': tool, 'pontos': points,
                                'cor': self.canvas.itemcget(item, 'fill'),
                                'espessura': int(float(self.canvas.itemcget(item, 'width')))})
        return records

    def save_annotations(self, destination) -> tuple:
        """Grava PNG transparente e arquivo JSON editável, sem capturar a tela."""
        return export_annotations(destination, self._annotation_records(),
                                  self.bounds.width, self.bounds.height)

    def export_dialog(self) -> None:
        if not self.history.visible:
            messagebox.showinfo('Anotações', 'Desenhe algo antes de salvar.',
                                parent=self.toolbar_window or self.parent)
            return
        self._text_changed()
        destination = filedialog.asksaveasfilename(parent=self.toolbar_window or self.parent,
            title='Salvar anotações (PNG transparente + JSON)',
            defaultextension='.png', initialfile='anotacoes.png',
            filetypes=[('Imagem PNG', '*.png')])
        if not destination:
            return
        try:
            png, js = self.save_annotations(destination)
            messagebox.showinfo('Anotações salvas',
                                f'Imagem: {png}\nDados editáveis: {js}',
                                parent=self.toolbar_window or self.parent)
        except (OSError, ValueError, MemoryError) as exc:
            messagebox.showerror('Falha ao salvar anotações', str(exc),
                                 parent=self.toolbar_window or self.parent)

    def set_drawing(self, enabled: bool) -> None:
        self.drawing = bool(enabled)
        # A janela visual transparente nunca deve interceptar o mouse.
        self._set_pass_through(True)
        if self.drawing:
            self._show_input_layer()
        else:
            self._finish_erase()
            self._hide_input_layer()
            self.anchor = None
            self.active_item = None
            self.active_tool = None
        self.canvas.itemconfigure(self.mode_text,
            state='normal' if self.drawing else 'hidden')

    def _apply_history(self, change: HistoryChange) -> None:
        for item in change.show:
            self.canvas.itemconfigure(item, state='normal')
        for item in change.hide:
            self.canvas.itemconfigure(item, state='hidden')
        for item in change.delete:
            self.canvas.delete(item)
        self._refresh_toolbar_buttons()

    def clear(self) -> None:
        """Limpa em uma etapa que pode ser desfeita (Ctrl+Alt+U)."""
        self._finish_erase()
        self._apply_history(self.history.clear())
        self.active_item = None
        self.anchor = None
        self.active_tool = None

    def undo(self) -> None:
        self._finish_erase()
        self._apply_history(self.history.undo())

    def redo(self) -> None:
        self._finish_erase()
        self._apply_history(self.history.redo())

    @staticmethod
    def toolbar_origin(bounds: CaptureBounds, width: int = 560,
                       height: int = 82) -> tuple[int, int]:
        # Os retângulos podem iniciar em monitores com coordenadas negativas.
        return (bounds.x + max(4, bounds.width - width - 12), bounds.y + 12)

    def _show_toolbar(self) -> None:
        """Barra topmost somente no modo desenho. Não altera o fluxo FFmpeg."""
        if self.closed or not self.visible or not self.drawing:
            return
        if self.toolbar_window is not None:
            self._raise_toolbar()
            return
        panel = tk.Toplevel(self.parent)
        panel.withdraw()
        panel.overrideredirect(True)
        panel.configure(bg='#142235')
        panel.wm_attributes('-topmost', True)
        panel.wm_attributes('-alpha', 0.96)
        panel.geometry('560x118+0+0')
        outer = tk.Frame(panel, bg='#142235', padx=7, pady=5)
        outer.pack(fill='both', expand=True)
        top = tk.Frame(outer, bg='#142235')
        top.pack(fill='x')
        grip = tk.Label(top, text='✎  DESENHO  ⋮⋮', fg='#d5e7ff', bg='#142235',
                        font=('Segoe UI', 9, 'bold'), cursor='fleur')
        grip.pack(side='left', padx=(2, 7))
        grip.bind('<ButtonPress-1>', self._start_toolbar_drag)
        grip.bind('<B1-Motion>', self._move_toolbar)
        for name in ANNOTATION_TOOLS:
            self._toolbar_button(top, 'tool:'+name, name, lambda name=name: self.set_tool(name))
        self._toolbar_button(top, 'exit', 'Sair ✕', lambda: self.set_drawing(False))
        bottom = tk.Frame(outer, bg='#142235')
        bottom.pack(fill='x', pady=(5, 0))
        for name, code in ANNOTATION_COLORS.items():
            btn = tk.Button(bottom, text='●', fg=code, bg='#26394f',
                            activebackground='#425d79', relief='flat',
                            font=('Segoe UI', 12, 'bold'), width=2,
                            command=lambda name=name: self.set_color(name))
            btn.pack(side='left', padx=2)
            self.toolbar_buttons['color:'+name] = btn
        for width in STROKE_WIDTHS:
            self._toolbar_button(bottom, 'width:'+str(width), str(width)+'px',
                                 lambda width=width: self.set_stroke_width(width))
        self._toolbar_button(bottom, 'undo', '↶', self.undo)
        self._toolbar_button(bottom, 'redo', '↷', self.redo)
        self._toolbar_button(bottom, 'clear', 'Limpar', self.clear)
        third = tk.Frame(outer, bg='#142235')
        third.pack(fill='x', pady=(4, 0))
        tk.Label(third, text='Texto:', fg='#d5e7ff', bg='#142235',
                 font=('Segoe UI', 9)).pack(side='left')
        self.text_entry = tk.Entry(third, width=36, bg='#26394f', fg='white',
                                   insertbackground='white', relief='flat',
                                   font=('Segoe UI', 9))
        self.text_entry.insert(0, self.text_value)
        self.text_entry.pack(side='left', padx=5)
        self.text_entry.bind('<KeyRelease>', self._text_changed)
        self._toolbar_button(third, 'save', 'Salvar PNG + JSON', self.export_dialog)
        panel.update_idletasks()
        panel.deiconify()
        self.toolbar_window = panel
        self.toolbar_position = self.toolbar_origin(self.bounds)
        self._raise_toolbar()
        self._refresh_toolbar_buttons()

    def _toolbar_button(self, frame: tk.Frame, key: str, label: str, command) -> None:
        button = tk.Button(frame, text=label, command=command,
                           bg='#26394f', fg='#ffffff', activebackground='#425d79',
                           activeforeground='white', font=('Segoe UI', 9),
                           relief='flat', padx=5, pady=2, cursor='hand2')
        button.pack(side='left', padx=2)
        self.toolbar_buttons[key] = button

    def _refresh_toolbar_buttons(self) -> None:
        for key, button in self.toolbar_buttons.items():
            selected = (key == 'tool:'+self.tool or
                        key == 'color:'+self.color_name or
                        key == 'width:'+str(self.stroke_width))
            button.configure(bg='#227a9f' if selected else '#26394f')
            if key == 'undo':
                button.configure(state='normal' if self.history.can_undo else 'disabled')
            if key == 'redo':
                button.configure(state='normal' if self.history.can_redo else 'disabled')

    def _raise_toolbar(self) -> None:
        panel = self.toolbar_window
        if panel is None:
            return
        x, y = self.toolbar_position or self.toolbar_origin(self.bounds)
        self._position_toolbar(panel, x, y)
        panel.lift()
        panel.wm_attributes('-topmost', True)

    @staticmethod
    def _position_toolbar(panel: tk.Toplevel, x: int, y: int) -> None:
        if sys.platform != 'win32':
            panel.geometry(f'+{max(0,x)}+{max(0,y)}')
            return
        # Coordenadas absolutas: geometria Tk com x negativo significa
        # distancia da borda DIREITA, não coordenada do monitor esquerdo.
        api = ctypes.windll.user32
        api.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
        api.GetAncestor.restype = wintypes.HWND
        raw = int(panel.winfo_id())
        hwnd = int(api.GetAncestor(wintypes.HWND(raw), 2) or raw)
        api.SetWindowPos(wintypes.HWND(hwnd), wintypes.HWND(HWND_TOPMOST),
                         int(x), int(y), 560, 118,
                         SWP_NOACTIVATE | SWP_SHOWWINDOW)

    def _start_toolbar_drag(self, event) -> None:
        self.toolbar_drag_anchor = (event.x_root, event.y_root)

    def _move_toolbar(self, event) -> None:
        if self.toolbar_window is None or self.toolbar_drag_anchor is None:
            return
        x, y = self.toolbar_position or self.toolbar_origin(self.bounds)
        dx = event.x_root - self.toolbar_drag_anchor[0]
        dy = event.y_root - self.toolbar_drag_anchor[1]
        # Evita mover a barra inteiramente para fora da área capturada.
        right = self.bounds.x + max(0, self.bounds.width - 80)
        bottom = self.bounds.y + max(0, self.bounds.height - 35)
        x = min(max(self.bounds.x, x + dx), right)
        y = min(max(self.bounds.y, y + dy), bottom)
        self.toolbar_position = (x, y)
        self.toolbar_drag_anchor = (event.x_root, event.y_root)
        self._raise_toolbar()

    def _hide_toolbar(self) -> None:
        panel = getattr(self, 'toolbar_window', None)
        self.toolbar_window = None
        self.toolbar_buttons = {}
        self.text_entry = None
        self.toolbar_drag_anchor = None
        if panel is not None:
            try:
                panel.destroy()
            except tk.TclError:
                pass

    def pause(self) -> None:
        self._finish_erase()
        self.visible = False
        self._hide_input_layer()
        self.window.withdraw()

    def resume(self) -> None:
        self.visible = True
        self.window.deiconify()
        self._place()
        if self.drawing:
            self._show_input_layer()

    def close(self) -> None:
        self._finish_erase()
        if self.closed:
            return
        self.closed = True
        self.visible = False
        self._hide_input_layer()
        self.window.destroy()

    def _press(self, event) -> None:
        if not self.drawing:
            return
        if self.tool == 'Borracha':
            self.pending_erase.clear()
            self.active_tool = 'Borracha'
            self._erase_at(event.x, event.y)
            return
        if self.tool == 'Texto':
            self._text_changed()
            value = self.text_value.strip()
            if not value:
                return
            size = {2: 18, 4: 24, 7: 32}.get(self.stroke_width, 24)
            item = self.canvas.create_text(event.x, event.y, anchor='nw',
                      text=value, fill=ANNOTATION_COLORS[self.color_name],
                      font=('Segoe UI', size, 'bold'))
            self.font_sizes[item] = size
            self._apply_history(self.history.record(item))
            return
        self.anchor = (event.x, event.y)
        self.active_tool = self.tool
        color = ANNOTATION_COLORS[self.color_name]
        width = self.stroke_width
        if self.active_tool == 'Caneta':
            self.active_item = self.canvas.create_line(event.x, event.y, event.x + 1,
                                                       event.y + 1, fill=color,
                                                       width=width, capstyle='round', smooth=True)
        elif self.active_tool == 'Seta':
            self.active_item = self.canvas.create_line(event.x, event.y, event.x + 1,
                                                       event.y + 1, fill=color, width=width,
                                                       arrow='last', arrowshape=(14, 18, 7))
        else:
            self.active_item = self.canvas.create_rectangle(event.x, event.y,
                             event.x + 1, event.y + 1, outline=color, width=width)

    def _drag(self, event) -> None:
        if not self.drawing:
            return
        if self.active_tool == 'Borracha':
            self._erase_at(event.x, event.y)
            return
        if self.active_item is None or self.anchor is None:
            return
        if self.active_tool == 'Caneta':
            self.canvas.coords(self.active_item,
                               *self.canvas.coords(self.active_item), event.x, event.y)
        else:
            self.canvas.coords(self.active_item, *self.anchor, event.x, event.y)

    def _release(self, event) -> None:
        if self.active_tool == 'Borracha':
            self._erase_at(event.x, event.y)
            self._finish_erase()
        elif self.active_item is not None:
            self._drag(event)
            self._apply_history(self.history.record(self.active_item))
        self.anchor = None
        self.active_item = None
        self.active_tool = None

    def _poll(self) -> None:
        if self.closed:
            return
        if self.visible:
            point = _cursor()
            relative = cursor_relative(self.bounds, *point) if point else None
            if relative:
                x, y = relative
                if self.highlight:
                    self.canvas.coords(self.halo, x - 21, y - 21, x + 21, y + 21)
                    self.canvas.itemconfigure(self.halo, state='normal')
                else:
                    self.canvas.itemconfigure(self.halo, state='hidden')
                down = _left_button_pressed()
                if down and not self.prev_down and self.clicks:
                    self.click_age = 5
                self.prev_down = down
                if self.click_age > 0:
                    radius = 14 + 7 * (5 - self.click_age)
                    self.canvas.coords(self.ring, x - radius, y - radius,
                                       x + radius, y + radius)
                    self.canvas.itemconfigure(self.ring, state='normal')
                    self.click_age -= 1
                else:
                    self.canvas.itemconfigure(self.ring, state='hidden')
            else:
                self.canvas.itemconfigure(self.halo, state='hidden')
                self.canvas.itemconfigure(self.ring, state='hidden')
                self.prev_down = False
        self.window.after(60, self._poll)

    def _remove_zoom(self) -> None:
        for prop in ('zoom_item', 'zoom_frame', 'zoom_caption'):
            item = getattr(self, prop)
            if item is not None:
                self.canvas.delete(item)
                setattr(self, prop, None)
        self.zoom_image = None

    def _refresh_zoom(self) -> None:
        if self.closed:
            return
        if self.visible and self.zoom and not self.drawing and self.bounds.width >= 320 and self.bounds.height >= 240:
            point = _cursor()
            if point:
                crop = zoom_crop(self.bounds, *point)
                if crop:
                    try:
                        # Recorte pequeno (~160x100) e apenas 3,3 FPS: custo baixo.
                        # Remover a lupa anterior antes de fotografar evita
                        # recursão visual quando o ponteiro passa perto dela.
                        self._remove_zoom()
                        original = ImageGrab.grab(bbox=crop, all_screens=True).convert('RGB')
                        enlarged = original.resize((256, 160), Image.Resampling.BILINEAR)
                        lx, ly = zoom_placement(self.bounds, *point)
                        self._remove_zoom()
                        self.zoom_image = ImageTk.PhotoImage(enlarged)
                        self.zoom_frame = self.canvas.create_rectangle(lx-3, ly-3, lx+259,
                                                                      ly+183, fill='#0f172a',
                                                                      outline='#00d8ff', width=3)
                        self.zoom_item = self.canvas.create_image(lx, ly,
                                                                  image=self.zoom_image, anchor='nw')
                        self.zoom_caption = self.canvas.create_text(lx+128, ly+171,
                                                                    text='ZOOM 2×', fill='#ffffff',
                                                                    font=('Segoe UI', 10, 'bold'))
                    except (OSError, ValueError, tk.TclError):
                        self._remove_zoom()
        else:
            self._remove_zoom()
        self.window.after(300, self._refresh_zoom)
