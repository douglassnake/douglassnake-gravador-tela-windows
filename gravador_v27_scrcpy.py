# -*- coding: utf-8 -*-
"""Android camera B via scrcpy over an authorized USB/ADB connection.

The camera is encoded on Android and recorded directly by scrcpy. No GDI
recapture, virtual webcam driver, network forwarding, or phone-side install.
The scrcpy Windows preview window enables a WM_CLOSE request at segment end,
so the MKV writer can finalize normally. Never treat forced termination as a
successful recording.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re
import time
from pathlib import Path
import shutil
import subprocess
import sys

SCRCPY_B_SOURCE = 'Câmera Android via scrcpy (USB)'
CAMERA_FACINGS = ('Traseira', 'Frontal')
WINDOW_TITLE = 'GravadorTelaWin - Camera Android B'


def locate_scrcpy(value: str | Path) -> tuple[Path, Path]:
    """Only use an explicit executable or one found on PATH. No installers."""
    candidate = str(value).strip().strip('"') if value else ''
    if not candidate:
        candidate = shutil.which('scrcpy.exe') or shutil.which('scrcpy') or ''
    p = Path(candidate).expanduser()
    if not p.is_file() or p.name.casefold() != 'scrcpy.exe':
        raise ValueError('Selecione o scrcpy.exe na pasta oficial do scrcpy para Windows.')
    adb = p.parent / 'adb.exe'
    if not adb.is_file():
        raise ValueError('adb.exe não encontrado junto ao scrcpy.exe; use o pacote completo do scrcpy.')
    return p.resolve(), adb.resolve()


def parse_adb_devices(output: str) -> list[dict]:
    """Never report an unauthorized/offline device as ready."""
    result = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith('List of devices') or line.startswith('*'):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] in ('device', 'unauthorized', 'offline'):
            result.append({'serial': parts[0], 'state': parts[1],
                           'usb': any(x.startswith('usb:') for x in parts[2:])})
    return result


def check_usb_android(adb: Path, *, runner=subprocess.run) -> dict:
    """adb -d selects a unique USB device; rejects TCP/IP-only connections."""
    kwargs = dict(capture_output=True, text=True, errors='replace', timeout=12)
    if sys.platform == 'win32':
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    res = runner([str(adb), 'devices', '-l'], **kwargs)
    if res.returncode:
        raise RuntimeError('ADB não conseguiu consultar os dispositivos: ' + res.stderr[-250:])
    found = parse_adb_devices(res.stdout)
    blocked = [x for x in found if x['state'] == 'unauthorized']
    if blocked:
        raise ValueError('Autorize a depuração USB na tela do Android e tente novamente.')
    offline = [x for x in found if x['state'] == 'offline']
    if offline:
        raise ValueError('ADB detectou aparelho offline; reconecte o cabo e reinicie a depuração USB.')
    # Cross-check by asking ADB itself to select exactly one physical USB device.
    check = runner([str(adb), '-d', 'get-state'], **kwargs)
    if check.returncode != 0 or check.stdout.strip() != 'device':
        raise ValueError('Conecte e autorize exatamente um Android por USB (ADB -d).')
    usb = [x for x in found if x['state'] == 'device' and x['usb']]
    return {'connected': True, 'authorized': True, 'usb_count': len(usb),
            'device_count': sum(x['state'] == 'device' for x in found)}


def scrcpy_camera_command(scrcpy_exe: Path, destination: Path, *,
                          facing: str = 'Traseira', fluidez: bool = True) -> list[str]:
    if facing not in CAMERA_FACINGS:
        raise ValueError('Escolha câmera traseira ou frontal.')
    if destination.suffix.lower() != '.mkv':
        raise ValueError('Use MKV temporário para tolerar interrupções de gravação.')
    if not destination.is_absolute():
        raise ValueError('O arquivo temporário deve ter caminho absoluto.')
    return [str(scrcpy_exe), '--select-usb', '--video-source=camera',
            '--camera-facing=' + ('back' if facing == 'Traseira' else 'front'),
            '--video-codec=h264', '--no-audio', '--no-control',
            '--window-title=' + WINDOW_TITLE,
            *(('--max-size=1280',) if fluidez else ()),
            '--record=' + str(destination)]



def scrcpy_log_excerpt(log_path: Path, *, max_chars: int = 650) -> str:
    """Small actionable excerpt for a local error dialog; complete log is retained.

    The log may include Android device identifiers. Never send it to a server.
    """
    try:
        lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return 'Log scrcpy ainda não disponível.'
    relevant = [line.strip() for line in lines
                if re.search(r'\b(?:ERROR|FATAL|WARN|exception|failed|camera|recording)\b',
                             line, flags=re.IGNORECASE)]
    selected = relevant[-4:] if relevant else lines[-4:]
    return ' | '.join(selected)[-max_chars:] if selected else 'Log scrcpy vazio.'


def scrcpy_recording_started(video: Path, log_path: Path) -> bool:
    """Do not require video data to exceed 1 KB before scrcpy flushes its MKV.

    Accept an explicit scrcpy recording-start message, or enough file bytes.
    The caller must check the child process is still alive before accepting.
    """
    try:
        if video.is_file() and video.stat().st_size > 1000:
            return True
    except OSError:
        pass
    try:
        content = log_path.read_text(encoding='utf-8', errors='replace')[-4096:]
    except OSError:
        return False
    return bool(re.search(r'(?i)\brecording\s+started\s+to\b', content))


def wait_for_scrcpy_recording(proc, video: Path, log_path: Path, *,
                              timeout: float = 25.0, interval: float = .2) -> None:
    """Allow slow ADB/camera startup, but report the actual child-process error.

    This must not close or minimize the preview: doing so before camera setup
    finishes can cause avoidable startup failures on some Windows configurations.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code = proc.poll()
        if code is not None:
            raise RuntimeError(
                f'scrcpy encerrou na inicialização (código {code}). '
                f'{scrcpy_log_excerpt(log_path)}. Log: {log_path}')
        if scrcpy_recording_started(video, log_path):
            return
        time.sleep(interval)
    code = proc.poll()
    if code is not None:
        raise RuntimeError(
            f'scrcpy encerrou na inicialização (código {code}). '
            f'{scrcpy_log_excerpt(log_path)}. Log: {log_path}')
    raise RuntimeError(
        f'Câmera B não confirmou início em {timeout:g}s. '
        f'{scrcpy_log_excerpt(log_path)}. Log: {log_path}')

def _windows_for_pid(pid: int, *, include_hidden: bool = False) -> list[int]:
    """Enumerate top-level HWNDs owned by this exact process (never other apps).

    SDL windows may no longer satisfy IsWindowVisible after changing state.
    A shutdown can examine hidden windows, while preview minimization may not.
    """
    if sys.platform != 'win32':
        return []
    user32 = ctypes.windll.user32
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    result = []
    CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visitor(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and (include_hidden or user32.IsWindowVisible(hwnd)):
            result.append(int(hwnd))
        return True
    cb = CALLBACK(visitor)
    user32.EnumWindows(cb, 0)
    return result

def minimize_preview(proc) -> bool:
    if sys.platform != 'win32':
        return False
    win = _windows_for_pid(proc.pid)
    for hwnd in win:
        ctypes.windll.user32.ShowWindow(wintypes.HWND(hwnd), 6)  # SW_MINIMIZE
    return bool(win)


def request_camera_close(proc) -> bool:
    """Ask the child scrcpy window to close, even if minimized or hidden.

    Prefer the exact title supplied to scrcpy. Fall back ONLY to visible
    top-level windows of the SAME process. Never broadcast a shutdown.
    """
    if proc.poll() is not None:
        return True
    if sys.platform != 'win32':
        return False
    candidates = _windows_for_pid(proc.pid, include_hidden=True)
    if not candidates:
        return proc.poll() is not None
    user32 = ctypes.windll.user32
    matched = []
    for hwnd in candidates:
        buf = ctypes.create_unicode_buffer(256)
        try:
            user32.GetWindowTextW(wintypes.HWND(hwnd), buf, len(buf))
            if buf.value.strip() == WINDOW_TITLE:
                matched.append(hwnd)
        except (OSError, AttributeError, ValueError):
            continue
    windows = matched or _windows_for_pid(proc.pid)
    posted = False
    for hwnd in windows:
        try:
            if user32.PostMessageW(wintypes.HWND(hwnd), 0x0010, 0, 0):
                posted = True
        except (OSError, AttributeError, ValueError):
            pass
    return posted or proc.poll() is not None


def gracefully_stop_camera(proc, timeout: float = 15.0) -> bool:
    """Wait for scrcpy to exit; this does NOT prove the MKV is readable."""
    if proc.poll() is not None:
        return True
    posted = request_camera_close(proc)
    if not hasattr(proc, 'wait'):
        return proc.poll() is not None  # compatible with minimal diagnostic fakes
    try:
        # Allow a natural exit even if Windows could not locate the window.
        proc.wait(timeout=timeout if posted else min(timeout, 2.0))
        return True
    except subprocess.TimeoutExpired:
        return proc.poll() is not None


def scrcpy_video_readable(ffmpeg: str, video: Path, *, timeout: float = 45.0,
                          runner=subprocess.run) -> bool:
    """Check a possibly interrupted MKV without modifying the original.

    Demux/stream-copy the H.264 track to a null output. Called on abnormal
    shutdown only, so normal recording does not pay this validation cost.
    """
    try:
        if not video.is_file() or video.stat().st_size < 1000:
            return False
        cmd = [str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-nostdin',
               '-i', str(video), '-map', '0:v:0', '-an', '-c:v', 'copy',
               '-f', 'null', '-']
        opts = {'capture_output': True, 'timeout': timeout}
        if sys.platform == 'win32':
            opts['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        result = runner(cmd, **opts)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False
