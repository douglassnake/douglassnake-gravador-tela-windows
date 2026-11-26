"""v2.7 RC2 regression tests for lag mitigation and dual encoder preflight."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import imageio_ffmpeg
from gravador_v27_perf import (
    DUAL_STABLE, DUAL_ORIGINAL, DUAL_PROFILES,
    dual_config, dual_cpu_options, dual_filter_expr,
    synthetic_dual_probe, dual_diagnostic,
)
from gravador_v27_dual import dual_capture_command, split_video_stream_command
from gravador_v21_perf import EncoderChoice
from gravador_tela import DualRecordingEngine, RecordingEngine, Screen, Settings


def region(x, y, w=1920, h=1080):
    return SimpleNamespace(x=x, y=y, width=w, height=h)


class DualProfileTests(unittest.TestCase):
    def test_stable_caps_fps_and_output_resolution(self):
        p = dual_config(DUAL_STABLE, 60)
        self.assertEqual(p.capture_fps,24)
        self.assertEqual((p.max_width,p.max_height), (1280,720))
        self.assertEqual(p.queue_frames,16)
        self.assertEqual(p.cpu_preset,'ultrafast')
        self.assertEqual(dual_config(DUAL_STABLE,15).capture_fps,15)
        self.assertEqual(dual_config(DUAL_ORIGINAL,60).capture_fps,60)
        self.assertEqual(dual_config(DUAL_ORIGINAL,60).queue_frames,32)

    def test_no_change_to_normal_recording(self):
        self.assertEqual(len(DUAL_PROFILES),2)
        settings=Settings(Screen('A',0,0,640,360),24,23,False,False,Path('.'))
        self.assertIsNone(settings.secondary_area)

    def test_invalid_profile_rejected(self):
        for profile in ['VeryFast', '', 'Silent']:
            with self.assertRaises(ValueError):dual_config(profile, 24)
        for fps in (0, 121, True):
            if isinstance(fps,bool):continue
            with self.assertRaises(ValueError):dual_config(DUAL_STABLE,fps)

    def test_stable_uses_bounded_input_queues_and_avoids_duplicate_frames(self):
        args=dual_capture_command('ffmpeg',region(0,0),region(1920,0),24,'libx264',
                                  ('-preset','superfast','-crf','23'),
                                  Path('progress'),Path('out.mkv'),profile=DUAL_STABLE)
        self.assertEqual(args.count('-thread_queue_size'),2)
        indexes=[i for i,x in enumerate(args) if x=='-thread_queue_size']
        self.assertTrue(all(args[i+1]=='16' for i in indexes))
        self.assertEqual(args.count('-fps_mode:v:0'),1)
        self.assertEqual(args.count('-fps_mode:v:1'),1)
        self.assertEqual(args[args.index('-fps_mode:v:0')+1],'vfr')
        self.assertIn('scale=',args[args.index('-filter_complex')+1])
        self.assertIn('min(iw,1280)',args[args.index('-filter_complex')+1])
        self.assertEqual(args[args.index('-preset')+1],'ultrafast')
        self.assertEqual(args[args.index('-tune')+1],'zerolatency')

    def test_original_retains_dimensions_but_bounds_queues(self):
        args=dual_capture_command('ffmpeg',region(0,0),region(1920,0),30,'h264_qsv',
                                  (),Path('progress'),Path('out.mkv'),profile=DUAL_ORIGINAL)
        self.assertEqual(args.count('32'),2)
        self.assertNotIn('scale=',args[args.index('-filter_complex')+1])
        self.assertNotIn('ultrafast',args)
        with self.assertRaises(ValueError):
            dual_capture_command('ffmpeg',region(0,0),region(1920,0),60,'libx264',(),
                                 Path('progress'),Path('out.mkv'),profile=DUAL_STABLE)

    def test_profile_is_per_dual_capture_only(self):
        cfg=dual_config(DUAL_STABLE,24)
        self.assertEqual(dual_cpu_options('h264_nvenc',('-cq','22'),cfg),('-cq','22'))
        self.assertEqual(dual_cpu_options('libx264',('-preset','superfast'),cfg),
                         ('-preset','ultrafast','-tune','zerolatency'))


class DualProbeTests(unittest.TestCase):
    def test_probe_both_streams(self):
        ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
        cfg=dual_config(DUAL_STABLE,15)
        r=synthetic_dual_probe(ffmpeg,'libx264',('-preset','ultrafast','-crf','23'),cfg,
                               region(0,0,320,180),region(400,0,192,108))
        self.assertTrue(r['ok'],str(r))
        self.assertGreater(r['speed'],0)

    def test_auto_fallback_to_cpu_after_dual_test(self):
        p=Settings(Screen('A',0,0,640,360),24,23,False,False,Path('.'),
                   encoder_preference='Automático',secondary_area=Screen('B',640,0,640,360),
                   dual_profile=DUAL_STABLE)
        def init_mock(engine, settings):
            engine.settings=settings
            engine.ffmpeg='ffmpeg'
            engine.encoder=EncoderChoice('h264_nvenc','NVIDIA NVENC',('-cq','23'))
            engine.warnings=[]
        with patch.object(RecordingEngine,'__init__',init_mock), patch(
                'gravador_tela.synthetic_dual_probe',side_effect=[
                    {'ok':False,'speed':0.0,'details':'hardware unsupported'},
                    {'ok':True,'speed':1.5,'details':''}]):
            engine=DualRecordingEngine(p)
        self.assertEqual(engine.encoder.codec,'libx264')
        self.assertEqual(engine.dual_preflight['speed'],1.5)

    def test_manual_encoder_is_not_overridden(self):
        p=Settings(Screen('A',0,0,640,360),24,23,False,False,Path('.'),
                   encoder_preference='NVIDIA NVENC',secondary_area=Screen('B',640,0,640,360),
                   dual_profile=DUAL_STABLE)
        def init_mock(engine, settings):
            engine.settings=settings
            engine.ffmpeg='ffmpeg'
            engine.encoder=EncoderChoice('h264_nvenc','NVIDIA NVENC',('-cq','23'))
            engine.warnings=[]
        with patch.object(RecordingEngine,'__init__',init_mock), patch(
                'gravador_tela.synthetic_dual_probe',return_value=
                {'ok':False,'speed':0.0,'details':'driver returned invalid'}) as mock:
            engine=DualRecordingEngine(p)
        self.assertEqual(engine.encoder.codec,'h264_nvenc')
        self.assertEqual(mock.call_count,1)
        self.assertIn('driver',engine.warnings[0])

    def test_benchmark_timeout_fails_closed(self):
        with patch('gravador_v27_perf.subprocess.run',side_effect=subprocess.TimeoutExpired('ffmpeg',5)):
            result=synthetic_dual_probe('ffmpeg','libx264',(),dual_config(DUAL_STABLE,24),
                                        region(0,0,640,360),region(640,0,640,360))
        self.assertFalse(result['ok'])
        self.assertEqual(result['speed'],0.0)


class DualDiagnosticsTests(unittest.TestCase):
    def test_report_is_privacy_preserving_and_summarizes_speed(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp=Path(tmp)
            with (temp/'desempenho_amostras.csv').open('w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['hora','velocidade'])
                writer.writeheader()
                writer.writerow({'hora':'2026-11-26','velocidade':'0.78'})
                writer.writerow({'hora':'2026-11-26','velocidade':'1.12'})
                writer.writerow({'hora':'2026-11-26','velocidade':'nan'})
            output=dual_diagnostic(temp,temp/'Gravacao_20261126_100000_AreaA.mp4',
                                   dual_config(DUAL_STABLE,24),'libx264',
                                   region(0,0),region(1920,0),{'ok':True,'speed':1.2},[])
            doc=json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(doc['amostras_de_velocidade'],2)
            self.assertEqual(doc['amostras_abaixo_tempo_real'],1)
            self.assertEqual(doc['velocidade_media'],0.95)
            self.assertNotIn('C:',output.read_text(encoding='utf-8'))
            self.assertNotIn('janelas',doc)
            self.assertIn('_captura_dupla_diagnostico.json',output.name)


class DualSyntheticIntegrationTests(unittest.TestCase):
    def test_vfr_dual_pipeline_and_independent_outputs(self):
        ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory() as temp:
            t=Path(temp)
            a=region(0,0,640,360)
            b=region(640,0,320,180)
            cmd=dual_capture_command(ffmpeg,a,b,15,'libx264',
                                     ('-preset','superfast','-crf','23'),
                                     t/'progress',t/'both.mkv',profile=DUAL_STABLE)
            suffix=cmd[cmd.index('-an'):]
            testcmd=[ffmpeg,'-hide_banner','-loglevel','error','-y',
                     '-f','lavfi','-i','testsrc2=size=640x360:rate=15:duration=0.7',
                     '-f','lavfi','-i','testsrc2=size=320x180:rate=15:duration=0.7']+suffix
            r=subprocess.run(testcmd,capture_output=True,timeout=22)
            self.assertEqual(r.returncode,0,r.stderr.decode(errors='replace')[-800:])
            for index in (0,1):
                target=t/f'area{index}.mkv'
                result=subprocess.run(split_video_stream_command(ffmpeg,t/'both.mkv',target,index),
                                      capture_output=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[-300:])
                self.assertGreater(target.stat().st_size,1000)

if __name__=='__main__':unittest.main()
