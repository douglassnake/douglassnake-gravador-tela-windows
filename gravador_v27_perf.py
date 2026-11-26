# -*- coding: utf-8 -*-
"""v2.7 RC2: bounded dual-capture profiles, real dual-encoder preflight and diagnostics.

No hardware calls on import. FFmpeg is invoked only when the caller explicitly
starts a dual recording; the single-area engine is unchanged.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

DUAL_STABLE = 'Fluidez (720p / até 24 FPS)'
DUAL_ORIGINAL = 'Resolução original (maior carga)'
DUAL_PROFILES = (DUAL_STABLE, DUAL_ORIGINAL)


@dataclass(frozen=True)
class DualConfig:
    name: str
    capture_fps: int
    queue_frames: int
    max_width: int | None
    max_height: int | None
    cpu_preset: str

    @property
    def scaled(self) -> bool:
        return self.max_width is not None


def dual_config(mode: str, requested_fps: int) -> DualConfig:
    if mode not in DUAL_PROFILES:
        raise ValueError('Perfil de captura dupla não reconhecido')
    if not isinstance(requested_fps, int) or not 1 <= requested_fps <= 120:
        raise ValueError('FPS inválido')
    if mode == DUAL_STABLE:
        return DualConfig(mode, min(requested_fps, 24), 16, 1280, 720, 'ultrafast')
    return DualConfig(mode, requested_fps, 32, None, None, 'superfast')


def dual_cpu_options(codec: str, options: tuple[str, ...] | list[str], config: DualConfig) -> tuple[str, ...]:
    if codec != 'libx264':
        return tuple(options)
    opts = list(options)
    if '-preset' in opts:
        opts[opts.index('-preset') + 1] = config.cpu_preset
    else:
        opts = ['-preset', config.cpu_preset] + opts
    # Avoid reorder/delayed B-frames. Rate is limited by the capture source.
    if '-tune' not in opts:
        opts += ['-tune', 'zerolatency']
    return tuple(opts)


def dual_filter_expr(config: DualConfig) -> str:
    if config.scaled:
        return ("scale=w='min(iw,1280)':h='min(ih,720)':"
                'force_original_aspect_ratio=decrease:force_divisible_by=2:flags=fast_bilinear,')
    return ''


def synthetic_dual_probe(ffmpeg: str, codec: str, options: tuple[str, ...],
                         config: DualConfig, a, b, *, timeout: float = 12.0) -> dict:
    """Test two independently ENCODED streams, not the old single-stream test.

    CPU source-generation overhead means this is an estimate, never proof that
    live gdigrab will sustain target FPS. Can be disabled in unit tests via mock.
    """
    from gravador_v21_perf import representative_probe_geometry
    frames = min(config.capture_fps, 24)
    fa = representative_probe_geometry(a.width, a.height)
    fb = representative_probe_geometry(b.width, b.height)
    graph = []
    for i in (0, 1):
        graph.append(f'[{i}:v]{dual_filter_expr(config)}format=yuv420p[v{i}]')
    cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin',
           '-f', 'lavfi', '-i', f'testsrc2=size={fa[0]}x{fa[1]}:rate={frames}:duration=1',
           '-f', 'lavfi', '-i', f'testsrc2=size={fb[0]}x{fb[1]}:rate={frames}:duration=1',
           '-filter_complex', ';'.join(graph), '-map', '[v0]', '-map', '[v1]',
           '-c:v', codec, *dual_cpu_options(codec, options, config),
           '-frames:v:0', str(frames), '-frames:v:1', str(frames),
           '-f', 'null', '-']
    t0 = time.perf_counter()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, errors='replace',
                                timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        took = time.perf_counter() - t0
        speed = round(1.0 / max(0.001, took), 3)
        return dict(ok=result.returncode == 0, speed=speed, seconds=round(took, 3),
                    details='' if result.returncode == 0 else result.stderr[-250:])
    except subprocess.TimeoutExpired:
        return dict(ok=False, speed=0.0, seconds=timeout, details='Teste de duas trilhas excedeu o limite')
    except OSError as exc:
        return dict(ok=False, speed=0.0, seconds=0, details=str(exc)[-250:])


def dual_diagnostic(tempdir: Path, output: Path, config: DualConfig,
                    codec: str, area_a, area_b, preflight: dict | None, warnings: list[str],
                    segment_metrics: list[dict] | None = None) -> Path:
    """Export only capture metrics. Never export window names, raw logs or user paths."""
    samples = []
    src = tempdir / 'desempenho_amostras.csv'
    if src.is_file():
        with src.open(encoding='utf-8', newline='') as handle:
            for row in csv.DictReader(handle):
                try:
                    speed = float(row.get('velocidade',''))
                    if math.isfinite(speed) and speed > 0:
                        samples.append(speed)
                except (TypeError, ValueError):
                    continue
    payload = {
        'formato': 'video360-dual-diagnostic-1',
        'perfil': config.name,
        'fps_configurado': config.capture_fps,
        'resolucao_maxima_saida': [config.max_width, config.max_height] if config.scaled else 'original',
        'resolucao_entrada_a': [area_a.width,area_a.height],
        'resolucao_entrada_b': [area_b.width,area_b.height],
        'codificador': codec,
        'benchmark_sintetico': preflight or {},
        'amostras_de_velocidade': len(samples),
        'velocidade_media': round(sum(samples)/len(samples), 3) if samples else None,
        'velocidade_minima': round(min(samples), 3) if samples else None,
        'amostras_abaixo_tempo_real': sum(x<1 for x in samples),
        'metricas_ffmpeg_por_segmento': segment_metrics or [],
        'avisos': [str(x)[:300] for x in warnings[:30]],
        'observacao': 'Benchmarks sinteticos nao medem FPS real do gdigrab; os videos devem ser avaliados fisicamente.',
    }
    dest = output.with_name(output.stem.replace('_AreaA','') + '_captura_dupla_diagnostico.json')
    partial = dest.with_suffix('.partial.json')
    partial.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(partial,dest)
    return dest
