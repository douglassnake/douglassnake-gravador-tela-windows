"""RC5.2: close minimized scrcpy windows and validate preserved MKV data."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import subprocess
import sys
import unittest

import gravador_v27_scrcpy as sc


class FakeScrcpy:
    def __init__(self, pid=2468, code=None):
        self.pid = pid
        self.code = code
        self.wait_calls = []
    def poll(self):
        return self.code
    def wait(self, timeout):
        self.wait_calls.append(timeout)
        if self.code is None:
            raise subprocess.TimeoutExpired('scrcpy',timeout)
        return self.code


class ShutdownTests(unittest.TestCase):
    def test_minimized_window_is_considered_for_wm_close(self):
        """Title-matched hidden window is targeted; never post to other PIDs."""
        class User32:
            def __init__(self):
                self.calls = []
            def GetWindowTextW(self, hwnd, buff, size):
                buff.value = sc.WINDOW_TITLE
            def PostMessageW(self, hwnd, msg, a, b):
                self.calls.append((hwnd.value, msg))
                return 1
        w = User32()
        proc = FakeScrcpy()
        with patch.object(sc.sys, 'platform', 'win32'), \
             patch.object(sc.ctypes, 'windll', SimpleNamespace(user32=w),create=True), \
             patch.object(sc, '_windows_for_pid',return_value=[6553]) as enum:
            self.assertTrue(sc.request_camera_close(proc))
        enum.assert_called_once_with(2468,include_hidden=True)
        self.assertEqual(w.calls, [(6553,0x0010)])

    def test_window_not_found_waits_for_natural_exit(self):
        p=FakeScrcpy(code=0)
        with patch.object(sc,'request_camera_close',return_value=False):
            self.assertTrue(sc.gracefully_stop_camera(p))
        self.assertEqual(p.wait_calls, [])

    def test_no_window_and_alive_is_not_reported_as_clean(self):
        p=FakeScrcpy()
        with patch.object(sc,'request_camera_close',return_value=False):
            self.assertFalse(sc.gracefully_stop_camera(p,timeout=30))
        self.assertEqual(p.wait_calls,[2.0])

    def test_mkv_validation_accepts_real_h264_and_rejects_garbage(self):
        try:
            import imageio_ffmpeg
            ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            self.skipTest('FFmpeg not installed')
        with TemporaryDirectory() as d:
            video=Path(d)/'camera.mkv'
            p=subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y',
              '-f','lavfi','-i','testsrc2=size=160x120:rate=12:duration=0.5',
              '-c:v','libx264',str(video)],capture_output=True,timeout=30)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertTrue(sc.scrcpy_video_readable(ffmpeg,video))
            video.write_bytes(b'garbage'*1000)
            self.assertFalse(sc.scrcpy_video_readable(ffmpeg,video))
            self.assertFalse(sc.scrcpy_video_readable(ffmpeg,Path(d)/'missing.mkv'))

    def test_video_probe_never_reencodes(self):
        with TemporaryDirectory() as d:
            video=Path(d)/'original.mkv';video.write_bytes(b'x'*2000)
            calls=[]
            def fake(cmd,**kwargs):
                calls.append((cmd,kwargs))
                return SimpleNamespace(returncode=0)
            self.assertTrue(sc.scrcpy_video_readable('ffmpeg',video,runner=fake))
            cmd=calls[0][0]
            self.assertIn('copy',cmd)
            self.assertEqual(cmd[-2:],['null','-'])
            self.assertNotIn('-y',cmd)
            self.assertNotIn('--record',cmd)


class StopSegmentRecoveryTests(unittest.TestCase):
    def _make_engine(self, folder: Path, with_mkv=True):
        from gravador_tela import ScrcpyDualEngine, Segment
        import io
        eng = ScrcpyDualEngine.__new__(ScrcpyDualEngine)
        eng.ffmpeg = 'ffmpeg'
        eng.tempdir = folder
        eng.warnings = []
        eng.scrcpy_camera_segments = {}
        eng.scrcpy_log = io.BytesIO(b'')
        eng.scrcpy_proc = FakeScrcpy(code=0)  # already exited; no kill allowed
        eng.current = Segment(1, folder/'area_a.mkv', None, None, 0.0, audio=[])
        if with_mkv:
            vid=folder/'android_camera_001.mkv'
            vid.write_bytes(b'fake-stream'*1000)
            eng.scrcpy_camera_segments[1]=vid
        return eng

    def test_unconfirmed_close_but_readable_video_is_recoverable(self):
        from gravador_tela import RecordingEngine
        with TemporaryDirectory() as d:
            eng=self._make_engine(Path(d))
            def stop_a(instance):
                instance.current=None
            with patch.object(RecordingEngine,'stop_segment', stop_a), \
                 patch('gravador_tela.gracefully_stop_camera', return_value=False), \
                 patch('gravador_tela.scrcpy_video_readable', return_value=True):
                eng.stop_segment()
            self.assertIsNone(eng.current)
            self.assertTrue(any('recuperada' in x.lower() for x in eng.warnings))

    def test_missing_camera_video_keeps_diagnostic_path(self):
        from gravador_tela import RecordingEngine
        with TemporaryDirectory() as d:
            eng=self._make_engine(Path(d),with_mkv=False)
            def stop_a(instance):
                instance.current=None
            with patch.object(RecordingEngine,'stop_segment', stop_a), \
                 patch('gravador_tela.gracefully_stop_camera', return_value=False), \
                 patch('gravador_tela.scrcpy_log_excerpt', return_value='Erro da camera'):
                with self.assertRaisesRegex(RuntimeError,'scrcpy código=0') as err:
                    eng.stop_segment()
            self.assertIn('Erro da camera',str(err.exception))
            self.assertIn(str(Path(d)),str(err.exception))

if __name__=='__main__':
    unittest.main()
