"""Candidate-only, palette-constrained portrait quantization. No landmark detector.

Weights prioritize source edges and optional reviewed ROI rectangles. Optimization
minimizes weighted squared CIELAB (Delta E76) error, not artistic quality.
No noise deletion, dithering, network access, or changes to approved masters.
"""
from __future__ import annotations
import numpy as np
import perler_delivery as p


def focus_mask(n, regions=()):
    mask=np.zeros((n,n),dtype=bool)
    for r in regions:
        if len(r)!=4 or not all(np.isfinite(r)) or not (0<=r[0]<r[2]<=1 and 0<=r[1]<r[3]<=1):
            raise p.PatternError('focus must be x0,y0,x1,y1 in normalized padded stage coordinates')
        x0,y0,x1,y1=r
        yy,xx=np.indices((n,n));mask|=((xx+.5)/n>=x0)&((xx+.5)/n<x1)&((yy+.5)/n>=y0)&((yy+.5)/n<y1)
    return mask


def weights(data, regions=()):
    n=data.shape[0]; lab=p.srgb_lab(data)
    edge=np.zeros((n,n),dtype=float)
    for axis in (0,1):
        diff=np.linalg.norm(np.diff(lab,axis=axis),axis=-1)
        if axis==0:
            edge[1:]=np.maximum(edge[1:],diff);edge[:-1]=np.maximum(edge[:-1],diff)
        else:
            edge[:,1:]=np.maximum(edge[:,1:],diff);edge[:,:-1]=np.maximum(edge[:,:-1],diff)
    # Cap contrast weights: dark hair/background edges must not dominate.
    w=1+0.7*np.clip(edge/25,0,1)
    return w*(1+2*focus_mask(n,regions)),edge


def _dist(data,palette):
    codes=sorted(palette)
    labs=p.srgb_lab(np.array([p.rgb(palette[c]) for c in codes],dtype=float))
    a=p.srgb_lab(data).reshape(-1,3)
    # Explicit differences: avoid the numerical cancellation of dot-product form.
    d=np.empty((len(a),len(codes)),dtype=np.float32)
    for j,lab in enumerate(labs): d[:,j]=np.sum((a-lab)**2,axis=1)
    return codes,d


def optimize(data, colors, palette, baseline, regions=()):
    n=data.shape[0]
    if data.shape!=(n,n,3) or not np.isfinite(data).all(): raise p.PatternError('invalid samples')
    codes,d=_dist(data,palette); w,_=weights(data,regions); w=w.reshape(-1).astype(np.float32)
    k=min(colors,len(codes),len(d)); selected=[]
    if k<1: raise p.PatternError('invalid palette budget')
    # Greedy facility location: each next actual MARD color reduces the objective.
    first=int(np.sum(d*w[:,None],axis=0,dtype=np.float64).argmin());selected.append(first)
    best=d[:,first].copy()
    for _ in range(k-1):
        gains=np.sum(np.maximum(best[:,None]-d,0)*w[:,None],axis=0,dtype=np.float64)
        gains[selected]=-1
        idx=int(gains.argmax())
        if gains[idx]<=1e-7: break
        selected.append(idx);best=np.minimum(best,d[:,idx])
    # Also consider the existing palette; never regress the weighted objective
    # merely because the greedy search got stuck in a local optimum.
    legacy=sorted({codes.index(c) for row in baseline for c in row})
    if len(legacy)<=k:
        legacy_cost=np.sum(np.min(d[:,legacy],axis=1)*w,dtype=np.float64)
        if legacy_cost < np.sum(best*w,dtype=np.float64): selected=legacy
    selected=sorted(selected)
    chosen=np.array(selected)[d[:,selected].argmin(axis=1)]
    return [[codes[i] for i in row] for row in chosen.reshape(n,n)]


def metrics(data, rows, palette, regions=()):
    """Shared area-average reference; these are diagnostic, not aesthetic scores."""
    stage=p.srgb_lab(data);n=stage.shape[0]
    result=p.srgb_lab(np.asarray([[p.rgb(palette[c]) for c in row] for row in rows]))
    delta=np.linalg.norm(result-stage,axis=-1);w,edge=weights(data,regions)
    mask=focus_mask(n,regions);a=np.asarray(rows);same=np.zeros((n,n),dtype=int)
    same[1:]+=a[1:]==a[:-1];same[:-1]+=a[:-1]==a[1:];same[:,1:]+=a[:,1:]==a[:,:-1];same[:,:-1]+=a[:,:-1]==a[:,1:]
    return {'mean_delta_e76':round(float(delta.mean()),4),
            'weighted_rms_delta_e76':round(float(np.sqrt(np.sum(w*delta**2)/w.sum())),4),
            'focus_mean_delta_e76':round(float(delta[mask].mean()),4) if mask.any() else None,
            'edge_mean_delta_e76':round(float(delta[edge>=12].mean()),4) if (edge>=12).any() else None,
            'isolated_cells_4neighbor':int((same==0).sum()),'colors':len(set(a.ravel())),
            'focus_cells':int(mask.sum())}


def conservative_cleanup(data, rows, palette, regions=()):
    """Only isolated cells outside focus/strong edges; no changes to source matrix.

    Accept a replacement only with three agreeing 4-neighbors, a low-contrast
    source neighborhood, and at most 1.5 additional Delta E76. One synchronous pass.
    """
    n=len(rows); mask=focus_mask(n,regions); _,edge=weights(data,regions)
    a=np.asarray(rows); out=a.copy(); stage=p.srgb_lab(data)
    labs={code:p.srgb_lab(np.array(p.rgb(palette[code]))) for code in set(a.ravel())}
    from collections import Counter
    edits=0
    for y in range(1,n-1):
        for x in range(1,n-1):
            if mask[y,x] or edge[y,x]>=8: continue
            val=a[y,x]; nb=[a[y-1,x],a[y+1,x],a[y,x-1],a[y,x+1]]
            if val in nb: continue
            replacement,count=Counter(nb).most_common(1)[0]
            if count<3: continue
            old=float(np.linalg.norm(stage[y,x]-labs[val]));new=float(np.linalg.norm(stage[y,x]-labs[replacement]))
            if new-old<=1.5 and np.linalg.norm(labs[val]-labs[replacement])<=8:
                out[y,x]=replacement;edits+=1
    return out.tolist(),edits
