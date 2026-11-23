# -*- coding: utf-8 -*-
"""Estúdio v2.2: webcam opcional e mix + trilhas individuais no mesmo MP4.

Todas as funções são puras, exceto list_webcams. Sem acesso à webcam ao importar.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

CAMERA_OFF = 'Nenhuma webcam (padrão)'


def parse_dshow_video_devices(output: str) -> list[str]:
    """Lê nomes de dispositivos DirectShow, evitando aliases e dispositivos de áudio."""
    found: list[str] = []
    in_video = False
    for line in output.splitlines():
        if 'DirectShow video devices' in line:
            in_video = True
            continue
        if 'DirectShow audio devices' in line:
            in_video = False
            continue
        if not in_video or 'Alternative name' in line:
            continue
        match = re.search(r'"([^"\r\n]+)"', line)
        if match and match.group(1) not in found:
            found.append(match.group(1))
    return found


def list_webcams(ffmpeg: str) -> list[str]:
    if sys.platform != 'win32':
        return []
    try:
        result = subprocess.run([ffmpeg, '-hide_banner', '-list_devices', 'true',
                                 '-f', 'dshow', '-i', 'dummy'],
                                text=True, errors='replace', capture_output=True,
                                timeout=12, creationflags=subprocess.CREATE_NO_WINDOW)
        return parse_dshow_video_devices(result.stderr + '\n' + result.stdout)
    except (OSError, subprocess.TimeoutExpired):
        return []


def studio_video_flags(camera: str | None, screen_width: int) -> tuple[list[str], list[str]]:
    """Retorna (entradas extras, opções de vídeo) sem modificar a captura desktop.

    A câmera é sobreposta no canto inferior direito, com 26% da largura gravada.
    """
    if not camera:
        return [], ['-an', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2']
    if any(ch in camera for ch in '\r\n\x00') or len(camera) > 250:
        raise ValueError('Nome inválido de câmera')
    width = max(160, min(480, int(screen_width * 0.26)))
    width += width % 2
    camera_flags = ['-thread_queue_size', '256', '-rtbufsize', '256M',
                    '-f', 'dshow', '-framerate', '15', '-i', f'video={camera}']
    # A câmera é opcional: gravar só a tela mantém a mesma pipeline da v2.1.2.
    overlay = (f'[1:v]fps=15,scale={width}:-2,setsar=1[cam];'
               '[0:v][cam]overlay=W-w-16:H-h-16:shortest=0:repeatlast=1,'
               'pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p[vout]')
    return camera_flags, ['-an', '-filter_complex', overlay, '-map', '[vout]']


def multi_audio_mux_command(
    ffmpeg: str, video: Path, output: Path, duration: float,
    tracks: list[tuple[str, Path | None, str | None]],
) -> list[str]:
    """Faz MP4 com primeiro áudio mix e depois cada fonte individual.

    tracks contém (nome, wav_validado_ou_None, filtro_com_indice_ou_None).
    Para fontes ausentes, gera silêncio. Todas as faixas possuem duração
    compatível, inclusive entre segmentos pausados, permitindo concat -c copy.
    """
    if not tracks or duration <= 0:
        raise ValueError('Faixas ou duração inválidas')
    args = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(video)]
    filters: list[str] = []
    labels: list[str] = []
    for idx, (name, path, filter_prefix) in enumerate(tracks, start=1):
        if name not in ('microfone', 'sistema'):
            raise ValueError('Fonte de áudio inválida')
        if path is not None:
            args += ['-i', str(path)]
            if not filter_prefix:
                raise ValueError('Filtro de sincronização ausente')
            prefix = filter_prefix
        else:
            args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
            prefix = f'[{idx}:a]aresample=48000,aformat=channel_layouts=stereo'
        # Split evita reutilizar a mesma saída filtrada duas vezes.
        filters.append(f'{prefix},apad,atrim=duration={duration:.3f},'
                       f'asetpts=PTS-STARTPTS,asplit=2[mix{idx}][separate{idx}]')
        labels.append(f'[mix{idx}]')
    if len(labels) > 1:
        filters.append(f'{"".join(labels)}amix=inputs={len(labels)}:duration=longest:'
                       'dropout_transition=0:normalize=1[mixed]')
    else:
        filters.append(f'{labels[0]}anull[mixed]')
    args += ['-filter_complex', ';'.join(filters), '-map', '0:v:0', '-map', '[mixed]']
    for idx in range(1, len(tracks) + 1):
        args += ['-map', f'[separate{idx}]']
    args += ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k',
             '-metadata:s:a:0', 'title=Mix', '-disposition:a:0', 'default']
    for idx, (name, _, _) in enumerate(tracks, start=1):
        args += [f'-metadata:s:a:{idx}', f'title={"Microfone" if name == "microfone" else "Sistema"}',
                 f'-disposition:a:{idx}', '0']
    args += ['-t', f'{duration:.3f}', '-movflags', '+faststart', str(output)]
    return args
