"""Regression tests for fictitious grid labels, swatches and rehashed image tampering."""
import argparse
import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import Mock, patch
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import perler_delivery as p
import first_sheet as f

class RenderingContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.palette=p.load_palette(p.PALETTE)
    def tearDown(self): self.tmp.cleanup()

    def test_axes_all_four_edges_include_49_50_51_and_55_56_57(self):
        draw=Mock();p.axis_labels(draw,100,200,58,58,40)
        entries=[(call.args[0],call.args[1]) for call in draw.text.call_args_list]
        self.assertEqual(len(entries),4*58)
        for i in range(1,59):
            self.assertIn(((100+(i-.5)*40,175),str(i)),entries)
            self.assertIn(((100+(i-.5)*40,200+58*40+25),str(i)),entries)
            self.assertIn(((75,200+(i-.5)*40),str(i)),entries)
            self.assertIn(((100+58*40+25,200+(i-.5)*40),str(i)),entries)

    def test_grid_text_and_swatches_match_every_cell(self):
        rows=[['A1','H7','EMPTY'],['B3','C3','G1']]
        actual_draw=ImageDraw.Draw; text_calls=[]
        class Recording:
            def __init__(self,*a,**k): self.inner=actual_draw(*a,**k)
            def __getattr__(self,name): return getattr(self.inner,name)
            def text(self,xy,label,*a,**k):
                text_calls.append((xy,label));return self.inner.text(xy,label,*a,**k)
        with patch.object(p.ImageDraw,'Draw',Recording):
            im=p.render_grid(rows,self.palette,cell=42)
        self.assertEqual([label for _,label in text_calls[:6]],['A1','H7','×','B3','C3','G1'])
        for y,row in enumerate(rows):
            for x,code in enumerate(row):
                self.assertEqual(im.getpixel((42+x*42+4,42+y*42+4)),p.rgb(p.fill_for(code,self.palette)))

    def test_reject_missing_column_56_and_wrong_row_90(self):
        path=self.root/'bad.csv';rows=[['H7']*58 for _ in range(58)];p.write_matrix(path,rows)
        lines=path.read_text(encoding='utf-8-sig').splitlines()
        orig=list(lines);lines[0]=lines[0].replace(',55,56,57,',',55,57,')
        path.write_text('\n'.join(lines),encoding='utf8')
        with self.assertRaises(p.PatternError):p.read_matrix(path)
        lines=orig;lines[50]='90,'+lines[50].split(',',1)[1];path.write_text('\n'.join(lines),encoding='utf8')
        with self.assertRaises(p.PatternError):p.read_matrix(path)

    def first_sheet(self):
        source=self.root/'source.png';im=Image.new('RGB',(50,50),'#eeeeee');d=ImageDraw.Draw(im);d.ellipse((8,8,42,45),fill='#261d21');im.save(source)
        prepared=self.root/'prepare';sheet=self.root/'sheet'
        f.prepare(argparse.Namespace(image=str(source),mode='photo',cartoon_image=None,grid=8,colors=8,out=str(prepared)))
        review=f.load(prepared/'visual_review_TEMPLATE.json');review['checks']={k:True for k in f.PHOTO_CHECKS};review['notes']='Synthetic test fixture, not a production visual assessment.'
        reviewpath=self.root/'review.json';f.dump(reviewpath,review)
        f.select(argparse.Namespace(prepared=str(prepared),variant='detail',review=str(reviewpath),out=str(sheet),name='Test portrait'))
        return prepared,sheet

    def test_realistic_sheet_uses_photo_without_cartoon_and_verifies_pdf(self):
        prepared,sheet=self.first_sheet();meta=f.load(sheet/'candidate_validation.json')
        self.assertEqual(meta['mode'],'photo');self.assertTrue((prepared/'photo_stage.png').exists())
        self.assertTrue((sheet/'candidate_sheet_A2.pdf').exists())
        self.assertFalse((sheet/p.MANIFEST_NAME).exists())
        self.assertEqual(meta['beads'],64)
        f.verify(argparse.Namespace(prepared=str(prepared),sheet=str(sheet)))

    def test_rehashed_wrong_chart_and_pdf_rejected(self):
        prepared,sheet=self.first_sheet();args=argparse.Namespace(prepared=str(prepared),sheet=str(sheet))
        mpath=sheet/'candidate_validation.json';meta=f.load(mpath)
        for name in ['candidate_sheet.png','pattern_with_codes.png','candidate_sheet_A2.pdf']:
            with self.subTest(name=name):
                path=sheet/name;original=path.read_bytes()
                if name.endswith('.png'):
                    with Image.open(path) as im:
                        bad=im.copy()
                    ImageDraw.Draw(bad).rectangle((0,0,250,250),fill='#f00');bad.save(path)
                else:path.write_bytes(b'%PDF-1.4\ninvalid replacement')
                meta['files'][name]=p.sha_file(path);f.dump(mpath,meta)
                with self.assertRaises(p.PatternError):f.verify(args)
                path.write_bytes(original);meta['files'][name]=p.sha_file(path);f.dump(mpath,meta)

    def test_rehashed_wrong_palette_blocked(self):
        source=self.root/'source.png';im=Image.new('RGB',(20,20),'#eeeeee');ImageDraw.Draw(im).rectangle((5,5,15,15),fill='#000');im.save(source)
        prepared=self.root/'prepare';f.prepare(argparse.Namespace(image=str(source),mode='photo',cartoon_image=None,grid=8,colors=5,out=str(prepared)))
        palpath=prepared/'palette.json';pal=f.load(palpath);pal['A1']='#000000';f.dump(palpath,pal)
        mp=prepared/'prepare.json';meta=f.load(mp);meta['palette_sha256']=p.sha_file(palpath);f.dump(mp,meta)
        with self.assertRaises(p.PatternError):f.verified_variant(prepared,'detail')

    def test_modified_approved_sheet_rehashed_rejected(self):
        src=self.root/'source.csv';p.write_matrix(src,[['H7','H19'],['A1','B3']]);master=self.root/'master';delivery=self.root/'delivery'
        p.freeze(argparse.Namespace(matrix=str(src),out=str(master),name='Test',board=29));p.deliver(argparse.Namespace(master=str(master),out=str(delivery)))
        path=delivery/'customer_sheet.png'
        with Image.open(path) as im: bad=im.copy()
        ImageDraw.Draw(bad).rectangle((0,0,100,100),fill='#000');bad.save(path)
        vp=delivery/'validation.json';meta=f.load(vp);meta['files_sha256'][path.name]=p.sha_file(path);f.dump(vp,meta)
        with self.assertRaisesRegex(p.PatternError,'重新渲染'):p.verify_master_delivery(master,delivery)

if __name__=='__main__':unittest.main()
