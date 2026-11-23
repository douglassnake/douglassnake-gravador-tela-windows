# -*- coding: utf-8 -*-
"""Estúdio 2.3: cursor destacado, lupa local e anotações sobre a área visível.

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

TRANSPARENT = '#ff00ff'
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
GWL_EXSTYLE = -20
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1
ANNOTATION_TOOLS = ('Caneta', 'Seta', 'Retângulo')


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
                 zoom: bool = False, tool: str = 'Caneta'):
        if sys.platform != 'win32':
            raise RuntimeError('Efeitos visuais disponíveis apenas no Windows')
        if tool not in ANNOTATION_TOOLS:
            raise ValueError('Ferramenta de anotação inválida')
        self.bounds = bounds
        self.highlight = bool(highlight)
        self.clicks = bool(clicks)
        self.zoom = bool(zoom)
        self.tool = tool
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

    def set_drawing(self, enabled: bool) -> None:
        self.drawing = bool(enabled)
        self._set_pass_through(not self.drawing)
        self.canvas.itemconfigure(self.mode_text,
            state='normal' if self.drawing else 'hidden')

    def clear(self) -> None:
        """Remove apenas desenhos, preservando halo e a lupa."""
        for item in self.canvas.find_all():
            if item not in (self.halo, self.ring, self.mode_text, self.zoom_item,
                            self.zoom_frame, self.zoom_caption):
                self.canvas.delete(item)
        self.active_item = None
        self.anchor = None

    def pause(self) -> None:
        self.visible = False
        self.window.withdraw()

    def resume(self) -> None:
        self.visible = True
        self.window.deiconify()
        self._place()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.visible = False
        self.window.destroy()

    def _press(self, event) -> None:
        if not self.drawing:
            return
        self.anchor = (event.x, event.y)
        if self.tool == 'Caneta':
            self.active_item = self.canvas.create_line(event.x, event.y, event.x + 1,
                                                       event.y + 1, fill='#ffed65',
                                                       width=4, capstyle='round', smooth=True)
        elif self.tool == 'Seta':
            self.active_item = self.canvas.create_line(event.x, event.y, event.x + 1,
                                                       event.y + 1, fill='#ffed65',
                                                       width=4, arrow='last', arrowshape=(14, 18, 7))
        else:
            self.active_item = self.canvas.create_rectangle(event.x, event.y, event.x + 1,
                                                            event.y + 1, outline='#ffed65', width=4)

    def _drag(self, event) -> None:
        if not self.drawing or self.active_item is None or self.anchor is None:
            return
        if self.tool == 'Caneta':
            self.canvas.coords(self.active_item,
                               *self.canvas.coords(self.active_item), event.x, event.y)
        else:
            self.canvas.coords(self.active_item, *self.anchor, event.x, event.y)

    def _release(self, event) -> None:
        if self.active_item is not None:
            self._drag(event)
        self.anchor = None
        self.active_item = None

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
