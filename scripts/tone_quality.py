"""Candidate-only refinement of reviewed skin regions using the existing palette.
Optimizes local luminance/chroma transitions. No universal skin tone, no dithering,
no new codes, no changes to protected/detail cells. Rejects metric regressions.
"""
from __future__ import annotations
from collections import Counter
import numpy as np
import perler_delivery as p
import portrait_quality as q
import region_finish as r


def refine(data, rows, palette, regions):
    n=len(rows);a=np.asarray(rows);m=r.masks(n,regions)
    if a.shape!=(n,n) or data.shape!=(n,n,3) or not np.isfinite(data).all() or 'EMPTY' in a:raise p.PatternError('tone needs full square finite candidate')
    lab=p.srgb_lab(data);_,edge=q.weights(data)
    skin=m['skin']&~m['protect'];fixed=~skin|(edge>=12)
    # Keep the immediate silhouette, protect-boundary and eye/mouth neighborhoods.
    interior=skin.copy();interior[0]=False;interior[-1]=False;interior[:,0]=False;interior[:,-1]=False
    interior[1:] &= skin[:-1];interior[:-1]&=skin[1:];interior[:,1:]&=skin[:,:-1];interior[:,:-1]&=skin[:,1:]
    fixed|=~interior
    codes=sorted(set(a.ravel()));idx={c:i for i,c in enumerate(codes)}
    base=np.array([[idx[c] for c in row] for row in rows]);out=base.copy();counts=Counter(out.ravel())
    pl=p.srgb_lab(np.array([p.rgb(palette[c]) for c in codes]));delta=pl[None,None,:,:]-lab[:,:,None,:];err=np.linalg.norm(delta,axis=-1)
    warm=skin&(lab[...,1]>=0)&(lab[...,2]>=-2)&(lab[...,0]>=30)
    warmok=(pl[:,1]>=4)&(pl[:,2]>=5)
    
    # Avoid introducing a new skin code, including a neutral/green shadow from outside skin.
    def tone_stats(vals):
        mapped=pl[vals]; d=mapped-lab
        lum=[];chroma=[];seams=0;links=0
        for ax in (0,1):
            link=(skin[1:]&skin[:-1]) if ax==0 else (skin[:,1:]&skin[:,:-1]);src=np.diff(lab,axis=ax);dst=np.diff(mapped,axis=ax);smooth=link&(np.linalg.norm(src,axis=-1)<=8)
            lum.extend(np.abs(dst[...,0]-src[...,0])[smooth].tolist());chroma.extend(np.linalg.norm(dst[...,1:]-src[...,1:],axis=-1)[smooth].tolist());links+=int(smooth.sum());seams+=int((smooth&((vals[1:]!=vals[:-1]) if ax==0 else (vals[:,1:]!=vals[:,:-1]))).sum())
        return {'skin_mean_delta_e76':round(float(np.linalg.norm(d,axis=-1)[skin].mean()),4) if skin.any() else None,'skin_smooth_links':links,'skin_luma_step_error':round(float(np.mean(lum)),4) if lum else None,'skin_chroma_step_error':round(float(np.mean(chroma)),4) if chroma else None,'skin_smooth_seams':seams,'warm_skin_violations':int((warm&~warmok[vals]).sum())}
    old=tone_stats(base)
    # Only accept single-cell edits that improve the local smooth links, without
    # creating a new isolated cell or sacrificing the existing palette. The
    # sum of these exact local differences equals the whole-grid change.
    def neighbors(y,x):
        return [(yy,xx) for yy,xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)) if 0<=yy<n and 0<=xx<n]
    def isolated(yy,xx):
        return int(all(out[yy,xx]!=out[ny,nx] for ny,nx in neighbors(yy,xx)))
    for sweep in range(3):
        changed=0
        seq=range(n) if sweep%2==0 else range(n-1,-1,-1)
        for y in seq:
            for x in seq:
                if fixed[y,x]:continue
                cur=int(out[y,x]);orig=int(base[y,x]);nb=neighbors(y,x)
                links=[(yy,xx,int(out[yy,xx]),lab[y,x]-lab[yy,xx]) for yy,xx in nb if skin[yy,xx] and np.linalg.norm(lab[y,x]-lab[yy,xx])<=8]
                if not links or counts[cur]<=1:continue
                affected=[(y,x)]+nb
                before_iso=sum(isolated(yy,xx) for yy,xx in affected)
                def local(k):
                    v=np.array([(pl[k]-pl[c])-src for yy,xx,c,src in links]);return (float(np.abs(v[:,0]).sum()),float(np.linalg.norm(v[:,1:],axis=-1).sum()),sum(k!=c for _,_,c,_ in links))
                before=local(cur);win=cur;gain=0.
                for k in sorted(set(c for _,_,c,_ in links)):
                    if k==cur or (warm[y,x] and not warmok[k]) or err[y,x,k]>min(err[y,x,orig]+2.0,err[y,x,cur]+.75) or np.linalg.norm(pl[k]-pl[orig])>14:continue
                    after=local(k)
                    if any(a>b+1e-8 for a,b in zip(after,before)):continue
                    score=(before[0]-after[0])+(before[1]-after[1])+.8*(before[2]-after[2])
                    if score<=gain+1e-8:continue
                    out[y,x]=k;iso=sum(isolated(yy,xx) for yy,xx in affected);out[y,x]=cur
                    if iso>before_iso:continue
                    win=k;gain=score
                if win!=cur:out[y,x]=win;counts[cur]-=1;counts[win]+=1;changed+=1
        if not changed:break
    proposal=np.asarray(codes)[out].tolist();new=tone_stats(out);b=q.metrics(data,rows,palette);c=q.metrics(data,proposal,palette)
    # Never accept purely because a new algorithm was run. Refuse degradation of
    # smooth skin transitions, palette use, protection or global fidelity caps.
    accepted=(old['skin_luma_step_error'] is not None and new['skin_luma_step_error']<=old['skin_luma_step_error'] and new['skin_chroma_step_error']<=old['skin_chroma_step_error'] and new['skin_smooth_seams']<=old['skin_smooth_seams'] and (new['skin_luma_step_error']<old['skin_luma_step_error'] or new['skin_chroma_step_error']<old['skin_chroma_step_error']) and new['skin_mean_delta_e76']<=old['skin_mean_delta_e76']+.25 and new['warm_skin_violations']<=old['warm_skin_violations'] and c['mean_delta_e76']<=b['mean_delta_e76']+.15 and c['isolated_cells_4neighbor']<=b['isolated_cells_4neighbor'] and set(out.ravel())==set(base.ravel()) and np.array_equal(out[fixed],base[fixed]))
    if not accepted:proposal=[row[:] for row in rows];out=base.copy()
    return proposal,{'accepted':bool(accepted),'before':old,'after':tone_stats(out),'modified_cells':int((out!=base).sum()),'fixed_cells':int(fixed.sum()),'fixed_changes':int((out[fixed]!=base[fixed]).sum()),'colors':len(codes)}
