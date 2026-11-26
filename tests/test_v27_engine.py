"""FFmpeg integration regression: dual-track capture -> two MP4 outputs (synthetic)."""
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

try:
    import mss  # noqa: F401
except ImportError:
    sys.modules['mss'] = SimpleNamespace(mss=lambda: None)

from gravador_tela import DualRecordingEngine, Segment, Screen, Settings
import imageio_ffmpeg


class DualEngineIntegration(unittest.TestCase):
    def test_finish_synthetic_dual_tracks_with_two_segments(self):
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            work=folder/'work'
            work.mkdir()
            engine=DualRecordingEngine.__new__(DualRecordingEngine)
            engine.ffmpeg=ffmpeg
            engine.tempdir=work
            engine.settings=Settings(
                area=Screen('A',0,0,320,180), fps=24, crf=22,
                mic=False, system_audio=False, folder=folder,
                secondary_area=Screen('B',400,0,192,108),
            )
            engine.current=None
            engine.warnings=[]
            engine.segments=[]
            for i in (1,2):
                src=work/f'video_{i:03d}.mkv'
                args=[ffmpeg,'-hide_banner','-loglevel','error','-y',
                      '-f','lavfi','-i','testsrc2=size=320x180:rate=24:duration=0.6',
                      '-f','lavfi','-i','testsrc2=size=192x108:rate=24:duration=0.6',
                      '-map','0:v','-map','1:v','-c:v','libx264','-threads','2',str(src)]
                run=subprocess.run(args,capture_output=True,timeout=25)
                self.assertEqual(run.returncode,0,run.stderr.decode(errors='replace')[-400:])
                engine.segments.append(Segment(i,src,None,None,0.,audio=[]))
            paths=engine.finish()
            self.assertEqual(len(paths),2)
            for path in paths:
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size,1000)
                self.assertNotIn('.partial',path.name)
                info=subprocess.run([ffmpeg,'-hide_banner','-i',str(path)],
                                    capture_output=True,timeout=15)
                self.assertIn(b'Video: h264',info.stderr)
            self.assertIn(b'320x180',subprocess.run([ffmpeg,'-hide_banner','-i',str(paths[0])],capture_output=True).stderr)
            self.assertIn(b'192x108',subprocess.run([ffmpeg,'-hide_banner','-i',str(paths[1])],capture_output=True).stderr)
            self.assertFalse(work.exists())


if __name__=='__main__': unittest.main()
