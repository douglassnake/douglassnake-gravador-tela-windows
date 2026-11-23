from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import gravador_v21_perf as perf


class CodecSelectionTests(unittest.TestCase):
    def test_quality_parameter_bounds_and_known_codecs(self):
        self.assertEqual(perf.encoder_arguments('libx264', 2)[-1], '16')
        self.assertEqual(perf.encoder_arguments('h264_nvenc', 99)[3], '35')
        self.assertIn('-global_quality', perf.encoder_arguments('h264_qsv', 23))
        self.assertIn('-qp_p', perf.encoder_arguments('h264_amf', 23))
        with self.assertRaises(ValueError):
            perf.encoder_arguments('unknown', 22)

    def test_gpu_auto_selected_only_if_probe_succeeds(self):
        with patch.object(perf, 'available_encoders', return_value={'h264_nvenc', 'h264_qsv', 'libx264'}), \
             patch.object(perf, 'probe_hardware_encoder', side_effect=[(False, 'sem driver'), (True, '')]) as check:
            selected = perf.select_encoder('ffmpeg', 'Automático', 23)
        self.assertEqual(selected.codec, 'h264_qsv')
        self.assertEqual(check.call_count, 2)

    def test_gpu_unsupported_fallback_cpu(self):
        with patch.object(perf, 'available_encoders', return_value={'h264_nvenc', 'libx264'}), \
             patch.object(perf, 'probe_hardware_encoder', return_value=(False, 'sem driver')):
            selected = perf.select_encoder('ffmpeg', 'Automático', 23)
            self.assertEqual(selected.codec, 'libx264')
            self.assertIn('CPU', selected.warning)

    def test_explicit_gpu_error_does_not_silently_fallback(self):
        with patch.object(perf, 'available_encoders', return_value={'libx264'}):
            with self.assertRaisesRegex(RuntimeError, 'não está incluído'):
                perf.select_encoder('ffmpeg', 'NVIDIA NVENC', 23)

    def test_real_probe_not_enough_to_just_list_encoder(self):
        fake = subprocess.CompletedProcess(['fake'], 1, stdout='', stderr='driver ausente')
        with patch.object(perf, '_execute', return_value=fake):
            good, diagnostic = perf.probe_hardware_encoder('ffmpeg', 'h264_nvenc')
        self.assertFalse(good)
        self.assertIn('driver', diagnostic)

    def test_cpu_forced_and_available_encoder_list(self):
        fake = subprocess.CompletedProcess(['ffmpeg'], 0, stdout=' V....D libx264  H264\n V....D h264_nvenc NVIDIA\n')
        with patch.object(perf, '_execute', return_value=fake):
            names = perf.available_encoders('ffmpeg')
        self.assertEqual(names, {'libx264', 'h264_nvenc'})
        with patch.object(perf, 'available_encoders', return_value=names):
            result = perf.select_encoder('ffmpeg', 'CPU (compatível)', 23)
            self.assertEqual(result.codec, 'libx264')


class ProgressTests(unittest.TestCase):
    def test_progress_takes_last_complete_block(self):
        text = 'frame=12\nfps=13.5\nspeed=0.80x\nprogress=continue\nframe=82\nfps=28.2\nspeed=1.04x\nprogress=continue\n'
        result = perf.parse_progress(text)
        self.assertEqual(result['frame'], 82)
        self.assertEqual(result['fps'], 28.2)
        self.assertEqual(result['speed'], 1.04)

    def test_partial_file_and_invalid_values_are_safe(self):
        self.assertEqual(perf.parse_progress('frame=oops\nfps=oops\nspeed=N/A\n'), {})
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'progress.txt'
            self.assertEqual(perf.load_progress(path), {})
            path.write_text('frame=50\nfps=29.7\nspeed=0.98x\nprogress=continue\n', encoding='utf8')
            self.assertEqual(perf.load_progress(path)['fps'], 29.7)


    def test_real_ffmpeg_writes_progress_file(self):
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, OSError):
            self.skipTest('FFmpeg indisponível')
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            progress = folder / 'ffmpeg.progress'
            output = folder / 'video.mkv'
            cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                   '-stats_period', '0.1', '-progress', str(progress),
                   '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=15',
                   '-frames:v', '15', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(output)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = perf.load_progress(progress)
            self.assertEqual(data.get('frame'), 15)
            self.assertEqual(data.get('progress'), 'end')

    def test_atomic_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            perf.save_health_snapshot(path, {'codec': 'h264_qsv', 'fps': 28.2})
            self.assertEqual(json.loads((path/'desempenho.json').read_text())['fps'], 28.2)
            self.assertFalse((path/'desempenho.json.tmp').exists())

    def test_installer_copies_v21_module(self):
        installer = (Path(__file__).resolve().parents[1] / 'INSTALAR.ps1').read_text(encoding='utf-8')
        self.assertIn('gravador_v21_perf.py', installer)

    def test_preset_values(self):
        self.assertEqual(perf.PROFILE_PRESETS['Fluido (60 FPS)'][0], 60)
        self.assertEqual(perf.PROFILE_PRESETS['Arquivo menor (24 FPS)'][1], 28)


if __name__ == '__main__':
    unittest.main()
