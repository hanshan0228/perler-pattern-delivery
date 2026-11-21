from __future__ import annotations
import argparse
import json
import tempfile
import unittest
from pathlib import Path
import sys

from PIL import Image, ImageDraw

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'scripts'))
import identity_candidate_pipeline as cp
import identity_fidelity as idf
import perler_delivery as pd


class IdentityCandidatePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.p=Path(self.temp.name)
        self.src=self.p/'original.png'
        im=Image.new('RGB',(90,130),'#b7c8e2');d=ImageDraw.Draw(im)
        d.ellipse((26,20,72,86),fill='#efc6ae');im.save(self.src)
        self.palette=BASE/'assets/mard_palette.json'
        self.pal=pd.load_palette(self.palette)
        self.rows=[['A1' if i%3==0 else 'B4' if i%3==1 else 'C3' for i in range(29)] for _ in range(29)]
        self.matrix1=self.p/'one.csv';self.matrix2=self.p/'two.csv'
        pd.write_matrix(self.matrix1,self.rows)
        pd.write_matrix(self.matrix2,[row[::-1] for row in self.rows])
        self.bead1=self.p/'bead1.png';self.bead2=self.p/'bead2.png'
        pd.semantic_image(self.rows,self.pal).save(self.bead1)
        pd.semantic_image([r[::-1] for r in self.rows],self.pal).save(self.bead2)
        self.cartoon1=self.p/'cartoon1.png';self.cartoon2=self.p/'cartoon2.png'
        a=im.copy();ImageDraw.Draw(a).rectangle((30,60,43,69),fill='#b66f88');a.save(self.cartoon1)
        b=im.copy();ImageDraw.Draw(b).rectangle((35,60,50,72),fill='#ab5f73');b.save(self.cartoon2)

    def tearDown(self):self.temp.cleanup()

    def _frame_args(self,out=None,**kwargs):
        d=dict(image=str(self.src),out=str(out or self.p/'frame'),face=[.25,.16,.8,.70],
               landmarks=None,grid=87,target_face_height=.53,face_x=.5,face_y=.43,size=512)
        d.update(kwargs)
        return argparse.Namespace(**d)

    def _manifest(self,override=None):
        d={'schema':cp.SCHEMA_COMPARE,'original':str(self.src),'palette':str(self.palette),
           'original_face':[.25,.16,.8,.7],
           'candidates':[
               {'name':'loose','cartoon':str(self.cartoon1),'matrix':str(self.matrix1),
                'preview':str(self.bead1),'face_box':[.25,.16,.8,.7]},
               {'name':'close','cartoon':str(self.cartoon2),'matrix':str(self.matrix2),
                'preview':str(self.bead2),'face_box':[.25,.16,.8,.7]}
            ]}
        if override:override(d)
        path=self.p/'manifest.json';cp.write_json(path,d)
        return path

    def test_face_first_crop_contains_full_face(self):
        box=[.25,.16,.8,.7]
        g=cp.frame_geometry((90,130),box,.53)
        roi=g['face_box_on_output']
        self.assertTrue(all(0<=x<=1 for x in roi))
        self.assertGreaterEqual(roi[2],roi[0]+.2)
        self.assertGreaterEqual(g['face_height_fraction'],.25)

    def test_frame_prepare_and_rebuild_verification(self):
        args=self._frame_args()
        cp.frame_prepare(args)
        cp.frame_verify(Path(args.out))
        with Image.open(Path(args.out)/'face_first_frame.png') as im:self.assertEqual(im.size,(512,512))

    def test_tamper_frame_rejected_even_rehashed(self):
        args=self._frame_args();cp.frame_prepare(args)
        target=Path(args.out)/'face_first_frame.png'
        with Image.open(target) as im:
            im=im.copy();im.putpixel((44,43),(1,2,3));im.save(target)
        r=cp.load_json(Path(args.out)/'frame_report.json')
        r['output_hashes']['face_first_frame.png']=pd.sha_file(target)
        cp.write_json(Path(args.out)/'frame_report.json',r)
        with self.assertRaises(pd.PatternError):cp.frame_verify(Path(args.out))

    def test_face_box_invalid_rejected(self):
        for b in [[.8,.2,.3,.6],[-.1,.0,.5,.6],[.2,.2,.23,.5]]:
            with self.assertRaises(pd.PatternError):cp.validate_box(b)

    def test_compare_two_valid_real_grids(self):
        m=self._manifest();out=self.p/'comp';cp.compare_prepare(argparse.Namespace(manifest=str(m),out=str(out)))
        r=cp.compare_verify(out)
        self.assertEqual(len(r['entries']),2)
        self.assertEqual(r['grid_size'],[29,29])
        self.assertEqual(r['entries'][0]['grid_validation']['cells_checked'],841)
        tmpl=cp.load_json(out/'human_selection_TEMPLATE.json')
        self.assertFalse(tmpl['user_confirmed'])

    def test_compare_tampered_matrix_rejected(self):
        m=self._manifest();out=self.p/'comp';cp.compare_prepare(argparse.Namespace(manifest=str(m),out=str(out)))
        rows=pd.read_matrix(self.matrix2);rows[0][0]='A1' if rows[0][0]!='A1' else 'B4';pd.write_matrix(self.matrix2,rows)
        with self.assertRaises(pd.PatternError):cp.compare_verify(out)

    def test_compare_tampered_preview_rejected_even_with_rehash(self):
        m=self._manifest();out=self.p/'comp';cp.compare_prepare(argparse.Namespace(manifest=str(m),out=str(out)))
        pic=out/'candidate_comparison.png'
        with Image.open(pic) as im:
            im=im.copy();im.putpixel((1,1),(0,0,0));im.save(pic)
        r=cp.load_json(out/'comparison_report.json');r['comparison_sha256']=pd.sha_file(pic)
        cp.write_json(out/'comparison_report.json',r)
        with self.assertRaises(pd.PatternError):cp.compare_verify(out)

    def test_compare_duplicate_art_rejected(self):
        m=self._manifest(lambda d:d['candidates'][1].update(cartoon=str(self.cartoon1)))
        with self.assertRaises(pd.PatternError):cp.collect_candidates(m)

    def test_compare_same_grid_required(self):
        small=[r[:28] for r in self.rows[:28]]
        pd.write_matrix(self.matrix2,small);pd.semantic_image(small,self.pal).save(self.bead2)
        m=self._manifest()
        with self.assertRaises(pd.PatternError):cp.collect_candidates(m)

    def test_compare_missing_face_roi_not_approved(self):
        m=self._manifest(lambda d:(d.pop('original_face'),d['candidates'][0].pop('face_box')))
        report=cp.collect_candidates(m)
        self.assertIsNone(report['original_face_box'])
        self.assertIsNone(report['entries'][0]['face_box'])

    def test_reject_wrong_palette(self):
        p=self.p/'wrong.json';d=dict(self.pal);d['A1']='#000000' if d['A1']!='#000000' else '#FFFFFF';p.write_text(json.dumps(d))
        m=self._manifest(lambda data:data.update(palette=str(p)))
        with self.assertRaises(pd.PatternError):cp.collect_candidates(m)

    def test_reject_original_as_cartoon(self):
        m=self._manifest(lambda d:d['candidates'][1].update(cartoon=str(self.src)))
        with self.assertRaises(pd.PatternError):cp.collect_candidates(m)


if __name__=='__main__':unittest.main()
