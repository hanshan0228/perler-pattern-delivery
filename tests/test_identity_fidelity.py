"""Strict identity-review workflow tests; identity accuracy is never inferred from a hash."""
from __future__ import annotations
import numpy as np
import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import identity_fidelity as f
import perler_delivery as p


class IdentityFidelityTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name)
        self.original=self.root/'original.png'
        self.cartoon=self.root/'cartoon.png'
        self.bead=self.root/'bead.png'
        self.matrix=self.root/'matrix.csv'
        self.palette=self.root/'palette.json'
        self.prepared=self.root/'prepared'
        self.review=self.root/'review.json'
        self.attested=self.root/'attested.json'
        self.pal={'H19':'#FFEEDD','H16':'#331122','R22':'#776655'}
        self.rows=[['H19','H16','H19','R22'],['R22','H19','H16','H19'],
                   ['H16','H19','R22','H19'],['H19','H19','H16','H19']]
        self.palette.write_text(json.dumps(self.pal))
        p.write_matrix(self.matrix,self.rows)
        p.semantic_image(self.rows,self.pal).resize((40,40),Image.Resampling.NEAREST).save(self.bead)
        Image.new('RGB',(200,200),'#d1c9bb').save(self.original)
        Image.new('RGB',(200,200),'#cdb3aa').save(self.cartoon)

    def tearDown(self):self.t.cleanup()

    def run_prepare(self,**kwargs):
        arguments=dict(original=str(self.original),cartoon=str(self.cartoon),bead=str(self.bead),
                       matrix=str(self.matrix),palette=str(self.palette),out=str(self.prepared),
                       landmarks_original=None,landmarks_cartoon=None,landmarks_bead=None)
        arguments.update(kwargs)
        return f.prepare(argparse.Namespace(**arguments))

    def test_grid_16_of_16_verified(self):
        x=f.strict_grid_preview(self.matrix,self.palette,self.bead)
        self.assertEqual((x['cells_checked'],x['mismatched_cells'],x['beads']), (16,0,16))
        self.assertEqual(x['preview_scale'],10)

    def test_preview_tamper_fails_even_one_rgb_pixel(self):
        im=Image.open(self.bead).convert('RGBA');im.putpixel((0,0),(255,0,0,255));im.save(self.bead)
        with self.assertRaisesRegex(p.PatternError,'1 格'):
            f.strict_grid_preview(self.matrix,self.palette,self.bead)

    def test_wrong_matrix_code_fails(self):
        self.rows[0][0]='R22';p.write_matrix(self.matrix,self.rows)
        with self.assertRaises(p.PatternError):f.strict_grid_preview(self.matrix,self.palette,self.bead)

    def test_preparation_requires_actual_review_and_never_certifies_identity(self):
        self.run_prepare()
        info=f.read_json(self.prepared/'identity_report.json')
        self.assertEqual(info['status'],'REVIEW_REQUIRED')
        self.assertEqual(info['chart']['cells_checked'],16)
        self.assertEqual(info['geometry']['original_to_cartoon']['status'],'NOT_EVALUATED_LANDMARKS_MISSING')
        self.assertTrue((self.prepared/'three_stage_comparison.png').exists())
        review=f.read_json(self.prepared/'human_review_TEMPLATE.json')
        f.write_json(self.review,review)
        with self.assertRaisesRegex(p.PatternError,'人工审核'):
            f.evaluate(argparse.Namespace(prepared=str(self.prepared),review=str(self.review),out=str(self.attested)))
        self.assertFalse(self.attested.exists())

    def test_preparation_does_not_modify_existing_master(self):
        before=p.sha_file(self.matrix);self.run_prepare()
        self.assertEqual(before,p.sha_file(self.matrix))
        self.assertFalse((self.prepared/'master_manifest.json').exists())

    def test_review_sha_mismatch_rejected(self):
        self.run_prepare();review=f.read_json(self.prepared/'human_review_TEMPLATE.json')
        for key in f.REVIEW_CHECKS:review['checks'][key]=True
        review.update(user_confirmed=True,notes='Eyes, jaw, mouth, hairline and pose were independently checked against the source.')
        review['comparison_sha256']='bad';f.write_json(self.review,review)
        with self.assertRaisesRegex(p.PatternError,'不一致'):
            f.evaluate(argparse.Namespace(prepared=str(self.prepared),review=str(self.review),out=str(self.attested)))

    def test_real_user_approval_record_can_be_bound_without_fake_metric(self):
        self.run_prepare();review=f.read_json(self.prepared/'human_review_TEMPLATE.json')
        for key in f.REVIEW_CHECKS:review['checks'][key]=True
        review.update(user_confirmed=True,notes='Human reviewed left/right eyes, mouth, chin and hairstyle, and confirmed likeness.')
        f.write_json(self.review,review)
        f.evaluate(argparse.Namespace(prepared=str(self.prepared),review=str(self.review),out=str(self.attested)))
        info=f.read_json(self.attested)
        self.assertEqual(info['status'],'HUMAN_ATTESTED_NOT_AUTOMATICALLY_CERTIFIED')

    def test_changes_to_source_after_prepare_are_rejected(self):
        self.run_prepare()
        review=f.read_json(self.prepared/'human_review_TEMPLATE.json')
        review['checks']={x:True for x in f.REVIEW_CHECKS}
        review.update(user_confirmed=True,notes='Human reviewed facial geometry, hairstyle, expression, and identity stability.')
        f.write_json(self.review,review)
        Image.new('RGB',(200,200),'red').save(self.cartoon)
        with self.assertRaisesRegex(p.PatternError,'源图发生变化'):
            f.evaluate(argparse.Namespace(prepared=str(self.prepared),review=str(self.review),out=str(self.attested)))

    def test_freeze_reviewed_requires_real_palette_and_user_approval(self):
        real_palette=p.load_palette(p.PALETTE)
        codes=list(real_palette)[:3]
        self.palette.write_bytes(p.PALETTE.read_bytes())
        self.rows=[[codes[(x+y)%3] for x in range(4)] for y in range(4)]
        p.write_matrix(self.matrix,self.rows)
        p.semantic_image(self.rows,real_palette).resize((40,40),Image.Resampling.NEAREST).save(self.bead)
        self.run_prepare()
        info=f.read_json(self.prepared/'human_review_TEMPLATE.json')
        info['checks']={k:True for k in f.REVIEW_CHECKS}
        info.update(user_confirmed=True,notes='User confirmed eye spacing, nose, mouth, jaw, earrings, hair and shoulder pose.')
        f.write_json(self.review,info)
        f.evaluate(argparse.Namespace(prepared=str(self.prepared),review=str(self.review),out=str(self.attested)))
        master=self.root/'master'
        f.freeze_reviewed(argparse.Namespace(prepared=str(self.prepared),review=str(self.review),
            attested=str(self.attested),out=str(master),board=29,name='Approved'))
        meta,rows,_,counts,empty=p.read_master(master)
        self.assertEqual(rows,self.rows)
        self.assertTrue((master/'identity_review_provenance.json').exists())

    def test_freeze_reviewed_does_not_accept_unreviewed_chart(self):
        self.run_prepare()
        with self.assertRaises((FileNotFoundError, p.PatternError)):
            f.freeze_reviewed(argparse.Namespace(prepared=str(self.prepared),review=str(self.review),
                attested=str(self.attested),out=str(self.root/'master'),board=29,name='No'))
        self.assertFalse((self.root/'master').exists())

    def make_points(self,shape=(200,200),change=0):
        pts={'left_eye_outer':(0.32,0.38),'left_eye_inner':(0.4,0.38),
             'right_eye_inner':(0.60,0.38),'right_eye_outer':(0.68,0.38),
             'nose_tip':(0.52,0.57),'mouth_left':(0.40,0.72),
             'mouth_right':(0.61,0.72),'upper_lip':(0.50,0.70),
             'lower_lip':(0.50,0.75),'chin':(0.50,0.88),
             'forehead':(0.5,0.18),'left_cheek':(0.28,0.60),'right_cheek':(0.72,0.60)}
        if change:pts['mouth_left']=(0.4-change,0.72)
        return {k:list(v) for k,v in pts.items()}

    def test_same_geometric_landmarks_produce_zero_drift(self):
        a={k:__import__('numpy').array(v) for k,v in self.make_points().items()}
        g=f.geometry_compare(a,a,(200,200),(200,200),'original_to_cartoon')
        self.assertAlmostEqual(g['rmse'],0.0,places=5)
        self.assertFalse(g['screening_alert'])
        self.assertIn('not_identity_similarity',g['metric'])

    def test_geometric_landmark_change_is_detected(self):
        import numpy as np
        a={k:np.array(v) for k,v in self.make_points().items()}
        b={k:np.array(v) for k,v in self.make_points(change=0.19).items()}
        g=f.geometry_compare(a,b,(200,200),(200,200),'original_to_cartoon')
        self.assertGreater(g['rmse'],0.1)
        self.assertGreater(abs(g['feature_ratios']['mouth_width_over_eye_spacing']['relative_change']),0.15)

    def test_landmark_sha_staleness_rejected(self):
        pth=self.root/'landmarks.json'
        f.write_json(pth, {'schema':f.LANDMARK_SCHEMA,'source':'manual','face_count':1,
                           'image_sha256':'WRONG','points':self.make_points()})
        with self.assertRaisesRegex(p.PatternError,'哈希不匹配'):
            f.read_landmarks(pth,p.sha_file(self.original))

    def test_prepared_geometry_from_actual_hash_bound_files(self):
        origlm=self.root/'orig_lm.json';cartlm=self.root/'cart_lm.json'
        for img,loc in [(self.original,origlm),(self.cartoon,cartlm)]:
            f.write_json(loc,{'schema':f.LANDMARK_SCHEMA,'source':'manual','face_count':1,
                              'image_sha256':p.sha_file(img),'points':self.make_points()})
        self.run_prepare(landmarks_original=str(origlm),landmarks_cartoon=str(cartlm))
        data=f.read_json(self.prepared/'identity_report.json')
        self.assertEqual(data['geometry']['original_to_cartoon']['rmse'],0)
        self.assertEqual(data['geometry']['cartoon_to_bead']['status'],'NOT_EVALUATED_LANDMARKS_MISSING')


class ResolutionBudgetTests(unittest.TestCase):
    def test_missing_landmarks_never_invents_a_score(self):
        result = f.pixel_resolution_budget(None, 87, 87)
        self.assertEqual(result['status'], 'NOT_EVALUATED_LANDMARKS_MISSING')
        self.assertNotIn('similarity', result)

    def test_tiny_faces_warn_with_real_bead_units(self):
        base = {k: [0.5, 0.5] for k in f.INDICES}
        for k,x in [('left_eye_outer',0.47), ('left_eye_inner',0.48),
                    ('right_eye_inner',0.52), ('right_eye_outer',0.53),
                    ('mouth_left',0.48), ('mouth_right',0.52),
                    ('left_cheek',0.44), ('right_cheek',0.56)]:
            base[k] = [x, 0.5]
        base['forehead'] = [0.5,0.43]
        base['chin'] = [0.5,0.57]
        budget = f.pixel_resolution_budget({k: np.array(v) for k,v in base.items()},87,87)
        self.assertEqual(budget['status'], 'HEURISTIC_SCREEN_ONLY')
        self.assertTrue(budget['warnings'])
        self.assertLess(budget['features']['eye_center_spacing_beads'],7)

    def test_larger_faces_have_more_bead_detail(self):
        base = {k: np.array([0.5,0.5]) for k in f.INDICES}
        for k,x in [('left_eye_outer',0.33),('left_eye_inner',0.37),
                    ('right_eye_inner',0.63),('right_eye_outer',0.67),
                    ('mouth_left',0.45),('mouth_right',0.55),
                    ('left_cheek',0.31),('right_cheek',0.69)]:
            base[k] = np.array([x,0.5])
        base['forehead'] = np.array([0.5,0.30])
        base['chin'] = np.array([0.5,0.75])
        budget = f.pixel_resolution_budget(base,87,87)
        self.assertEqual(budget['warnings'],[])
        self.assertGreaterEqual(budget['features']['mouth_width_beads'],4)


if __name__=='__main__':unittest.main()
