"""Candidate-only spatial regularization on the *same* MARD palette.

Source-aware local Potts energy, bounded color error, and immutable focus/edge
cells. No face detection, aesthetic certification, or changes to MASTER.
"""
from __future__ import annotations
import numpy as np
import portrait_quality as q
import perler_delivery as p


def continuity(data, rows, palette):
    lab=p.srgb_lab(data); a=np.asarray(rows)
    total=0; transitions=0; flat=0
    for axis in (0,1):
        delta=np.linalg.norm(np.diff(lab,axis=axis),axis=-1)
        diff=(a[1:]!=a[:-1]) if axis==0 else (a[:,1:]!=a[:,:-1])
        flat_mask=delta<=6.0
        total+=int(diff.sum());flat+=int(flat_mask.sum());transitions+=int((diff&flat_mask).sum())
    return {'neighbor_transitions':total,'flat_source_edges':flat,'flat_region_transitions':transitions}


def regularize(data, rows, palette, regions=(), *, strength='balanced'):
    """Reduce unnecessary seams; keep source edge and focus cells unchanged.

    Same used colors (not just same limit); each edit can add at most 2.5
    Delta E76 relative to the input candidate. Four fixed sweeps, deterministic.
    Only neighbor colors, no new codes. Reject candidates that increase isolated
    cells or breach mean/color-weighted error caps. Return an honest no-op.
    """
    if strength not in ('balanced','gentle'): raise p.PatternError('invalid spatial strength')
    n=len(rows); a=np.asarray(rows); codes=sorted(set(a.ravel()))
    if a.shape!=(n,n) or data.shape!=(n,n,3) or 'EMPTY' in codes: raise p.PatternError('spatial candidate must be full square')
    idx={c:i for i,c in enumerate(codes)}; before=np.array([[idx[c] for c in row] for row in rows],dtype=np.int32)
    out=before.copy(); counts=np.bincount(out.ravel(),minlength=len(codes))
    lab=p.srgb_lab(data); pal=p.srgb_lab(np.array([p.rgb(palette[c]) for c in codes]))
    err=np.linalg.norm(lab[:,:,None,:]-pal[None,None,:,:],axis=-1)
    weights, edge=q.weights(data,regions); fixed=q.focus_mask(n,regions)|(edge>=12.)
    base_err=np.take_along_axis(err,before[...,None],axis=-1)[...,0]
    lam=40. if strength=='balanced' else 20.
    cap=2.5 if strength=='balanced' else 1.5
    # A boundary is cheap if the original itself has a visible edge.
    wy=np.exp(-((np.linalg.norm(lab[1:]-lab[:-1],axis=-1)/6.)**2))
    wx=np.exp(-((np.linalg.norm(lab[:,1:]-lab[:,:-1],axis=-1)/6.)**2))
    for sweep in range(4):
        edits=0
        rr=range(n) if sweep%2==0 else range(n-1,-1,-1)
        for y in rr:
            for x in rr:
                if fixed[y,x]: continue
                cur=int(out[y,x]); nb=[]
                if y: nb.append((int(out[y-1,x]),wy[y-1,x]))
                if y+1<n: nb.append((int(out[y+1,x]),wy[y,x]))
                if x: nb.append((int(out[y,x-1]),wx[y,x-1]))
                if x+1<n: nb.append((int(out[y,x+1]),wx[y,x]))
                if counts[cur]<=1: continue
                def cost(k): return weights[y,x]*err[y,x,k]**2+lam*sum(w for c,w in nb if c!=k)
                best=cur; best_cost=cost(cur)
                for k in sorted({c for c,_ in nb}):
                    if k==cur or err[y,x,k]>base_err[y,x]+cap: continue
                    # Preserve intentional high-contrast palette boundaries, even on smooth source.
                    if np.linalg.norm(pal[k]-pal[int(before[y,x])])>14: continue
                    val=cost(k)
                    if val<best_cost-1e-8: best=k;best_cost=val
                if best!=cur:
                    out[y,x]=best;counts[cur]-=1;counts[best]+=1;edits+=1
        if not edits: break
    result=np.asarray(codes)[out].tolist()
    base=q.metrics(data,rows,palette,regions);new=q.metrics(data,result,palette,regions)
    b=continuity(data,rows,palette);c=continuity(data,result,palette)
    # Caps relative to the same source and actual palette, no hidden fidelity loss.
    accepted=(new['mean_delta_e76']<=base['mean_delta_e76']+0.45 and
              new['weighted_rms_delta_e76']<=base['weighted_rms_delta_e76']+0.4 and
              new['isolated_cells_4neighbor']<=base['isolated_cells_4neighbor'] and
              c['flat_region_transitions']<b['flat_region_transitions'])
    if not accepted: result=[r[:] for r in rows]
    report={'strength':strength,'modified_cells':int(np.sum(np.asarray(result)!=a)),
            'protected_cells':int(fixed.sum()),'accepted':bool(accepted),
            'baseline':b,'result':continuity(data,result,palette)}
    return result,report


def pareto(scores):
    """Diagnostic nondominance, not an aesthetic ranking."""
    keys=('weighted_rms_delta_e76','isolated_cells_4neighbor','flat_region_transitions','colors')
    def vals(v): return [scores[v][k] for k in keys]
    return [a for a in scores if not any(all(x<=y for x,y in zip(vals(b),vals(a))) and any(x<y for x,y in zip(vals(b),vals(a))) for b in scores if b!=a)]


def refine_palette(data, rows, palette, regions=()):
    """Bounded medoid swaps; actual used color count fixed, ROI/edge error guards."""
    codes,d=q._dist(data,palette); n=len(rows); original=np.asarray(rows)
    chosen=sorted({codes.index(c) for c in original.ravel()}); k=len(chosen)
    w,edge=q.weights(data,regions); w=w.ravel()
    best_rows=[r[:] for r in rows]
    initial=q.metrics(data,rows,palette,regions); current=initial.copy(); swaps=[]
    for _ in range(2):
        if k<2 or k==len(codes): break
        sub=d[:,chosen]; order=np.argsort(sub,axis=1,kind='stable'); first=order[:,0]; second=order[:,1]
        best=sub[np.arange(len(d)),first]; backup=sub[np.arange(len(d)),second]
        gain=np.sum(np.maximum(best[:,None]-d,0)*w[:,None],axis=0);gain[chosen]=-1
        additions=[int(i) for i in np.argsort(-gain,kind='stable')[:24] if gain[i]>=0 and i not in chosen]
        if not additions: break
        loss=np.bincount(first,weights=w*(backup-best),minlength=k)
        removes=np.argsort(loss,kind='stable')[:min(12,k)]
        best_cost=float(np.sum(w*best)); winner=None; win_rows=None; win_scores=None
        for rem in removes:
            without=np.where(first==rem,backup,best)
            trial=np.minimum(without[:,None],d[:,additions]); costs=np.sum(w[:,None]*trial,axis=0)
            for j in np.argsort(costs,kind='stable'):
                if costs[j]>=best_cost-1e-6: break
                candidate=sorted([c for i,c in enumerate(chosen) if i!=rem]+[additions[j]])
                nearest=d[:,candidate].argmin(axis=1)
                if len(np.unique(nearest))!=k: continue
                trial_rows=np.asarray([codes[c] for c in candidate])[nearest.reshape(n,n)].tolist()
                stats=q.metrics(data,trial_rows,palette,regions)
                if any(stats[key] is not None and current[key] is not None and stats[key]>current[key]+1e-4 for key in ('focus_mean_delta_e76','edge_mean_delta_e76')): continue
                if stats['weighted_rms_delta_e76']>=current['weighted_rms_delta_e76']: continue
                best_cost=float(costs[j]);winner=candidate;win_rows=trial_rows;win_scores=stats
        if winner is None: break
        swaps.append({'removed':codes[next(i for i in chosen if i not in winner)],'added':codes[next(i for i in winner if i not in chosen)]})
        chosen=winner;best_rows=win_rows;current=win_scores
    return best_rows, {'swaps':swaps,'colors':k,'modified_cells':int(np.sum(np.asarray(best_rows)!=original)),
                      'weighted_rms_before':initial['weighted_rms_delta_e76'],'weighted_rms_after':current['weighted_rms_delta_e76']}
