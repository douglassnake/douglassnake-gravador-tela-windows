# -*- coding: utf-8 -*-
"""Gravador de Tela Windows - aplicativo local, sem conta ou servidor.

Requer Windows 10/11, Python 3.11+ e os pacotes de requirements.txt.
Captura de vídeo via FFmpeg/gdigrab; áudio via WASAPI/soundcard.
"""
from __future__ import annotations

import ctypes
import datetime as dt
import math
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

from gravador_v2_utils import (
    enumerate_windows, window_info, find_recoverable_sessions,
    write_session_manifest, recover_session, visible_window_rect, desktop_capture_args,
)
from gravador_v21_perf import (
    ENCODER_LABELS, PROFILE_PRESETS, load_progress, save_health_snapshot,
    select_encoder, append_performance_sample,
)
from gravador_v22_studio import (
    CAMERA_OFF, list_webcams, studio_video_flags, multi_audio_mux_command,
)
from gravador_v23_overlay import (
    StudioOverlay, CaptureBounds, ANNOTATION_TOOLS,
)

APP_NAME = "GravadorTelaWin 2.5 RC1 (Estúdio)"
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
    hwnd: int | None = None  # HWND identifica a janela; captura usa a área visível do desktop


@dataclass
class Settings:
    area: Screen
    fps: int
    crf: int
    mic: bool
    system_audio: bool
    folder: Path
    encoder_preference: str = "Automático"
    webcam_device: str | None = None
    separate_audio_tracks: bool = False


class AudioCapture:
    """Grava uma fonte WASAPI em um WAV temporário por segmento."""

    def __init__(self, kind: str, path: Path, video_started_at: float):
        self.kind = kind
        self.path = path
        self.video_started_at = video_started_at
        self.first_audio_at: float | None = None
        self.error: str | None = None
        self.frames = 0
        self.level_dbfs: float | None = None
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
                        rms = float(np.sqrt(np.mean(np.square(data, dtype=np.float64))))
                        self.level_dbfs = max(-60.0, min(0.0, 20.0 * math.log10(max(rms, 1e-9))))
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
    progress_path: Path | None = None


class RecordingEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        # Teste de GPU real (e não apenas presença do nome no FFmpeg).
        self.encoder = select_encoder(self.ffmpeg, settings.encoder_preference, settings.crf,
                                      width=settings.area.width, height=settings.area.height,
                                      fps=settings.fps)
        self.settings.folder.mkdir(parents=True, exist_ok=True)
        self.tempdir = Path(tempfile.mkdtemp(prefix="gravador_tela_", dir=self.settings.folder))
        self.segments: list[Segment] = []
        self.current: Segment | None = None
        self.warnings: list[str] = []
        write_session_manifest(self.tempdir, fps=settings.fps, source=settings.area.name,
                               audio=settings.mic or settings.system_audio)

    def _ffmpeg_command(self, path: Path) -> list[str]:
        a = self.settings.area
        encoder = getattr(self, "encoder", None)  # compatível com testes do motor v2.0
        codec = encoder.codec if encoder else "libx264"
        encoder_opts = encoder.options if encoder else ("-preset", "veryfast", "-crf", str(self.settings.crf))
        progress_file = getattr(self, "_progress_path", path.with_suffix(".progress"))
        # Hotfix: gdigrab(hwnd=...) pode retornar quadros pretos no Chrome.
        # Reutiliza o modo por região, que já funciona no Windows do usuário.
        source = desktop_capture_args(a.x, a.y, a.width, a.height)
        camera_inputs, video_flags = studio_video_flags(getattr(self.settings, "webcam_device", None), a.width)
        return [
            self.ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
            "-stats_period", "1", "-progress", str(progress_file),
            "-f", "gdigrab", "-framerate", str(self.settings.fps),
            "-draw_mouse", "1", *source, *camera_inputs, *video_flags,
            "-c:v", codec, *encoder_opts,
            "-g", str(2 * self.settings.fps), "-pix_fmt", "yuv420p", str(path),
        ]

    def start_segment(self) -> None:
        if self.current is not None:
            raise RuntimeError("Já existe uma captura ativa.")
        idx = len(self.segments) + 1
        video = self.tempdir / f"video_{idx:03d}.mkv"
        self._progress_path = self.tempdir / f"ffmpeg_{idx:03d}.progress"
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
        segment = Segment(idx, video, process, log_handle, started_at,
                          progress_path=self._progress_path)
        self.current = segment
        if self.settings.mic:
            source = AudioCapture("microfone", self.tempdir / f"mic_{idx:03d}.wav", started_at)
            segment.audio.append(source)
            source.start()
        if self.settings.system_audio:
            source = AudioCapture("sistema", self.tempdir / f"sistema_{idx:03d}.wav", started_at)
            segment.audio.append(source)
            source.start()

        time.sleep(0.8 if getattr(self.settings, "webcam_device", None) else (0.6 if self.encoder.codec != "libx264" else 0.15))
        if process.poll() is not None:
            for source in segment.audio:
                source.stop()
            segment.log_handle.close()
            self.current = None
            log_txt = (self.tempdir / f"ffmpeg_{idx:03d}.log").read_text(errors="replace")
            if self.settings.encoder_preference == "Automático" and self.encoder.codec != "libx264":
                failed_codec = self.encoder.label
                self.encoder = select_encoder(self.ffmpeg, "CPU (compatível)", self.settings.crf)
                self.warnings.append(f"Falha na captura via {failed_codec}; repetindo com CPU.")
                self.start_segment()  # somente uma tentativa; CPU não recorre novamente
                return
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

    def health(self) -> dict:
        """Informações locais para diagnóstico e prevenção de falha em gravações longas."""
        state: dict = {
            "encoder": self.encoder.label,
            "codec": self.encoder.codec,
            "fps_configurado": self.settings.fps,
            "disco_livre_mb": round(shutil.disk_usage(self.settings.folder).free / (1024 ** 2), 1),
        }
        # Exportação MP4 precisa de espaço adicional para remux e arquivo final.
        # Exibe uma estimativa conservadora, não uma garantia de tamanho.
        try:
            media_bytes = sum(p.stat().st_size for p in self.tempdir.glob("*.mkv") if p.is_file())
            media_bytes += sum(p.stat().st_size for p in self.tempdir.glob("*.wav") if p.is_file())
        except OSError:
            media_bytes = 0
        media_mb = media_bytes / (1024 ** 2)
        state["reserva_exportacao_mb"] = round(max(550, media_mb * 2.4 + 150), 1)
        if self.current is not None:
            state["ffmpeg_ativo"] = self.current.process.poll() is None
            if self.current.progress_path:
                state.update(load_progress(self.current.progress_path))
        return state

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
            self._run_ffmpeg([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(seg.video),
                              "-map", "0:v:0", "-an", "-c:v", "copy", "-movflags", "+faststart", str(ready)])
            return ready

        available = [a for a in seg.audio if a.valid]
        duration = self._video_duration(seg.video)
        if self.settings.separate_audio_tracks:
            names = (["microfone"] if self.settings.mic else []) + (["sistema"] if self.settings.system_audio else [])
            tracks = []
            for name in names:
                source = next((a for a in available if a.kind == name), None)
                tracks.append((name, source.path if source else None,
                               self._audio_filter(len(tracks) + 1, source) if source else None))
            self._run_ffmpeg(multi_audio_mux_command(self.ffmpeg, seg.video, ready, duration, tracks))
            return ready
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
        # Conclusão atômica: nunca deixar um arquivo final com nome .mp4 incompleto.
        partial = output.with_suffix(".partial.mp4")
        if len(ready) == 1:
            shutil.copy2(ready[0], partial)
        else:
            concat_file = self.tempdir / "trechos.txt"
            concat_file.write_text(
                "".join(f"file '{p.name}'\n" for p in ready), encoding="utf-8"
            )
            self._run_ffmpeg([
                self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_file),
                *(["-map", "0"] if self.settings.separate_audio_tracks else []),
                "-c", "copy", "-movflags", "+faststart", str(partial),
            ])
        if not partial.is_file() or partial.stat().st_size < 1000:
            raise RuntimeError("O MP4 final não foi criado corretamente.")
        os.replace(partial, output)
        # Preserva amostras de desempenho para identificar eventuais engasgos.
        csv_path = self.tempdir / 'desempenho_amostras.csv'
        if csv_path.exists():
            try:
                shutil.copy2(csv_path, output.with_name(output.stem + '_desempenho.csv'))
            except OSError as exc:
                self.warnings.append(f'Não foi possível salvar o relatório de desempenho: {exc}')
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
    """Hotkeys de gravação e de efeitos visuais opcionais no Windows."""

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
        MOD_CONTROL, MOD_SHIFT, MOD_ALT, MOD_NOREPEAT = 0x0002, 0x0004, 0x0001, 0x4000
        ids = [
            (201, ord("R"), "toggle_record", MOD_CONTROL | MOD_SHIFT),
            (202, ord("P"), "toggle_pause", MOD_CONTROL | MOD_SHIFT),
            (203, ord("H"), "toggle_highlight", MOD_CONTROL | MOD_ALT),
            (204, ord("C"), "toggle_clicks", MOD_CONTROL | MOD_ALT),
            (205, ord("Z"), "toggle_zoom", MOD_CONTROL | MOD_ALT),
            (206, ord("D"), "toggle_draw", MOD_CONTROL | MOD_ALT),
            (207, ord("E"), "clear_draw", MOD_CONTROL | MOD_ALT),
            (208, ord("U"), "undo_draw", MOD_CONTROL | MOD_ALT),
            (209, ord("Y"), "redo_draw", MOD_CONTROL | MOD_ALT),
        ]
        registered = []
        for ident, key, _, modifiers in ids:
            if user32.RegisterHotKey(None, ident, modifiers | MOD_NOREPEAT, key):
                registered.append(ident)
        if len(registered) < len(ids):
            self.events.put(("warning", "Um atalho global já está sendo usado por outro aplicativo."))
        msg = wintypes.MSG()
        try:
            while not self.stop.is_set():
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0x0001):
                    if msg.message == 0x0312:  # WM_HOTKEY
                        for ident, _, action, _ in ids:
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
        self.geometry("985x975")
        self.minsize(855, 810)
        self.configure(bg="#111827")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.events: queue.Queue = queue.Queue()
        self.shortcuts = GlobalShortcuts(self.events)
        self.state = "idle"
        self.engine: RecordingEngine | None = None
        self.selected_area: Screen | None = None
        self.window_lookup: dict[str, int] = {}
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.recorded_sec = 0.0
        self.segment_started = 0.0
        self.health_last = 0.0
        self.snapshot_last = 0.0
        self.last_disk_warning = False
        self.job_thread: threading.Thread | None = None
        self.lento_amostras = 0
        self.lento_avisado = False
        self.studio_overlay: StudioOverlay | None = None
        self.studio_draw_mode = False

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
        self.after(900, self._refresh_preview)
        self.after(1250, self._offer_recovery)

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TCombobox", fieldbackground="#283449", background="#283449", foreground="white", arrowcolor="white", borderwidth=0)
        style.map("Dark.TCombobox", fieldbackground=[("readonly", "#283449")], foreground=[("readonly", "white")])
        style.configure("Dark.TCheckbutton", background="#1d293a", foreground="white", font=("Segoe UI", 10))
        style.map("Dark.TCheckbutton", background=[("active", "#1d293a")], foreground=[("disabled", "#7f899b")])

        main = tk.Frame(self, bg="#111827", padx=23, pady=18)
        main.pack(fill="both", expand=True)
        tk.Label(main, text="GRAVADOR DE TELA • ESTÚDIO V2.5 RC1", font=("Segoe UI", 20, "bold"), bg="#111827", fg="#f9fafb").pack(anchor="w")
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
        self.area_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.refresh_windows_button = tk.Button(box, text="Atualizar lista de janelas", command=self._refresh_window_choices,
                              bg="#334963", fg="white", relief="flat", cursor="hand2", padx=10, pady=6)
        self.refresh_windows_button.grid(row=3, column=0, columnspan=2, sticky="w", pady=(9, 0))
        preview_frame = tk.Frame(box, bg="#101928", padx=4, pady=4)
        preview_frame.grid(row=1, column=2, rowspan=3, sticky="e", padx=(16, 0))
        self.preview_label = tk.Label(preview_frame, text="PRÉVIA\nAguardando captura", width=33, height=9,
                                      bg="#101928", fg="#9ca3af", font=("Segoe UI", 9))
        self.preview_label.pack()
        tk.Label(preview_frame, text="Prévia da área visível • 1 FPS aprox.", bg="#101928", fg="#94a3b8",
                 font=("Segoe UI", 8)).pack(pady=(3, 0))
        box.columnconfigure(0, weight=1)
        self._refresh_window_choices(keep_selection=False)
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
        self.quality_combo.grid(row=2, column=1, sticky="ew", padx=(0, 9), pady=(5, 13), ipady=4)
        tk.Label(controls, text="Perfil", bg="#1d293a", fg="white").grid(row=1, column=2, sticky="w")
        self.profile_var = tk.StringVar(value="Equilibrado (30 FPS)")
        self.profile_combo = ttk.Combobox(controls, textvariable=self.profile_var,
                                          values=[*PROFILE_PRESETS, "Personalizado"],
                                          state="readonly", style="Dark.TCombobox", width=22)
        self.profile_combo.grid(row=2, column=2, sticky="ew", padx=(0, 9), pady=(5, 13), ipady=4)
        self.profile_combo.bind("<<ComboboxSelected>>", self._preset_changed)
        self.fps_combo.bind("<<ComboboxSelected>>", lambda _: self.profile_var.set("Personalizado"))
        self.quality_combo.bind("<<ComboboxSelected>>", lambda _: self.profile_var.set("Personalizado"))
        tk.Label(controls, text="Codificação de vídeo", bg="#1d293a", fg="white").grid(row=1, column=3, sticky="w")
        self.encoder_var = tk.StringVar(value="Automático")
        self.encoder_combo = ttk.Combobox(controls, textvariable=self.encoder_var,
                                          values=list(ENCODER_LABELS), state="readonly",
                                          style="Dark.TCombobox", width=19)
        self.encoder_combo.grid(row=2, column=3, sticky="ew", pady=(5, 13), ipady=4)
        self.mic_var = tk.BooleanVar(value=False)
        self.sys_var = tk.BooleanVar(value=False)
        self.mic_check = ttk.Checkbutton(controls, text="Áudio do microfone", variable=self.mic_var, style="Dark.TCheckbutton")
        self.mic_check.grid(row=3, column=0, columnspan=2, sticky="w")
        self.sys_check = ttk.Checkbutton(controls, text="Áudio do computador", variable=self.sys_var, style="Dark.TCheckbutton")
        self.sys_check.grid(row=3, column=2, columnspan=2, sticky="w")
        tk.Label(controls, text="ESTÚDIO (opcional)", bg="#1d293a", fg="#8ebeff",
                 font=("Segoe UI", 10, "bold")).grid(row=4, column=0, columnspan=4, sticky="w", pady=(10, 5))
        self.webcam_var = tk.StringVar(value=CAMERA_OFF)
        self.webcam_combo = ttk.Combobox(controls, textvariable=self.webcam_var, values=[CAMERA_OFF],
                                        state="readonly", style="Dark.TCombobox")
        self.webcam_combo.grid(row=5, column=0, columnspan=3, sticky="ew", padx=(0, 8), pady=(0, 4))
        self.webcam_button = tk.Button(controls, text="Buscar webcams", command=self._refresh_cameras,
                                       bg="#334963", fg="white", relief="flat", cursor="hand2", padx=10)
        self.webcam_button.grid(row=5, column=3, sticky="ew", pady=(0, 4))
        self.separate_tracks_var = tk.BooleanVar(value=False)
        self.separate_tracks_check = ttk.Checkbutton(
            controls, text="Guardar mix + trilhas de áudio separadas (MP4)",
            variable=self.separate_tracks_var, style="Dark.TCheckbutton")
        self.separate_tracks_check.grid(row=6, column=0, columnspan=4, sticky="w", pady=(3, 0))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, weight=1)
        controls.columnconfigure(3, weight=1)
        self.audio_levels = tk.StringVar(value="MIC: —    SISTEMA: —")
        tk.Label(controls, textvariable=self.audio_levels, bg="#1d293a", fg="#7cddc0",
                 font=("Consolas", 10)).grid(row=7, column=0, columnspan=4, sticky="w", pady=(9, 0))

        tk.Label(controls, text="EFEITOS NA GRAVAÇÃO (opcionais)", bg="#1d293a", fg="#8ebeff",
                 font=("Segoe UI", 10, "bold")).grid(row=8, column=0, columnspan=4,
                                                       sticky="w", pady=(10, 4))
        self.highlight_var = tk.BooleanVar(value=False)
        self.clicks_var = tk.BooleanVar(value=False)
        self.zoom_var = tk.BooleanVar(value=False)
        self.highlight_check = ttk.Checkbutton(controls, text="Halo do cursor",
            variable=self.highlight_var, style="Dark.TCheckbutton")
        self.highlight_check.grid(row=9, column=0, sticky="w")
        self.clicks_check = ttk.Checkbutton(controls, text="Destacar cliques",
            variable=self.clicks_var, style="Dark.TCheckbutton")
        self.clicks_check.grid(row=9, column=1, sticky="w")
        self.zoom_check = ttk.Checkbutton(controls, text="Lupa 2×",
            variable=self.zoom_var, style="Dark.TCheckbutton")
        self.zoom_check.grid(row=9, column=2, sticky="w")
        self.annotation_var = tk.StringVar(value="Caneta")
        self.annotation_combo = ttk.Combobox(controls, textvariable=self.annotation_var,
            values=ANNOTATION_TOOLS, state="readonly", style="Dark.TCombobox", width=16)
        self.annotation_combo.grid(row=9, column=3, sticky="ew")
        self.studio_status = tk.StringVar(value="Desenho Ctrl+Alt+D • Desfazer Ctrl+Alt+U • Refazer Ctrl+Alt+Y • Limpar Ctrl+Alt+E")
        tk.Label(controls, textvariable=self.studio_status, bg="#1d293a", fg="#9ca3af",
                 font=("Segoe UI", 9)).grid(row=10, column=0, columnspan=4, sticky="w", pady=(5, 0))

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
        action.pack(fill="x", pady=(13, 0))
        self.record_button = tk.Button(action, text="●  INICIAR GRAVAÇÃO", command=self._record_action,
                                       bg="#dc3545", fg="white", activebackground="#bb2939", activeforeground="white",
                                       relief="flat", cursor="hand2", font=("Segoe UI", 12, "bold"), pady=12)
        self.record_button.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.pause_button = tk.Button(action, text="Ⅱ  PAUSAR", command=self._pause_action,
                                      bg="#475569", fg="white", relief="flat", font=("Segoe UI", 11, "bold"),
                                      cursor="hand2", padx=18, pady=12, state="disabled")
        self.pause_button.pack(side="left")
        self.recover_button = tk.Button(action, text="RECUPERAR VÍDEO", command=self._recover_dialog,
                                       bg="#25607e", fg="white", relief="flat", font=("Segoe UI", 9, "bold"),
                                       cursor="hand2", padx=10, pady=12)
        self.recover_button.pack(side="left", padx=(10, 0))

        foot = tk.Frame(main, bg="#111827")
        foot.pack(fill="x", pady=(17, 0))
        self.status_var = tk.StringVar(value="Pronto para gravar")
        tk.Label(foot, textvariable=self.status_var, bg="#111827", fg="#a7b8c9", font=("Segoe UI", 10)).pack(side="left")
        self.performance_var = tk.StringVar(value="Codificador: aguardando   •   FPS: —   •   Disco: —")
        tk.Label(main, textvariable=self.performance_var, bg="#111827", fg="#93c5fd",
                 font=("Consolas", 10)).pack(anchor="w", pady=(8, 0))
        self.elapsed_var = tk.StringVar(value="00:00:00")
        tk.Label(foot, textvariable=self.elapsed_var, bg="#111827", fg="white", font=("Consolas", 16, "bold")).pack(side="right")
        tk.Label(main, text="Ctrl+Shift+R/P: gravar/pausar  •  Ctrl+Alt+D: desenhar  •  Ctrl+Alt+U/Y: desfazer/refazer  •  E: limpar",
                 bg="#111827", fg="#8391a4", font=("Segoe UI", 9)).pack(anchor="w", pady=(12, 0))

    def _refresh_cameras(self) -> None:
        """Busca dispositivos sem bloquear o Tkinter. Não abre a webcam."""
        if self.state != "idle":
            return
        self.webcam_button.configure(state="disabled")
        self.status_var.set("Buscando webcams no Windows...")
        def work():
            try:
                devices = list_webcams(imageio_ffmpeg.get_ffmpeg_exe())
                self.events.put(("webcams", devices))
            except Exception as exc:
                self.events.put(("webcam_error", str(exc)))
        threading.Thread(target=work, daemon=True, name="webcams").start()

    def _refresh_window_choices(self, keep_selection: bool = True) -> None:
        previous = self.screen_var.get() if keep_selection else self.screens[1].name
        self.window_lookup = {}
        for target in enumerate_windows(exclude_title=APP_NAME):
            label = f"Janela • {target.title[:66]} [{target.hwnd:#x}]"
            self.window_lookup[label] = target.hwnd
        values = [s.name for s in self.screens] + ["Área personalizada"] + list(self.window_lookup)
        self.screen_combo.configure(values=values)
        if previous not in values:
            self.screen_var.set(self.screens[1].name)
        if keep_selection:
            self._update_area_label()

    def _refresh_preview(self) -> None:
        try:
            if self.state in ("idle", "paused"):
                area = self._selected_screen()
                image = ImageGrab.grab(bbox=(area.x, area.y, area.x + area.width, area.y + area.height),
                                       all_screens=True).convert("RGB")
                image.thumbnail((235, 132), Image.Resampling.LANCZOS)
                self.preview_photo = ImageTk.PhotoImage(image)
                self.preview_label.configure(image=self.preview_photo, text="", width=235, height=132)
        except Exception:
            if self.state == "idle":
                self.preview_label.configure(image="", text="Prévia indisponível", width=33, height=9)
        finally:
            self.after(1200, self._refresh_preview)

    def _recover_dialog(self) -> None:
        if self.state != "idle":
            return
        base = Path(self.folder_var.get().strip()).expanduser()
        chosen = filedialog.askdirectory(title="Selecione a pasta gravador_tela_* para recuperar",
                                         initialdir=str(base) if base.is_dir() else str(Path.home()))
        if chosen:
            self._start_recovery(Path(chosen))

    def _offer_recovery(self) -> None:
        if self.state != "idle":
            return
        base = Path(self.folder_var.get().strip()).expanduser()
        sessions = find_recoverable_sessions(base)
        if sessions and messagebox.askyesno("Sessão interrompida", f"Encontradas {len(sessions)} sessões com vídeo MKV.\n\n"
                                               "Deseja tentar recuperar a sessão mais recente?\n"
                                               "O áudio pode não estar disponível."):
            self._start_recovery(sessions[0])

    def _start_recovery(self, session: Path) -> None:
        if self.state != "idle":
            return
        self.state = "recovering"
        self._set_config_enabled(False)
        self.record_button.configure(state="disabled")
        self.pause_button.configure(state="disabled")
        self.status_var.set("Recuperando trechos MKV, mantenha o programa aberto...")
        destination = Path(self.folder_var.get().strip()).expanduser()
        def work():
            try:
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                dest = recover_session(ffmpeg, session, destination)
                self.events.put(("recovered", dest))
            except Exception as exc:
                self.events.put(("recovery_error", str(exc)))
        self.job_thread = threading.Thread(target=work, daemon=True, name="recuperacao")
        self.job_thread.start()

    def _selected_screen(self) -> Screen:
        value = self.screen_var.get()
        if value in self.window_lookup:
            target = window_info(self.window_lookup[value])
            if target is None:
                raise ValueError("A janela foi fechada ou minimizada. Atualize a lista.")
            x, y, width, height = visible_window_rect(
                target, (self.screens[0].x, self.screens[0].y,
                         self.screens[0].width, self.screens[0].height))
            return Screen(target.title, x, y, width, height, target.hwnd)
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
            warning = "  •  Janela visível: não cubra nem mova durante a captura" if s.hwnd is not None else ""
            self.area_label.configure(text=f"{s.width} × {s.height} pixels  •  Origem: ({s.x}, {s.y}){warning}")
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

    def _preset_changed(self, _event=None) -> None:
        preset = PROFILE_PRESETS.get(self.profile_var.get())
        if preset:
            fps, crf = preset
            self.fps_var.set(str(fps))
            # CRF exato é aplicado em _settings; os nomes aqui são aproximações.
            self.quality_var.set("Alta" if crf <= 21 else "Equilibrada" if crf <= 24 else "Arquivo menor")

    def _settings(self) -> Settings:
        folder = Path(self.folder_var.get().strip()).expanduser()
        if not str(self.folder_var.get()).strip():
            raise ValueError("Informe a pasta onde as gravações serão salvas.")
        crf = {"Alta": 19, "Equilibrada": 23, "Arquivo menor": 28}[self.quality_var.get()]
        preset = PROFILE_PRESETS.get(self.profile_var.get())
        if preset and int(self.fps_var.get()) == preset[0]:
            crf = preset[1]
        return Settings(self._selected_screen(), int(self.fps_var.get()), crf,
                        self.mic_var.get(), self.sys_var.get(), folder,
                        self.encoder_var.get(),
                        None if self.webcam_var.get() == CAMERA_OFF else self.webcam_var.get(),
                        self.separate_tracks_var.get())

    def _set_config_enabled(self, enabled: bool) -> None:
        readonly = "readonly" if enabled else "disabled"
        for widget in [self.screen_combo, self.fps_combo, self.quality_combo,
                       self.profile_combo, self.encoder_combo, self.webcam_combo,
                       self.annotation_combo]:
            widget.configure(state=readonly)
        for widget in [self.mic_check, self.sys_check, self.separate_tracks_check,
                       self.webcam_button, self.area_button, self.browse_button,
                       self.highlight_check, self.clicks_check, self.zoom_check]:
            widget.configure(state="normal" if enabled else "disabled")
        self.folder_entry.configure(state="normal" if enabled else "disabled")
        self.refresh_windows_button.configure(state="normal" if enabled else "disabled")
        self.recover_button.configure(state="normal" if enabled else "disabled")

    def _overlay_start(self, area: Screen) -> None:
        """Erros de efeito nunca podem interromper a gravação principal."""
        self._overlay_stop()
        self.studio_draw_mode = False
        if not (self.highlight_var.get() or self.clicks_var.get() or self.zoom_var.get()):
            # O desenho continua disponível sob demanda, por atalho.
            return
        self._overlay_ensure(area)

    def _overlay_ensure(self, area: Screen | None = None) -> None:
        if self.studio_overlay is not None:
            return
        if area is None:
            if self.engine is None:
                return
            area = self.engine.settings.area
        try:
            self.studio_overlay = StudioOverlay(self,
                CaptureBounds(area.x, area.y, area.width, area.height),
                highlight=self.highlight_var.get(), clicks=self.clicks_var.get(),
                zoom=self.zoom_var.get(), tool=self.annotation_var.get())
        except Exception as exc:
            self.studio_overlay = None
            self.studio_status.set(f"Efeitos indisponíveis: {exc}")
            if self.engine is not None:
                self.engine.warnings.append("Efeitos visuais indisponíveis: " + str(exc))

    def _overlay_stop(self) -> None:
        if self.studio_overlay is not None:
            try:
                self.studio_overlay.close()
            except tk.TclError:
                pass
        self.studio_overlay = None
        self.studio_draw_mode = False

    def _visual_shortcut(self, action: str) -> None:
        if self.state != "recording" and not (self.state == "paused" and action in ("clear_draw", "undo_draw", "redo_draw")):
            return
        if action in ("toggle_highlight", "toggle_clicks", "toggle_zoom"):
            variable = {"toggle_highlight": self.highlight_var,
                        "toggle_clicks": self.clicks_var,
                        "toggle_zoom": self.zoom_var}[action]
            variable.set(not variable.get())
        self._overlay_ensure()
        overlay = self.studio_overlay
        if overlay is None:
            return
        if self.state == "paused":
            overlay.pause()
        if action == "toggle_highlight":
            overlay.set_highlight(self.highlight_var.get())
        elif action == "toggle_clicks":
            overlay.set_clicks(self.clicks_var.get())
        elif action == "toggle_zoom":
            overlay.set_zoom(self.zoom_var.get())
        elif action == "toggle_draw":
            self.studio_draw_mode = not self.studio_draw_mode
            overlay.set_drawing(self.studio_draw_mode)
        elif action == "clear_draw":
            overlay.clear()
        elif action == "undo_draw":
            overlay.undo()
        elif action == "redo_draw":
            overlay.redo()
        self.studio_status.set(
            f"Halo: {'ON' if self.highlight_var.get() else 'OFF'}  •  "
            f"Cliques: {'ON' if self.clicks_var.get() else 'OFF'}  •  "
            f"Lupa: {'ON' if self.zoom_var.get() else 'OFF'}  •  "
            f"Desenho: {'ON' if self.studio_draw_mode else 'OFF'}")

    def _prepare_visible_window(self, hwnd: int | None) -> None:
        """Remove o próprio gravador da frente e dá foco à janela selecionada.

        Chamado somente na thread de interface. O Windows pode impedir foco de
        outros processos; em tal caso a janela precisa ser trazida manualmente
        para a frente. Não minimizamos nem movemos a janela escolhida.
        """
        if hwnd is None or sys.platform != "win32":
            return
        self.iconify()
        try:
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            user32.SetForegroundWindow.restype = wintypes.BOOL
            user32.SetForegroundWindow(wintypes.HWND(hwnd))
        except (AttributeError, OSError, ValueError):
            pass

    def _resume_visible_window(self) -> None:
        """Retoma após a interface ser minimizada para não aparecer no vídeo."""
        try:
            assert self.engine is not None
            self.engine.start_segment()
        except Exception as exc:
            self.state = "paused"
            self.pause_button.configure(state="normal")
            self.record_button.configure(state="normal")
            self.deiconify()
            messagebox.showerror("Não foi possível retomar", str(exc))
            return
        self.segment_started = time.monotonic()
        self.state = "recording"
        if self.studio_overlay is not None:
            self.studio_overlay.resume()
        else:
            self._overlay_start(self.engine.settings.area)
        self.pause_button.configure(text="Ⅱ  PAUSAR", state="normal")
        self.record_button.configure(state="normal")
        if self.engine and self.engine.settings.area.hwnd is not None:
            self.status_var.set("● Gravando janela visível (não cubra nem mova)")
        else:
            self.status_var.set("● Gravando a tela...")

    def _record_action(self) -> None:
        if self.state == "idle":
            try:
                settings = self._settings()
                if settings.area.hwnd is not None and window_info(settings.area.hwnd) is None:
                    raise ValueError("A janela foi fechada ou minimizada. Selecione outra janela.")
                settings.folder.mkdir(parents=True, exist_ok=True)
                if shutil.disk_usage(settings.folder).free < 400 * 1024 * 1024:
                    raise ValueError("Espaço insuficiente: libere pelo menos 400 MB no disco de gravação.")
            except Exception as exc:
                messagebox.showerror("Não foi possível iniciar", str(exc))
                return
            self.lento_amostras = 0
            self.lento_avisado = False
            self.state = "starting"
            self._set_config_enabled(False)
            self.record_button.configure(state="disabled")
            self.pause_button.configure(state="disabled")
            self.status_var.set("Testando codificador GPU e preparando gravação...")
            if settings.area.hwnd is not None:
                self._prepare_visible_window(settings.area.hwnd)

            def start_in_background():
                engine = None
                try:
                    engine = RecordingEngine(settings)
                    engine.start_segment()
                    self.events.put(("started", engine))
                except Exception as exc:
                    self.events.put(("start_error", (str(exc), engine.tempdir if engine else None)))

            self.job_thread = threading.Thread(target=start_in_background, daemon=True, name="start")
            if settings.area.hwnd is not None:
                self.after(350, self.job_thread.start)  # deixar o Chrome redesenhar sem o gravador à frente
            else:
                self.job_thread.start()
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
            if self.engine is not None and self.engine.settings.area.hwnd is not None:
                self.state = "resuming"
                self.pause_button.configure(state="disabled")
                self.record_button.configure(state="disabled")
                self._prepare_visible_window(self.engine.settings.area.hwnd)
                self.after(350, self._resume_visible_window)
            else:
                self._resume_visible_window()

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
        self._overlay_stop()
        self.state = "idle"
        self.engine = None
        self._set_config_enabled(True)
        self.record_button.configure(text="●  INICIAR GRAVAÇÃO", bg="#dc3545", state="normal")
        self.pause_button.configure(text="Ⅱ  PAUSAR", state="disabled")
        self.status_var.set("Pronto para gravar")
        self.audio_levels.set("MIC: —    SISTEMA: —")
        self.performance_var.set("Codificador: aguardando   •   FPS: —   •   Disco: —")

    def _poll(self) -> None:
        try:
            while True:
                event, data = self.events.get_nowait()
                if event == "started":
                    self.engine = data
                    self.recorded_sec = 0.0
                    self.segment_started = data.current.started_at
                    self.health_last = 0.0
                    self.snapshot_last = 0.0
                    self.last_disk_warning = False
                    self.state = "recording"
                    self._overlay_start(data.settings.area)
                    self.record_button.configure(text="■  ENCERRAR E SALVAR", bg="#c93543", state="normal")
                    self.pause_button.configure(state="normal")
                    recording_label = "janela visível" if data.settings.area.hwnd is not None else "a tela"
                    self.status_var.set("● Gravando " + recording_label + " • " + data.encoder.label)
                elif event == "start_error":
                    msg, tmp = data
                    self._reset()
                    self.deiconify()
                    messagebox.showerror("Não foi possível iniciar", f"{msg}\n\nArquivos temporários: {tmp or 'não criados'}")
                elif event == "paused":
                    self.state = "paused"
                    if self.studio_overlay is not None:
                        self.studio_overlay.pause()
                    self.audio_levels.set("MIC: —    SISTEMA: —")
                    self.status_var.set("Ⅱ Gravação pausada")
                    self.pause_button.configure(text="▶  RETOMAR", state="normal")
                    self.record_button.configure(state="normal")
                elif event == "finished":
                    path, warnings = data
                    # A interface ainda está viva: salvar anotações no mesmo diretório
                    # do MP4 antes de destruir a camada visual. Falha de sidecar
                    # jamais invalida o vídeo concluído.
                    if self.studio_overlay is not None and self.studio_overlay.history.visible:
                        try:
                            self.studio_overlay.save_annotations(
                                path.with_name(path.stem + '_anotacoes.png'))
                        except (OSError, ValueError, MemoryError) as exc:
                            warnings.append('Anotações não exportadas: ' + str(exc))
                    self._reset()
                    self.deiconify()
                    self.status_var.set(f"Salvo: {path.name}")
                    details = "\n\nAvisos de áudio:\n" + "\n".join(warnings[:5]) if warnings else ""
                    if messagebox.askyesno("Gravação concluída", f"Arquivo salvo com sucesso:\n{path}{details}\n\nAbrir pasta da gravação?"):
                        os.startfile(path.parent) if sys.platform == "win32" else None
                elif event == "error":
                    msg, workdir = data
                    self._reset()
                    self.deiconify()
                    messagebox.showerror("Erro na gravação", f"{msg}\n\nArquivos temporários para recuperação:\n{workdir}")
                elif event == "recovered":
                    self._reset()
                    self.status_var.set("Vídeo recuperado: " + data.name)
                    messagebox.showinfo("Recuperação concluída", "Vídeo recuperado sem garantia de áudio:\n" + str(data) +
                                        "\n\nA pasta original foi preservada para sua segurança.")
                elif event == "recovery_error":
                    self._reset()
                    messagebox.showerror("Falha na recuperação", str(data))
                elif event == "webcams":
                    self.webcam_combo.configure(values=[CAMERA_OFF] + data)
                    if self.webcam_var.get() not in [CAMERA_OFF] + data:
                        self.webcam_var.set(CAMERA_OFF)
                    self.webcam_button.configure(state="normal")
                    self.status_var.set(f"Webcams encontradas: {len(data)}. Escolha uma ou mantenha desativada.")
                elif event == "webcam_error":
                    self.webcam_button.configure(state="normal")
                    self.webcam_var.set(CAMERA_OFF)
                    self.status_var.set(f"Falha ao buscar webcams: {data}")
                elif event == "warning":
                    self.status_var.set(str(data))
                elif event == "shortcut":
                    if data == "toggle_record" and self.state in ("idle", "recording", "paused"):
                        self._record_action()
                    if data == "toggle_pause" and self.state in ("recording", "paused"):
                        self._pause_action()
                    if data in ("toggle_highlight", "toggle_clicks", "toggle_zoom",
                                "toggle_draw", "clear_draw", "undo_draw", "redo_draw"):
                        self._visual_shortcut(data)
        except queue.Empty:
            pass
        self.after(120, self._poll)

    def _tick(self) -> None:
        seconds = self.recorded_sec
        if self.state == "recording":
            seconds += time.monotonic() - self.segment_started
        whole = int(seconds)
        self.elapsed_var.set(f"{whole // 3600:02d}:{whole // 60 % 60:02d}:{whole % 60:02d}")
        if self.engine is not None and self.state == "recording" and self.engine.current:
            now = time.monotonic()
            if now - self.health_last >= 1.5:
                self.health_last = now
                try:
                    h = self.engine.health()
                    fps_value = h.get("fps")
                    fps_txt = f"{fps_value:.1f}" if isinstance(fps_value, float) and fps_value > 0 else "—"
                    speed = h.get("speed")
                    speed_txt = f"{speed:.2f}x" if isinstance(speed, float) and speed > 0 else "—"
                    self.performance_var.set(
                        f"Encoder: {h['encoder']}  •  FPS real: {fps_txt}/{h['fps_configurado']}"
                        f"  •  Vel.: {speed_txt}  •  Disco: {h['disco_livre_mb'] / 1024:.1f} GB")
                    try:
                        append_performance_sample(self.engine.tempdir, h,
                            dt.datetime.now().isoformat(timespec='seconds'))
                    except OSError:
                        pass  # Falha de telemetria nunca interrompe uma gravação.
                    # Speed indica throughput do FFmpeg. FPS de saída isolado não é
                    # uma medida confiável da frequência real da captura de tela.
                    speed_ratio = h.get('speed')
                    if seconds >= 10 and isinstance(speed_ratio, (int, float)) and 0 < speed_ratio < 0.85:
                        self.lento_amostras += 1
                    else:
                        self.lento_amostras = 0
                    if self.lento_amostras >= 3 and not self.lento_avisado:
                        self.lento_avisado = True
                        warning = ('Codificação abaixo do tempo real: reduza para 24 FPS '
                                   'ou use o perfil Equilibrado para evitar cortes.')
                        self.engine.warnings.append(warning)
                        self.status_var.set('⚠ Codificação lenta: considere 24 FPS no próximo vídeo')
                    if now - self.snapshot_last >= 5:
                        self.snapshot_last = now
                        save_health_snapshot(self.engine.tempdir, {
                            "capturado_em": dt.datetime.now().isoformat(timespec="seconds"),
                            **h,
                        })
                    if h["disco_livre_mb"] < h["reserva_exportacao_mb"] and not self.last_disk_warning:
                        self.last_disk_warning = True
                        self.engine.warnings.append("Disco próximo da reserva estimada para exportação; salvando preventivamente.")
                        self._record_action()  # salva antes que o disco fique completamente cheio
                    elif h.get("ffmpeg_ativo") is False:
                        self.engine.warnings.append("O FFmpeg encerrou inesperadamente.")
                        self._record_action()
                except (OSError, ValueError) as exc:
                    self.performance_var.set(f"Diagnóstico temporariamente indisponível: {exc}")
            values = {a.kind: a.level_dbfs for a in self.engine.current.audio}
            def show(name):
                v = values.get(name)
                return "—" if v is None else f"{v:5.1f} dBFS"
            self.audio_levels.set(f"MIC: {show('microfone')}    SISTEMA: {show('sistema')}")
        self.after(250, self._tick)

    def _on_close(self) -> None:
        if self.state != "idle":
            messagebox.showinfo("Gravação em andamento", "Encerre e salve a gravação antes de fechar o aplicativo.")
            return
        self._overlay_stop()
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
