from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from gravador_v2_utils import WindowTarget, visible_window_rect, desktop_capture_args

class ChromeWindowCaptureTests(unittest.TestCase):
    def test_chrome_maximized_clipped_to_desktop(self):
        w=WindowTarget(100, 'Chrome', -8, -8, 1936, 1096)
        self.assertEqual(visible_window_rect(w, (0,0,1920,1080)),(0,0,1920,1080))
    def test_negative_monitor_coordinates(self):
        w=WindowTarget(100, 'Chrome', -1900,35,1240,920)
        self.assertEqual(visible_window_rect(w,(-1920,0,3840,1080)),(-1900,35,1240,920))
    def test_partial_window_visible(self):
        w=WindowTarget(100, 'Chrome',1800,850,640,600)
        self.assertEqual(visible_window_rect(w,(0,0,1920,1080)),(1800,850,120,230))
    def test_outside_desktop_rejected(self):
        with self.assertRaises(ValueError):
            visible_window_rect(WindowTarget(10,'Chrome',3000,3000,500,500),(0,0,1920,1080))
    def test_window_uses_desktop_not_hwnd(self):
        source=desktop_capture_args(-1900,35,1240,920)
        self.assertEqual(source,['-offset_x','-1900','-offset_y','35','-video_size','1240x920','-i','desktop'])
        self.assertNotIn('hwnd=', ' '.join(source))
    def test_engine_uses_desktop_with_window_id(self):
        if 'mss' not in sys.modules:
            try: __import__('mss')
            except ImportError: sys.modules['mss']=types.ModuleType('mss')
        import gravador_tela as app
        e=app.RecordingEngine.__new__(app.RecordingEngine)
        e.ffmpeg='ffmpeg'
        e.settings=types.SimpleNamespace(area=app.Screen('Chrome',100,200,1200,800,0x1234),fps=30,crf=23)
        e.encoder=types.SimpleNamespace(codec='libx264',options=('-preset','veryfast','-crf','23'))
        e._progress_path=Path('progress.log')
        command=e._ffmpeg_command(Path('video.mkv'))
        self.assertIn('desktop',command)
        self.assertIn('1200x800',command)
        self.assertNotIn('hwnd=', ' '.join(command))
    def test_app_selection_returns_clipped_window(self):
        if 'mss' not in sys.modules:
            try: __import__('mss')
            except ImportError: sys.modules['mss']=types.ModuleType('mss')
        import gravador_tela as app
        title='Janela • Chrome'
        dummy=types.SimpleNamespace(screen_var=types.SimpleNamespace(get=lambda:title),
              window_lookup={title:0x1234},selected_area=None,
              screens=[app.Screen('Todos',0,0,1920,1080),app.Screen('Monitor 1',0,0,1920,1080)])
        with patch.object(app,'window_info',return_value=WindowTarget(0x1234,'Chrome',-8,-8,1936,1096)):
            result=app.App._selected_screen(dummy)
        self.assertEqual((result.x,result.y,result.width,result.height),(0,0,1920,1080))
        self.assertEqual(result.hwnd,0x1234)
if __name__=='__main__':
    unittest.main()
