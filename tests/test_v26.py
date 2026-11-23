# -*- coding: utf-8 -*-
"""Regressões v2.6: arquivos editáveis e edição de textos sobre a tela."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from gravador_v24_history import AnnotationHistory
from gravador_v26_project import project_document, save_project, load_project, PROJECT_FORMAT
from gravador_v23_overlay import StudioOverlay, CaptureBounds

def samples():
    return [
        {'tipo':'Caneta','pontos':[10,12,20,23,31,35], 'cor':'#ffed65', 'espessura':4},
        {'tipo':'Retângulo','pontos':[20,20,70,80], 'cor':'#ff5b6e', 'espessura':2},
        {'tipo':'Texto','pontos':[32,48], 'cor':'#43d6ff', 'espessura':2, 'texto':'Aviso de teste', 'fonte_px':24},
    ]

class ProjectTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'notas.gtwproj'
            self.assertEqual(save_project(p,samples(),640,480),p)
            self.assertEqual(load_project(p,640,480),project_document(samples(),640,480)['anotacoes'])
            self.assertEqual(json.loads(p.read_text(encoding='utf-8'))['formato'],PROJECT_FORMAT)

    def test_legacy_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'old.json'
            p.write_text(json.dumps({'versao':1,'largura':640,'altura':480,
                'sistema_coordenadas':'local da area capturada','anotacoes':samples()}), encoding='utf-8')
            self.assertEqual(len(load_project(p,640,480)),3)

    def test_dimension_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'old.gtwproj';save_project(p,samples(),640,480)
            with self.assertRaisesRegex(ValueError,'640 × 480'):load_project(p,1280,720)

    def test_corrupted_empty_and_unsupported(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.gtwproj'
            for data in (b'',b'not json',b'[]',b'{}'):
                p.write_bytes(data)
                with self.assertRaises(ValueError):load_project(p,640,480)
            p.write_text(json.dumps({'formato':PROJECT_FORMAT,'versao':2,
                'largura':640,'altura':480,'anotacoes':[]}), encoding='utf-8')
            with self.assertRaises(ValueError):load_project(p,640,480)

    def test_oversize(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'huge.gtwproj'
            with p.open('wb') as f:f.seek(8*1024*1024);f.write(b'0')
            with self.assertRaises(ValueError):load_project(p,640,480)

    def test_invalid_shapes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'shapes.gtwproj';data=project_document(samples(),640,480)
            data['anotacoes'][0]['pontos']=[5,5]
            p.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):load_project(p,640,480)

    def test_invalid_extension_and_dimension(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):save_project(Path(d)/'bad.json',[],640,480)
            with self.assertRaises(ValueError):project_document([],True,480)

    def test_existing_file_safe_when_invalid_data(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'good.gtwproj';save_project(p,samples(),640,480)
            original=p.read_bytes()
            with self.assertRaises(ValueError):save_project(p,[{'tipo':'errado'}],640,480)
            self.assertEqual(p.read_bytes(),original)

class HistoryTests(unittest.TestCase):
    def test_replace_undo_redo(self):
        h=AnnotationHistory();h.record(10);change=h.replace(10,11)
        self.assertEqual(change.hide,(10,));self.assertEqual(h.visible,{11})
        self.assertEqual(h.undo().show,(10,));self.assertEqual(h.visible,{10})
        self.assertEqual(h.redo().show,(11,));self.assertEqual(h.all_items,{10,11})

    def test_invalid_replace(self):
        h=AnnotationHistory();h.record(10)
        with self.assertRaises(ValueError):h.replace(10,10)
        with self.assertRaises(ValueError):h.replace(7,12)

    def test_replace_branch(self):
        h=AnnotationHistory();h.record(10);h.replace(10,11);h.undo()
        self.assertIn(11,h.record(12).delete)
        self.assertFalse(h.can_redo)

    def test_replace_erase_chain(self):
        h=AnnotationHistory();h.record(10);h.replace(10,11);h.erase([11])
        h.undo();self.assertEqual(h.visible,{11})
        h.undo();self.assertEqual(h.visible,{10})

class OverlayTests(unittest.TestCase):
    def overlay(self):
        o=StudioOverlay.__new__(StudioOverlay)
        o.bounds=CaptureBounds(0,0,640,480)
        o.canvas=MagicMock();o.parent=MagicMock();o.window=MagicMock()
        o.history=AnnotationHistory();o.font_sizes={};o.selected_text_id=None
        o.toolbar_window=None;o.toolbar_buttons={};o.selection_label=None
        o.anchor=None;o.active_item=None;o.active_tool=None;o.pending_erase=set()
        o.tool='Texto';o.color_name='Amarelo';o.stroke_width=4
        o.text_value='Nova nota';o.text_entry=None;o.drawing=True;o.visible=True
        o.on_tool_changed=None
        return o

    def test_import_replaces_old_annotations(self):
        o=self.overlay();o.history.record(99)
        ids=iter([101,102,103])
        o.canvas.create_line.side_effect=lambda *a,**kw:next(ids)
        o.canvas.create_rectangle.side_effect=lambda *a,**kw:next(ids)
        o.canvas.create_text.side_effect=lambda *a,**kw:next(ids)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.gtwproj';save_project(p,samples(),640,480)
            self.assertEqual(o.load_project(p),3)
            self.assertEqual(o.history.visible,{101,102,103})
            o.canvas.delete.assert_called_with(99)
            self.assertEqual(o.font_sizes,{103:24})

    def test_invalid_import_keeps_canvas(self):
        o=self.overlay();o.history.record(99)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.gtwproj';save_project(p,samples(),640,480)
            o.bounds=CaptureBounds(0,0,1280,720)
            with self.assertRaises(ValueError):o.load_project(p)
            o.canvas.delete.assert_not_called()
            self.assertEqual(o.history.visible,{99})

    def test_select_existing_text(self):
        o=self.overlay();o.history.record(17)
        o.canvas.find_overlapping.return_value=(17,)
        o.canvas.type.return_value='text';o.canvas.itemcget.return_value='Antes'
        o.text_entry=MagicMock()
        self.assertTrue(o._select_existing_text(11,12))
        self.assertEqual(o.selected_text_id,17)
        o.text_entry.insert.assert_called_once_with(0,'Antes')

    def test_update_text_and_undo(self):
        o=self.overlay();o.history.record(17);o.selected_text_id=17
        o.font_sizes[17]=24
        o.text_entry=MagicMock();o.text_entry.get.return_value='Depois'
        o.canvas.type.return_value='text'
        o.canvas.itemcget.side_effect=lambda _id,key:{'text':'Antes','fill':'#ffffff'}[key]
        o.canvas.coords.return_value=[22.,44.]
        o.canvas.create_text.return_value=18
        o.update_selected_text()
        self.assertEqual(o.history.visible,{18})
        self.assertEqual(o.font_sizes[18],24)
        o.history.undo();self.assertEqual(o.history.visible,{17})

    def test_click_on_text_does_not_duplicate(self):
        o=self.overlay();o.history.record(17)
        o.canvas.find_overlapping.return_value=(17,)
        o.canvas.type.return_value='text';o.canvas.itemcget.return_value='Antes'
        o._press(SimpleNamespace(x=9,y=17))
        o.canvas.create_text.assert_not_called()
        self.assertEqual(o.history.visible,{17})

if __name__=='__main__': unittest.main()
