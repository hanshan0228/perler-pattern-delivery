"""v2.8: real indexed semantic mask contract and opt-in pixel region refinement."""
from __future__ import annotations
import argparse
import tempfile
import json
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import semantic_masks as s
import perler_delivery as p
import first_sheet as f
import region_finish as r

class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.pal=p.load_palette(p.PALETTE)
    def tearDown(self): self.tmp.cleanup()

    def stage(self,n=70):
        # Synthetic portrait fixture with credible distinct hair, skin, clothes.
        im=Image.new('RGB',(n,n),'#66534e');d=ImageDraw.Draw(im)
        d.ellipse((7,1,n-9,n-10),fill='#19171e')
        d.ellipse((n//3,n//4,n*2//3,n*3//4),fill='#e6af99')
        d.rectangle((n//3, n*4//5, n*2//3,n),fill='#f6f2ef')
        return im

    def mask(self,n=70):
        mask=Image.new('L',(n,n),0);d=ImageDraw.Draw(mask)
        d.ellipse((7,1,n-9,n-10),fill=1)
        d.ellipse((n//3,n//4,n*2//3,n*3//4),fill=3)
        d.rectangle((n//3,n*4//5,n*2//3,n-1),fill=4)
        d.ellipse((n//2-2,n//2,n//2+2,n//2+3),fill=5)
        return mask

    def test_category_id_and_rgb_rejection(self):
        arr=np.array([[0,1,2],[3,4,5]],dtype=np.uint8)
        np.testing.assert_array_equal(s.validate(arr),arr)
        with self.assertRaises(p.PatternError):s.validate(np.array([[0,6]],dtype=np.uint8))
        with self.assertRaises(p.PatternError):s.validate(arr.astype(np.float32))
        path=self.root/'bad.png';self.mask(20).convert('RGB').save(path)
        with self.assertRaisesRegex(p.PatternError,'indexed'):s.load_indexed_png(path,(20,20))

    def test_downsample_uses_class_voting_not_rgb(self):
        arr=np.repeat(np.repeat(np.array([[1,3],[4,0]],np.uint8),10,axis=0),10,axis=1)
        got=s.to_grid(arr,2)
        np.testing.assert_array_equal(got,[[1,3],[4,0]])

    def test_dimensions_and_coverage_fail_closed(self):
        pth=self.root/'mask.png';self.mask(70).save(pth)
        with self.assertRaisesRegex(p.PatternError,'dimensions'):s.load_indexed_png(pth,(71,71))
        with self.assertRaisesRegex(p.PatternError,'insufficient'):s.check_coverage(np.zeros((29,29),np.uint8))
        with self.assertRaisesRegex(p.PatternError,'not found'):s.infer_with_mediapipe(self.stage(),self.root/'missing.tflite')

    def test_protects_all_accessories_and_semantic_boundaries(self):
        labels=s.to_grid(np.asarray(self.mask()),15)
        data=np.array(self.stage().resize((15,15),Image.Resampling.BOX),dtype=float)
        masks=s.masks_from_classes(labels,data)
        self.assertTrue(masks['protect'][labels==5].all())
        self.assertGreater(int(masks['protect'].sum()),0)
        self.assertTrue(np.all(masks['skin'] == np.isin(labels,[2,3])))

    def test_optimize_requires_one_label_source(self):
        labels=s.to_grid(np.asarray(self.mask()),15)
        im=self.stage().resize((15,15),Image.Resampling.BOX)
        data=np.asarray(im,dtype=float)
        rows=p.quantize_pixels(data,15,12,self.pal)
        out,report=r.optimize(data,rows,self.pal,None,max_colors=12,category_labels=labels)
        masks=s.masks_from_classes(labels,data)
        a=np.asarray(rows);b=np.asarray(out)
        self.assertTrue(np.array_equal(a[masks['protect']],b[masks['protect']]))
        self.assertEqual(report['source'],'semantic_multiclass')
        self.assertEqual(report['protected_changes'],0)
        with self.assertRaises(p.PatternError):r.optimize(data,rows,self.pal,None,max_colors=12)
        with self.assertRaises(p.PatternError):r.optimize(data,rows,self.pal,[{'kind':'skin','polygon':[[0,0],[1,0],[1,1]]}],max_colors=12,category_labels=labels)

    def prepared(self,grid=15):
        src=self.root/'original.png';self.stage().save(src)
        mask=self.root/'categories.png';self.mask().save(mask)
        output=self.root/'prepared'
        f.prepare(argparse.Namespace(image=str(src),mode='photo',cartoon_image=None,out=str(output),grid=grid,
             colors=16,regions=None,focus=None,finish_colors=16,segmentation_mask=str(mask),mediapipe_model=None))
        return output

    def test_first_sheet_import_actual_indexed_mask(self):
        output=self.prepared()
        meta=f.load(output/'prepare.json')
        self.assertEqual(meta['schema'],'first-sheet-v5')
        self.assertEqual(meta['segmentation']['origin'],'imported_indexed_mask')
        self.assertEqual(set(meta['variants']),set(f.ALL_VARIANTS))
        f.verify_diagnostics(output,meta)
        self.assertEqual(f.verified_variant(output,'finish')[0]['finish_report']['protected_changes'],0)
        with Image.open(output/'segmentation_cells.png') as im:self.assertEqual(im.size,(15,15))
        self.assertTrue((output/'segmentation_overlay.png').exists())

    def test_rehashed_grid_tampering_is_detected(self):
        output=self.prepared()
        c=output/'segmentation_cells.png'
        with Image.open(c) as im: arr=np.asarray(im).copy()
        arr[0,0]=5
        Image.fromarray(arr,'L').save(c)
        meta=f.load(output/'prepare.json')
        meta['segmentation']['cells_sha256']=p.sha_file(c)
        f.dump(output/'prepare.json',meta)
        with self.assertRaisesRegex(p.PatternError,'not derived'):f.verified_variant(output,'finish')

    def test_rehashed_overlay_tampering_is_detected(self):
        output=self.prepared()
        c=output/'segmentation_overlay.png'
        im=Image.open(c).convert('RGB');im.putpixel((3,3),(0,0,0));im.save(c)
        meta=f.load(output/'prepare.json')
        meta['segmentation']['overlay_sha256']=p.sha_file(c)
        f.dump(output/'prepare.json',meta)
        with self.assertRaises(p.PatternError):f.verified_variant(output,'finish')


    def test_visual_mask_review_cannot_be_skipped(self):
        output=self.prepared()
        meta=f.load(output/'prepare.json')
        review=f.load(output/'visual_review_TEMPLATE.json')
        review['checks']={k:True for k in f.checks_for('photo')}
        review['notes']='Synthetic fixture explicitly inspected source hair/face/clothes and indexed mask overlay.'
        with self.assertRaisesRegex(p.PatternError,'segmentation overlay'):
            f.review_ok(review,meta,'detail')
        review['segmentation_overlay_checked']=True
        f.review_ok(review,meta,'detail')

if __name__=='__main__':unittest.main()
