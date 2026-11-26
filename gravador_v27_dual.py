# -*- coding: utf-8 -*-
"""Capture two desktop sources in one FFmpeg process, without touching single mode.

No desktop API is called on import. Inputs are validated before starting FFmpeg.
This module intentionally does not install or change video drivers.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from gravador_v2_utils import desktop_capture_args
from gravador_v27_perf import DUAL_ORIGINAL, dual_config, dual_cpu_options, dual_filter_expr


def _region(region) -> tuple[int, int, int, int]:
    vals = (region.x, region.y, region.width, region.height)
    if any(not isinstance(v, int) or isinstance(v, bool) for v in vals):
        raise ValueError('Coordenadas inválidas para captura dupla')
    x, y, width, height = vals
    if width < 64 or height < 64 or width > 16384 or height > 16384:
        raise ValueError('As duas regiões devem ter dimensões entre 64 e 16384 pixels')
    return x, y, width, height


def dual_regions_valid(primary, secondary) -> None:
    """The two regions must differ; partial overlap is allowed by design."""
    if _region(primary) == _region(secondary):
        raise ValueError('Áreas A e B são idênticas; escolha regiões diferentes')


def dual_capture_command(
    ffmpeg: str, primary, secondary, fps: int, codec: str,
    encoder_opts: tuple[str, ...] | list[str], progress_path: Path,
    output: Path, webcam: str | None = None, *,
    profile: str = DUAL_ORIGINAL,
) -> list[str]:
    """Single clock/session, two gdigrab sources and two encoded MKV video tracks.

    Video A may include webcam, B is always the selected desktop region.
    Sound is recorded once by the existing WASAPI workers and added on export.
    """
    dual_regions_valid(primary, secondary)
    if not 1 <= fps <= 120:
        raise ValueError('FPS de captura inválido')
    if codec not in ('libx264', 'h264_nvenc', 'h264_qsv', 'h264_amf'):
        raise ValueError('Codificador não autorizado para captura dupla')
    config = dual_config(profile, fps)
    if config.capture_fps != fps:
        raise ValueError('FPS pedido diverge do perfil efetivo')
    command = [ffmpeg, '-hide_banner', '-loglevel', 'warning', '-y',
               '-stats_period', '1', '-progress', str(progress_path)]
    for region in (primary, secondary):
        command += ['-thread_queue_size', str(config.queue_frames), '-f', 'gdigrab',
                    '-framerate', str(fps), '-draw_mouse', '1',
                    *desktop_capture_args(region.x, region.y, region.width, region.height)]
    graph: list[str] = []
    if webcam:
        if any(ch in webcam for ch in '\r\n\x00') or len(webcam) > 250:
            raise ValueError('Nome inválido da webcam')
        width = max(160, min(480, int(primary.width * .26)))
        width += width % 2
        command += ['-thread_queue_size', str(config.queue_frames), '-rtbufsize', '64M',
                    '-f', 'dshow', '-framerate', '15', '-i', 'video=' + webcam]
        graph += [f'[2:v]fps=15,scale={width}:-2,setsar=1[cam]',
                  '[0:v][cam]overlay=W-w-16:H-h-16:shortest=0:repeatlast=1,'
                  'pad=ceil(iw/2)*2:ceil(ih/2)*2,' + dual_filter_expr(config) + 'format=yuv420p[v0]']
    else:
        graph.append('[0:v]pad=ceil(iw/2)*2:ceil(ih/2)*2,' + dual_filter_expr(config) + 'format=yuv420p[v0]')
    graph.append('[1:v]pad=ceil(iw/2)*2:ceil(ih/2)*2,' + dual_filter_expr(config) + 'format=yuv420p[v1]')
    return command + [
        '-an', '-filter_complex', ';'.join(graph),
        '-map', '[v0]', '-map', '[v1]',
        '-c:v', codec, *dual_cpu_options(codec, encoder_opts, config),
        '-g', str(2 * fps), '-fps_mode:v:0', 'vfr', '-fps_mode:v:1', 'vfr',
        '-pix_fmt', 'yuv420p', str(output),
    ]


def split_video_stream_command(ffmpeg: str, source: Path, destination: Path,
                               stream_index: int) -> list[str]:
    if stream_index not in (0, 1):
        raise ValueError('Índice de vídeo deve ser 0 ou 1')
    return [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
            '-i', str(source), '-map', f'0:v:{stream_index}',
            '-an', '-c:v', 'copy', str(destination)]


def choose_output_pair(folder: Path, stamp: str | None = None) -> tuple[Path, Path]:
    """Allocate paired, collision-resistant names without touching prior files."""
    timestamp = stamp or datetime.now().strftime('%Y%m%d_%H%M%S')
    if len(timestamp) != 15 or timestamp[8] != '_' or not timestamp[:8].isdigit() or not timestamp[9:].isdigit():
        raise ValueError('Identificador de gravação inválido')
    for counter in range(1000):
        label = f'Gravacao_{timestamp}' + (f'_{counter:03d}' if counter else '')
        a, b = folder / f'{label}_AreaA.mp4', folder / f'{label}_AreaB.mp4'
        if not any(p.exists() or p.with_suffix('.partial.mp4').exists() for p in (a, b)):
            return a, b
    raise RuntimeError('Não foi possível gerar nomes disponíveis para os dois MP4')
