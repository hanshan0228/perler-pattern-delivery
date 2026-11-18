import argparse,json,sys,tempfile,unittest
from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import perler_delivery as p
import region_finish as r
import print_contract as pc
import first_sheet as f

class RegionFinishTests(unittest.TestCase):
    def setUp(self):
        self.pal=p.load_palette(p.PALETTE)
        self.regions=[{'kind':'skin','polygon':[[0,0],[1,0],[1,1],[0,1]]},{'kind':'protect','polygon':[[0,0],[.25,0],[.25,.25],[0,.25]]}]
    def test_warm_region_and_fixed_coordinates(self):
        data=np.full((8,8,3),[225.,175.,150.]);rows=[['H4']*8 for _ in range(8)];rows[0][0]='H7';before=[row[:] for row in rows]
        out,rep=r.optimize(data,rows,self.pal,self.regions,max_colors=8)
        self.assertEqual(rows,before);self.assertEqual(rep['after']['warm_skin_violations'],0);self.assertEqual(rep['protected_changes'],0);self.assertLessEqual(rep['after']['colors'],8)
        self.assertEqual(out,r.optimize(data,rows,self.pal,self.regions,max_colors=8)[0]);self.assertEqual(out[0][0],'H7')
    def test_insufficient_budget_protected_fails(self):
        data=np.full((4,4,3),[225.,175.,150.]);rows=[['H4','H7']*2 for _ in range(4)];regs=[{'kind':'protect','polygon':[[0,0],[1,0],[1,1],[0,1]]}]
        with self.assertRaises(p.PatternError):r.optimize(data,rows,self.pal,regs,max_colors=1)
    def test_invalid_regions(self):
        with self.assertRaises(p.PatternError):r.masks(8,[{'kind':'skin','polygon':[[0,0],[1.1,0],[1,1]]}])
    def test_full_palette_contrast(self):
        for bg in self.pal.values():
            a,b=sorted([p.luminance(bg),p.luminance(p.contrast_ink(bg))]);self.assertGreaterEqual((b+.05)/(a+.05),4.5)
    def test_board_render_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=[['H4','H7'],['A1','EMPTY']];pc.make_boards(root,rows,self.pal)
            self.assertEqual({x.relative_to(root).as_posix() for x in root.rglob('*') if x.is_file()},pc.board_paths(rows));pc.verify_boards(root,rows,self.pal)
            im=Image.open(root/'boards/board_01_color.png');im.putpixel((50,50),(1,2,3));im.save(root/'boards/board_01_color.png')
            with self.assertRaises(p.PatternError):pc.verify_boards(root,rows,self.pal)
    def test_regional_prepare_recomputation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'source.png';im=Image.new('RGB',(40,40),'#e1af96');ImageDraw.Draw(im).rectangle((4,4,12,12),fill='#33252a');im.save(src)
            reg=root/'regions.json';reg.write_text(json.dumps(self.regions));out=root/'prepared'
            f.prepare(argparse.Namespace(image=str(src),mode='photo',cartoon_image=None,grid=8,colors=10,out=str(out),regions=str(reg),finish_colors=8))
            meta,rows,_,_,_=f.verified_variant(out,'finish');self.assertLessEqual(len(set(sum(rows,[]))),8)
            meta['finish_report']['modified_cells']+=1;f.dump(out/'prepare.json',meta)
            with self.assertRaisesRegex(p.PatternError,'region finish'):f.verified_variant(out,'finish')
if __name__=='__main__':unittest.main()
