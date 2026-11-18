from __future__ import annotations
import argparse
import json
import tempfile
import unittest
from pathlib import Path
import sys
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import first_sheet as f
import perler_delivery as p

class FirstSheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name)
        self.original=self.dir/'original.png';self.art=self.dir/'cartoon.png'
        Image.new('RGB',(90,120),'#faf3e0').save(self.original)
        im=Image.new('RGB',(90,120),'#faf3e0');d=ImageDraw.Draw(im);d.ellipse((12,5,80,100),fill='#e7b1a0',outline='#3a222a',width=3);d.rectangle((25,36,31,43),fill='#3a222a');d.rectangle((56,36,62,43),fill='#3a222a');d.arc((36,53,53,75),0,180,fill='#d14e68',width=4);im.save(self.art)
        self.root=self.dir/'prepared';self.sheet=self.dir/'sheet'
    def tearDown(self): self.tmp.cleanup()
    def prepare(self):
        f.prepare(argparse.Namespace(image=str(self.original),cartoon_image=str(self.art),out=str(self.root),grid=29,colors=12))
    def review(self,passed=True):
        r=f.load(self.root/'visual_review_TEMPLATE.json');r['checks']={k:passed for k in f.CHECKS};r['notes']='Synthetic test fixture: face, eyes, mouth, and silhouette checked independently.';path=self.dir/'review.json';f.dump(path,r);return path
    def select(self,review):
        f.select(argparse.Namespace(prepared=str(self.root),out=str(self.sheet),variant='detail',review=str(review),name='Test'))
    def test_fit_no_crop(self):
        a=Image.new('RGB',(20,30),'red');b=f.fit_square(a);self.assertEqual(b.size,(30,30));self.assertEqual(b.getpixel((5,0)),(255,0,0));self.assertEqual(b.getpixel((24,29)),(255,0,0))
    def test_prepare_requires_real_file(self):
        with self.assertRaises(p.PatternError):f.prepare(argparse.Namespace(image=str(self.original),cartoon_image=str(self.original),out=str(self.root),grid=29,colors=12))
        self.assertFalse(self.root.exists())
    def test_unreviewed_draft_is_blocked(self):
        self.prepare()
        with self.assertRaises(p.PatternError):self.select(self.review(False))
        self.assertFalse(self.sheet.exists())
    def test_review_must_match_candidate_digest(self):
        self.prepare();rev=self.review();r=f.load(rev);r['codes_sha256']='wrong';f.dump(rev,r)
        with self.assertRaises(p.PatternError):self.select(rev)
    def test_two_variants_exact_grid_and_palette(self):
        self.prepare()
        for v in f.VARIANTS:
            m,rows,pal,counts,empty=f.verified_variant(self.root,v);self.assertEqual(sum(counts.values()),29**2);self.assertLessEqual(len(counts),12);self.assertEqual(empty,0)
    def test_verified_first_sheet_and_tamper(self):
        self.prepare();self.select(self.review());args=argparse.Namespace(prepared=str(self.root),sheet=str(self.sheet));f.verify(args)
        m=f.load(self.sheet/'candidate_validation.json');self.assertEqual(m['status'],'UNAPPROVED');self.assertFalse((self.sheet/'master_manifest.json').exists());self.assertTrue((self.sheet/'candidate_sheet.png').is_file())
        (self.sheet/'legend.csv').write_text('tampered')
        with self.assertRaises(p.PatternError):f.verify(args)
    def test_tampered_source_preview_blocks_selection(self):
        self.prepare();(self.root/'detail'/'candidate_preview.png').write_bytes(b'invalid')
        with self.assertRaises(p.PatternError):self.select(self.review())

if __name__=='__main__':unittest.main()
