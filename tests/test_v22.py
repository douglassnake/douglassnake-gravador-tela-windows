import subprocess
import tempfile
import unittest
import imageio_ffmpeg
from pathlib import Path
from gravador_v22_studio import (
    CAMERA_OFF, parse_dshow_video_devices, studio_video_flags, multi_audio_mux_command,
)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


class StudioTests(unittest.TestCase):
    def test_dshow_parser(self):
        text = '''[dshow @ abc] DirectShow video devices (some may be both video and audio devices)
[dshow @ abc]  "USB Video"
[dshow @ abc]     Alternative name "@device_pnp_12"
[dshow @ abc]  "Integrated Camera"
[dshow @ abc] DirectShow audio devices
[dshow @ abc]  "Microphone"
'''
        self.assertEqual(parse_dshow_video_devices(text), ['USB Video','Integrated Camera'])

    def test_video_disabled_matches_previous_filter(self):
        camera_args, flags = studio_video_flags(None, 1920)
        self.assertEqual(camera_args, [])
        self.assertEqual(flags, ['-an', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2'])
        self.assertTrue(CAMERA_OFF)

    def test_overlay_filter_for_different_resolutions(self):
        for width in (640, 1280, 1920, 3840):
            args, opts = studio_video_flags('USB Camera', width)
            self.assertIn('video=USB Camera', args)
            self.assertIn('[vout]', opts)
            self.assertIn('overlay=W-w-16', ' '.join(opts))
        with self.assertRaises(ValueError):
            studio_video_flags('foo\nbar', 1920)

    def test_audio_missing_keeps_stream_layout(self):
        command = multi_audio_mux_command('ffmpeg', Path('input.mkv'), Path('out.mp4'), 4.0,
                                          [('microfone', None, None), ('sistema', None, None)])
        self.assertEqual(command.count('-map'), 4)
        self.assertIn('title=Mix', command)
        self.assertIn('title=Microfone', command)
        self.assertIn('title=Sistema', command)
        self.assertEqual(command.count('anullsrc=r=48000:cl=stereo'), 2)

    def test_audio_sources_validated(self):
        with self.assertRaises(ValueError):
            multi_audio_mux_command('ffmpeg', Path('in'), Path('out'), 0, [('microfone', None, None)])
        with self.assertRaises(ValueError):
            multi_audio_mux_command('ffmpeg', Path('in'), Path('out'), 3, [('camera', None, None)])

    @unittest.skipUnless(Path(FFMPEG).exists(), 'FFmpeg ausente')
    def test_real_audio_tracks_and_concat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            segments = []
            for index in range(2):
                video = root / f'video{index}.mkv'
                out = root / f'out{index}.mp4'
                make = [FFMPEG, '-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
                        'testsrc2=s=320x240:r=24:d=1.2','-an','-c:v','libx264',
                        '-preset','ultrafast', str(video)]
                subprocess.run(make, check=True, capture_output=True)
                # Segmento 1 com dois sons reais; segmento 2 simula microfone indisponível.
                mic = root / f'mic{index}.wav'
                sys = root / f'system{index}.wav'
                for wav,freq in [(mic,440),(sys,660)]:
                    subprocess.run([FFMPEG, '-hide_banner','-loglevel','error','-y','-f','lavfi',
                                    '-i', f'sine=frequency={freq}:duration=1.2',
                                    '-c:a','pcm_s16le',str(wav)],check=True,capture_output=True)
                tracks = [('microfone', mic if index == 0 else None,
                           '[1:a]aresample=48000,aformat=channel_layouts=stereo' if index == 0 else None),
                          ('sistema',sys,'[2:a]aresample=48000,aformat=channel_layouts=stereo')]
                cmd = multi_audio_mux_command(FFMPEG,video,out,1.2,tracks)
                subprocess.run(cmd,check=True,capture_output=True)
                segments.append(out)
            filelist = root/'concat.txt'
            filelist.write_text(''.join(f"file '{x.name}'\n" for x in segments))
            final = root/'final.mp4'
            subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0',
                            '-i',str(filelist),'-map','0','-c','copy',str(final)],check=True,capture_output=True)
            probe = subprocess.run([FFMPEG,'-hide_banner','-i',str(final)],
                                   capture_output=True,text=True,errors='replace')
            streams=[line for line in probe.stderr.splitlines() if 'Stream #0:' in line]
            self.assertEqual(sum('Video:' in x for x in streams),1)
            self.assertEqual(sum('Audio:' in x for x in streams),3)
            self.assertGreater(final.stat().st_size,10_000)

    @unittest.skipUnless(Path(FFMPEG).exists(), 'FFmpeg ausente')
    def test_webcam_overlay_synthetic(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'overlay.mkv'
            _,filters=studio_video_flags('Mock Camera',640)
            subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-y',
                            '-f','lavfi','-i','testsrc2=s=640x360:r=24:d=1',
                            '-f','lavfi','-i','testsrc2=s=320x240:r=15:d=1',
                            *filters,'-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',str(dest)],
                           check=True,capture_output=True,timeout=15)
            self.assertGreater(dest.stat().st_size,10_000)

if __name__=='__main__':
    unittest.main()
