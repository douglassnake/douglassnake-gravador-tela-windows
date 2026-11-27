"""Synthetic dual output from an existing desktop stream and Android camera file.

Makes no ADB calls. Tests the actual file export path without a physical device.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

import imageio_ffmpeg
import sys
from types import SimpleNamespace
try:
    import mss
except ImportError:
    sys.modules['mss'] = SimpleNamespace(mss=lambda: None)
from gravador_tela import ScrcpyDualEngine, Segment, Screen, Settings


class ScrcpyExportTests(unittest.TestCase):
    def test_two_segments_export_separate_mp4_with_audio_only_on_area_a(self):
        exe=imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            work=folder/'work';work.mkdir()
            engine=ScrcpyDualEngine.__new__(ScrcpyDualEngine)
            engine.ffmpeg=exe
            engine.tempdir=work
            engine.settings=Settings(area=Screen('A',0,0,320,180), fps=24,
                crf=23,mic=False,system_audio=False,folder=folder,
                scrcpy_exe_b='dummy.exe',scrcpy_facing='Traseira')
            engine.current=None
            engine.segments=[]
            engine.scrcpy_camera_segments={}
            engine.scrcpy_timing=[]
            engine.warnings=[]
            for idx in (1,2):
                a=work/f'video_{idx:03d}.mkv';b=work/f'android_camera_{idx:03d}.mkv'
                for path,sz in ((a,'320x180'),(b,'192x108')):
                    cmd=[exe,'-hide_banner','-loglevel','error','-y',
                         '-f','lavfi','-i',f'testsrc2=size={sz}:rate=24:duration=0.4',
                         '-c:v','libx264','-threads','2',str(path)]
                    r=subprocess.run(cmd,capture_output=True,timeout=30)
                    self.assertEqual(r.returncode,0,r.stderr.decode(errors='replace')[-400:])
                engine.segments.append(Segment(idx,a,None,None,0.0,audio=[]))
                engine.scrcpy_camera_segments[idx]=b
            outputs=engine.finish()
            self.assertEqual(len(outputs),2)
            self.assertFalse(work.exists())
            for out in outputs:
                self.assertTrue(out.is_file())
                self.assertGreater(out.stat().st_size,1000)
                probe=subprocess.run([exe,'-hide_banner','-i',str(out)],capture_output=True)
                self.assertIn(b'Video: h264',probe.stderr)
            report=folder/(outputs[0].stem.replace('_AreaA','')+'_android_diagnostico.json')
            self.assertTrue(report.exists())
            self.assertIn('sem alinhamento quadro a quadro',report.read_text(encoding='utf-8'))
            self.assertIn(b'320x180',subprocess.run([exe,'-hide_banner','-i',str(outputs[0])],capture_output=True).stderr)
            self.assertIn(b'192x108',subprocess.run([exe,'-hide_banner','-i',str(outputs[1])],capture_output=True).stderr)


if __name__=='__main__':
    unittest.main()
