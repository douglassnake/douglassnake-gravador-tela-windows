"""Regressão: atalho ligava desenho, mas área transparente não capturava cliques."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from gravador_v23_overlay import StudioOverlay, CaptureBounds, INPUT_LAYER_ALPHA


class DrawingInputLayerTests(unittest.TestCase):
    def overlay(self):
        o = StudioOverlay.__new__(StudioOverlay)
        o.parent = MagicMock()
        o.bounds = CaptureBounds(-1280, 60, 1280, 720)
        o.closed = False
        o.visible = True
        o.drawing = False
        o.input_window = None
        o.input_canvas = None
        o.window = MagicMock()
        o.canvas = MagicMock()
        o.mode_text = 17
        o.active_item = None
        o.anchor = None
        o.tool = 'Caneta'
        return o

    def test_toggling_drawing_keeps_visual_click_through_but_uses_input_shield(self):
        o = self.overlay()
        with patch.object(o, '_set_pass_through') as passthrough, \
             patch.object(o, '_show_input_layer') as show, \
             patch.object(o, '_hide_input_layer') as hide:
            o.set_drawing(True)
            self.assertTrue(o.drawing)
            passthrough.assert_called_with(True)
            show.assert_called_once_with()
            hide.assert_not_called()
            o.set_drawing(False)
            self.assertFalse(o.drawing)
            self.assertEqual(passthrough.call_count, 2)
            hide.assert_called_once_with()
            o.canvas.itemconfigure.assert_called_with(17, state='hidden')

    def test_input_capture_has_nonzero_alpha_no_colorkey_and_bindings(self):
        o = self.overlay()
        visual_input = MagicMock()
        input_canvas = MagicMock()
        with patch('gravador_v23_overlay.tk.Toplevel', return_value=visual_input), \
             patch('gravador_v23_overlay.tk.Canvas', return_value=input_canvas), \
             patch.object(o, '_position_input_layer') as place_shield, \
             patch.object(o, '_place') as place_visual:
            o._show_input_layer()
            self.assertIs(o.input_window, visual_input)
            self.assertIs(o.input_canvas, input_canvas)
            self.assertTrue(0 < INPUT_LAYER_ALPHA <= 0.10)
            visual_input.wm_attributes.assert_any_call('-alpha', INPUT_LAYER_ALPHA)
            self.assertNotIn('-transparentcolor', [c.args[0] for c in visual_input.wm_attributes.call_args_list])
            input_canvas.bind.assert_any_call('<ButtonPress-1>', o._press)
            input_canvas.bind.assert_any_call('<B1-Motion>', o._drag)
            input_canvas.bind.assert_any_call('<ButtonRelease-1>', o._release)
            place_shield.assert_called_once_with(visual_input)
            place_visual.assert_called_once_with()
            o._show_input_layer()
            self.assertEqual(input_canvas.bind.call_count, 3)
            o._hide_input_layer()
            visual_input.destroy.assert_called_once_with()
            self.assertIsNone(o.input_window)

    def test_mouse_drag_writes_line_to_visible_overlay_canvas(self):
        o = self.overlay()
        o.drawing = True
        o.canvas.create_line.return_value = 42
        o.canvas.coords.return_value = [15, 20, 16, 21]
        o._press(SimpleNamespace(x=15, y=20))
        self.assertEqual(o.active_item, 42)
        o._drag(SimpleNamespace(x=100, y=80))
        o.canvas.coords.assert_called_with(42, 15, 20, 16, 21, 100, 80)
        o._release(SimpleNamespace(x=110, y=90))
        self.assertIsNone(o.active_item)

    def test_pause_resume_releases_mouse_interception(self):
        o = self.overlay()
        o.drawing = True
        with patch.object(o, '_hide_input_layer') as hide, \
             patch.object(o, '_show_input_layer') as show, \
             patch.object(o, '_place'):
            o.pause()
            self.assertFalse(o.visible)
            hide.assert_called_once_with()
            o.resume()
            self.assertTrue(o.visible)
            show.assert_called_once_with()

    def test_close_removes_input_layer(self):
        o = self.overlay()
        with patch.object(o, '_hide_input_layer') as hide:
            o.close()
            hide.assert_called_once_with()
            o.window.destroy.assert_called_once_with()
            self.assertTrue(o.closed)

if __name__ == '__main__':
    unittest.main()
