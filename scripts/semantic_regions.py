"""Optional offline MediaPipe SelfieMulticlass adapter for reviewed bead masks.

Official class order: background, hair, body-skin, face-skin, clothes, others.
No automatic model downloads, image uploads, identity inference, or fallback.
The network is optional; confidence projection is independently testable.
"""
from __future__ import annotations
import re
from pathlib import Path
import numpy as np
from PIL import Image
import perler_delivery as p

MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite'
CLASS_NAMES = ('background','hair','body-skin','face-skin','clothes','others')
ALIASES = ({'background'}, {'hair'}, {'bodyskin','body'}, {'faceskin','face'}, {'clothes','clothing'}, {'others','other','accessories','othersaccessories'})
# Exact v2.8 editor IDs; face/body skin merge; accessories default to protect.
EDITOR_IDS = np.array([4,2,1,1,3,5],dtype=np.uint8)

def require(ok,msg):
    if not ok: raise p.PatternError(msg)

def check_model(path,expected_sha):
    path=Path(path)
    require(isinstance(expected_sha,str) and bool(re.fullmatch(r'[0-9a-fA-F]{64}',expected_sha)), 'provide the SHA-256 of your explicitly selected local model with --model-sha256')
    require(path.is_file() and path.stat().st_size>8,'local model missing or empty; see references/SEMANTIC_REGIONS.md')
    actual=p.sha_file(path)
    require(actual==expected_sha.lower(),'model SHA-256 mismatch')
    with path.open('rb') as file: header=file.read(8)
    require(header[4:8]==b'TFL3','expected a TensorFlow Lite model, not HTML or a different file type')
    return actual

def check_labels(labels):
    if labels:
        norm=[re.sub(r'[^a-z]','',str(x).lower()) for x in labels]
        require(len(norm)==6 and all(v in ALIASES[i] for i,v in enumerate(norm)), 'model labels do not match the official six-class selfie model')

def confidence_mask_to_2d(mask):
    """Normalize MediaPipe confidence-mask numpy views across API versions.

    MediaPipe 0.10.35 may expose H×W×1 rather than H×W.  Only a trailing
    singleton channel is accepted: indiscriminate squeeze can hide malformed
    masks or produce unexpectedly shaped arrays.  Always detach the result
    from the segmenter's native buffers before its context closes.
    """
    a = np.asarray(mask.numpy_view(), dtype=np.float32)
    if a.ndim == 3 and a.shape[-1] == 1:
        a = a[:, :, 0]
    require(a.ndim == 2 and a.shape[0] >= 2 and a.shape[1] >= 2,
            f'expected confidence mask (H, W) or (H, W, 1), got {a.shape}')
    return np.array(a, dtype=np.float32, copy=True)


def infer(stage,model,expected_sha):
    """Run MediaPipe CPU inference on the exact padded stage. No cloud calls."""
    sha=check_model(model,expected_sha)
    try: import mediapipe as mp
    except ImportError as exc: raise p.PatternError('MediaPipe not installed; install requirements-semantic.txt in a supported Python environment') from exc
    try:
        options=mp.tasks.vision.ImageSegmenterOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(Path(model).resolve())),running_mode=mp.tasks.vision.RunningMode.IMAGE,output_confidence_masks=True,output_category_mask=False)
        with mp.tasks.vision.ImageSegmenter.create_from_options(options) as segmenter:
            model_labels=getattr(segmenter,'labels',None)
            check_labels(model_labels)
            result=segmenter.segment(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(np.asarray(stage.convert('RGB')))))
            require(result.confidence_masks is not None and len(result.confidence_masks)==6,'expected exactly six model confidence maps')
            maps=np.stack([confidence_mask_to_2d(m) for m in result.confidence_masks])
    except p.PatternError: raise
    except (RuntimeError,ValueError,AttributeError,TypeError,OSError) as exc: raise p.PatternError(f'MediaPipe inference failed: {exc}') from exc
    require(p.sha_file(Path(model))==sha,'model file changed during inference')
    return maps,{'engine':'mediapipe-selfie-multiclass','model_sha256':sha,'mediapipe_version':str(getattr(mp,'__version__','unknown')),'class_order':list(CLASS_NAMES),'labels_metadata_checked':bool(model_labels)}

def _mean_grid(channel,n):
    # Floating-point BOX is area averaging; resize only confidence, never bead labels.
    return np.asarray(Image.fromarray(np.asarray(channel,dtype=np.float32)).resize((n,n),Image.Resampling.BOX),dtype=np.float32)

def project(stage,maps,n,*,min_confidence=.70,min_margin=.15,min_coverage=.70):
    """Project class probabilities to whole bead cells; abstain on ambiguous cells.

    Coverage measures the fraction of source-mask samples won by the selected
    category. Protect confident accessories and strong visible face edges.
    Thresholds are engineering heuristics, not calibrated model accuracy.
    """
    require(type(n) is int and 1<=n<=145,'grid 1..145')
    require(stage.width==stage.height,'semantic mask requires exact padded square stage')
    for name,val in [('confidence',min_confidence),('margin',min_margin),('coverage',min_coverage)]:
        require(isinstance(val,(int,float)) and np.isfinite(val) and 0<=val<=1,f'invalid {name} threshold')
    a=np.asarray(maps,dtype=np.float32)
    require(a.ndim==3 and a.shape[0]==6 and a.shape[1]==a.shape[2] and 2<=a.shape[1]<=4096,'expect six square confidence maps')
    require(np.isfinite(a).all() and np.min(a)>=-1e-6 and np.max(a)<=1+1e-6,'invalid confidence values (expected finite 0..1)')
    a=np.clip(a,0,1)
    # Refuse undersampled masks rather than imply unobserved spatial precision.
    require(n<=a.shape[1],'confidence mask resolution is below requested bead grid')
    probs=np.stack([_mean_grid(ch,n) for ch in a]); winner=probs.argmax(0)
    peak=np.take_along_axis(probs,winner[None],axis=0)[0]
    margin=peak-np.partition(probs,-2,axis=0)[-2]
    raw=a.argmax(0); coverage=np.stack([_mean_grid((raw==i).astype(np.float32),n) for i in range(6)])
    agreement=np.take_along_axis(coverage,winner[None],axis=0)[0]
    confident=(peak>=min_confidence)&(margin>=min_margin)&(agreement>=min_coverage)
    labels=np.zeros((n,n),np.uint8);labels[confident]=EDITOR_IDS[winner[confident]]
    # Model does not distinguish eyes or lips. Extra *heuristic* protection of
    # strong edges inside reasonably face-supported cells, not a landmark detector.
    import first_sheet as f
    import portrait_quality as q
    data=f.samples(stage,n,'flat');_,edges=q.weights(data)
    face_support=(probs[3]>=.45)&((winner==3)|(winner==5))
    strong=face_support&(edges>=12)
    # Dilate by one cell, clipped to face support, to protect thin features.
    expanded=strong.copy()
    expanded[1:]|=strong[:-1];expanded[:-1]|=strong[1:];expanded[:,1:]|=strong[:,:-1];expanded[:,:-1]|=strong[:,1:]
    protection=expanded&face_support
    labels[protection]=5
    return labels,{'confidence_threshold':float(min_confidence),'margin_threshold':float(min_margin),'coverage_threshold':float(min_coverage),'model_mask_shape':list(a.shape),'confidence_pass_cells':int(confident.sum()),'unknown_cells':int((labels==0).sum()),'accessory_protect_cells':int((confident&(winner==5)).sum()),'face_edge_protect_cells':int(protection.sum()),'method_note':'six neural classes plus heuristic face-edge protection; not landmark detection or certified segmentation'}
