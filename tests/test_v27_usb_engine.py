"""Mixed capture engine: A is desktop, B is selected USB camera."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile, unittest

try:
    import imageio_ffmpeg
    import sys
    sys.modules.setdefault('mss', SimpleNamespace(mss=lambda: None))
    from gravador_tela import DualRecordingEngine, RecordingEngine, Screen, Settings
except ImportError:
    DualRecordingEngine = None

@unittest.skipIf(DualRecordingEngine is None, 'GUI application dependencies unavailable')
class EngineUSBTests(unittest.TestCase):
    def settings(self,folder):
        return Settings(area=Screen('Área A',0,0,640,360), fps=24, crf=24,
            mic=False, system_audio=False, folder=Path(folder),
            secondary_area=None,usb_camera_b='Android Webcam')

    def test_ffmpeg_command_dispatches_to_usb_with_one_gdi(self):
        with tempfile.TemporaryDirectory() as tmp:
            eng=DualRecordingEngine.__new__(DualRecordingEngine)
            eng.ffmpeg='ffmpeg';eng.settings=self.settings(tmp)
            eng.encoder=SimpleNamespace(codec='libx264',options=('-preset','ultrafast'))
            args=eng._ffmpeg_command(Path('out.mkv'))
            self.assertEqual(args.count('gdigrab'),1)
            self.assertEqual(args.count('dshow'),1)
            self.assertEqual(args.count('-map'),2)

    def test_dual_reject_same_camera_a_and_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings=self.settings(tmp)
            settings.webcam_device='Android Webcam'
            with self.assertRaisesRegex(ValueError,'mesma câmera'):
                DualRecordingEngine(settings)

    def test_dual_reject_missing_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings=self.settings(tmp)
            settings.usb_camera_b=None
            with self.assertRaisesRegex(ValueError,'fonte B'):
                DualRecordingEngine(settings)

    def test_dual_reject_two_b_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings=self.settings(tmp)
            settings.secondary_area=Screen('Área B',700,0,500,400)
            with self.assertRaisesRegex(ValueError,'somente uma'):
                DualRecordingEngine(settings)

if __name__=='__main__':unittest.main()
