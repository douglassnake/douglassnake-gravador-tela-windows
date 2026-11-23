"""Testes para carga realista de GPU, metadados de desempenho e perfil estável."""
from __future__ import annotations

import csv
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import gravador_v21_perf as perf


class BenchmarkTests(unittest.TestCase):
    def test_probe_preserva_proporcao_e_dimensoes_pares(self):
        self.assertEqual(perf.representative_probe_geometry(1920, 1080), (1920, 1080))
        self.assertEqual(perf.representative_probe_geometry(3840, 2160), (2560, 1440))
        self.assertEqual(perf.representative_probe_geometry(1280, 720), (1280, 720))
        with self.assertRaises(ValueError):
            perf.representative_probe_geometry(40, 1080)

    def test_probe_usa_video_dinamico_na_resolucao_informada(self):
        fake = subprocess.CompletedProcess(['ffmpeg'], 0, stdout='', stderr='')
        with patch.object(perf, '_execute', return_value=fake) as run, \
             patch.object(perf.time, 'perf_counter', side_effect=[10, 11]):
            ok, desc = perf.probe_encoder_throughput('ffmpeg', 'h264_nvenc', 19, 1920, 1080, 30)
        self.assertTrue(ok, desc)
        command = run.call_args[0][0]
        self.assertIn('testsrc2=size=1920x1080:rate=30', command)
        self.assertEqual(command[command.index('-frames:v')+1], '60')

    def test_probe_recusa_gpu_mais_lenta_que_tempo_real(self):
        fake = subprocess.CompletedProcess(['ffmpeg'], 0, stdout='', stderr='')
        with patch.object(perf, '_execute', return_value=fake), \
             patch.object(perf.time, 'perf_counter', side_effect=[0, 4]):
            ok, desc = perf.probe_encoder_throughput('ffmpeg', 'h264_nvenc', 19, 1920, 1080, 30)
        self.assertFalse(ok)
        self.assertIn('0.50x', desc)

    def test_automatico_troca_gpu_lenta_por_outra_aprovada(self):
        with patch.object(perf, 'available_encoders', return_value={'h264_nvenc','h264_qsv','libx264'}), \
             patch.object(perf, 'probe_hardware_encoder', return_value=(True,'')), \
             patch.object(perf, 'probe_encoder_throughput', side_effect=[(False,'0.65x'), (True,'2.0x')]) as test:
            encoder = perf.select_encoder('ffmpeg', 'Automático', 19, width=1920, height=1080, fps=30)
        self.assertEqual(encoder.codec, 'h264_qsv')
        self.assertEqual(test.call_count, 2)

    def test_automatico_faz_fallback_cpu_se_todas_gpu_lentas(self):
        with patch.object(perf, 'available_encoders', return_value={'h264_nvenc','libx264'}), \
             patch.object(perf, 'probe_hardware_encoder', return_value=(True,'')), \
             patch.object(perf, 'probe_encoder_throughput', return_value=(False,'0.50x')):
            encoder = perf.select_encoder('ffmpeg', 'Automático', 19, width=1920, height=1080, fps=30)
        self.assertEqual(encoder.codec, 'libx264')
        self.assertEqual(perf.encoder_arguments('libx264', 19), ('-preset','superfast','-crf','19'))

    def test_perfil_estavel_24fps_qualidade_alta(self):
        self.assertEqual(perf.PROFILE_PRESETS['Estável (24 FPS)'], (24, 21))

    def test_registro_csv_somente_dados_tecnicos(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            perf.append_performance_sample(root, {'codec':'libx264','encoder':'CPU',
                'fps_configurado':24,'fps':23.9,'speed':1.01,'frame':52,
                'disco_livre_mb':2200,'nome_janela':'E-mail privado',
                'fonte':'C:/Users/Teste'},'2026-11-23T08:30:00')
            perf.append_performance_sample(root, {'codec':'libx264','encoder':'CPU',
                'fps_configurado':24,'fps':23.8,'speed':0.99,'frame':102,
                'disco_livre_mb':2198},'2026-11-23T08:30:02')
            content=(root/'desempenho_amostras.csv').read_text('utf-8')
            self.assertNotIn('E-mail privado',content)
            self.assertNotIn('Users',content)
            rows=list(csv.DictReader(content.splitlines()))
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[-1]['velocidade'],'0.99')

    def test_parse_duplicados_e_quedas(self):
        result=perf.parse_progress('frame=10\ndrop_frames=2\ndup_frames=3\nprogress=continue\n')
        self.assertEqual(result['drop_frames'],2)
        self.assertEqual(result['dup_frames'],3)


if __name__ == '__main__':
    unittest.main()

class EndToEndOutputTests(unittest.TestCase):
    def test_real_ffmpeg_encodes_and_preserves_metrics_csv(self):
        import sys
        import types
        if 'mss' not in sys.modules:
            try:
                __import__('mss')
            except ImportError:
                sys.modules['mss'] = types.ModuleType('mss')
        import gravador_tela as app
        import imageio_ffmpeg
        ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            segment_dir=root/'gravador_tela_teste'
            segment_dir.mkdir()
            mkv=segment_dir/'video_001.mkv'
            cmd=[ffmpeg,'-hide_banner','-loglevel','error','-y',
                 '-f','lavfi','-i','testsrc2=size=640x360:rate=24',
                 '-frames:v','48','-an','-c:v','libx264','-preset','superfast',
                 '-crf','21','-pix_fmt','yuv420p',str(mkv)]
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            perf.append_performance_sample(segment_dir,{'encoder':'CPU (compatível)',
                'codec':'libx264','fps_configurado':24,'fps':24.0,
                'speed':1.01,'frame':48,'disco_livre_mb':2048},
                '2026-11-23T09:00:00')
            engine=app.RecordingEngine.__new__(app.RecordingEngine)
            engine.ffmpeg=ffmpeg
            engine.tempdir=segment_dir
            engine.settings=app.Settings(app.Screen('Teste',0,0,640,360),24,21,False,False,root)
            engine.current=None
            engine.segments=[app.Segment(1,mkv,None,None,0,[])]
            engine.warnings=[]
            output=engine.finish()
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size,5000)
            self.assertTrue(output.with_name(output.stem+'_desempenho.csv').exists())
            self.assertFalse(segment_dir.exists())
