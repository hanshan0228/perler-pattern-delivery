"""v2.2 regression tests: real cartoon candidate and immutable delivery contract."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import perler_delivery as m
from cartoon_pipeline import cartoonize, open_rgb
from candidate_processing import cleanup, sample_pixel_art


class CartoonModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.palette=m.load_palette(m.PALETTE)

    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.p=Path(self.t.name)
        self.source=self.p/'original.png'
        art=Image.new('RGB',(140,140),'#f7ede6')
        d=ImageDraw.Draw(art)
        d.ellipse((22,18,110,130),fill='#352c38')
        d.ellipse((36,32,96,115),fill='#e8b796')
        d.ellipse((48,61,56,66),fill='#332633')
        d.ellipse((76,61,84,66),fill='#332633')
        d.arc((55,72,82,97),10,170,fill='#8a3a4e',width=3)
        # Photographic texture ensures even poster style performs an actual simplification.
        a=np.asarray(art).copy().astype(np.int16)
        yy,xx=np.indices(a.shape[:2]); jitter=((xx*7+yy*11)%17-8)[:,:,None]
        art=Image.fromarray(np.uint8(np.clip(a+jitter,0,255)),'RGB')
        art.save(self.source)

    def tearDown(self): self.t.cleanup()

    def _cli(self,*args,success=True):
        result=subprocess.run([sys.executable,str(ROOT/'scripts'/'perler_delivery.py'),*map(str,args)],capture_output=True,text=True,timeout=120)
        if success and result.returncode:
            self.fail(result.stdout+'\n'+result.stderr)
        if not success:
            self.assertNotEqual(result.returncode,0)
        return result

    def test_all_offline_styles_produce_visual_changes(self):
        original=open_rgb(self.source)
        for style in ('soft','comic','poster'):
            with self.subTest(style=style):
                output=cartoonize(original,style)
                self.assertEqual(output.mode,'RGB')
                self.assertEqual(output.size,original.size)
                self.assertGreater(np.mean(np.abs(np.asarray(output,dtype=np.int16)-np.asarray(original,dtype=np.int16))),0.1)

    def test_cartoon_cli_outputs_real_matrix_and_stage(self):
        out=self.p/'cartoon'
        self._cli('generate','--image',self.source,'--mode','cartoon','--grid',29,'--colors',15,'--filter','medium','--out',out)
        info=json.loads((out/'candidate_info.json').read_text())
        rows=m.read_matrix(out/'candidate_matrix.csv')
        counts,empty,w,h=m.stats(rows,self.palette)
        self.assertEqual((w,h,empty),(29,29,0))
        self.assertLessEqual(len(counts),15)
        self.assertEqual(info['mode'],'cartoon')
        self.assertEqual(info['cartoon_engine'],'offline')
        self.assertEqual(info['cartoon_stage_sha256'],m.sha_file(out/'cartoon_stage.png'))
        self.assertNotEqual((out/'cartoon_stage.png').read_bytes(),self.source.read_bytes())
        self.assertTrue((out/'candidate_preview.png').is_file())
        self.assertTrue((out/'candidate_codes.png').is_file())

    def test_cartoon_external_image_requires_explicit_file(self):
        bad=self._cli('generate','--image',self.source,'--mode','cartoon','--cartoon-engine','external',
                      '--out',self.p/'bad',success=False)
        self.assertIn('cartoon-image',bad.stderr)
        self.assertFalse((self.p/'bad').exists())
        ext=self.p/'external.png'
        Image.new('RGB',(140,140),'#ff78a4').save(ext)
        out=self.p/'external_result'
        self._cli('generate','--image',self.source,'--mode','cartoon','--cartoon-engine','external',
                  '--cartoon-image',ext,'--grid',29,'--colors',9,'--out',out)
        meta=json.loads((out/'candidate_info.json').read_text())
        self.assertEqual(meta['external_image_sha256'],m.sha_file(ext))
        self.assertEqual(meta['cartoon_engine'],'external')
        self.assertTrue((out/'cartoon_stage.png').exists())

    def test_pixel_mode_keeps_single_cell_colors_despite_grid_lines(self):
        grid=5; cell=8
        colors=[(200,30,70),(20,200,70),(30,80,220),(235,200,15),(230,230,230)]
        im=Image.new('RGB',(grid*cell,grid*cell),'white')
        d=ImageDraw.Draw(im)
        for y in range(grid):
            for x in range(grid):
                col=colors[(x+2*y)%len(colors)]
                d.rectangle((x*cell,y*cell,(x+1)*cell-1,(y+1)*cell-1),fill=col)
        for i in range(0,grid*cell,cell):
            d.line((i,0,i,grid*cell-1),fill='black',width=1)
            d.line((0,i,grid*cell-1,i),fill='black',width=1)
        sampled,alignment=sample_pixel_art(im,grid=5,pixel_cell=8,origin_x=0,origin_y=0)
        self.assertEqual(sampled.shape,(5,5,3))
        self.assertTrue(np.allclose(sampled[1,3],colors[(3+2*1)%len(colors)]))
        path=self.p/'pixel.png';im.save(path)
        out=self.p/'pixel_result'
        self._cli('import-pixel','--image',path,'--grid',5,'--pixel-cell',8,
                  '--pixel-origin-x',0,'--pixel-origin-y',0,'--colors',5,'--out',out)
        meta=json.loads((out/'candidate_info.json').read_text())
        self.assertEqual(meta['mode'],'pixel')
        self.assertEqual(meta['pixel_alignment']['sampling'],'central_median_no_BOX')

    def test_cleanup_is_non_destructive_and_off_by_default(self):
        matrix=[['H7','H7','H7'],['H7','E5','H7'],['H7','H7','H7']]
        baseline=[r[:] for r in matrix]
        untouched,report=cleanup(matrix,strength='none')
        self.assertEqual(untouched,baseline)
        self.assertEqual(report['modified_cells'],0)
        changed,report2=cleanup(matrix,strength='high')
        self.assertEqual(matrix,baseline)
        self.assertGreaterEqual(report2['modified_cells'],1)
        self.assertEqual(changed[1][1],'H7')

    def test_legacy_approved_master_is_never_modified_by_generation(self):
        approved=ROOT/'examples'/'approved_87x87.csv'
        digest_before=m.digest_codes(m.read_matrix(approved))
        out=self.p/'cartoon'
        self._cli('generate','--image',self.source,'--mode','cartoon',
                  '--grid',29,'--colors',10,'--out',out)
        self.assertEqual(digest_before,m.digest_codes(m.read_matrix(approved)))
        self.assertEqual(digest_before,'8c7bcbb1ad12ac1257b38c89496b1924f93fb40cc06a50c7859d1d2b201e6fc5')

    def test_cartoon_end_to_end_freeze_delivery_verify(self):
        candidate=self.p/'candidate'
        master=self.p/'master'
        delivery=self.p/'delivery'
        self._cli('generate','--image',self.source,'--mode','cartoon','--grid',29,'--colors',9,'--out',candidate)
        self._cli('freeze','--matrix',candidate/'candidate_matrix.csv','--out',master,'--name','CartoonTest')
        self._cli('deliver','--master',master,'--out',delivery)
        self._cli('verify','--master',master,'--delivery',delivery)
        mtime=(master/'master_matrix.csv').stat().st_mtime_ns
        self.assertEqual((master/'master_matrix.csv').stat().st_mtime_ns,mtime)
        self._cli('generate','--image',self.source,'--mode','cartoon','--grid',29,'--colors',9,
                  '--out',candidate,success=False)


if __name__=='__main__': unittest.main()
