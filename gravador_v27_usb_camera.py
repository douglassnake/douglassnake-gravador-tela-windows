# -*- coding: utf-8 -*-
"""Fonte B de vídeo USB/DirectShow (UVC), isolada da gravação convencional.

O Windows expõe certas câmeras de celular no DirectShow. O módulo NÃO presume
que todo celular ligado por USB seja UVC, não executa ADB e não instala driver.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

from gravador_v22_studio import parse_dshow_video_devices
from gravador_v2_utils import desktop_capture_args
from gravador_v27_perf import DUAL_ORIGINAL, dual_config, dual_cpu_options, dual_filter_expr

WINDOWS_B_SOURCE = "Outra tela/região do Windows"
USB_B_SOURCE = "Câmera do celular via USB (UVC)"


@dataclass(frozen=True)
class EstimatedCameraRegion:
    # Somente para o pré-teste sintético de codificação, NÃO é a resolução da câmera.
    width: int = 1280
    height: int = 720


def estimated_camera_region() -> EstimatedCameraRegion:
    return EstimatedCameraRegion()


def validate_video_device_name(name: str) -> str:
    if (not isinstance(name, str) or not name.strip() or len(name) > 250
            or any(c in name for c in '\r\n\x00')):
        raise ValueError("Nome inválido da câmera USB")
    return name


def camera_matches_mobile(name: str) -> bool:
    """Heurística de interface; não prova que o dispositivo seja um telefone."""
    value = name.casefold()
    return any(word in value for word in (
        'android webcam', 'pixel', 'samsung', 'motorola', 'iphone',
        'phone camera', 'webcam android', 'câmera android', 'caméra android',
    ))


def list_usb_camera_devices(ffmpeg: str, *, runner=subprocess.run) -> list[str]:
    """Lista dispositivos de vídeo DirectShow sem abrir stream.

    Pode incluir webcams do notebook e placas de captura HDMI; a seleção é
    explícita, e não a identificação física infalível de um celular.
    """
    if sys.platform != "win32":
        return []
    result = runner([ffmpeg, '-hide_banner', '-list_devices', 'true',
                     '-f', 'dshow', '-i', 'dummy'],
                    capture_output=True, text=True, errors='replace', timeout=12,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    # -list_devices costuma retornar status != 0 porque a entrada dummy não existe.
    output = (result.stderr or '') + '\n' + (result.stdout or '')
    return [name for name in parse_dshow_video_devices(output)
            if _reasonable_name(name)]


def _reasonable_name(name: str) -> bool:
    try:
        validate_video_device_name(name)
    except ValueError:
        return False
    return True


def usb_camera_capture_command(
    ffmpeg: str, primary, camera_name: str, fps: int, codec: str,
    encoder_opts: tuple[str, ...] | list[str], progress_path: Path,
    output: Path, webcam_a: str | None = None, *, profile: str = DUAL_ORIGINAL,
) -> list[str]:
    """Um único FFmpeg: 0=gdigrab Área A, 1=dshow câmera USB Área B.

    O fluxo externo não é re-capturado por GDI. O FPS e a resolução de saída
    seguem o perfil da captura dupla. O formato de entrada DirectShow é
    negociado com o driver do dispositivo, não presumido pelo aplicativo.
    """
    validate_video_device_name(camera_name)
    if webcam_a:
        validate_video_device_name(webcam_a)
        if webcam_a == camera_name:
            raise ValueError("Uma câmera USB não pode abrir duas vezes como A e B")
    if not all(isinstance(getattr(primary, key, None), int) and
               not isinstance(getattr(primary, key), bool) for key in ('x','y','width','height')):
        raise ValueError('Coordenadas de Área A inválidas')
    if not 64 <= primary.width <= 16384 or not 64 <= primary.height <= 16384:
        raise ValueError('Área A inválida')
    if codec not in ('libx264', 'h264_nvenc', 'h264_qsv', 'h264_amf'):
        raise ValueError('Codificador não permitido')
    config = dual_config(profile, fps)
    if config.capture_fps != fps:
        raise ValueError('FPS incompatível com o perfil de captura dupla')
    command = [ffmpeg, '-hide_banner', '-loglevel', 'warning', '-y',
               '-stats_period', '1', '-progress', str(progress_path),
               '-thread_queue_size', str(config.queue_frames),
               '-f', 'gdigrab', '-framerate', str(fps), '-draw_mouse', '1',
               *desktop_capture_args(primary.x, primary.y, primary.width, primary.height),
               '-thread_queue_size', str(config.queue_frames), '-rtbufsize', '64M',
               '-f', 'dshow', '-i', 'video=' + camera_name]
    if webcam_a:
        command += ['-thread_queue_size', str(config.queue_frames), '-rtbufsize', '64M',
                    '-f', 'dshow', '-i', 'video=' + webcam_a]
        width = max(160, min(480, int(primary.width * 0.26)))
        width += width % 2
        graph_a = (f'[2:v]fps=15,scale={width}:-2,setsar=1[cam];'
                   '[0:v][cam]overlay=W-w-16:H-h-16:shortest=0:repeatlast=1,'
                   'pad=ceil(iw/2)*2:ceil(ih/2)*2,' + dual_filter_expr(config) +
                   'format=yuv420p[v0]')
    else:
        graph_a = ('[0:v]pad=ceil(iw/2)*2:ceil(ih/2)*2,' +
                   dual_filter_expr(config) + 'format=yuv420p[v0]')
    # A câmera pode negociar FPS diferente de 24. Normalizar somente a saída B;
    # não alegar que o sensor passou a capturar 24 quadros nativos por segundo.
    graph_b = (f'[1:v]fps={fps},pad=ceil(iw/2)*2:ceil(ih/2)*2,' +
               dual_filter_expr(config) + 'format=yuv420p[v1]')
    return command + [
        '-an', '-filter_complex', graph_a + ';' + graph_b,
        '-map', '[v0]', '-map', '[v1]',
        '-c:v', codec, *dual_cpu_options(codec, encoder_opts, config),
        '-g', str(2 * fps), '-fps_mode:v:0', 'vfr', '-fps_mode:v:1', 'vfr',
        '-pix_fmt', 'yuv420p', str(output),
    ]
