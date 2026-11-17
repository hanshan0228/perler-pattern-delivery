"""Offline cartoon preprocessor for UNAPPROVED fuse-bead candidates.

Independent implementation inspired by well-known edge-preserving smoothing +
flat-color quantization workflows. No pretrained weights or third-party repo
code are bundled. Optional OpenCV acceleration; pure-Pillow fallback.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageOps, ImageFilter
import numpy as np

STYLES = ("soft", "comic", "poster")


def open_rgb(path: Path, *, max_side: int = 900) -> Image.Image:
    with Image.open(path) as raw:
        im = ImageOps.exif_transpose(raw).convert("RGBA")
        # Avoid smearing transparency into dark edge pixels.
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg.convert("RGB")
    im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return im


def _pillow_cartoon(im: Image.Image, style: str) -> Image.Image:
    # Whole pipeline is deterministic, local, and dependency-light.
    smoothed = im.filter(ImageFilter.MedianFilter(size=5)).filter(ImageFilter.SMOOTH_MORE)
    colors = {"soft": 40, "comic": 28, "poster": 24}[style]
    flattened = smoothed.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
    if style == "poster":
        return flattened
    # Use only strong image edges as thin, semi-transparent line art.
    gray = im.convert("L").filter(ImageFilter.GaussianBlur(radius=1.2))
    ed = gray.filter(ImageFilter.FIND_EDGES)
    edge_arr = np.asarray(ed, dtype=np.uint8)
    level = {"soft": 83, "comic": 66}[style]
    mask = (edge_arr > level).astype(np.uint8)
    # Do not introduce light/shadow gradients in the *final grid*: this is only a pre-grid image.
    weight = {"soft": 0.42, "comic": 0.76}[style]
    flat = np.asarray(flattened, dtype=np.float32).copy()
    dark = np.array([43, 37, 53], dtype=np.float32)
    alpha = (mask * weight)[:, :, None]
    result = flat * (1 - alpha) + dark * alpha
    return Image.fromarray(np.clip(result, 0, 255).astype("uint8"), "RGB")


def _opencv_cartoon(im: Image.Image, style: str) -> Image.Image:
    try:
        import cv2
    except ImportError:
        return _pillow_cartoon(im, style)
    source = np.asarray(im, dtype=np.uint8)
    bgr = cv2.cvtColor(source, cv2.COLOR_RGB2BGR)
    # Bilateral filtering smooths large regions while retaining feature boundaries.
    smooth = cv2.bilateralFilter(bgr, d=9, sigmaColor=65, sigmaSpace=20)
    smooth = cv2.bilateralFilter(smooth, d=7, sigmaColor=45, sigmaSpace=14)
    colors = {"soft": 46, "comic": 30, "poster": 26}[style]
    softened = Image.fromarray(cv2.cvtColor(smooth, cv2.COLOR_BGR2RGB))
    flat = np.asarray(softened.quantize(colors=colors, method=Image.Quantize.MEDIANCUT,
                                       dither=Image.Dither.NONE).convert("RGB"), dtype=np.float32).copy()
    if style == "poster":
        return Image.fromarray(flat.astype("uint8"), "RGB")
    gray = cv2.cvtColor(source, cv2.COLOR_RGB2GRAY)
    gray = cv2.medianBlur(gray, 5)
    # Canny avoids the thick black bands often caused by naive adaptive thresholds.
    edges = cv2.Canny(gray, threshold1=75 if style == "soft" else 60,
                     threshold2=165 if style == "soft" else 140)
    # Suppress extremely tiny isolated edges, which become single stray dark beads.
    num, labels, counts, _ = cv2.connectedComponentsWithStats((edges > 0).astype("uint8"), connectivity=8)
    for i in range(1, num):
        if counts[i, cv2.CC_STAT_AREA] < 5:
            edges[labels == i] = 0
    strength = {"soft": 0.45, "comic": 0.83}[style]
    alpha = ((edges > 0).astype(np.float32) * strength)[:, :, None]
    dark = np.array([42, 31, 49], dtype=np.float32)
    out = flat * (1 - alpha) + dark * alpha
    return Image.fromarray(np.clip(out, 0, 255).astype("uint8"), "RGB")


def cartoonize(im: Image.Image, style: str = "soft") -> Image.Image:
    if style not in STYLES:
        raise ValueError(f"Unsupported cartoon style: {style}")
    return _opencv_cartoon(im.convert("RGB"), style)
