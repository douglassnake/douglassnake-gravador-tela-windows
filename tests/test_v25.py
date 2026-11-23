"""Regressões 2.5: borracha, texto, PNG/JSON e compatibilidade do gravador."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image
from gravador_v24_history import AnnotationHistory
from gravador_v23_overlay import StudioOverlay, CaptureBounds, ANNOTATION_TOOLS
from gravador_v25_export import export_annotations, render_png, validate_records


class EraserHistoryTests(unittest.TestCase):
    def test_erase_multiple_one_undo(self):
        h=AnnotationHistory()
        for n in (10,11,12): h.record(n)
        change=h.erase([10,11,11,800])
        self.assertEqual(set(change.hide),{10,11})
        self.assertEqual(h.visible,{12})
        self.assertEqual(set(h.undo().show),{10,11})
        self.assertEqual(h.visible,{10,11,12})
        self.assertEqual(set(h.redo().hide),{10,11})
        h.undo();h.erase([12]);self.assertFalse(h.can_redo)

    def test_erase_empty_no_step(self):
        h=AnnotationHistory()
        self.assertFalse(h.erase([3]).hide)
        self.assertFalse(h.can_undo)

    def test_clear_and_erasing_with_undo(self):
        h=AnnotationHistory()
        h.record(1);h.record(2);h.erase([1]);h.clear()
        h.undo();self.assertEqual(h.visible,{2})
        h.undo();self.assertEqual(h.visible,{1,2})
        h.redo();self.assertEqual(h.visible,{2})


class OverlayV25Tests(unittest.TestCase):
    def overlay(self):
        o=StudioOverlay.__new__(StudioOverlay)
        o.parent=MagicMock();o.bounds=CaptureBounds(-1280,20,1280,720)
        o.canvas=MagicMock();o.window=MagicMock()
        o.visible=True;o.closed=False;o.drawing=True
        o.history=AnnotationHistory();o.tool='Caneta';o.color_name='Vermelho';o.stroke_width=4
        o.text_value='Observação';o.text_entry=None;o.font_sizes={};o.pending_erase=set()
        o.active_item=None;o.active_tool=None;o.anchor=None;o.on_tool_changed=None
        o.toolbar_window=None;o.toolbar_buttons={}
        return o

    def test_eraser_drag_hides_but_can_undo(self):
        o=self.overlay();o.history.record(31);o.history.record(32)
        o.canvas.find_overlapping.side_effect=[(31,), (32,), (32,)]
        o.set_tool('Borracha')
        o._press(SimpleNamespace(x=12,y=20))
        o._drag(SimpleNamespace(x=42,y=25))
        o._release(SimpleNamespace(x=44,y=26))
        self.assertEqual(o.history.visible,set())
        self.assertEqual(o.history._cursor,3)  # one gesture after two additions
        o.undo();self.assertEqual(o.history.visible,{31,32})
        o.canvas.itemconfigure.assert_any_call(31,state='hidden')
        o.canvas.itemconfigure.assert_any_call(32,state='normal')

    def test_text_placed_once_and_undo(self):
        o=self.overlay();o.set_tool('Texto')
        o.canvas.create_text.return_value=80
        o._press(SimpleNamespace(x=90,y=40))
        self.assertEqual(o.history.visible,{80})
        self.assertEqual(o.font_sizes[80],24)
        self.assertEqual(o.canvas.create_text.call_args.kwargs['text'],'Observação')
        o._drag(SimpleNamespace(x=120,y=60));o._release(SimpleNamespace(x=120,y=60))
        self.assertEqual(o.history._cursor,1)
        o.undo();self.assertEqual(o.history.visible,set())

    def test_export_collects_only_history_items(self):
        o=self.overlay();o.history.record(10);o.history.record(11);o.history.record(12)
        o.canvas.find_all.return_value=(1,2,3,10,11,12,13)
        o.canvas.type.side_effect=lambda i:{10:'line',11:'rectangle',12:'text'}[i]
        o.canvas.coords.side_effect=lambda i:{10:[10,20,30,40],11:[10,20,40,80],12:[50,60]}[i]
        o.canvas.itemcget.side_effect=lambda i,k: {
            (10,'arrow'):'none',(10,'fill'):'#ffed65',(10,'width'):'4',
            (11,'outline'):'#ff0000',(11,'width'):'2',
            (12,'fill'):'#00ff00',(12,'text'):'Nota',
        }[(i,k)]
        o.font_sizes[12]=24
        rows=o._annotation_records()
        self.assertEqual([r['tipo'] for r in rows],['Caneta','Retângulo','Texto'])
        with tempfile.TemporaryDirectory() as tmp:
            png,js=export_annotations(Path(tmp)/'comentarios.png', rows, 160, 120)
            self.assertTrue(png.exists());self.assertTrue(js.exists())
            with Image.open(png) as im:
                self.assertEqual(im.mode,'RGBA')
                self.assertEqual(im.size,(160,120))
                self.assertEqual(im.getpixel((159,119))[3],0)
            data=json.loads(js.read_text(encoding='utf-8'))
            self.assertEqual(len(data['anotacoes']),3)

    def test_tools_list_preserves_old_ones(self):
        self.assertEqual(ANNOTATION_TOOLS[:3],('Caneta','Seta','Retângulo'))
        self.assertIn('Texto',ANNOTATION_TOOLS)
        self.assertIn('Borracha',ANNOTATION_TOOLS)


class ExportTests(unittest.TestCase):
    def test_png_is_transparent_outside_annotations(self):
        records=[{'tipo':'Seta','pontos':[10,10,45,45],'cor':'#ffed65','espessura':4},
                 {'tipo':'Texto','pontos':[15,60],'cor':'#ffffff','espessura':4,'texto':'ABC','fonte_px':24}]
        image=render_png(records,120,100)
        self.assertEqual(image.getpixel((119,99)),(0,0,0,0))
        self.assertGreater(image.getpixel((20,20))[3],0)

    def test_validation_rejects_out_of_bounds_or_bad_color(self):
        with self.assertRaises(ValueError):validate_records([],9000,100)
        with self.assertRaises(ValueError):validate_records([{'tipo':'Texto','pontos':[1,2],'cor':'white','texto':'x'}],120,100)
        with self.assertRaises(ValueError):validate_records([{'tipo':'Texto','pontos':[float('nan'),2],'cor':'#ffffff'}],120,100)

    def test_export_without_desktop_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('PIL.ImageGrab.grab',side_effect=RuntimeError('screen capture should never happen')):
                png,js=export_annotations(Path(tmp)/'only_annotations.png',[],120,90)
                self.assertTrue(png.exists());self.assertTrue(js.exists())

if __name__=='__main__': unittest.main()
