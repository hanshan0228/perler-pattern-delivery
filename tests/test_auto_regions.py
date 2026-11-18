import argparse,json,sys,tempfile,unittest
from pathlib import Path
from PIL import Image
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import auto_regions as a
import tone_quality as t
import region_finish as r
import first_sheet as f
import perler_delivery as p

class AutoRegionTests(unittest.TestCase):
    def setUp(self):
        self.pal=p.load_palette(p.PALETTE)
        self.stage=Image.new('RGB',(40,40),'#dfb098')
        self.stage.paste('#29212c',(0,0,10,40))
        self.stage.paste('#fffff0',(25,28,40,40))
        self.labels=np.zeros((8,8),np.uint8);self.labels[1:7,1:6]=1;self.labels[2,3]=5
    def test_proposal_shape_repeatability(self):
        x,m=a.propose(self.stage,16,[.2,.1,.8,.8]);y,_=a.propose(self.stage,16,[.2,.1,.8,.8]);self.assertEqual(x.shape,(16,16));self.assertTrue(np.array_equal(x,y));self.assertTrue((x==0).any());self.assertTrue((x==1).any())
    def test_unknown_when_no_skin_seed(self):
        x,m=a.propose(Image.new('RGB',(24,24),'#333333'),8,[0,0,1,1]);self.assertFalse(x.any());self.assertIn('reason',m)
    def test_exact_roundtrip_and_invalid_mask(self):
        with tempfile.TemporaryDirectory() as d:
            pth=Path(d)/'x.png';a.color_image(self.labels).save(pth);self.assertTrue(np.array_equal(a.read_mask(pth,8),self.labels))
            m=r.masks(8,a.spec(self.labels));self.assertTrue(np.array_equal(m['skin'],self.labels==1));self.assertTrue(np.array_equal(m['protect'],self.labels==5))
            im=Image.open(pth);im.putpixel((0,0),(1,2,3));im.save(pth)
            with self.assertRaises(p.PatternError):a.read_mask(pth,8)
    def test_exact_stage_review_and_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);stage=base/'stage.png';self.stage.save(stage);root=base/'review';a.propose_cli(argparse.Namespace(stage=str(stage),out=str(root),grid=8,manual=True,face=None));mask=base/'m.png';a.color_image(self.labels).save(mask);out=base/'plan.json';a.accept(argparse.Namespace(proposal=str(root),mask=str(mask),notes='Checked source face and shoulder boundaries manually.',out=str(out)))
            plan=a.load_plan(out,self.stage,8);self.assertEqual(plan['regions'],a.spec(self.labels));self.assertTrue((root/'mask_editor.html').is_file())
            with self.assertRaises(p.PatternError):a.load_plan(out,Image.new('RGB',(40,40),'white'),8)
            with self.assertRaises(p.PatternError):a.load_plan(out,self.stage,9)
            plan['regions'][0]['runs'].append(plan['regions'][0]['runs'][0])
            with self.assertRaises(p.PatternError):a.verify_plan(plan,self.stage,8)
    def test_tone_invariants_repeatable(self):
        data=f.samples(self.stage,8,'flat');regions=a.spec(self.labels);base=[['H4' if (x+y)%2 else 'H7' for x in range(8)] for y in range(8)];before=[row[:] for row in base];out,rep=t.refine(data,base,self.pal,regions);self.assertEqual(base,before);self.assertEqual(out,t.refine(data,base,self.pal,regions)[0]);self.assertEqual(set(sum(base,[])),set(sum(out,[])));self.assertEqual(rep['fixed_changes'],0)
        self.assertLessEqual(rep['after']['skin_luma_step_error'],rep['before']['skin_luma_step_error']);self.assertLessEqual(rep['after']['skin_chroma_step_error'],rep['before']['skin_chroma_step_error']);self.assertEqual(out[2][3],base[2][3])
    def test_plan_pipeline_recomputes_tone_and_rejects_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'src.png';self.stage.save(src);plan=root/'plan.json';f.dump(plan,{'schema':a.SCHEMA,'grid':8,'stage_digest':a.stage_digest(self.stage),'regions':a.spec(self.labels),'review_notes':'Visually checked skin and distinctive protected feature.','status':'REGION_REVIEWED_NOT_CUSTOMER_APPROVED'});prepared=root/'prepared'
            f.prepare(argparse.Namespace(image=str(src),mode='photo',cartoon_image=None,grid=8,colors=10,out=str(prepared),region_plan=str(plan),finish_colors=8));meta,rows,_,_,_=f.verified_variant(prepared,'tone');self.assertEqual(set(meta['variants']),set(f.ALL_VARIANTS));self.assertLessEqual(len(set(sum(rows,[]))),8)
            meta['tone_report']['modified_cells']+=1;f.dump(prepared/'prepare.json',meta)
            with self.assertRaisesRegex(p.PatternError,'tone refinement'):f.verified_variant(prepared,'tone')
if __name__=='__main__':unittest.main()
