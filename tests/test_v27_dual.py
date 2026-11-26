"""Regressions for v2.7 dual source capture, output allocation and mux."""
from __future__ import annotations
import pathlib
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from gravador_v27_dual import (
    dual_regions_valid, dual_capture_command, split_video_stream_command,
    choose_output_pair,
)


def region(x, y, w=640, h=360):
    return SimpleNamespace(x=x, y=y, width=w, height=h)


class DualCaptureTests(unittest.TestCase):
    def test_reject_duplicate_regions(self):
        with self.assertRaisesRegex(ValueError, 'idênticas'):
            dual_regions_valid(region(0,0), region(0,0))

    def test_distinct_and_overlapping_regions_allowed(self):
        dual_regions_valid(region(-1000,20),region(0,20))
        dual_regions_valid(region(0,0),region(10,10))

    def test_invalid_geometry_fails_fast(self):
        for bad in [region(0,0,20,80),region(0,0,20000,600),region(0.5,0)]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    dual_regions_valid(region(0,0),bad)

    def test_dual_inputs_one_process_two_mapped_tracks(self):
        args=dual_capture_command('ffmpeg',region(-1280,0,1024,768),region(20,45,640,360),
                                  24,'libx264',('-preset','superfast'),pathlib.Path('p.txt'),pathlib.Path('out.mkv'))
        self.assertEqual(args.count('gdigrab'),2)
        self.assertEqual(args.count('desktop'),2)
        self.assertEqual(args.count('-map'),2)
        self.assertIn('-offset_x',args)
        self.assertIn('-1280',args)
        self.assertIn('0:v', '0:v')
        self.assertIn('[v1]',args)
        self.assertNotIn('dshow',args)
        self.assertEqual(args[-1], 'out.mkv')

    def test_webcam_overlay_only_area_a(self):
        args=dual_capture_command('ffmpeg',region(0,0),region(800,0),24,
                                  'libx264',(),pathlib.Path('p'),pathlib.Path('o'),webcam='USB Camera')
        graph=args[args.index('-filter_complex')+1]
        self.assertIn('[2:v]fps=15',graph)
        self.assertIn('[0:v][cam]overlay',graph)
        self.assertIn('[1:v]pad',graph)
        self.assertEqual(args.count('dshow'),1)
        self.assertEqual(args.count('desktop'),2)
        with self.assertRaises(ValueError):
            dual_capture_command('ffmpeg',region(0,0),region(800,0),24,
                                  'libx264',(),pathlib.Path('p'),pathlib.Path('o'),webcam='evil\nvideo')

    def test_invalid_codec_rejected(self):
        with self.assertRaises(ValueError):
            dual_capture_command('ffmpeg',region(0,0),region(640,0),30,
                                  'some_codec',(),pathlib.Path('p'),pathlib.Path('o'))

    def test_stream_selection_and_naming(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=pathlib.Path(tmp)
            a,b=choose_output_pair(folder,'20261126_101010')
            self.assertEqual(a.name,'Gravacao_20261126_101010_AreaA.mp4')
            self.assertEqual(b.name,'Gravacao_20261126_101010_AreaB.mp4')
            a.touch()
            c,d=choose_output_pair(folder,'20261126_101010')
            self.assertIn('_001_',c.name)
            self.assertIn('_001_',d.name)
            self.assertEqual(split_video_stream_command('ffmpeg',a,b,1)[-3:-1], ['-c:v','copy'])

    def test_reject_malformed_name_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                choose_output_pair(pathlib.Path(tmp),'../../escape')
        with self.assertRaises(ValueError):
            split_video_stream_command('ffmpeg',pathlib.Path('a'),pathlib.Path('b'),2)

    def test_split_two_real_ffmpeg_streams(self):
        try:
            import imageio_ffmpeg
            ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            self.skipTest('FFmpeg not installed')
        with tempfile.TemporaryDirectory() as tmp:
            tmp=pathlib.Path(tmp)
            dual=tmp/'both.mkv'
            cmd=[ffmpeg,'-hide_banner','-loglevel','error','-y',
                 '-f','lavfi','-i','testsrc2=size=320x180:rate=24:duration=0.7',
                 '-f','lavfi','-i','testsrc2=size=192x108:rate=24:duration=0.7',
                 '-map','0:v','-map','1:v','-c:v','libx264','-threads','2',str(dual)]
            p=subprocess.run(cmd,capture_output=True,timeout=25)
            if p.returncode:
                self.skipTest('H.264 encoding unavailable: '+p.stderr.decode(errors='replace')[-180:])
            outputs=[]
            for i in (0,1):
                out=tmp/f'area{i}.mkv'
                result=subprocess.run(split_video_stream_command(ffmpeg,dual,out,i),
                                       capture_output=True,timeout=25)
                self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[-500:])
                self.assertGreater(out.stat().st_size,1000)
                outputs.append(out)
            self.assertNotEqual(outputs[0].stat().st_size,outputs[1].stat().st_size)


if __name__=='__main__':
    unittest.main()
