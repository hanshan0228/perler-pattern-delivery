"""Controlled filters and pixel-art grid sampling for UNAPPROVED candidates.

Never call these on a frozen MASTER. All filters operate on a copy; 4-way
connected components provide reproducible noise statistics and replacements.
"""
from __future__ import annotations
from collections import Counter, deque
import numpy as np
from PIL import Image


def cleanup(rows: list[list[str]], *, strength: str = "none", protected=None):
    if strength not in {"none", "low", "medium", "high"}:
        raise ValueError("filter must be none|low|medium|high")
    before = [r[:] for r in rows]
    if strength == "none":
        return before, {"modified_cells": 0, "small_components_considered": 0}
    h = len(rows)
    w = len(rows[0])
    protected = set(protected or ())
    max_area = {"low": 1, "medium": 2, "high": 3}[strength]
    counts = Counter(v for row in before for v in row if v != "EMPTY")
    visited = set()
    edits = []
    ncomp = 0
    for y in range(h):
        for x in range(w):
            val = before[y][x]
            if (y, x) in visited or val == "EMPTY" or val in protected:
                continue
            # Ignore rare color codes altogether for low/medium so eye highlights survive.
            if strength != "high" and counts[val] <= 2:
                continue
            q = deque([(y, x)])
            visited.add((y, x))
            component = []
            border = Counter()
            while q:
                yy, xx = q.popleft()
                component.append((yy, xx))
                for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    ny, nx = yy + dy, xx + dx
                    if not (0 <= ny < h and 0 <= nx < w):
                        continue
                    neighbor = before[ny][nx]
                    if neighbor == val:
                        if (ny, nx) not in visited:
                            visited.add((ny, nx)); q.append((ny, nx))
                    elif neighbor != "EMPTY":
                        border[neighbor] += 1
            if len(component) <= max_area:
                ncomp += 1
                if not border:
                    continue
                best, frequency = border.most_common(1)[0]
                if frequency < 2 or best in protected:
                    continue
                # Conserve thin outlines: only replace if overwhelming surrounding consensus.
                if strength != "high" and frequency < 3:
                    continue
                for coord in component:
                    edits.append((coord[0], coord[1], best))
    out = [r[:] for r in before]
    for y, x, code in edits:
        out[y][x] = code
    return out, {"modified_cells": len(edits), "small_components_considered": ncomp}


def _edge_energy(a: np.ndarray, axis: int) -> np.ndarray:
    if axis == 1:  # vertical boundaries along x
        return np.mean(np.abs(np.diff(a.astype(np.int16), axis=1)), axis=(0, 2))
    return np.mean(np.abs(np.diff(a.astype(np.int16), axis=0)), axis=(1, 2))


def _infer_offset(energy: np.ndarray, cell: int, total: int) -> int:
    if cell <= 1:
        return 0
    # Score periodic boundaries x=offset+cell, ... . A contrast peak is indicative
    # of a true cell boundary; same-color neighbors naturally produce zero peaks.
    candidates=[]
    for offset in range(cell):
        xs = np.arange(offset + cell - 1, len(energy), cell)
        if len(xs) < 1:
            continue
        candidates.append((float(np.mean(energy[xs])), -offset, offset))
    return max(candidates)[2] if candidates else 0


def _grid_sample(src: np.ndarray, cols: int, rows: int, cell_x: float, cell_y: float, x0: float, y0: float):
    h, w, _ = src.shape
    sampled = np.empty((rows, cols, 3), dtype=np.float64)
    for r in range(rows):
        for c in range(cols):
            # Sample the central 40%, ignoring printed grid lines and antialiased borders.
            left = max(0, int(round(x0 + (c + .30) * cell_x)))
            right = min(w, int(round(x0 + (c + .70) * cell_x)))
            top = max(0, int(round(y0 + (r + .30) * cell_y)))
            bottom = min(h, int(round(y0 + (r + .70) * cell_y)))
            if not (right > left and bottom > top):
                raise ValueError("pixel grid exceeds image bounds; specify --pixel-cell/--pixel-origin")
            sampled[r, c] = np.median(src[top:bottom, left:right].reshape(-1, 3), axis=0)
    return sampled


def sample_pixel_art(im: Image.Image, *, grid: int, pixel_cell: int | None = None,
                     origin_x: int | None = None, origin_y: int | None = None):
    """Samples an existing pixel drawing without BOX interpolation.

    `grid` defines both width and height (square patterns). Use manual origin/cell
    for screenshots with margins and rulers. Automated offset is a best effort.
    """
    src = np.asarray(im.convert("RGB"))
    h, w, _ = src.shape
    if pixel_cell is not None:
        if pixel_cell < 1: raise ValueError("--pixel-cell must be positive")
        cell_x = cell_y = pixel_cell
    else:
        cell_x = w / grid
        cell_y = h / grid
    if origin_x is None:
        if pixel_cell is not None and w >= pixel_cell * grid:
            origin_x = _infer_offset(_edge_energy(src, 1), pixel_cell, w)
        else:
            origin_x = 0
    if origin_y is None:
        if pixel_cell is not None and h >= pixel_cell * grid:
            origin_y = _infer_offset(_edge_energy(src, 0), pixel_cell, h)
        else:
            origin_y = 0
    if (origin_x + cell_x * grid > w + 0.75 or origin_y + cell_y * grid > h + 0.75):
        raise ValueError("Pixel grid larger than source. Supply correct --grid, --pixel-cell, and origin.")
    data = _grid_sample(src, grid, grid, cell_x, cell_y, origin_x, origin_y)
    return data, {"origin_x": origin_x, "origin_y": origin_y,
                  "cell_width": cell_x, "cell_height": cell_y,
                  "sampling": "central_median_no_BOX"}
