import csv
import sys
import unittest
import tempfile
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import perler_delivery as p
import chart_release_gate as g

class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.palette=p.load_palette(p.PALETTE)
        self.rows=[['H3','H3','C12'],['H3','H3','C12'],['C12','H3','C12']]
        self.cnt,_,_,_=p.stats(self.rows,self.palette)
        self.csv=self.root/'matrix.csv';p.write_matrix(self.csv,self.rows)
        self.leg=self.root/'legend.csv';p.legend_csv(self.leg,self.cnt,self.palette)
    def tearDown(self):self.tmp.cleanup()
    def test_valid_grid_and_legend(self):
        im=p.render_customer(self.rows,self.palette,'Test',29,self.cnt,0,approved=False,readable=True)
        f=self.root/'chart.png';im.save(f)
        self.assertEqual(g.verify_background_pixels(f,self.rows,self.palette),9)
        self.assertEqual(len(g.checked_legend(self.leg,self.cnt,self.palette)),2)
    def test_corrupt_chart_pixel_detected(self):
        im=p.render_customer(self.rows,self.palette,'Test',29,self.cnt,0,approved=False,readable=True)
        f=self.root/'chart.png'
        cell=min(90,max(20,int(4290/3)));x=(4960-3*cell)//2;y=1030+(4310-3*cell)//2
        im.putpixel((x+7,y+7),(1,2,3));im.save(f)
        with self.assertRaises(p.PatternError):g.verify_background_pixels(f,self.rows,self.palette)
    def test_incorrect_legend_detected(self):
        with self.leg.open('r',encoding='utf-8-sig',newline='') as f:rows=list(csv.reader(f))
        rows[1][3]='1000'
        with self.leg.open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerows(rows)
        with self.assertRaises(p.PatternError):g.checked_legend(self.leg,self.cnt,self.palette)
    def test_missing_axis_in_csv_detected(self):
        self.csv.write_text('行\\列,1,3\n1,H3,H3\n2,C12,C12\n',encoding='utf8')
        with self.assertRaises(p.PatternError):p.read_matrix(self.csv)

if __name__=='__main__':unittest.main()
