"""Run: python -m unittest discover -s tests -v"""
from __future__ import annotations
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('perler_delivery',ROOT/'scripts'/'perler_delivery.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class PerlerDeliveryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pal=m.load_palette(ROOT/'assets'/'mard_palette.json')

    def test_palette_has_291_reference_colors(self):
        self.assertEqual(len(self.pal),291)
        self.assertEqual(self.pal['H7'],'#000000')
        self.assertEqual(self.pal['H19'],'#F6EFE2')

    def test_user_approved_regression_matrices(self):
        expected = {
            58:(20,3364,"316307e8157a1086fbe5af9691a163c0859d8d0099ffd9e1ce097173d56c9c3f"),
            87:(33,7569,"8c7bcbb1ad12ac1257b38c89496b1924f93fb40cc06a50c7859d1d2b201e6fc5"),
        }
        for dim,(num_colors,num_beads,digest) in expected.items():
            rows=m.read_matrix(ROOT/'examples'/f'approved_{dim}x{dim}.csv')
            counts,empty,w,h=m.stats(rows,self.pal)
            self.assertEqual((w,h,len(counts),sum(counts.values()),empty),(dim,dim,num_colors,num_beads,0))
            self.assertEqual(m.digest_codes(rows),digest)

    def test_one_cell_one_color_and_empty_is_transparent(self):
        matrix=[['H7','H19'],['EMPTY','E4']]
        rgba=m.semantic_image(matrix,self.pal)
        self.assertEqual(rgba.size,(2,2))
        self.assertEqual(rgba.getpixel((0,0)),(0,0,0,255))
        self.assertEqual(rgba.getpixel((0,1)),(0,0,0,0))
        self.assertEqual(rgba.getpixel((1,1)),(*m.rgb(self.pal['E4']),255))
        counts,empty,w,h=m.stats(matrix,self.pal)
        self.assertEqual((w,h,len(counts),empty,sum(counts.values())),(2,2,3,1,3))

    def test_strict_csv_roundtrip(self):
        matrix=[['H7','H19','H7'],['E4','EMPTY','P9']]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'m.csv'
            m.write_matrix(p,matrix)
            self.assertEqual(matrix,m.read_matrix(p))

    def test_reject_corrupted_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.csv'
            p.write_text('行\\列,1,2\n1,H7,E4\n3,H7,E4\n',encoding='utf8')
            with self.assertRaises(m.PatternError): m.read_matrix(p)

    def test_reject_bad_width_and_unknown_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.csv'
            p.write_text('H7,E4\nH7\n',encoding='utf8')
            with self.assertRaises(m.PatternError): m.read_matrix(p)
        with self.assertRaises(m.PatternError): m.stats([['INVALID']],self.pal)

    def test_json_editor_project_null_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'proj.json'
            p.write_text(json.dumps({'grid':[['H7',None],['E4','P9']]}),encoding='utf8')
            self.assertEqual(m.read_matrix(p),[['H7','EMPTY'],['E4','P9']])

    def test_board_partition_uses_each_cell_once(self):
        matrix=[[f'R{i:02d}C{j:02d}' for j in range(7)] for i in range(5)]
        pieces=m.boards(matrix,3)
        self.assertEqual(len(pieces),6)
        original={code for row in matrix for code in row}
        flat=[code for _,_,_,_,rows in pieces for row in rows for code in row]
        self.assertEqual(set(flat),original)
        self.assertEqual(len(flat),len(original))

    def test_master_lock_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            src=tmp/'source.csv'
            m.write_matrix(src,[['H7','H19'],['E4','P9']])
            dest=tmp/'master'
            args=type('Args',(),{'matrix':str(src),'out':str(dest),'name':'Test','board':29})
            m.freeze(args)
            self.assertEqual(m.read_master(dest)[0]['beads'],4)
            with self.assertRaises(m.PatternError): m.freeze(args)
            with (dest/'master_matrix.csv').open('a',encoding='utf8') as f: f.write('\n')
            with self.assertRaises(m.PatternError): m.read_master(dest)

    def test_photo_conversion_candidate_with_valid_palette(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            p=tmp/'input.png'
            Image.new('RGB',(30,30),(245,140,190)).save(p)
            rows=m.quantize_photo(p,7,3,self.pal)
            self.assertEqual(len(rows),7)
            self.assertEqual(len(rows[0]),7)
            self.assertTrue(all(cd in self.pal for row in rows for cd in row))

if __name__=='__main__': unittest.main()
