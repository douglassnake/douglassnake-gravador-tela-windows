"""Testes portáteis: coordenadas, recorte, compatibilidade e comportamento opcional."""
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

from gravador_v23_overlay import (
    ANNOTATION_TOOLS, CaptureBounds, cursor_relative, zoom_crop, zoom_placement,
    StudioOverlay,
)


class V23OverlayTests(unittest.TestCase):
    @staticmethod
    def _app_module():
        # mss é nativo em Windows; não exige dependência na máquina de CI Linux.
        if 'mss' not in sys.modules:
            try:
                import mss  # noqa
            except ImportError:
                sys.modules['mss'] = types.SimpleNamespace(mss=lambda: None)
        import gravador_tela
        return gravador_tela

    def test_defaults_not_enable_any_overlay(self):
        gravador_tela = self._app_module()
        obj = gravador_tela.Settings(
            gravador_tela.Screen('Tela', 0, 0, 1920, 1080), 24, 23,
            False, False, Path('.'),
        )
        self.assertIsNone(obj.webcam_device)
        self.assertFalse(obj.separate_audio_tracks)
        self.assertEqual(obj.encoder_preference, 'Automático')

    def test_bounds_rejects_tiny_capture(self):
        with self.assertRaises(ValueError):
            CaptureBounds(0, 0, 20, 20)
        self.assertEqual(CaptureBounds(-1920, 0, 1920, 1080).x, -1920)

    def test_cursor_bounds_with_negative_monitor(self):
        area = CaptureBounds(-1920, -100, 1280, 800)
        self.assertEqual(cursor_relative(area, -1900, 5), (20, 105))
        self.assertIsNone(cursor_relative(area, -600, 0))
        self.assertIsNone(cursor_relative(area, -1950, 0))

    def test_zoom_crop_never_exposes_other_window(self):
        bounds = CaptureBounds(250, 130, 640, 400)
        for x, y in [(250, 130), (889, 529), (380, 300)]:
            crop = zoom_crop(bounds, x, y)
            self.assertIsNotNone(crop)
            left, top, right, bottom = crop
            self.assertGreaterEqual(left, bounds.x)
            self.assertGreaterEqual(top, bounds.y)
            self.assertLessEqual(right, bounds.x + bounds.width)
            self.assertLessEqual(bottom, bounds.y + bounds.height)
            self.assertEqual((right-left, bottom-top), (160, 100))
        self.assertIsNone(zoom_crop(bounds, 0, 0))

    def test_zoom_on_tiny_area_caps_size(self):
        bounds = CaptureBounds(-800, 0, 100, 80)
        self.assertEqual(zoom_crop(bounds, -800, 0), (-800, 0, -700, 80))

    def test_zoom_corner_away_from_cursor(self):
        bounds = CaptureBounds(0, 0, 1920, 1080)
        left, top = zoom_placement(bounds, 1800, 950)
        self.assertLess(left, 100)
        self.assertLess(top, 100)
        right, bottom = zoom_placement(bounds, 80, 50)
        self.assertGreater(right, 1000)
        self.assertGreater(bottom, 500)

    def test_valid_annotation_tools(self):
        self.assertTrue({'Caneta', 'Seta', 'Retângulo'} <= set(ANNOTATION_TOOLS))

    def test_no_overlay_on_non_windows(self):
        # Não cria janela de gravação fora do Windows.
        with patch('gravador_v23_overlay.sys.platform', 'linux'):
            with self.assertRaises(RuntimeError):
                StudioOverlay(MagicMock(), CaptureBounds(0, 0, 1920, 1080))

    def test_same_ffmpeg_pipeline_when_off(self):
        gravador_tela = self._app_module()
        base = gravador_tela.RecordingEngine.__new__(gravador_tela.RecordingEngine)
        base.settings = gravador_tela.Settings(
            gravador_tela.Screen('Chrome', 100, 100, 1280, 720),
            24, 23, False, False, Path('.'))
        base.ffmpeg = 'ffmpeg'
        base._progress_path = Path('progress.log')
        base.encoder = MagicMock(codec='libx264', options=('-preset','superfast','-crf','23'))
        cmd = base._ffmpeg_command(Path('video.mkv'))
        self.assertEqual(cmd.count('-f'), 1)
        self.assertIn('gdigrab', cmd)
        self.assertEqual(cmd[cmd.index('-framerate')+1], '24')
        self.assertNotIn('dshow', cmd)
        self.assertNotIn('zoompan', cmd)
        self.assertNotIn('hwnd=', ' '.join(cmd))


if __name__ == '__main__':
    unittest.main()
