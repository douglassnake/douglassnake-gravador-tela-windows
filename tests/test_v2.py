from pathlib import Path
import json
import tempfile
import unittest
import subprocess

from gravador_v2_utils import (find_recoverable_sessions, recover_session,
                               write_session_manifest, enumerate_windows, window_info)


class RecoveryTests(unittest.TestCase):
    def test_manifest_is_atomic_and_valid(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_session_manifest(root, fps=30, source='Monitor 1', audio=True)
            manifest = json.loads((root / 'sessao.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['fps'], 30)
            self.assertTrue(manifest['audio_requested'])
            self.assertFalse((root / 'sessao.json.tmp').exists())

    def test_scan_ignores_other_directories_and_short_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good = root / 'gravador_tela_abc'; good.mkdir()
            (good / 'video_001.mkv').write_bytes(b'z' * 1500)
            bad = root / 'gravador_tela_def'; bad.mkdir()
            (bad / 'video_001.mkv').write_bytes(b'z' * 8)
            other = root / 'outra_pasta'; other.mkdir()
            (other / 'video_001.mkv').write_bytes(b'z' * 1500)
            self.assertEqual(find_recoverable_sessions(root), [good])
            self.assertEqual(find_recoverable_sessions(root / 'no-such-path'), [])

    def test_recovery_rejects_invalid_session(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(ValueError):
                recover_session('ffmpeg', root, root)

    def test_remux_recovery_with_real_ffmpeg(self):
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, OSError):
            self.skipTest('FFmpeg indisponível no ambiente de teste')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            session = root / 'gravador_tela_abc'; session.mkdir()
            output = root / 'saida'
            for idx in (1, 2):
                mkv = session / f'video_{idx:03d}.mkv'
                proc = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                                      '-f', 'lavfi', '-i', 'color=c=blue:size=320x180:rate=15',
                                      '-t', '0.6', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(mkv)],
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
            path = recover_session(ffmpeg, session, output)
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 1024)
            self.assertTrue((session / 'video_001.mkv').exists())
            self.assertTrue((session / 'video_002.mkv').exists())
            self.assertEqual(list(output.glob('*.partial.mp4')), [])

    def test_window_enumeration_is_safe_non_windows(self):
        import sys
        if sys.platform != 'win32':
            self.assertEqual(enumerate_windows(), [])
            self.assertIsNone(window_info(1234))


if __name__ == '__main__':
    unittest.main()

class EnginePipelineTests(unittest.TestCase):
    def test_engine_finish_produces_mp4_from_mkv(self):
        import sys, types
        if 'mss' not in sys.modules:
            try:
                __import__('mss')
            except ImportError:
                sys.modules['mss'] = types.ModuleType('mss')
        import gravador_tela as app
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            working = root / 'gravador_tela_test'; working.mkdir()
            segments = []
            for idx in (1,2):
                mkv = working / f'video_{idx:03d}.mkv'
                process = subprocess.run([ffmpeg, '-loglevel', 'error', '-y', '-f', 'lavfi', '-i',
                                          'color=c=red:s=320x180:r=15', '-t', '0.4', '-c:v', 'libx264',
                                          '-pix_fmt', 'yuv420p', str(mkv)], capture_output=True, text=True)
                self.assertEqual(process.returncode, 0, process.stderr)
                segments.append(app.Segment(idx, mkv, None, None, 0, []))
            engine = app.RecordingEngine.__new__(app.RecordingEngine)
            engine.ffmpeg = ffmpeg
            engine.tempdir = working
            engine.settings = app.Settings(app.Screen('Monitor 1',0,0,320,180),30,23,False,False,root)
            engine.current = None
            engine.segments = segments
            engine.warnings = []
            destination = engine.finish()
            self.assertTrue(destination.is_file())
            self.assertFalse(working.exists())
            self.assertEqual(list(root.glob('*.partial.mp4')), [])
            info = subprocess.run([ffmpeg, '-hide_banner', '-i', str(destination)], capture_output=True, text=True)
            self.assertIn('Video:', info.stderr)

    def test_ffmpeg_window_capture_uses_visible_desktop_region(self):
        import sys, types
        if 'mss' not in sys.modules:
            try:
                __import__('mss')
            except ImportError:
                sys.modules['mss'] = types.ModuleType('mss')
        import gravador_tela as app
        engine = app.RecordingEngine.__new__(app.RecordingEngine)
        engine.ffmpeg = 'ffmpeg.exe'
        engine.settings = app.Settings(app.Screen('Bloco de notas',0,0,640,480, hwnd=0x1234),30,23,False,False,Path('Z:/'))
        command = engine._ffmpeg_command(Path('video_001.mkv'))
        self.assertIn('desktop', command)
        self.assertIn('640x480', command)
        self.assertNotIn('hwnd=', ' '.join(command))
        self.assertIn('video_001.mkv', command)
        engine.settings = app.Settings(app.Screen('Monitor 1',-1920,0,1920,1080),30,23,False,False,Path('Z:/'))
        cmd = engine._ffmpeg_command(Path('video_002.mkv'))
        self.assertIn('desktop',cmd)
        self.assertIn('-1920',cmd)

class AudioMuxTests(unittest.TestCase):
    def test_audio_video_mux_keeps_both_streams(self):
        import sys, types, wave, math
        if 'mss' not in sys.modules:
            try: __import__('mss')
            except ImportError: sys.modules['mss'] = types.ModuleType('mss')
        import gravador_tela as app
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); work = root / 'gravador_tela_01'; work.mkdir()
            mkv = work / 'video_001.mkv'
            result = subprocess.run([ffmpeg, '-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
                                     'color=c=green:s=320x180:r=15','-t','0.6',
                                     '-c:v','libx264','-pix_fmt','yuv420p',str(mkv)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            audio_file = work / 'mic_001.wav'
            import struct
            with wave.open(str(audio_file),'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(48000)
                samples = (int(0.1 * 32767 * math.sin(2 * math.pi * 440 * x / 48000)) for x in range(28800))
                f.writeframes(b''.join(struct.pack('<h',s) for s in samples))
            fake_audio=types.SimpleNamespace(valid=True,path=audio_file,first_audio_at=1.0,video_started_at=1.0)
            engine=app.RecordingEngine.__new__(app.RecordingEngine)
            engine.ffmpeg=ffmpeg;engine.tempdir=work
            engine.settings=app.Settings(app.Screen('Monitor',0,0,320,180),30,23,True,False,root)
            engine.current=None;engine.segments=[app.Segment(1,mkv,None,None,1.0,[fake_audio])]
            engine.warnings=[]
            output=engine.finish()
            probe=subprocess.run([ffmpeg,'-hide_banner','-i',str(output)],capture_output=True,text=True)
            self.assertIn('Video:',probe.stderr)
            self.assertIn('Audio:',probe.stderr)
            self.assertEqual(engine.warnings,[])
