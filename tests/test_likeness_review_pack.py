from __future__ import annotations

import argparse
import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import likeness_review_pack as lr
import identity_fidelity as idf
import perler_delivery as pd


class LikenessReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.d=Path(self.temp.name)
        pal=pd.load_palette(pd.PALETTE)
        self.codes=list(pal)[:5]
        self.rows=[[self.codes[(r+c)%5] for c in range(11)] for r in range(11)]
        self.matrix=self.d/'matrix.csv';pd.write_matrix(self.matrix,self.rows)
        self.palette=self.d/'palette.json';shutil.copyfile(pd.PALETTE,self.palette)
        self.bead=self.d/'bead.png';pd.semantic_image(self.rows,pal).resize((121,121),Image.Resampling.NEAREST).save(self.bead)
        self.original=self.d/'original.png';self.cartoon=self.d/'cartoon.png'
        Image.new('RGB',(180,240),'#aad5ec').save(self.original)
        Image.new('RGB',(180,240),'#ffdbec').save(self.cartoon)
        self.p=self.d/'prepared'
        self.kwargs=dict(original=str(self.original),cartoon=str(self.cartoon),bead=str(self.bead),
            matrix=str(self.matrix),palette=str(self.palette),out=str(self.p),
            face_original=[0.18,0.12,0.82,0.71],face_cartoon=[0.18,0.12,0.82,0.71],
            face_bead=[0.18,0.12,0.82,0.71],
            landmarks_original=None,landmarks_cartoon=None,landmarks_bead=None)

    def tearDown(self):self.temp.cleanup()

    def run_prepare(self, **kw):
        self.kwargs.update(kw)
        return lr.prepare(argparse.Namespace(**self.kwargs))

    def test_prepared_files_and_exact_thumbnails(self):
        self.run_prepare()
        r=lr.verify(self.p)
        self.assertEqual(r['chart']['cells_checked'],121)
        self.assertEqual(r['chart']['mismatched_cells'],0)
        self.assertEqual(r['face_crop_status'],'READY_FOR_MANUAL_COMPARISON')
        self.assertEqual(set(r['outputs']),{'likeness_review.png','bead_view_1x.png','bead_view_2x.png','bead_view_4x.png'})
        with Image.open(self.p/'bead_view_1x.png') as im:self.assertEqual(im.size,(11,11))

    def test_missing_box_is_not_fake_pass(self):
        self.run_prepare(face_bead=None)
        r=lr.verify(self.p)
        self.assertEqual(r['face_crop_status'],'NOT_EVALUATED_MISSING_FACE_BOXES')
        review=self.p/'user_review_TEMPLATE.json'
        with self.assertRaisesRegex(pd.PatternError,'缺少全部三张'):
            lr.attest(argparse.Namespace(prepared=str(self.p),review=str(review),out=str(self.d/'att.json')))

    def test_invalid_box_rejected_before_output(self):
        with self.assertRaisesRegex(pd.PatternError,'脸矩形太小'):
            self.run_prepare(face_original=[0.1,0.1,0.11,0.70])
        self.assertFalse(self.p.exists())

    def test_tampered_bead_fails_on_prepare(self):
        with Image.open(self.bead) as im:
            a=im.convert('RGBA');a.putpixel((0,0),(11,25,32,255));a.save(self.bead)
        with self.assertRaises(pd.PatternError):self.run_prepare()
        self.assertFalse(self.p.exists())

    def test_tampered_actual_original_rejected(self):
        self.run_prepare()
        Image.new('RGB',(180,240),'#000000').save(self.original)
        with self.assertRaisesRegex(pd.PatternError,'original 文件已发生变化'):
            lr.verify(self.p)

    def test_tampered_montage_rejected_even_after_rehash(self):
        self.run_prepare()
        path=self.p/'likeness_review.png'
        with Image.open(path) as im:
            changed=im.copy();changed.putpixel((50,50),(255,0,0));changed.save(path)
        info=idf.read_json(self.p/'likeness_report.json')
        info['outputs']['likeness_review.png']=pd.sha_file(path)
        idf.write_json(self.p/'likeness_report.json',info)
        with self.assertRaisesRegex(pd.PatternError,'无法从已绑定'):
            lr.verify(self.p)

    def test_preview_tamper_rejected_even_after_rehash(self):
        self.run_prepare()
        path=self.p/'bead_view_2x.png'
        with Image.open(path) as im:
            changed=im.copy();changed.putpixel((0,0),(255,0,0,255));changed.save(path)
        info=idf.read_json(self.p/'likeness_report.json')
        info['outputs'][path.name]=pd.sha_file(path)
        idf.write_json(self.p/'likeness_report.json',info)
        with self.assertRaisesRegex(pd.PatternError,'不符合真实矩阵'):
            lr.verify(self.p)

    def test_no_auto_approval_unreviewed(self):
        self.run_prepare()
        review=self.p/'user_review_TEMPLATE.json'
        with self.assertRaisesRegex(pd.PatternError,'未经完整人工检查'):
            lr.attest(argparse.Namespace(prepared=str(self.p),review=str(review),out=str(self.d/'att.json')))
        self.assertFalse((self.d/'att.json').exists())

    def test_attestation_explicit_review_only(self):
        self.run_prepare()
        review=idf.read_json(self.p/'user_review_TEMPLATE.json')
        review['stage_A_original_to_cartoon']={k:True for k in lr.REVIEW_A}
        review['stage_B_cartoon_to_bead']={k:True for k in lr.REVIEW_B}
        review['small_preview_reviewed']=True
        review['user_confirmed']=True
        review['notes_original_to_cartoon']='Human synthetic fixture review: geometry and expression visually inspected.'
        review['notes_cartoon_to_bead']='Human synthetic fixture review: bead eye, lips, small preview inspected.'
        rfile=self.d/'review.json';idf.write_json(rfile,review)
        target=self.d/'att.json'
        lr.attest(argparse.Namespace(prepared=str(self.p),review=str(rfile),out=str(target)))
        att=idf.read_json(target)
        self.assertEqual(att['status'],'HUMAN_ATTESTATION_RECORDED_NOT_BIOMETRIC_VERIFICATION')

    def test_landmarks_bound_to_source_image_sha(self):
        self.run_prepare()
        bad=idf.read_json(self.p/'likeness_report.json')
        self.assertIsNone(bad['landmark_paths']['original'])
        landmark=self.d/'landmark.json'
        idf.write_json(landmark,{'schema':idf.LANDMARK_SCHEMA,'source':'manual','face_count':1,
                                 'image_sha256':'invalid','points':{}})
        other=self.d/'other'
        with self.assertRaisesRegex(pd.PatternError,'哈希不匹配'):
            lr.prepare(argparse.Namespace(**{**self.kwargs,'out':str(other),
                        'face_original':None,'landmarks_original':str(landmark)}))


if __name__=='__main__':unittest.main()
