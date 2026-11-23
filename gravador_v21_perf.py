# -*- coding: utf-8 -*-
"""Seleção conservadora de H.264 e leitura de diagnósticos do FFmpeg.

GPU só é escolhida após um teste REAL de codificação. Nenhum subprocesso
é executado no import; os utilitários também funcionam em Linux para testes.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys

PROFILE_PRESETS: dict[str, tuple[int, int]] = {
    "Equilibrado (30 FPS)": (30, 23),
    "Alta qualidade (30 FPS)": (30, 19),
    "Arquivo menor (24 FPS)": (24, 28),
    "Fluido (60 FPS)": (60, 21),
}
ENCODER_LABELS: dict[str, str] = {
    "Automático": "",
    "CPU (compatível)": "libx264",
    "NVIDIA NVENC": "h264_nvenc",
    "Intel Quick Sync": "h264_qsv",
    "AMD AMF": "h264_amf",
}
GPU_ORDER = ("h264_nvenc", "h264_qsv", "h264_amf")
DISPLAY_NAMES = {v: k for k, v in ENCODER_LABELS.items() if v}


@dataclass(frozen=True)
class EncoderChoice:
    codec: str
    label: str
    options: tuple[str, ...]
    warning: str = ""


def encoder_arguments(codec: str, quality: int) -> tuple[str, ...]:
    """Parâmetros de qualidade compatíveis com as quatro famílias H.264."""
    q = max(16, min(35, int(quality)))
    if codec == "libx264":
        return ("-preset", "veryfast", "-crf", str(q))
    if codec == "h264_nvenc":
        return ("-rc", "vbr", "-cq", str(q), "-b:v", "0")
    if codec == "h264_qsv":
        return ("-global_quality", str(q))
    if codec == "h264_amf":
        return ("-rc", "cqp", "-qp_i", str(q), "-qp_p", str(q))
    raise ValueError(f"Codificador não permitido: {codec}")


def _execute(command: list[str], timeout: int = 8) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, errors="replace",
                          timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


def available_encoders(ffmpeg: str) -> set[str]:
    try:
        out = _execute([ffmpeg, "-hide_banner", "-encoders"], timeout=8)
        if out.returncode != 0:
            return set()
        return set(re.findall(r"(?m)^\s*V\S*\s+(h264_(?:nvenc|qsv|amf)|libx264)\s", out.stdout))
    except (OSError, subprocess.TimeoutExpired):
        return set()


def probe_hardware_encoder(ffmpeg: str, codec: str, quality: int = 23) -> tuple[bool, str]:
    """Um encoder listado pode falhar por ausência de driver/GPU; testar de fato."""
    if codec not in GPU_ORDER:
        return False, "Hardware não suportado pelo teste"
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
               "-f", "lavfi", "-i", "color=c=black:s=128x128:r=30",
               "-frames:v", "3", "-an", "-pix_fmt", "yuv420p",
               "-c:v", codec, *encoder_arguments(codec, quality),
               "-f", "null", "-"]
    try:
        result = _execute(command, timeout=8)
    except subprocess.TimeoutExpired:
        return False, "Teste da GPU excedeu 8 segundos"
    except OSError as exc:
        return False, str(exc)
    if result.returncode != 0:
        return False, (result.stderr or "Falha do driver/encoder")[-300:].strip()
    return True, ""


def select_encoder(ffmpeg: str, preference: str, quality: int) -> EncoderChoice:
    if preference not in ENCODER_LABELS:
        raise ValueError("Selecione um codificador válido.")
    codecs = available_encoders(ffmpeg)
    if preference == "CPU (compatível)":
        if "libx264" not in codecs:
            raise RuntimeError("Este FFmpeg não contém o codificador libx264.")
        return EncoderChoice("libx264", preference, encoder_arguments("libx264", quality))
    if preference != "Automático":
        chosen = ENCODER_LABELS[preference]
        if chosen not in codecs:
            raise RuntimeError(f"{preference} não está incluído neste FFmpeg. Escolha Automático ou CPU.")
        success, reason = probe_hardware_encoder(ffmpeg, chosen, quality)
        if not success:
            raise RuntimeError(f"{preference} não passou no teste da GPU: {reason}\n"
                               "Atualize o driver ou escolha Automático/CPU.")
        return EncoderChoice(chosen, preference, encoder_arguments(chosen, quality))
    for candidate in GPU_ORDER:
        if candidate in codecs:
            success, _reason = probe_hardware_encoder(ffmpeg, candidate, quality)
            if success:
                return EncoderChoice(candidate, DISPLAY_NAMES[candidate], encoder_arguments(candidate, quality))
    if "libx264" not in codecs:
        raise RuntimeError("Nenhum codificador H.264 compatível encontrado no FFmpeg.")
    return EncoderChoice("libx264", "CPU (compatível)", encoder_arguments("libx264", quality),
                         "Nenhuma GPU H.264 passou no autoteste; gravação pela CPU.")


def parse_progress(text: str) -> dict[str, float | int | str]:
    """Interpreta o último registro completo de `-progress` do FFmpeg."""
    current: dict[str, str] = {}
    latest: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not re.fullmatch(r"[a-zA-Z0-9_]+", key):
            continue
        current[key] = value.strip()
        if key == "progress":
            latest = current
            current = {}
    if not latest:
        latest = current
    result: dict[str, float | int | str] = {}
    if "frame" in latest:
        try:
            result["frame"] = max(0, int(latest["frame"]))
        except ValueError:
            pass
    if "fps" in latest:
        try:
            result["fps"] = max(0.0, float(latest["fps"]))
        except ValueError:
            pass
    if "speed" in latest:
        try:
            result["speed"] = max(0.0, float(latest["speed"].removesuffix("x")))
        except ValueError:
            pass
    if "progress" in latest:
        result["progress"] = latest["progress"]
    return result


def load_progress(path: Path) -> dict[str, float | int | str]:
    try:
        if not path.is_file():
            return {}
        return parse_progress(path.read_text(encoding="utf-8", errors="replace")[-20_000:])
    except OSError:
        return {}


def save_health_snapshot(session: Path, status: dict) -> None:
    """Escrita atômica de dados técnicos; nunca inclui a imagem da tela."""
    dest = session / "desempenho.json"
    temp = session / "desempenho.json.tmp"
    temp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, dest)
