# -*- coding: utf-8 -*-
"""Gravador de Tela Windows - aplicativo local, sem conta ou servidor.

Requer Windows 10/11, Python 3.11+ e os pacotes de requirements.txt.
Captura de vídeo via FFmpeg/gdigrab; áudio via WASAPI/soundcard.
"""
from __future__ import annotations

import ctypes
import datetime as dt
import os
import re
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import imageio_ffmpeg
import mss
import numpy as np
from PIL import Image, ImageGrab, ImageTk

APP_NAME = "Gravador de Tela Windows"
RATE = 48_000


def configure_dpi() -> None:
    """Evita coordenadas divergentes em monitores com escalas diferentes."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (OSError, AttributeError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (OSError, AttributeError):
            pass


@dataclass(frozen=True)
class Screen:
    name: str
    x: int
    y: int
    width: int
    height: int


@dataclass
class Settings:
    area: Screen
    fps: int
    crf: int
    mic: bool
    system_audio: bool
    folder: Path


class AudioCapture:
    """Grava uma fonte WASAPI em um WAV temporário por segmento."""

    def __init__(self, kind: str, path: Path, video_started_at: float):
        self.kind = kind
        self.path = path
        self.video_started_at = video_started_at
        self.first_audio_at: float | None = None
        self.error: str | None = None
        self.frames = 0
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name=f"audio-{kind}")

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            self.error = "O dispositivo de áudio não encerrou a captura a tempo."

    @property
    def valid(self) -> bool:
        return (
            self.error is None
            and self.frames > 0
            and self.first_audio_at is not None
            and self.path.exists()
            and self.path.stat().st_size > 44
        )

    def _run(self) -> None:
        comtypes = None
        com_initialized = False
        try:
            if sys.platform == "win32":
                import comtypes as _comtypes
                comtypes = _comtypes
                comtypes.CoInitialize()
                com_initialized = True

            import soundcard as sc
            if self.kind == "microfone":
                source = sc.default_microphone()
            else:
                speaker = sc.default_speaker()
                source = sc.get_microphone(id=speaker.id, include_loopback=True) if speaker else None
            if source is None:
                raise RuntimeError(f"Dispositivo não encontrado: {self.kind}")

            with source.recorder(samplerate=RATE, blocksize=2048) as rec:
                with wave.open(str(self.path), "wb") as wav:
                    wav.setsampwidth(2)
                    wav.setframerate(RATE)
                    nchannels = None
                    while not self.stop_event.is_set():
                        data = np.asarray(rec.record(numframes=4800), dtype=np.float32)
                        if data.ndim == 1:
                            data = data.reshape(-1, 1)
                        if data.shape[0] == 0:
                            continue
                        if nchannels is None:
                            nchannels = max(1, min(2, data.shape[1]))
                            wav.setnchannels(nchannels)
                            self.first_audio_at = time.monotonic() - data.shape[0] / RATE
                        data = data[:, :nchannels]
                        pcm = (np.clip(data, -1.0, 1.0) * 32767.0).astype("<i2")
                        wav.writeframesraw(pcm.tobytes())
                        self.frames += len(data)
                    if nchannels is None:
                        wav.setnchannels(1)
        except Exception as exc:
            self.error = f"{self.kind}: {exc}"
        finally:
            if com_initialized and comtypes is not None:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass


@dataclass
class Segment:
    index: int
    video: Path
    process: subprocess.Popen
    log_handle: object
    started_at: float
    audio: list[AudioCapture] = field(default_factory=list)


class RecordingEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        self.settings.folder.mkdir(parents=True, exist_ok=True)
        self.tempdir = Path(tempfile.mkdtemp(prefix="gravador_tela_", dir=self.settings.folder))
        self.segments: list[Segment] = []
        self.current: Segment | None = None
        self.warnings: list[str] = []

    def _ffmpeg_command(self, path: Path) -> list[str]:
        a = self.settings.area
        return [
            self.ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
            "-f", "gdigrab", "-framerate", str(self.settings.fps),
            "-draw_mouse", "1",
            "-offset_x", str(a.x), "-offset_y", str(a.y),
            "-video_size", f"{a.width}x{a.height}",
            "-i", "desktop", "-an", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(self.settings.crf),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path),
        ]

    def start_segment(self) -> None:
        if self.current is not None:
            raise RuntimeError("Já existe uma captura ativa.")
        idx = len(self.segments) + 1
        video = self.tempdir / f"video_{idx:03d}.mp4"
        log_handle = (self.tempdir / f"ffmpeg_{idx:03d}.log").open("wb")
        try:
            process = subprocess.Popen(
                self._ffmpeg_command(video), stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=log_handle,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except Exception:
            log_handle.close()
            raise
        started_at = time.monotonic()
        segment = Segment(idx, video, process, log_handle, started_at)
        self.current = segment
        if self.settings.mic:
            source = AudioCapture("microfone", self.tempdir / f"mic_{idx:03d}.wav", started_at)
            segment.audio.append(source)
            source.start()
        if self.settings.system_audio:
            source = AudioCapture("sistema", self.tempdir / f"sistema_{idx:03d}.wav", started_at)
            segment.audio.append(source)
            source.start()

        time.sleep(0.15)
        if process.poll() is not None:
            for source in segment.audio:
                source.stop()
            segment.log_handle.close()
            self.current = None
            log_txt = (self.tempdir / f"ffmpeg_{idx:03d}.log").read_text(errors="replace")
            raise RuntimeError("Falha ao iniciar o FFmpeg.\n" + log_txt[-1600:])

    @staticmethod
    def _end_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            if process.stdin:
                process.stdin.write(b"q\n")
                process.stdin.flush()
                process.stdin.close()
            process.wait(timeout=12)
        except (OSError, subprocess.TimeoutExpired):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)

    def stop_segment(self) -> None:
        seg = self.current
        if seg is None:
            return
        self.current = None
        self._end_process(seg.process)
        seg.log_handle.close()
        for source in seg.audio:
            source.stop()
            if source.error:
                self.warnings.append(source.error)
        if not seg.video.is_file() or seg.video.stat().st_size < 1000:
            log_txt = (self.tempdir / f"ffmpeg_{seg.index:03d}.log").read_text(errors="replace")
            raise RuntimeError("Nenhum vídeo foi gravado neste trecho.\n" + log_txt[-1600:])
        if seg.process.returncode != 0:
            self.warnings.append(f"O trecho {seg.index} encerrou com código {seg.process.returncode}.")
        self.segments.append(seg)

    def _run_ffmpeg(self, command: list[str]) -> None:
        p = subprocess.run(
            command, capture_output=True, text=True, errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if p.returncode != 0:
            raise RuntimeError("Falha na conversão do vídeo:\n" + p.stderr[-2000:])

    def _video_duration(self, video: Path) -> float:
        # ffprobe não faz parte do pacote imageio-ffmpeg; ler cabeçalho do FFmpeg.
        result = subprocess.run(
            [self.ffmpeg, "-hide_banner", "-i", str(video)],
            capture_output=True, text=True, errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
        if not match:
            raise RuntimeError(f"Não foi possível identificar a duração do trecho: {video.name}")
        hh, mm, ss = match.groups()
        return 3600 * int(hh) + 60 * int(mm) + float(ss)

    @staticmethod
    def _audio_filter(index: int, audio: AudioCapture) -> str:
        assert audio.first_audio_at is not None
        # Estimativa do desfasamento inicial; preserva sincronia entre segmentos.
        offset = audio.first_audio_at - audio.video_started_at
        base = f"[{index}:a]aresample={RATE},aformat=channel_layouts=stereo"
        if offset >= 0:
            delay_ms = min(3000, max(0, round(offset * 1000)))
            return f"{base},adelay={delay_ms}:all=1"
        trim_secs = min(3.0, -offset)
        return f"{base},atrim=start={trim_secs:.3f},asetpts=PTS-STARTPTS"

    def _mux_segment(self, seg: Segment) -> Path:
        ready = self.tempdir / f"pronto_{seg.index:03d}.mp4"
        if not (self.settings.mic or self.settings.system_audio):
            shutil.copy2(seg.video, ready)
            return ready

        available = [a for a in seg.audio if a.valid]
        duration = self._video_duration(seg.video)
        inputs = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(seg.video)]
        if not available:
            inputs += ["-f", "lavfi", "-i", f"anullsrc=r={RATE}:cl=stereo"]
            command = inputs + [
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
                "-b:a", "160k", "-t", f"{duration:.3f}", "-movflags", "+faststart", str(ready),
            ]
            self._run_ffmpeg(command)
            return ready

        for audio in available:
            inputs += ["-i", str(audio.path)]
        filters: list[str] = []
        for i, audio in enumerate(available, start=1):
            filters.append(self._audio_filter(i, audio) + f"[a{i}]")
        if len(available) == 1:
            filters.append("[a1]apad[aout]")
        else:
            refs = "".join(f"[a{i}]" for i in range(1, len(available) + 1))
            filters.append(
                f"{refs}amix=inputs={len(available)}:duration=longest:"
                "dropout_transition=0:normalize=1,apad[aout]"
            )
        command = inputs + [
            "-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{duration:.3f}",
            "-movflags", "+faststart", str(ready),
        ]
        try:
            self._run_ffmpeg(command)
        except RuntimeError as exc:
            # Mesmo que o hardware de áudio falhe, o usuário não perde a imagem.
            self.warnings.append(f"Áudio do trecho {seg.index} indisponível: {exc}")
            inputs = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(seg.video),
                      "-f", "lavfi", "-i", f"anullsrc=r={RATE}:cl=stereo"]
            self._run_ffmpeg(inputs + [
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
                "-b:a", "160k", "-t", f"{duration:.3f}", str(ready),
            ])
        return ready

    def finish(self) -> Path:
        if self.current is not None:
            self.stop_segment()
        if not self.segments:
            raise RuntimeError("Nenhum trecho de vídeo foi gravado.")

        base = f"Gravacao_{dt.datetime.now():%Y%m%d_%H%M%S}"
        output = self.settings.folder / f"{base}.mp4"
        for i in range(1, 1000):
            if not output.exists():
                break
            output = self.settings.folder / f"{base}_{i:03d}.mp4"

        ready = [self._mux_segment(seg) for seg in self.segments]
        if len(ready) == 1:
            shutil.copy2(ready[0], output)
        else:
            concat_file = self.tempdir / "trechos.txt"
            concat_file.write_text(
                "".join(f"file '{p.name}'\n" for p in ready), encoding="utf-8"
            )
            self._run_ffmpeg([
                self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-c", "copy", "-movflags", "+faststart", str(output),
            ])
        if not output.is_file() or output.stat().st_size < 1000:
            raise RuntimeError("O MP4 final não foi criado corretamente.")
        shutil.rmtree(self.tempdir, ignore_errors=True)
        return output


class RegionSelector:
    """Seleção visual de retângulo no desktop virtual (também em multimonitor)."""

    def __init__(self, parent: tk.Tk, desktop: Screen, on_select):
        self.desktop = desktop
        self.on_select = on_select
        # Capture a tela antes de criar a sobreposição, para não fotografá-la.
        img = ImageGrab.grab(all_screens=True).convert("RGB")
        if img.size != (desktop.width, desktop.height):
            img = img.resize((desktop.width, desktop.height), Image.Resampling.BILINEAR)
        self.top = tk.Toplevel(parent)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.configure(background="#000000")
        self.top.geometry(f"{desktop.width}x{desktop.height}+0+0")
        self.top.update_idletasks()
        if sys.platform == "win32":
            from ctypes import wintypes
            setter = ctypes.windll.user32.SetWindowPos
            setter.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                               ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            setter.restype = wintypes.BOOL
            setter(self.top.winfo_id(), -1, desktop.x, desktop.y,
                   desktop.width, desktop.height, 0x0040)
        self.canvas = tk.Canvas(self.top, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.canvas.create_rectangle(8, 8, 590, 45, fill="#162235", outline="")
        self.canvas.create_text(
            18, 27, anchor="w", text="ARRASTE PARA SELECIONAR  •  ESC para cancelar",
            fill="white", font=("Segoe UI", 12, "bold"),
        )
        self.start: tuple[int, int] | None = None
        self.rect_id = None
        self.canvas.bind("<ButtonPress-1>", self._down)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", self._up)
        self.top.bind("<Escape>", lambda _: self.top.destroy())
        self.top.focus_force()
        self.top.grab_set()

    def _down(self, event) -> None:
        self.start = (event.x, event.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#43d6ff", width=3, dash=(6, 3),
        )

    def _move(self, event) -> None:
        if self.start and self.rect_id:
            self.canvas.coords(self.rect_id, *self.start, event.x, event.y)

    def _up(self, event) -> None:
        if self.start is None:
            return
        x1, y1 = self.start
        x2, y2 = event.x, event.y
        left, top = max(0, min(x1, x2)), max(0, min(y1, y2))
        right = min(self.desktop.width, max(x1, x2))
        bottom = min(self.desktop.height, max(y1, y2))
        w, h = right - left, bottom - top
        if w < 64 or h < 64:
            messagebox.showwarning("Área muito pequena", "Selecione uma área de pelo menos 64 × 64 pixels.", parent=self.top)
            return
        self.top.grab_release()
        self.top.destroy()
        self.on_select(Screen("Área selecionada", left + self.desktop.x, top + self.desktop.y, w, h))


class GlobalShortcuts:
    """Hotkeys globais de Windows: Ctrl+Shift+R e Ctrl+Shift+P."""

    def __init__(self, events: queue.Queue):
        self.events = events
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if sys.platform != "win32":
            return
        self.thread = threading.Thread(target=self._worker, daemon=True, name="atalhos")
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)

    def _worker(self) -> None:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x0002, 0x0004, 0x4000
        ids = [(201, ord("R"), "toggle_record"), (202, ord("P"), "toggle_pause")]
        registered = []
        for ident, key, _ in ids:
            if user32.RegisterHotKey(None, ident, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, key):
                registered.append(ident)
        if len(registered) < len(ids):
            self.events.put(("warning", "Um atalho global já está sendo usado por outro aplicativo."))
        msg = wintypes.MSG()
        try:
            while not self.stop.is_set():
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0x0001):
                    if msg.message == 0x0312:  # WM_HOTKEY
                        for ident, _, action in ids:
                            if msg.wParam == ident:
                                self.events.put(("shortcut", action))
                time.sleep(0.045)
        finally:
            for ident in registered:
                user32.UnregisterHotKey(None, ident)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("780x635")
        self.minsize(690, 590)
        self.configure(bg="#111827")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.events: queue.Queue = queue.Queue()
        self.shortcuts = GlobalShortcuts(self.events)
        self.state = "idle"
        self.engine: RecordingEngine | None = None
        self.selected_area: Screen | None = None
        self.recorded_sec = 0.0
        self.segment_started = 0.0
        self.job_thread: threading.Thread | None = None

        with mss.mss() as sct:
            virtual = sct.monitors[0]
            self.screens = [Screen("Todos os monitores", int(virtual["left"]), int(virtual["top"]),
                                   int(virtual["width"]), int(virtual["height"]))]
            for i, display in enumerate(sct.monitors[1:], start=1):
                self.screens.append(Screen(f"Monitor {i}", display["left"], display["top"], display["width"], display["height"]))
        if len(self.screens) < 2:
            raise RuntimeError("Não foi detectado nenhum monitor para capturar.")
        self._build_ui()
        self.shortcuts.start()
        self.after(120, self._poll)
        self.after(250, self._tick)

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TCombobox", fieldbackground="#283449", background="#283449", foreground="white", arrowcolor="white", borderwidth=0)
        style.map("Dark.TCombobox", fieldbackground=[("readonly", "#283449")], foreground=[("readonly", "white")])
        style.configure("Dark.TCheckbutton", background="#1d293a", foreground="white", font=("Segoe UI", 10))
        style.map("Dark.TCheckbutton", background=[("active", "#1d293a")], foreground=[("disabled", "#7f899b")])

        main = tk.Frame(self, bg="#111827", padx=28, pady=24)
        main.pack(fill="both", expand=True)
        tk.Label(main, text="GRAVADOR DE TELA", font=("Segoe UI", 21, "bold"), bg="#111827", fg="#f9fafb").pack(anchor="w")
        tk.Label(main, text="Windows 10/11  •  MP4  •  Captura local, sem envio para a nuvem",
                 font=("Segoe UI", 10), bg="#111827", fg="#9ca3af").pack(anchor="w", pady=(1, 17))

        box = tk.Frame(main, bg="#1d293a", padx=20, pady=17)
        box.pack(fill="x")
        tk.Label(box, text="O QUE GRAVAR", bg="#1d293a", fg="#8ebeff", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 9))
        self.screen_var = tk.StringVar(value=self.screens[1].name)
        self.screen_combo = ttk.Combobox(box, textvariable=self.screen_var,
                                          values=[s.name for s in self.screens] + ["Área personalizada"],
                                          state="readonly", style="Dark.TCombobox", font=("Segoe UI", 11))
        self.screen_combo.grid(row=1, column=0, sticky="ew", padx=(0, 12), ipady=5)
        self.screen_combo.bind("<<ComboboxSelected>>", self._screen_changed)
        self.area_button = tk.Button(box, text="Selecionar área", command=self._pick_area,
                                     bg="#334963", fg="white", activebackground="#43627e", activeforeground="white",
                                     relief="flat", cursor="hand2", padx=15, pady=8, font=("Segoe UI", 10, "bold"))
        self.area_button.grid(row=1, column=1, sticky="ew")
        self.area_label = tk.Label(box, text="", bg="#1d293a", fg="#9ca3af", font=("Segoe UI", 9))
        self.area_label.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        box.columnconfigure(0, weight=1)
        self._update_area_label()

        controls = tk.Frame(main, bg="#1d293a", padx=20, pady=17)
        controls.pack(fill="x", pady=(12, 0))
        tk.Label(controls, text="CONFIGURAÇÕES", bg="#1d293a", fg="#8ebeff", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
        tk.Label(controls, text="Quadros por segundo", bg="#1d293a", fg="white").grid(row=1, column=0, sticky="w")
        self.fps_var = tk.StringVar(value="30")
        self.fps_combo = ttk.Combobox(controls, textvariable=self.fps_var, values=["15", "24", "30", "60"],
                                       width=9, state="readonly", style="Dark.TCombobox")
        self.fps_combo.grid(row=2, column=0, sticky="ew", padx=(0, 15), pady=(5, 13), ipady=4)
        tk.Label(controls, text="Qualidade", bg="#1d293a", fg="white").grid(row=1, column=1, sticky="w")
        self.quality_var = tk.StringVar(value="Equilibrada")
        self.quality_combo = ttk.Combobox(controls, textvariable=self.quality_var,
                                           values=["Alta", "Equilibrada", "Arquivo menor"],
                                           state="readonly", style="Dark.TCombobox")
        self.quality_combo.grid(row=2, column=1, columnspan=3, sticky="ew", pady=(5, 13), ipady=4)
        self.mic_var = tk.BooleanVar(value=False)
        self.sys_var = tk.BooleanVar(value=False)
        self.mic_check = ttk.Checkbutton(controls, text="Áudio do microfone", variable=self.mic_var, style="Dark.TCheckbutton")
        self.mic_check.grid(row=3, column=0, columnspan=2, sticky="w")
        self.sys_check = ttk.Checkbutton(controls, text="Áudio do computador", variable=self.sys_var, style="Dark.TCheckbutton")
        self.sys_check.grid(row=3, column=2, columnspan=2, sticky="w")
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, weight=1)

        paths = tk.Frame(main, bg="#1d293a", padx=20, pady=15)
        paths.pack(fill="x", pady=(12, 0))
        tk.Label(paths, text="SALVAR GRAVAÇÕES EM", bg="#1d293a", fg="#8ebeff", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 7))
        path_line = tk.Frame(paths, bg="#1d293a")
        path_line.pack(fill="x")
        self.folder_var = tk.StringVar(value=str(Path.home() / "Videos" / "GravadorTela"))
        self.folder_entry = tk.Entry(path_line, textvariable=self.folder_var, bg="#283449", fg="white",
                                    insertbackground="white", relief="flat", font=("Segoe UI", 10))
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 12))
        self.browse_button = tk.Button(path_line, text="Procurar", command=self._browse, bg="#334963", fg="white",
                                       relief="flat", cursor="hand2", padx=15, pady=8)
        self.browse_button.pack(side="right")

        action = tk.Frame(main, bg="#111827")
        action.pack(fill="x", pady=(20, 0))
        self.record_button = tk.Button(action, text="●  INICIAR GRAVAÇÃO", command=self._record_action,
                                       bg="#dc3545", fg="white", activebackground="#bb2939", activeforeground="white",
                                       relief="flat", cursor="hand2", font=("Segoe UI", 12, "bold"), pady=12)
        self.record_button.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.pause_button = tk.Button(action, text="Ⅱ  PAUSAR", command=self._pause_action,
                                      bg="#475569", fg="white", relief="flat", font=("Segoe UI", 11, "bold"),
                                      cursor="hand2", padx=18, pady=12, state="disabled")
        self.pause_button.pack(side="left")

        foot = tk.Frame(main, bg="#111827")
        foot.pack(fill="x", pady=(17, 0))
        self.status_var = tk.StringVar(value="Pronto para gravar")
        tk.Label(foot, textvariable=self.status_var, bg="#111827", fg="#a7b8c9", font=("Segoe UI", 10)).pack(side="left")
        self.elapsed_var = tk.StringVar(value="00:00:00")
        tk.Label(foot, textvariable=self.elapsed_var, bg="#111827", fg="white", font=("Consolas", 16, "bold")).pack(side="right")
        tk.Label(main, text="Atalhos globais: Ctrl + Shift + R  (iniciar/parar)   •   Ctrl + Shift + P  (pausar/retomar)",
                 bg="#111827", fg="#8391a4", font=("Segoe UI", 9)).pack(anchor="w", pady=(15, 0))

    def _selected_screen(self) -> Screen:
        value = self.screen_var.get()
        if value == "Área personalizada":
            if self.selected_area is None:
                raise ValueError("Clique em 'Selecionar área' para definir o recorte.")
            return self.selected_area
        for screen in self.screens:
            if screen.name == value:
                return screen
        return self.screens[1]

    def _update_area_label(self) -> None:
        try:
            s = self._selected_screen()
            self.area_label.configure(text=f"{s.width} × {s.height} pixels  •  Origem: ({s.x}, {s.y})")
        except ValueError:
            self.area_label.configure(text="Nenhuma área personalizada foi selecionada")

    def _screen_changed(self, _event=None) -> None:
        self._update_area_label()
        if self.screen_var.get() == "Área personalizada" and self.selected_area is None:
            self._pick_area()

    def _pick_area(self) -> None:
        if self.state != "idle":
            return
        try:
            RegionSelector(self, self.screens[0], self._area_chosen)
        except Exception as exc:
            messagebox.showerror("Seleção indisponível", str(exc))

    def _area_chosen(self, area: Screen) -> None:
        self.selected_area = area
        self.screen_var.set("Área personalizada")
        self._update_area_label()

    def _browse(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() if Path(self.folder_var.get()).is_dir() else str(Path.home()))
        if folder:
            self.folder_var.set(folder)

    def _settings(self) -> Settings:
        folder = Path(self.folder_var.get().strip()).expanduser()
        if not str(self.folder_var.get()).strip():
            raise ValueError("Informe a pasta onde as gravações serão salvas.")
        crf = {"Alta": 19, "Equilibrada": 23, "Arquivo menor": 28}[self.quality_var.get()]
        return Settings(self._selected_screen(), int(self.fps_var.get()), crf,
                        self.mic_var.get(), self.sys_var.get(), folder)

    def _set_config_enabled(self, enabled: bool) -> None:
        readonly = "readonly" if enabled else "disabled"
        for widget in [self.screen_combo, self.fps_combo, self.quality_combo]:
            widget.configure(state=readonly)
        for widget in [self.mic_check, self.sys_check, self.area_button, self.browse_button]:
            widget.configure(state="normal" if enabled else "disabled")
        self.folder_entry.configure(state="normal" if enabled else "disabled")

    def _record_action(self) -> None:
        if self.state == "idle":
            try:
                self.engine = RecordingEngine(self._settings())
                self.engine.start_segment()
            except Exception as exc:
                tmp = self.engine.tempdir if self.engine else None
                messagebox.showerror("Não foi possível iniciar", f"{exc}\n\n{f'Arquivos de diagnóstico: {tmp}' if tmp else ''}")
                self.engine = None
                return
            self.recorded_sec = 0
            self.segment_started = time.monotonic()
            self.state = "recording"
            self._set_config_enabled(False)
            self.record_button.configure(text="■  ENCERRAR E SALVAR", bg="#c93543")
            self.pause_button.configure(state="normal")
            self.status_var.set("● Gravando a tela...")
        elif self.state in ("recording", "paused"):
            if self.state == "recording":
                self.recorded_sec += time.monotonic() - self.segment_started
            self.state = "saving"
            self.status_var.set("Finalizando e salvando o arquivo MP4...")
            self.record_button.configure(state="disabled")
            self.pause_button.configure(state="disabled")
            self._launch_job("finish")

    def _pause_action(self) -> None:
        if self.state == "recording":
            self.recorded_sec += time.monotonic() - self.segment_started
            self.state = "processing_pause"
            self.status_var.set("Pausando gravação...")
            self.pause_button.configure(state="disabled")
            self.record_button.configure(state="disabled")
            self._launch_job("pause")
        elif self.state == "paused":
            try:
                assert self.engine is not None
                self.engine.start_segment()
            except Exception as exc:
                messagebox.showerror("Não foi possível retomar", str(exc))
                return
            self.segment_started = time.monotonic()
            self.state = "recording"
            self.pause_button.configure(text="Ⅱ  PAUSAR")
            self.status_var.set("● Gravando a tela...")

    def _launch_job(self, task: str) -> None:
        def work():
            try:
                assert self.engine is not None
                if task == "pause":
                    self.engine.stop_segment()
                    self.events.put(("paused", None))
                elif task == "finish":
                    result = self.engine.finish()
                    self.events.put(("finished", (result, list(self.engine.warnings))))
            except Exception as exc:
                self.events.put(("error", (str(exc), self.engine.tempdir if self.engine else None)))
        self.job_thread = threading.Thread(target=work, daemon=True, name=task)
        self.job_thread.start()

    def _reset(self) -> None:
        self.state = "idle"
        self.engine = None
        self._set_config_enabled(True)
        self.record_button.configure(text="●  INICIAR GRAVAÇÃO", bg="#dc3545", state="normal")
        self.pause_button.configure(text="Ⅱ  PAUSAR", state="disabled")
        self.status_var.set("Pronto para gravar")

    def _poll(self) -> None:
        try:
            while True:
                event, data = self.events.get_nowait()
                if event == "paused":
                    self.state = "paused"
                    self.status_var.set("Ⅱ Gravação pausada")
                    self.pause_button.configure(text="▶  RETOMAR", state="normal")
                    self.record_button.configure(state="normal")
                elif event == "finished":
                    path, warnings = data
                    self._reset()
                    self.status_var.set(f"Salvo: {path.name}")
                    details = "\n\nAvisos de áudio:\n" + "\n".join(warnings[:5]) if warnings else ""
                    if messagebox.askyesno("Gravação concluída", f"Arquivo salvo com sucesso:\n{path}{details}\n\nAbrir pasta da gravação?"):
                        os.startfile(path.parent) if sys.platform == "win32" else None
                elif event == "error":
                    msg, workdir = data
                    self._reset()
                    messagebox.showerror("Erro na gravação", f"{msg}\n\nArquivos temporários para recuperação:\n{workdir}")
                elif event == "warning":
                    self.status_var.set(str(data))
                elif event == "shortcut":
                    if data == "toggle_record" and self.state in ("idle", "recording", "paused"):
                        self._record_action()
                    if data == "toggle_pause" and self.state in ("recording", "paused"):
                        self._pause_action()
        except queue.Empty:
            pass
        self.after(120, self._poll)

    def _tick(self) -> None:
        seconds = self.recorded_sec
        if self.state == "recording":
            seconds += time.monotonic() - self.segment_started
        whole = int(seconds)
        self.elapsed_var.set(f"{whole // 3600:02d}:{whole // 60 % 60:02d}:{whole % 60:02d}")
        self.after(250, self._tick)

    def _on_close(self) -> None:
        if self.state != "idle":
            messagebox.showinfo("Gravação em andamento", "Encerre e salve a gravação antes de fechar o aplicativo.")
            return
        self.shortcuts.close()
        self.destroy()


def main() -> int:
    if sys.platform != "win32":
        print("Este aplicativo grava a tela somente no Windows 10/11.")
        return 1
    configure_dpi()
    try:
        app = App()
        app.mainloop()
    except Exception as exc:
        try:
            fallback = tk.Tk()
            fallback.withdraw()
            messagebox.showerror(APP_NAME, f"Erro ao iniciar:\n{exc}")
            fallback.destroy()
        except Exception:
            print(f"Erro ao iniciar: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
