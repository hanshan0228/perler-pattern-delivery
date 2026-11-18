"""Optional semantic-region masks for UNAPPROVED portrait bead candidates.

Official MediaPipe SelfieMulticlass IDs: 0 background, 1 hair,
2 body-skin, 3 face-skin, 4 clothes, 5 others/accessories.

No model or image is downloaded or uploaded. Python MediaPipe and a locally
obtained multiclass .tflite/.task model are optional. A precomputed *indexed*
mask can be imported for offline reproducibility. Masks MUST align exactly with
the padded square stage; never silently warp/crop mismatched images.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import perler_delivery as p

CLASSES = ('background', 'hair', 'body_skin', 'face_skin', 'clothes', 'accessories')
COLORS = np.asarray([(66,63,74),(54,60,126),(253,176,117),(254,114,114),(90,194,188),(255,214,73)],dtype=np.uint8)


def validate(mask: np.ndarray, shape: tuple[int,int] | None=None) -> np.ndarray:
    a=np.asarray(mask)
    if a.ndim!=2 or a.dtype.kind not in 'uib' or a.size==0 or not np.all((a>=0)&(a<=5)):
        raise p.PatternError('segmentation category mask must be 2-D integer indices 0..5 (MediaPipe SelfieMulticlass)')
    if shape is not None and a.shape!=shape:
        raise p.PatternError(f'segmentation mask dimensions {a.shape} differ from padded stage {shape}; no auto alignment')
    return a.astype(np.uint8,copy=True)


def load_indexed_png(path: Path, shape: tuple[int,int]) -> np.ndarray:
    with Image.open(path) as im:
        if im.mode not in ('L','P'):
            raise p.PatternError('segmentation mask PNG must be grayscale/indexed class indices; RGB visualization is not a mask')
        values=np.asarray(im)
    return validate(values,shape)


def infer_with_mediapipe(stage:Image.Image, model_path:Path) -> np.ndarray:
    model_path=Path(model_path)
    if not model_path.is_file():
        raise p.PatternError('MediaPipe multiclass model not found locally; supply --segmentation-mask or install a licensed model')
    try:
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
    except (ImportError, AttributeError) as e:
        raise p.PatternError('MediaPipe not installed/compatible. Install mediapipe or import a verified indexed class mask') from e
    rgb=np.asarray(stage.convert('RGB'),dtype=np.uint8).copy()
    options=vision.ImageSegmenterOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.IMAGE,
        output_category_mask=True,
        output_confidence_masks=False)
    try:
        with vision.ImageSegmenter.create_from_options(options) as segmenter:
            result=segmenter.segment(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb))
            if result.category_mask is None:
                raise p.PatternError('MediaPipe model produced no category mask')
            a=result.category_mask.numpy_view().copy()
    except p.PatternError:
        raise
    except Exception as e:
        raise p.PatternError('MediaPipe segmentation inference failed; check model type and version') from e
    return validate(a,(stage.height,stage.width))


def to_grid(mask: np.ndarray, grid: int) -> np.ndarray:
    """Central-3/5 per cell categorical mode; never resample labels with BOX/Lanczos."""
    src=validate(mask)
    if not 1<=grid<=145: raise p.PatternError('grid must be 1..145')
    enlarged=np.asarray(Image.fromarray(src,mode='L').resize((grid*5,grid*5),Image.Resampling.NEAREST),dtype=np.uint8)
    patches=enlarged.reshape(grid,5,grid,5)[:,1:4,:,1:4].transpose(0,2,1,3).reshape(grid,grid,9)
    vote=np.stack([(patches==code).sum(axis=2) for code in range(6)],axis=2)
    return validate(vote.argmax(axis=2).astype(np.uint8),(grid,grid))


def check_coverage(labels:np.ndarray, *, portrait:bool=True):
    labels=validate(labels)
    counts=np.bincount(labels.ravel(),minlength=6)
    # Deliberately modest plausibility test. This is not semantic accuracy.
    if portrait and (counts[2]+counts[3]<max(4,int(labels.size*.02)) or counts[1]<max(4,int(labels.size*.01))):
        raise p.PatternError('segmentation has insufficient face/body skin or hair coverage; inspect mask/model rather than blindly applying skin rules')
    return {name:int(counts[i]) for i,name in enumerate(CLASSES)}


def boundaries(labels:np.ndarray) -> np.ndarray:
    a=validate(labels)
    # Face/body skin are one region for seam/border protection.
    b=a.copy();b[b==3]=2
    boundary=np.zeros(b.shape,dtype=bool)
    boundary[1:]|=b[1:]!=b[:-1]
    boundary[:-1]|=b[:-1]!=b[1:]
    boundary[:,1:]|=b[:,1:]!=b[:,:-1]
    boundary[:,:-1]|=b[:,:-1]!=b[:,1:]
    return boundary


def masks_from_classes(labels:np.ndarray, data:np.ndarray | None=None) -> dict[str,np.ndarray]:
    lab=validate(labels)
    out={
        'skin':np.isin(lab,[2,3]),'hair':lab==1,
        'cloth':lab==4,'background':lab==0,
        'protect':(lab==5)|boundaries(lab),
    }
    if data is not None:
        import portrait_quality as q
        if data.shape!=(lab.shape[0],lab.shape[1],3):
            raise p.PatternError('semantic data and grid labels dimension mismatch')
        _,edge=q.weights(data)
        out['protect']|=(lab==3)&(edge>=12)
    # Explicit protect always wins over class styling. Mask sources are preserved.
    return out


def overlay(stage:Image.Image, mask:np.ndarray) -> Image.Image:
    a=validate(mask,(stage.height,stage.width))
    base=np.asarray(stage.convert('RGB'),dtype=np.uint8)
    colored=COLORS[a]
    blend=np.uint8(np.round(.57*base+.43*colored))
    out=Image.fromarray(blend,'RGB')
    d=ImageDraw.Draw(out)
    d.rectangle((0,0,stage.width-1,stage.height-1),outline='#222222',width=2)
    return out
