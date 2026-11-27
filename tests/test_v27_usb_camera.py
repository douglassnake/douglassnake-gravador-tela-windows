"""USB camera as Area B: DirectShow, safety, contracts, and isolation."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys
import unittest

from gravador_v27_usb_camera import (
    list_usb_camera_devices, camera_matches_mobile, usb_camera_capture_command,
    validate_video_device_name, estimated_camera_region, WINDOWS_B_SOURCE, USB_B_SOURCE,
)
from gravador_v27_perf import DUAL_STABLE, DUAL_ORIGINAL, dual_config


def area(x=0,y=0,w=1043,h=511):
    return SimpleNamespace(x=x,y=y,width=w,height=h)


class USBWebcamTests(unittest.TestCase):
    def test_dshow_video_only_with_alt_names_and_audio(self):
        report='''[dshow @ abc] DirectShow video devices (some may be both video and audio devices)
[dshow @ abc]  "Integrated Camera"
[dshow @ abc]     Alternative name "@device_pnp_\\\\?\\usb#vid_1111"
[dshow @ abc]  "Android Webcam"
[dshow @ abc]     Alternative name "@device_pnp_\\\\?\\usb#vid_2222"
[dshow @ abc] DirectShow audio devices
[dshow @ abc]  "Microphone"
'''
        with patch('gravador_v27_usb_camera.sys.platform', 'win32'):
            run=Mock(return_value=SimpleNamespace(stdout='',stderr=report,returncode=1))
            names=list_usb_camera_devices('ffmpeg.exe',runner=run)
        self.assertEqual(names,['Integrated Camera','Android Webcam'])
        self.assertEqual(run.call_args.args[0][:2],['ffmpeg.exe','-hide_banner'])
        self.assertTrue(camera_matches_mobile('Android Webcam'))
        self.assertFalse(camera_matches_mobile('Integrated Camera'))

    def test_not_false_claim_of_phone_on_generic_webcam(self):
        self.assertFalse(camera_matches_mobile('USB Video Device'))
        self.assertTrue(camera_matches_mobile('Pixel Camera'))
        self.assertFalse(camera_matches_mobile(''))

    def test_no_detection_outside_windows(self):
        with patch('gravador_v27_usb_camera.sys.platform', 'linux'):
            run=Mock()
            self.assertEqual(list_usb_camera_devices('ffmpeg',runner=run),[])
            run.assert_not_called()

    def test_bad_device_names_rejected(self):
        for name in ('', ' ', 'Cam\nEvil','a'*251, 'Cam\x00bad', None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_video_device_name(name)
        self.assertEqual(validate_video_device_name('Android Webcam'), 'Android Webcam')

    def test_camera_b_uses_dshow_not_second_gdigrab(self):
        args=usb_camera_capture_command(
            'ffmpeg',area(-1280,20),'Android Webcam',24,'libx264',
            ('-preset','superfast'),Path('progress'),Path('capture.mkv'),
            profile=DUAL_STABLE,
        )
        self.assertEqual(args.count('gdigrab'),1)
        self.assertEqual(args.count('dshow'),1)
        self.assertEqual(args.count('desktop'),1)
        self.assertIn('video=Android Webcam',args)
        self.assertEqual(args.count('-map'),2)
        self.assertIn('[v0]',args)
        self.assertIn('[v1]',args)
        self.assertIn('-1280',args)
        self.assertEqual(args[-1], 'capture.mkv')
        self.assertIn('-fps_mode:v:1',args)
        graph=args[args.index('-filter_complex')+1]
        self.assertIn('[1:v]fps=24',graph)
        self.assertIn('scale=',graph)
        self.assertIn('-thread_queue_size',args)
        self.assertNotIn('256', args)

    def test_regular_dual_paths_unchanged(self):
        from gravador_v27_dual import dual_capture_command
        args=dual_capture_command('ffmpeg',area(0,0),area(1500,0),24,
            'libx264',('-preset','ultrafast'),Path('progress'),Path('out.mkv'),
            profile=DUAL_STABLE)
        self.assertEqual(args.count('gdigrab'),2)
        self.assertEqual(args.count('dshow'),0)

    def test_stable_profile_remains_24_fps_and_preserves_original(self):
        a=usb_camera_capture_command('ffmpeg',area(),'Android Webcam',24,
            'libx264',(),Path('p'),Path('o'),profile=DUAL_ORIGINAL)
        graph=a[a.index('-filter_complex')+1]
        self.assertNotIn('scale=',graph)
        self.assertEqual(dual_config(DUAL_STABLE, 60).capture_fps,24)
        self.assertEqual(estimated_camera_region().width,1280)
        self.assertNotEqual(WINDOWS_B_SOURCE,USB_B_SOURCE)

    def test_reject_same_camera_twice(self):
        with self.assertRaisesRegex(ValueError,'duas vezes'):
            usb_camera_capture_command('ffmpeg',area(),'Android Webcam',24,
                'libx264',(),Path('p'),Path('o'),webcam_a='Android Webcam',
                profile=DUAL_STABLE)

    def test_allow_optional_distinct_webcam_a_with_three_sources(self):
        args=usb_camera_capture_command('ffmpeg',area(),'Android Webcam',24,
             'libx264',(),Path('p'),Path('o'),webcam_a='Integrated Camera',
             profile=DUAL_STABLE)
        self.assertEqual(args.count('dshow'),2)
        self.assertIn('video=Integrated Camera',args)
        self.assertIn('[2:v]fps=15',args[args.index('-filter_complex')+1])

    def test_invalid_codec_and_profile_rejected(self):
        with self.assertRaises(ValueError):
            usb_camera_capture_command('ffmpeg',area(),'Android Webcam',24,
                 'danger',(),Path('p'),Path('o'),profile=DUAL_STABLE)
        with self.assertRaises(ValueError):
            usb_camera_capture_command('ffmpeg',area(),'Android Webcam',60,
                 'libx264',(),Path('p'),Path('o'),profile=DUAL_STABLE)

    def test_ffmpeg_graph_two_video_tracks_with_synthetic_camera(self):
        # This checks the same graph topology as the Windows USB camera path,
        # substituting two lavfi sources because DirectShow is Windows-only.
        import subprocess
        import tempfile
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            self.skipTest('FFmpeg unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dual.mkv'
            cmd = usb_camera_capture_command(ffmpeg, area(0,0,640,360),
                  'Android Webcam', 24, 'libx264', ('-preset','ultrafast'),
                  Path(tmp)/'p', path, profile=DUAL_STABLE)
            end_of_inputs = cmd.index('-an')
            tail = cmd[end_of_inputs:]
            synthetic = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                         '-f','lavfi','-i','testsrc2=size=640x360:rate=24:duration=0.55',
                         '-f','lavfi','-i','testsrc2=size=640x480:rate=30:duration=0.55']
            output = synthetic + tail[:-1] + ['-t','0.55',str(path)]
            done = subprocess.run(output,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25)
            self.assertEqual(done.returncode,0,done.stderr.decode(errors='replace')[-650:])
            self.assertGreater(path.stat().st_size,1000)
            info = subprocess.run([ffmpeg,'-hide_banner','-i',str(path)],
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=12)
            self.assertGreaterEqual(info.stderr.count(b'Video: h264'),2)

    def test_no_shell_execution(self):
        # Camera name is always part of ONE -i argument; never a shell command.
        args=usb_camera_capture_command('ffmpeg',area(),'Android Webcam;calc',24,
            'libx264',(),Path('p'),Path('o'),profile=DUAL_STABLE)
        self.assertIn('video=Android Webcam;calc',args)
        self.assertNotIn('calc',args)


if __name__=='__main__':
    unittest.main()
