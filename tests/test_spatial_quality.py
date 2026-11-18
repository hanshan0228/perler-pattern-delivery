"""Spatial/region optimization and same-budget regression tests."""
import argparse
import tempfile
import unittest
from pathlib import Path
import sys
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import portrait_quality as q
import spatial_quality as s
import first_sheet as f
import perler_delivery as p

class SpatialTests(unittest.TestCase):
    def setUp(self):
        self.palette={'a':'#808080','b':'#848484','c':'#262626','d':'#EEEEEE'}
        self.data=np.full((12,12,3),129.,dtype=float)
        self.data[8:,8:]=132.;self.data[5,5]=38
        self.rows=[['a']*12 for _ in range(12)]
        for y,x in ((1,1),(1,4),(3,3),(6,1),(9,2),(10,1)): self.rows[y][x]='b'
        for y in range(8,12):
            for x in range(8,12): self.rows[y][x]='b'
        self.rows[5][5]='c'
    def test_coherence_same_actual_palette_and_no_mutation(self):
        before=[r[:] for r in self.rows];out,report=s.regularize(self.data,self.rows,self.palette)
        self.assertTrue(report['accepted']);self.assertGreater(report['modified_cells'],0)
        self.assertEqual(set(np.array(out).ravel()),set(np.array(before).ravel()));self.assertEqual(self.rows,before)
        self.assertLess(report['result']['flat_region_transitions'],report['baseline']['flat_region_transitions'])
        self.assertEqual(out,s.regularize(self.data,self.rows,self.palette)[0])
    def test_focus_and_source_edges_unchanged(self):
        roi=[(0,0,.4,.4)];out,report=s.regularize(self.data,self.rows,self.palette,roi)
        _,edge=q.weights(self.data,roi);fixed=q.focus_mask(12,roi)|(edge>=12)
        np.testing.assert_array_equal(np.array(out)[fixed],np.array(self.rows)[fixed]);self.assertEqual(out[5][5],'c')
        self.assertEqual(report['protected_cells'],int(fixed.sum()))
    def test_error_caps(self):
        out,_=s.regularize(self.data,self.rows,self.palette);old=q.metrics(self.data,self.rows,self.palette);new=q.metrics(self.data,out,self.palette)
        self.assertLessEqual(new['mean_delta_e76'],old['mean_delta_e76']+.45)
        self.assertLessEqual(new['weighted_rms_delta_e76'],old['weighted_rms_delta_e76']+.4)
        self.assertLessEqual(new['isolated_cells_4neighbor'],old['isolated_cells_4neighbor'])
        src=p.srgb_lab(self.data);a=p.srgb_lab(np.array([[p.rgb(self.palette[c]) for c in r] for r in self.rows]));b=p.srgb_lab(np.array([[p.rgb(self.palette[c]) for c in r] for r in out]));self.assertTrue(np.all(np.linalg.norm(src-b,axis=-1)-np.linalg.norm(src-a,axis=-1)<=2.500001))
    def test_fully_protected_is_noop(self):
        out,report=s.regularize(self.data,self.rows,self.palette,[(0,0,1,1)])
        self.assertEqual(out,self.rows);self.assertFalse(report['accepted']);self.assertEqual(report['modified_cells'],0)
    def test_palette_refinement_actual_swap_and_guard(self):
        pal={'a':'#000000','b':'#CCCCCC','c':'#FFEEEE','d':'#FFFFFF'};data=np.full((8,8,3),255.);data[:4]=0
        rows=[['a' if y<4 else 'b']*8 for y in range(8)]
        out,r=s.refine_palette(data,rows,pal,[(0,.5,1,1)])
        self.assertGreater(len(r['swaps']),0);self.assertEqual(len(set(np.array(out).ravel())),2)
        self.assertLess(r['weighted_rms_after'],r['weighted_rms_before']);self.assertEqual(out,s.refine_palette(data,rows,pal,[(0,.5,1,1)])[0])
    def test_pareto_not_scalar_rank(self):
        a={'weighted_rms_delta_e76':1,'isolated_cells_4neighbor':4,'flat_region_transitions':4,'colors':4}
        b={**a,'weighted_rms_delta_e76':2,'isolated_cells_4neighbor':2}
        c={**a,'weighted_rms_delta_e76':2}
        self.assertEqual(s.pareto({'a':a,'b':b,'c':c}),['a','b'])
    def test_report_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);src=root/'src.png';Image.fromarray(self.data.astype('uint8')).save(src);out=root/'prepared'
            f.prepare(argparse.Namespace(image=str(src),mode='photo',cartoon_image=None,grid=12,colors=9,out=str(out),focus=[(0,0,.4,.4)]))
            meta=f.load(out/'prepare.json');f.verify_diagnostics(out,meta)
            original=meta['spatial_report']['modified_cells'];meta['spatial_report']['modified_cells']=original+1;f.dump(out/'prepare.json',meta)
            with self.assertRaisesRegex(p.PatternError,'spatial refinement'):f.verified_variant(out,'coherent')
            meta['spatial_report']['modified_cells']=original;meta['pareto_diagnostics']=['bogus'];f.dump(out/'prepare.json',meta)
            with self.assertRaisesRegex(p.PatternError,'Pareto diagnostics'):f.verify_diagnostics(out,meta)

if __name__=='__main__':unittest.main()
