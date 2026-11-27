"""RC5.1: scrcpy startup must not mistake buffered recordings for failure."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from gravador_v27_scrcpy import (
    scrcpy_log_excerpt, scrcpy_recording_started, wait_for_scrcpy_recording,
)

class StartupEvidenceTests(unittest.TestCase):
    def test_small_file_and_recording_log_mean_ready(self):
        with TemporaryDirectory() as d:
            root=Path(d); vid=root/'android_camera_001.mkv'; log=root/'scrcpy_001.log'
            vid.write_bytes(b'\x1a\x45\xdf\xa3')  # Matroska header, packets still buffered
            log.write_text('INFO: Recording started to mkv file: android_camera_001.mkv\n')
            self.assertTrue(scrcpy_recording_started(vid,log))
            p=SimpleNamespace(poll=lambda:None)
            wait_for_scrcpy_recording(p,vid,log,timeout=0.5,interval=0.001)

    def test_log_start_signal_without_buffered_file(self):
        with TemporaryDirectory() as d:
            root=Path(d);vid=root/'video.mkv';log=root/'camera.log'
            log.write_text('INFO: Recording started to mkv file: output.mkv\n')
            self.assertTrue(scrcpy_recording_started(vid,log))

    def test_sufficient_file_data_means_ready(self):
        with TemporaryDirectory() as d:
            root=Path(d);vid=root/'video.mkv';log=root/'camera.log'
            vid.write_bytes(b'a'*1300)
            self.assertTrue(scrcpy_recording_started(vid,log))

    def test_no_evidence_false(self):
        with TemporaryDirectory() as d:
            root=Path(d);vid=root/'video.mkv';log=root/'camera.log'
            log.write_text('INFO: Device found\n')
            self.assertFalse(scrcpy_recording_started(vid,log))
            vid.write_bytes(b'0'*10)
            self.assertFalse(scrcpy_recording_started(vid,log))

    def test_exited_process_reports_real_log_error(self):
        with TemporaryDirectory() as d:
            root=Path(d);vid=root/'video.mkv';log=root/'camera.log'
            log.write_text('INFO: Device found\nERROR: Cannot open camera, already in use\n')
            p=SimpleNamespace(poll=lambda:2)
            with self.assertRaisesRegex(RuntimeError,'código 2') as ctx:
                wait_for_scrcpy_recording(p,vid,log,timeout=1)
            self.assertIn('Cannot open camera',str(ctx.exception))
            self.assertIn('camera.log',str(ctx.exception))

    def test_timeout_reports_context_and_does_not_claim_success(self):
        with TemporaryDirectory() as d:
            root=Path(d);vid=root/'video.mkv';log=root/'camera.log'
            log.write_text('INFO: Device found\n')
            p=SimpleNamespace(poll=lambda:None)
            with patch('gravador_v27_scrcpy.time.monotonic',side_effect=[0.0, 0.5, 2.0]):
                with patch('gravador_v27_scrcpy.time.sleep'):
                    with self.assertRaisesRegex(RuntimeError,'não confirmou início'):
                        wait_for_scrcpy_recording(p,vid,log,timeout=1)

    def test_excerpt_is_short_and_preserves_errors(self):
        with TemporaryDirectory() as d:
            root=Path(d);log=root/'camera.log'
            log.write_text('INFO: started\nERROR: Codec unsupported\nWARN: fallback\n')
            excerpt=scrcpy_log_excerpt(log,max_chars=80)
            self.assertIn('Codec unsupported',excerpt)
            self.assertLessEqual(len(excerpt),80)

if __name__ == '__main__':
    unittest.main()
