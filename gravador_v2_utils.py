# -*- coding: utf-8 -*-
"""Utilitários da v2: seleção de janelas e recuperação segura de vídeos.

Sem imports de bibliotecas de captura; pode ser testado fora do Windows.
"""
from __future__ import annotations

import ctypes
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowTarget:
    hwnd: int
    title: str
    x: int
    y: int
    width: int
    height: int


def window_info(hwnd: int) -> WindowTarget | None:
    """Lê a janela pelo HWND; não depende de títulos possivelmente repetidos."""
    if sys.platform != "win32" or hwnd <= 0:
        return None
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    handle = wintypes.HWND(hwnd)
    if not user32.IsWindow(handle) or not user32.IsWindowVisible(handle) or user32.IsIconic(handle):
        return None
    length = user32.GetWindowTextLengthW(handle)
    if length <= 0:
        return None
    title_buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, title_buffer, length + 1)
    rect = wintypes.RECT()
    if not user32.GetWindowRect(handle, ctypes.byref(rect)):
        return None
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width < 64 or height < 64:
        return None
    return WindowTarget(hwnd, title_buffer.value, rect.left, rect.top, width, height)


def enumerate_windows(exclude_title: str = "") -> list[WindowTarget]:
    if sys.platform != "win32":
        return []
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    entries: list[WindowTarget] = []
    callback_t = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def add(hwnd, _lparam):
        info = window_info(hwnd)
        if info and info.title != exclude_title:
            entries.append(info)
        return True

    cb = callback_t(add)
    user32.EnumWindows.argtypes = [callback_t, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumWindows(cb, 0)
    return entries[:150]


def find_recoverable_sessions(folder: Path) -> list[Path]:
    """List only v2 working directories with usable MKV media; never delete them."""
    if not folder.is_dir():
        return []
    results: list[Path] = []
    for path in folder.glob("gravador_tela_*"):
        if path.is_dir() and not path.is_symlink():
            if any(p.is_file() and p.stat().st_size > 1024 for p in path.glob("video_[0-9][0-9][0-9].mkv")):
                results.append(path)
    return sorted(results, key=lambda p: p.stat().st_mtime, reverse=True)


def write_session_manifest(session: Path, *, fps: int, source: str, audio: bool) -> None:
    """Escrita atômica do manifesto para localizar sessões após uma queda."""
    payload = {"schema": 1, "version": "2.0.0", "started_at": dt.datetime.now().isoformat(timespec="seconds"),
               "fps": int(fps), "source": source, "audio_requested": bool(audio)}
    temp = session / "sessao.json.tmp"
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, session / "sessao.json")


def _exec(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, errors="replace",
                            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout)[-2200:])


def _unique_destination(folder: Path, stem: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(0, 1000):
        name = stem if i == 0 else f"{stem}_{i:03d}"
        output = folder / (name + ".mp4")
        if not output.exists() and not output.with_suffix(".partial.mp4").exists():
            return output
    raise RuntimeError("Não há nome de gravação disponível.")


def recover_session(ffmpeg: str, session: Path, destination: Path) -> Path:
    """Recupera o vídeo dos MKVs, preservando os originais e sem prometer áudio.

    O WAV pode não ter sido finalizado na falha: por segurança recupera apenas
    vídeo, com aviso explícito na interface. Não remove nenhum arquivo de origem.
    """
    if not session.is_dir() or session.is_symlink() or not session.name.startswith("gravador_tela_"):
        raise ValueError("Selecione uma pasta de sessão gravador_tela_* válida.")
    videos = sorted(p for p in session.glob("video_[0-9][0-9][0-9].mkv")
                    if p.is_file() and p.stat().st_size > 1024)
    if not videos:
        raise ValueError("Não encontrei segmentos MKV recuperáveis nesta sessão.")
    dest = _unique_destination(destination, "Recuperada_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
    tmp = dest.with_suffix(".partial.mp4")
    work = session / "_recuperacao"
    work.mkdir(exist_ok=True)
    processed: list[Path] = []
    try:
        for i, source in enumerate(videos, 1):
            output = work / f"segmento_{i:03d}.mp4"
            _exec([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-fflags", "+genpts",
                   "-i", str(source), "-map", "0:v:0", "-an", "-c:v", "copy", "-movflags", "+faststart", str(output)])
            if output.stat().st_size <= 1024:
                raise RuntimeError(f"Trecho {i} não produziu vídeo utilizável.")
            processed.append(output)
        if len(processed) == 1:
            shutil.copy2(processed[0], tmp)
        else:
            file_list = work / "lista.txt"
            file_list.write_text("".join(f"file '{p.name}'\n" for p in processed), encoding="utf-8")
            _exec([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                   "-i", str(file_list), "-c:v", "copy", "-movflags", "+faststart", str(tmp)])
        if not tmp.is_file() or tmp.stat().st_size < 1024:
            raise RuntimeError("Arquivo recuperado incompleto.")
        os.replace(tmp, dest)
        return dest
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        # Nenhum arquivo original é excluído. Somente os remuxes auxiliares.
        shutil.rmtree(work, ignore_errors=True)
