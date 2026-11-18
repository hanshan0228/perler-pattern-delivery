"""v2.5 candidate quality: deterministic palette budget and local detail protection."""
import argparse
import tempfile
import unittest
from pathlib import Path
import sys
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import portrait_quality as q
import first_sheet as f
import perler_delivery as p


class PortraitQualityTests(unittest.TestCase):
    def setUp(self):
        self.pal={'a':'#808080','b':'#828282','c':'#E5AD91','d':'#181515','e':'#AC634E'}
        self.data=np.full((9,9,3),129.,dtype=float)
        self.data[2:7,2:7]=[225,172,150]
        self.data[3,3:5]=[24,21,21]
        self.data[5,4:6]=[172,99,78]

    def test_direct_palette_budget_and_determinism(self):
        baseline=[['a']*9 for _ in range(9)]
        a=q.optimize(self.data,4,self.pal,baseline,[(.2,.2,.8,.8)])
        self.assertEqual(a,q.optimize(self.data,4,self.pal,baseline,[(.2,.2,.8,.8)]))
        self.assertEqual((len(a),len(a[0])),(9,9));self.assertLessEqual(len({x for r in a for x in r}),4)
        self.assertTrue(all(x in self.pal for r in a for x in r))

    def test_weighted_objective_not_worse_before_cleanup(self):
        baseline=[['a']*9 for _ in range(9)]
        roi=[(.2,.2,.8,.8)]
        a=q.optimize(self.data,4,self.pal,baseline,roi)
        self.assertLessEqual(q.metrics(self.data,a,self.pal,roi)['weighted_rms_delta_e76'],q.metrics(self.data,baseline,self.pal,roi)['weighted_rms_delta_e76'])

    def test_focus_validated_and_weighted(self):
        mask=q.focus_mask(10,[(.2,.3,.6,.7)]);self.assertEqual(int(mask.sum()),16)
        with self.assertRaises(p.PatternError):q.focus_mask(9,[(.8,0,.1,1)])
        w,_=q.weights(self.data,[(0,0,1,1)]);plain,_=q.weights(self.data,[])
        np.testing.assert_allclose(w,3*plain)

    def test_low_contrast_singleton_cleanup_and_focus_protection(self):
        data=np.full((7,7,3),129.)
        rows=[['a']*7 for _ in range(7)];rows[3][3]='b'
        original=[r[:] for r in rows]
        clean,count=q.conservative_cleanup(data,rows,self.pal)
        self.assertEqual(count,1);self.assertEqual(clean[3][3],'a');self.assertEqual(rows,original)
        clean,count=q.conservative_cleanup(data,rows,self.pal,[(.4,.4,.6,.6)])
        self.assertEqual(count,0);self.assertEqual(clean,original)

    def test_high_contrast_eye_like_cell_is_not_removed(self):
        data=np.full((7,7,3),129.);data[3,3]=[24,21,21]
        rows=[['a']*7 for _ in range(7)];rows[3][3]='d'
        out,count=q.conservative_cleanup(data,rows,self.pal)
        self.assertEqual(count,0);self.assertEqual(out,rows)

    def test_prepare_three_candidates_and_metric_tamper(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=root/'src.png';Image.fromarray(self.data.astype('uint8')).save(source)
            out=root/'prepared'
            f.prepare(argparse.Namespace(image=str(source),mode='photo',cartoon_image=None,grid=9,colors=7,out=str(out),focus=[(.2,.2,.8,.8)]))
            meta=f.load(out/'prepare.json');self.assertEqual(set(meta['variants']),{'detail','flat','portrait','regional','coherent'})
            for v in f.VARIANTS:f.verified_variant(out,v)
            meta['quality_metrics']['portrait']['focus_mean_delta_e76']=-1;f.dump(out/'prepare.json',meta)
            with self.assertRaisesRegex(p.PatternError,'quality metrics'):f.verified_variant(out,'portrait')


if __name__=='__main__':unittest.main()
