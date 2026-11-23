# -*- coding: utf-8 -*-
"""Estúdio v2.4: desenho personalizável, histórico e controles seguros."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from gravador_v24_history import (
    AnnotationHistory, ANNOTATION_COLORS, STROKE_WIDTHS, HistoryChange,
)
from gravador_v23_overlay import StudioOverlay, CaptureBounds


class HistoryTests(unittest.TestCase):
    def test_draw_undo_redo(self):
        history = AnnotationHistory()
        self.assertFalse(history.can_undo)
        self.assertFalse(history.can_redo)
        history.record(11)
        history.record(12)
        self.assertEqual(history.visible, {11, 12})
        self.assertEqual(history.undo(), HistoryChange(hide=(12,)))
        self.assertEqual(history.visible, {11})
        self.assertEqual(history.undo(), HistoryChange(hide=(11,)))
        self.assertEqual(history.redo(), HistoryChange(show=(11,)))
        self.assertEqual(history.redo(), HistoryChange(show=(12,)))
        self.assertFalse(history.can_redo)

    def test_clear_is_one_reversible_event(self):
        h = AnnotationHistory()
        for i in (2, 3, 4): h.record(i)
        self.assertEqual(h.clear(), HistoryChange(hide=(2, 3, 4)))
        self.assertEqual(h.visible, set())
        self.assertEqual(h.undo(), HistoryChange(show=(2, 3, 4)))
        self.assertEqual(h.redo(), HistoryChange(hide=(2, 3, 4)))

    def test_new_stroke_after_undo_discards_redo_orphans(self):
        h = AnnotationHistory()
        h.record(13)
        h.record(14)
        h.undo()
        self.assertEqual(h.record(15), HistoryChange(delete=(14,)))
        self.assertEqual(h.visible, {13, 15})
        self.assertFalse(h.can_redo)

    def test_preserves_old_drawings_after_clearing_branch(self):
        h = AnnotationHistory()
        h.record(1)
        h.clear()
        h.undo()  # draw 1 visível; ramo 'clear' descartado no próximo registro
        self.assertEqual(h.record(2), HistoryChange())
        self.assertEqual(h.visible, {1, 2})
        self.assertEqual(h.undo(), HistoryChange(hide=(2,)))
        self.assertEqual(h.undo(), HistoryChange(hide=(1,)))

    def test_empty_history_and_validation(self):
        h=AnnotationHistory()
        self.assertEqual(h.undo(), HistoryChange())
        self.assertEqual(h.redo(), HistoryChange())
        self.assertEqual(h.clear(), HistoryChange())
        with self.assertRaises(ValueError): h.record(-1)
        with self.assertRaises(ValueError): AnnotationHistory(max_actions=0)

    def test_history_bounds(self):
        h=AnnotationHistory(max_actions=2)
        for i in range(5): h.record(i)
        self.assertEqual(h.visible, {0,1,2,3,4})
        h.undo(); h.undo()
        self.assertFalse(h.can_undo)
        self.assertEqual(h.visible,{0,1,2})


class OverlayTests(unittest.TestCase):
    def make(self):
        o=StudioOverlay.__new__(StudioOverlay)
        o.parent=MagicMock()
        o.bounds=CaptureBounds(-1280, 40, 1280, 720)
        o.canvas=MagicMock()
        o.window=MagicMock()
        o.input_window=None
        o.input_canvas=None
        o.visible=True
        o.closed=False
        o.drawing=True
        o.tool='Caneta'
        o.color_name='Vermelho'
        o.stroke_width=7
        o.active_item=None
        o.active_tool=None
        o.anchor=None
        o.on_tool_changed=None
        o.toolbar_window=None
        o.toolbar_position=None
        o.toolbar_drag_anchor=None
        o.toolbar_buttons={}
        o.history=AnnotationHistory()
        return o

    def test_canvas_style_and_undo_redo(self):
        o=self.make()
        o.canvas.create_line.return_value=31
        o.canvas.coords.return_value=[2,3,3,4]
        o._press(SimpleNamespace(x=2,y=3))
        self.assertEqual(o.active_item, 31)
        self.assertEqual(o.active_tool,'Caneta')
        self.assertEqual(o.canvas.create_line.call_args.kwargs['fill'],ANNOTATION_COLORS['Vermelho'])
        self.assertEqual(o.canvas.create_line.call_args.kwargs['width'],7)
        o._drag(SimpleNamespace(x=8,y=10))
        o._release(SimpleNamespace(x=9,y=11))
        self.assertEqual(o.history.visible, {31})
        o.undo()
        o.canvas.itemconfigure.assert_any_call(31,state='hidden')
        o.redo()
        o.canvas.itemconfigure.assert_any_call(31,state='normal')

    def test_arrow_and_rect_use_current_color_width(self):
        o=self.make()
        o.canvas.create_line.return_value=41
        o.set_tool('Seta')
        o.set_color('Azul'); o.set_stroke_width(2)
        o._press(SimpleNamespace(x=3,y=4))
        self.assertEqual(o.canvas.create_line.call_args.kwargs['fill'],ANNOTATION_COLORS['Azul'])
        self.assertEqual(o.canvas.create_line.call_args.kwargs['width'],2)
        self.assertEqual(o.canvas.create_line.call_args.kwargs['arrow'],'last')
        o._release(SimpleNamespace(x=20,y=21))
        o.set_tool('Retângulo')
        o.canvas.create_rectangle.return_value=42
        o._press(SimpleNamespace(x=3,y=4))
        self.assertEqual(o.canvas.create_rectangle.call_args.kwargs['outline'],ANNOTATION_COLORS['Azul'])
        self.assertEqual(o.canvas.create_rectangle.call_args.kwargs['width'],2)
        o._release(SimpleNamespace(x=20,y=21))
        self.assertEqual(o.history.visible,{41,42})

    def test_color_does_not_recolor_existing_annotations(self):
        o=self.make()
        o.canvas.create_line.return_value=22
        o._press(SimpleNamespace(x=3,y=4))
        o._release(SimpleNamespace(x=9,y=15))
        o.set_color('Verde')
        self.assertEqual(o.canvas.create_line.call_args.kwargs['fill'],ANNOTATION_COLORS['Vermelho'])
        self.assertEqual(o.color_name,'Verde')

    def test_clear_is_reversible_and_protects_special_items(self):
        o=self.make()
        o.canvas.create_line.return_value=80
        o._press(SimpleNamespace(x=2,y=2))
        o._release(SimpleNamespace(x=7,y=8))
        o.clear()
        o.canvas.itemconfigure.assert_any_call(80,state='hidden')
        o.undo()
        o.canvas.itemconfigure.assert_any_call(80,state='normal')
        self.assertNotIn('delete', [call[0] for call in o.canvas.method_calls])

    def test_invalid_inputs(self):
        o=self.make()
        for fn, value in ((o.set_tool,'Borracha'),(o.set_color,'Marrom'),(o.set_stroke_width,13)):
            with self.assertRaises(ValueError): fn(value)
        self.assertEqual(STROKE_WIDTHS,(2,4,7))

    def test_toolbar_uses_negative_coordinates(self):
        o=self.make()
        x,y=o.toolbar_origin(o.bounds)
        self.assertEqual((x,y),(-1280+1280-560-12,52))
        o.toolbar_window=MagicMock()
        o.toolbar_position=(x,y)
        with patch.object(o, '_position_toolbar') as placement:
            o._raise_toolbar()
            placement.assert_called_once_with(o.toolbar_window, x, y)

    def test_toolbar_visible_only_while_drawing(self):
        o=self.make()
        o.drawing=False
        with patch('gravador_v23_overlay.tk.Toplevel') as constructor:
            o._show_toolbar()
            constructor.assert_not_called()
        o.mode_text=17
        with patch.object(o,'_set_pass_through') as passthrough, \
             patch.object(o,'_hide_input_layer') as hide:
            o.set_drawing(False)
            passthrough.assert_called_once_with(True)
            hide.assert_called_once_with()
            o.canvas.itemconfigure.assert_any_call(17, state='hidden')

    def test_app_hotkeys_registered(self):
        from pathlib import Path
        content=(Path(__file__).parents[1]/'gravador_tela.py').read_text(encoding='utf-8')
        self.assertIn('"undo_draw"',content)
        self.assertIn('"redo_draw"',content)
        self.assertIn('"toggle_draw"',content)


if __name__ == '__main__':
    unittest.main()
