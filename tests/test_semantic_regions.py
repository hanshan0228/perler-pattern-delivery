"""Probability projection, source binding and mocked adapter tests.
Set PERLER_SELFIE_MODEL and PERLER_SELFIE_SHA256 to opt into real inference.
Synthetic or mocked maps are NOT evidence of actual neural segmentation quality.
"""
import argparse, hashlib, json, os, sys, tempfile, types, unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import semantic_regions as s
import auto_regions as a
import perler_delivery as p

class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.stage=Image.new('RGB',(32,32),'#dfb098')
        self.maps=np.zeros((6,32,32),np.float32)
        for i in range(6):self.maps[i,:,i*5:(i+1)*5]=.95
        self.maps[0,:,30:]=.95
    def test_map_classes_exact_and_accessories_are_protected(self):
        labels,rep=s.project(self.stage,self.maps,32)
        self.assertEqual(labels.shape,(32,32));self.assertEqual([int(labels[8,i*5+2]) for i in range(6)],[4,2,1,1,3,5]);self.assertEqual(rep['accessory_protect_cells'],160)
    def test_abstains_on_low_confidence_and_ties(self):
        maps=np.zeros((6,32,32),np.float32);maps[3]=.49;maps[2]=.49
        labels,rep=s.project(self.stage,maps,8);self.assertFalse(labels.any());self.assertEqual(rep['unknown_cells'],64)
    def test_mixed_boundary_rejected_even_with_high_mean(self):
        maps=np.zeros((6,8,8),np.float32);maps[0,:,:5]=1;maps[1,:,5:]=1
        result,_=s.project(self.stage,maps,2,min_confidence=.5,min_margin=.1,min_coverage=.8)
        self.assertTrue(np.all(result[:,0]==4));self.assertTrue(np.all(result[:,1]==0))
    def test_invalid_nan_shape_and_too_low_resolution(self):
        for maps,n in [(self.maps[:5],8),(np.full((6,32,32),np.nan),8),(self.maps[:,:,:30],8),(self.maps,33),(self.maps*2,8)]:
            with self.subTest(n=n,shape=maps.shape),self.assertRaises(p.PatternError):s.project(self.stage,maps,n)
    def test_model_file_verification_before_loading(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'model.tflite';path.write_bytes(b'1234TFL3fixture')
            sha=p.sha_file(path);self.assertEqual(s.check_model(path,sha),sha)
            with self.assertRaisesRegex(p.PatternError,'SHA-256 mismatch'):s.check_model(path,'0'*64)
            path.write_bytes(b'not a model file')
            with self.assertRaisesRegex(p.PatternError,'TensorFlow Lite'):s.check_model(path,p.sha_file(path))
            with self.assertRaises(p.PatternError):s.check_labels(['background','hair','clothes','face','body','others'])
    def test_mocked_mediapipe_inference_api(self):
        maps=self.maps
        class FakeSegmenter:
            labels=s.CLASS_NAMES
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def segment(self,image):return types.SimpleNamespace(confidence_masks=[types.SimpleNamespace(numpy_view=lambda c=c:c) for c in maps])
        mp=types.SimpleNamespace(__version__='mock-test',Image=lambda **kw:kw,ImageFormat=types.SimpleNamespace(SRGB=1),tasks=types.SimpleNamespace(BaseOptions=lambda **kw:kw,vision=types.SimpleNamespace(ImageSegmenterOptions=lambda **kw:kw,RunningMode=types.SimpleNamespace(IMAGE=1),ImageSegmenter=types.SimpleNamespace(create_from_options=lambda x:FakeSegmenter()))))
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/'x';model.write_bytes(b'1234TFL3mock')
            with patch.dict(sys.modules,{'mediapipe':mp}):result,meta=s.infer(self.stage,model,p.sha_file(model))
            self.assertTrue(np.array_equal(result,maps));self.assertEqual(meta['mediapipe_version'],'mock-test');self.assertTrue(meta['labels_metadata_checked'])
    def test_mediapipe_singleton_channel_confidence_maps(self):
        """Reproduces a real Windows MediaPipe 0.10.35 API shape (H, W, 1)."""
        classes = self.maps
        class FakeSegmenter:
            labels=s.CLASS_NAMES
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def segment(self,image):
                return types.SimpleNamespace(confidence_masks=[
                    types.SimpleNamespace(numpy_view=lambda c=c:c[:, :, None])
                    for c in classes])
        mp=types.SimpleNamespace(
            __version__='0.10.35',Image=lambda **kw:kw,
            ImageFormat=types.SimpleNamespace(SRGB=1),
            tasks=types.SimpleNamespace(BaseOptions=lambda **kw:kw,
                vision=types.SimpleNamespace(ImageSegmenterOptions=lambda **kw:kw,
                    RunningMode=types.SimpleNamespace(IMAGE=1),
                    ImageSegmenter=types.SimpleNamespace(create_from_options=lambda x:FakeSegmenter()))))
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/'model.tflite';model.write_bytes(b'1234TFL3mock')
            with patch.dict(sys.modules,{'mediapipe':mp}):
                maps,meta=s.infer(self.stage,model,p.sha_file(model))
        self.assertEqual(maps.shape,(6,32,32))
        self.assertTrue(np.array_equal(maps,self.maps))
        self.assertEqual(meta['mediapipe_version'],'0.10.35')
        projected,_=s.project(self.stage,maps,16)
        self.assertEqual(projected.shape,(16,16))

    def test_confidence_mask_shape_rejects_extra_channels(self):
        good=np.zeros((16,16,1),np.float32)
        class Mock:
            def __init__(self, a):self.arr=a
            def numpy_view(self):return self.arr
        self.assertEqual(s.confidence_mask_to_2d(Mock(good)).shape,(16,16))
        self.assertEqual(s.confidence_mask_to_2d(Mock(good[:,:,0])).shape,(16,16))
        for invalid in [np.zeros((16,16,2)),np.zeros((1,16,16)),np.zeros((16,16,1,1)),np.zeros((16,))]:
            with self.subTest(shape=invalid.shape),self.assertRaises(p.PatternError):
                s.confidence_mask_to_2d(Mock(invalid))

    def test_review_gate_and_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'source.png';self.stage.save(source);proposal=root/'proposal';plan=root/'plan.json'
            fake={'engine':'mediapipe-selfie-multiclass','model_sha256':'b'*64,'mediapipe_version':'mock-test','class_order':list(s.CLASS_NAMES)}
            args=argparse.Namespace(stage=str(source),grid=16,out=str(proposal),manual=False,face=None,model='unused',model_sha256='b'*64)
            with patch.object(s,'infer',return_value=(self.maps,fake)):a.propose_cli(args)
            self.assertEqual(json.loads((proposal/'proposal.json').read_text())['status'],'UNREVIEWED');self.assertTrue((proposal/'mask_editor.html').exists())
            with self.assertRaises(p.PatternError):a.accept(argparse.Namespace(proposal=str(proposal),mask=str(proposal/'proposed_mask.png'),notes='short',out=str(plan)))
            a.accept(argparse.Namespace(proposal=str(proposal),mask=str(proposal/'proposed_mask.png'),notes='Synthetic fixture reviewed; class order and region boundaries checked.',out=str(plan)))
            verified=a.load_plan(plan,self.stage,16);self.assertEqual(verified['proposal_provenance']['model_sha256'],'b'*64)
            with self.assertRaises(p.PatternError):a.load_plan(plan,Image.new('RGB',(32,32),'white'),16)
    def test_failed_neural_proposal_does_not_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'s.png';self.stage.save(src);out=root/'p'
            args=argparse.Namespace(stage=str(src),grid=16,out=str(out),manual=False,face=None,model='missing',model_sha256='a'*64)
            with self.assertRaises(p.PatternError):a.propose_cli(args)
            self.assertFalse(out.exists())
    @unittest.skipUnless(os.getenv('PERLER_SELFIE_MODEL') and os.getenv('PERLER_SELFIE_SHA256'),'real model weights/runtime not configured')
    def test_real_mediapipe_smoke(self):
        maps,meta=s.infer(self.stage,os.environ['PERLER_SELFIE_MODEL'],os.environ['PERLER_SELFIE_SHA256']);labels,report=s.project(self.stage,maps,16);self.assertEqual(labels.shape,(16,16));self.assertEqual(len(meta['class_order']),6)

if __name__=='__main__':unittest.main()
