"""Reviewed region-aware palette optimization, candidate-only (no semantic detector).
Polygons are normalized coordinates on the padded stage. Explicitly protect features.
No neural model, identity claim, or approved master edits.
"""
from __future__ import annotations
from collections import Counter
import numpy as np
from PIL import Image, ImageDraw
import perler_delivery as p
import portrait_quality as q
import spatial_quality as s

KINDS=('skin','hair','cloth','background','protect')

def masks(n, regions):
    result={k:np.zeros((n,n),bool) for k in KINDS}
    for region in regions:
        kind=region['kind']; pts=region['polygon']
        if kind not in KINDS or len(pts)<3 or any(len(t)!=2 or not all(np.isfinite(t)) or not all(0<=v<=1 for v in t) for t in pts):
            raise p.PatternError('invalid normalized polygon')
        im=Image.new('1',(n*4,n*4));ImageDraw.Draw(im).polygon([(round(x*n*4),round(y*n*4)) for x,y in pts],fill=1)
        mask=np.asarray(im)[2::4,2::4]
        if kind!='protect':
            for k in KINDS[:-1]: result[k][mask]=False
        result[kind]|=mask
    return result

def optimize(data, rows, palette, regions, *, max_colors=None, rare_limit=5):
    n=len(rows); a=np.asarray(rows); counts,empty,w,h=p.stats(rows,palette)
    if w!=h or data.shape!=(n,n,3) or empty or not np.isfinite(data).all(): raise p.PatternError('full square finite source required')
    if not isinstance(rare_limit,int) or not 0<=rare_limit<=20: raise p.PatternError('rare limit 0..20')
    budget=len(counts) if max_colors is None else max_colors
    if not 1<=budget<=len(palette): raise p.PatternError('invalid color budget')
    m=masks(n,regions); lab=p.srgb_lab(data); weight,edge=q.weights(data)
    codes,dist=q._dist(data,palette); pl=p.srgb_lab(np.array([p.rgb(palette[c]) for c in codes])); ix={c:i for i,c in enumerate(codes)}
    old=np.array([ix[c] for c in a.ravel()]); fixed=m['protect'].ravel(); fixed_colors=sorted(set(old[fixed]))
    if len(fixed_colors)>budget: raise p.PatternError('protected codes exceed budget')
    # Warm source skin/background only; never impose a universal skin tone.
    # Exclude shadows, neutral highlights, and explicit feature protection.
    A=lab[...,1]; B=lab[...,2]; L=lab[...,0]
    warm_skin=m['skin'] & (A>=0) & (B>=-2) & (L>=30) & ~m['protect']
    warm_bg=m['background'] & (A>=0) & (B>=0) & ~m['protect']
    neutral_hair=m['hair'] & (np.hypot(A,B)<=15) & (L<45) & ~m['protect']
    neutral_cloth=m['cloth'] & (np.hypot(A,B)<=14) & ~m['protect']
    # Hard reject green/purple/gray substitutions on explicitly warm skin; soft penalty elsewhere.
    allowed=np.ones(dist.shape,dtype=bool)
    warm_ok=(pl[:,1]>=4)&(pl[:,2]>=5)
    allowed[warm_skin.ravel()]=warm_ok
    penalty=np.zeros_like(dist)
    penalty[warm_bg.ravel()]=10*np.maximum(0,2-pl[:,1])**2+6*np.maximum(0,2-pl[:,2])**2
    penalty[neutral_hair.ravel()]=3*np.maximum(0,np.hypot(pl[:,1],pl[:,2])-12)**2
    penalty[neutral_cloth.ravel()]=2*np.maximum(0,np.hypot(pl[:,1],pl[:,2])-14)**2
    # Use a modest region-specific chroma error emphasis, not arbitrary saturation boost.
    cost=dist+penalty
    flat=lab.reshape(-1,3); skin=warm_skin.ravel()
    cost[skin]+=1.5*((flat[skin,1,None]-pl[None,:,1])**2+(flat[skin,2,None]-pl[None,:,2])**2)
    cost[~allowed]=1e8
    cost[fixed]=1e8;cost[np.where(fixed)[0],old[fixed]]=0
    weights=weight.ravel().astype(np.float32);weights[skin]*=2.0
    selected=list(fixed_colors); best=np.min(cost[:,selected],axis=1) if selected else np.full(len(old),1e8,dtype=np.float32)
    for _ in range(budget-len(selected)):
        gains=np.sum(np.maximum(best[:,None]-cost,0)*weights[:,None],axis=0,dtype=np.float64)
        gains[selected]=-1; j=int(gains.argmax())
        if gains[j]<=1e-6: break
        selected.append(j);best=np.minimum(best,cost[:,j])
    if not selected or np.any(best>=1e8): raise p.PatternError('cannot satisfy region palette constraints')
    selected=sorted(selected);out=np.array(selected)[cost[:,selected].argmin(1)]
    # Rare-color elimination is all-or-nothing, respects protected coordinates,
    # strong edges, region eligibility and per-cell measured color-error limits.
    removed=[]
    for code,num in sorted(Counter(out).items(),key=lambda t:(t[1],t[0])):
        if num>rare_limit or code in fixed_colors: continue
        loc=np.flatnonzero(out==code)
        if not len(loc) or np.any(edge.ravel()[loc]>=12): continue
        choices=sorted(set(out)-{code})
        if not choices: continue
        rep=np.array(choices)[cost[loc][:,choices].argmin(1)]
        if np.any(cost[loc,rep]>=1e8) or np.any(np.sqrt(dist[loc,rep])-np.sqrt(dist[loc,code])>2.5): continue
        out[loc]=rep;removed.append(codes[code])
    # Local seam reduction, only same region, no added colors or disappearing protected codes.
    aa=out.reshape(n,n); base=aa.copy(); active=Counter(out); err=np.sqrt(dist); rr=cost.reshape(n,n,-1)
    region_id=np.zeros((n,n),int)
    for j,k in enumerate(KINDS[:-1],1): region_id[m[k]]=j
    for sweep in range(2):
        for y in range(n):
            for x in range(n):
                if m['protect'][y,x] or edge[y,x]>=12: continue
                i=y*n+x;cur=int(aa[y,x]); orig=int(base[y,x]); nb=[int(aa[yy,xx]) for yy,xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)) if 0<=yy<n and 0<=xx<n and region_id[yy,xx]==region_id[y,x]]
                if len(nb)<2 or active[cur]<=1: continue
                opts=sorted(set(nb)); k=min(opts,key=lambda c:(float(rr[y,x,c])+30*sum(t!=c for t in nb),c))
                if k==cur or rr[y,x,k]>=1e8 or err[i,k]>err[i,orig]+2.0: continue
                if rr[y,x,k]+30*sum(t!=k for t in nb)>=rr[y,x,cur]+30*sum(t!=cur for t in nb): continue
                aa[y,x]=k;active[cur]-=1;active[k]+=1
    final=aa.ravel();result=np.asarray(codes)[aa].tolist()
    if not (np.array_equal(final[fixed],old[fixed]) and len(set(final))<=budget and np.all(allowed[np.arange(len(final)),final])):
        raise p.PatternError('regional output violates protection, palette budget or skin constraint')
    def summary(v):
        r=np.asarray(codes)[v.reshape(n,n)].tolist(); c=Counter(v)
        return {**q.metrics(data,r,palette),**s.continuity(data,r,palette),'rare_colors':sum(x<=rare_limit for x in c.values()),'warm_skin_violations':int((skin & ~warm_ok[v]).sum())}
    return result,{'before':summary(old),'after':summary(final),'protected_cells':int(fixed.sum()),'protected_changes':int(np.sum(final[fixed]!=old[fixed])),'warm_skin_cells':int(skin.sum()),'removed_codes':removed,'modified_cells':int(np.sum(final!=old)),'region_cells':{k:int(v.sum()) for k,v in m.items()}}
