"""Conservative, editable portrait region proposals. Not a semantic neural parser.
Optional OpenCV Haar face localization; unknown pixels stay unknown. Review
is required before any mask can drive a candidate. No network or identity inference.
"""
from __future__ import annotations
import argparse, base64, io, json, sys
from pathlib import Path
import numpy as np
from PIL import Image
import perler_delivery as p
import portrait_quality as q

LABELS={'unknown':(0,0,0),'skin':(255,160,110),'hair':(90,95,200),'cloth':(98,205,245),'background':(68,185,110),'protect':(240,60,130)}
SCHEMA='reviewed-region-mask-v1'

def require(ok,msg):
    if not ok: raise p.PatternError(msg)

def stage_data(path):
    import first_sheet as f
    from cartoon_pipeline import open_rgb
    return f.fit_square(open_rgb(Path(path),max_side=1200))

def stage_digest(stage):
    import hashlib
    return hashlib.sha256(f'{stage.mode}:{stage.width}:{stage.height}:'.encode()+stage.tobytes()).hexdigest()

def face_box(stage):
    try: import cv2
    except ImportError: raise p.PatternError('Optional OpenCV unavailable; provide --face X0 Y0 X1 Y1 or use manually painted mask')
    im=stage.copy();im.thumbnail((800,800));a=np.asarray(im)
    detector=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    boxes=detector.detectMultiScale(cv2.cvtColor(a,cv2.COLOR_RGB2GRAY),1.08,5,minSize=(40,40))
    require(len(boxes)>0,'No reliable face localization; provide --face or edit a manual mask')
    boxes=sorted(boxes,key=lambda b:-int(b[2]*b[3]));x,y,w,h=map(int,boxes[0])
    require(len(boxes)==1 or boxes[1][2]*boxes[1][3]<0.35*w*h,'Multiple probable faces; specify the intended face box')
    return [x/im.width,y/im.height,(x+w)/im.width,(y+h)/im.height]

def components(mask, seeds):
    from collections import deque
    result=np.zeros_like(mask); h,w=mask.shape
    queue=deque(map(tuple,np.argwhere(mask&seeds)));result[mask&seeds]=True
    while queue:
        y,x=queue.popleft()
        for yy,xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
            if 0<=yy<h and 0<=xx<w and mask[yy,xx] and not result[yy,xx]:
                result[yy,xx]=True;queue.append((yy,xx))
    return result

def propose(stage,n,box):
    require(1<=n<=145,'grid 1..145');require(len(box)==4 and np.isfinite(box).all() and 0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1,'invalid normalized face box')
    import first_sheet as f
    data=f.samples(stage,n,'flat');lab=p.srgb_lab(data);L,A,B=lab.transpose(2,0,1);_,edge=q.weights(data)
    x0,y0,x1,y1=box;w=x1-x0;h=y1-y0; yy,xx=np.indices((n,n));X=(xx+.5)/n;Y=(yy+.5)/n
    face=((X-x0)/w>=.12)&((X-x0)/w<=.9)&((Y-y0)/h>=.10)&((Y-y0)/h<=.98)
    seed=face&(L>=30)&(A>=4)&(B>=2)&(edge<18)
    if seed.sum()<max(4,n*n*.002): return np.zeros((n,n),np.uint8),{'reason':'insufficient warm face seed; manual mask required'}
    ref=np.median(lab[seed],axis=0)
    # Connected face/neck/shoulder proposals; no universal skin-color threshold.
    # Warm bias is enabled only for source-supported visibly warm seeds.
    distance=np.hypot(A-ref[1],B-ref[2]); warm=(A>=max(2,ref[1]-14))&(B>=max(0,ref[2]-15))&(L>=max(27,ref[0]-34))&(distance<19)
    roi=(((X-(x0+.52*w))/(.57*w))**2+((Y-(y0+.50*h))/(.68*h))**2<=1)&(Y<=y1+.04*h)
    skin=components(warm&roi,seed)&roi
    # Require source support and leave uncertain boundary/unknown pixels unlabelled.
    skin &= edge<23
    dark=(L<30)&(np.hypot(A,B)<20)&~skin
    hairzone=(((X-(x0+.08*w))/(.82*w))**2+((Y-(y0-.03*h))/(.80*h))**2<=1)&(Y<y0+.53*h)
    hair=components(dark&hairzone,(Y<y0+.18*h)&hairzone)
    cloth=(Y>y1+.20*h)&(X>x0+.35*w)&(L>82)&(np.hypot(A,B)<10)&~skin&~hair&(edge<16)
    # Background only weakly supported corner-connected colors; uncertain remains unknown.
    bg=np.zeros((n,n),bool)
    for r,c in [(0,0),(0,n-1),(n-1,0),(n-1,n-1)]:
        d=np.linalg.norm(lab-lab[r,c],axis=-1); seeds=np.zeros((n,n),bool);seeds[r,c]=True
        bg|=components((d<10)&~skin&~hair&~cloth&((X<max(0,x0-.50*w))|(X>min(1,x1+.40*w))|(Y<max(0,y0-.40*h))),seeds)
    labels=np.zeros((n,n),np.uint8);labels[bg]=4;labels[cloth]=3;labels[hair]=2;labels[skin]=1
    # Protective face strip includes eyes, nose and mouth; strong face transitions
    # and unknown boundary features remain safe. Reviewer can refine it.
    protect=face&((edge>=12)|(((Y-y0)/h>.28)&((Y-y0)/h<.61)&((X-x0)/w>.20)))&roi
    labels[protect]=5
    return labels,{'face_seed_cells':int(seed.sum()),'source_face_lab_median':[round(float(x),2) for x in ref]}

def color_image(labels):
    return Image.fromarray(np.asarray(list(LABELS.values()),np.uint8)[labels],'RGB')

def read_mask(path,n):
    with Image.open(path) as im:
        require(im.mode in ('RGB','RGBA') and im.size==(n,n),'mask must be exact grid-size RGB/RGBA PNG (no scaling or antialiasing)')
        if im.mode=='RGBA': require(np.all(np.asarray(im)[...,3]==255),'mask alpha must be fully opaque')
        a=np.asarray(im.convert('RGB'))
    out=np.full((n,n),255,np.uint8)
    for i,col in enumerate(LABELS.values()): out[np.all(a==col,axis=-1)]=i
    require(not np.any(out==255),'mask has invalid label colors');return out

def spec(labels):
    """Compact exact, nonoverlapping horizontal runs, not interpolated polygons."""
    n=len(labels);regions=[]
    for i,k in enumerate(LABELS):
        if i==0:continue
        runs=[]
        for y,row in enumerate(labels):
            x=0
            while x<n:
                if row[x]!=i:x+=1;continue
                a=x
                while x<n and row[x]==i:x+=1
                runs.append([y,a,x])
        if runs:regions.append({'kind':k,'runs':runs,'grid':n})
    return regions

def mask_editor(stage,labels,path):
    b=io.BytesIO();stage.save(b,format='PNG');src=base64.b64encode(b.getvalue()).decode()
    # Offline editor: canvas displays blend; exported mask uses exact unblended RGB labels.
    html='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>拼豆区域校对</title><style>body{font:16px system-ui;background:#f6f2ee;color:#30282e;margin:24px}canvas{width:min(78vw,700px);height:auto;image-rendering:pixelated;touch-action:none;border:1px solid #888}button,select{font:inherit;padding:8px;margin:4px}label{display:inline-block}</style><h1>区域蒙版校对 / Region review</h1><p>自动建议不是语义真值。修正错标；不确定位置用 unknown，五官细节用 protect。下载后须用 accept 记录实际审核。</p><div><select id="kind"></select><label>笔刷 <select id="brush"><option value="1">1格</option><option value="3">3格</option><option value="5">5格</option></select></label><label><input type="checkbox" id="blend" checked>叠加原图</label><button id="undo">撤销</button><button id="save">下载校正蒙版 PNG</button></div><canvas id="c"></canvas><script>const cols=COLORS,n=GRID,src=SOURCE;let a=Uint8Array.from(DATA),history=[],drawing=false;const c=document.querySelector('#c'),ctx=c.getContext('2d'),kind=document.querySelector('#kind'),blend=document.querySelector('#blend');c.width=c.height=n;Object.keys(cols).forEach((k,i)=>{let o=new Option(k,i);kind.add(o);o.style.backgroundColor='rgb('+cols[k].join(',')+')';o.style.color=k==='unknown'?'white':'black'});kind.value=1;const im=new Image();function mask(){let d=new ImageData(n,n);for(let i=0;i<a.length;i++){const col=Object.values(cols)[a[i]];d.data.set([...col,255],4*i)}return d}function draw(){ctx.putImageData(mask(),0,0);if(blend.checked&&im.complete&&im.naturalWidth){const t=document.createElement('canvas');t.width=t.height=n;const tc=t.getContext('2d');tc.drawImage(im,0,0,n,n);const d=tc.getImageData(0,0,n,n),m=mask();for(let i=0;i<a.length;i++){if(a[i]!==0)for(let j=0;j<3;j++)d.data[4*i+j]=.57*d.data[4*i+j]+.43*m.data[4*i+j]}ctx.putImageData(d,0,0)}}im.onload=draw;im.src=src;function paint(e){let b=c.getBoundingClientRect(),x=Math.floor((e.clientX-b.left)*n/b.width),y=Math.floor((e.clientY-b.top)*n/b.height);if(x>=0&&x<n&&y>=0&&y<n){const k=Number(kind.value),r=(Number(document.querySelector('#brush').value)-1)/2;for(let yy=Math.max(0,y-r);yy<=Math.min(n-1,y+r);yy++)for(let xx=Math.max(0,x-r);xx<=Math.min(n-1,x+r);xx++)a[yy*n+xx]=k;draw()}}c.onpointerdown=e=>{history.push(a.slice());drawing=true;c.setPointerCapture(e.pointerId);paint(e)};c.onpointermove=e=>{if(drawing)paint(e)};c.onpointerup=c.onpointercancel=()=>drawing=false;blend.onchange=draw;document.querySelector('#undo').onclick=()=>{if(history.length){a=history.pop();draw()}};document.querySelector('#save').onclick=()=>{const temp=document.createElement('canvas');temp.width=temp.height=n;temp.getContext('2d').putImageData(mask(),0,0);const link=document.createElement('a');link.href=temp.toDataURL('image/png');link.download='reviewed_mask.png';link.click()};draw();</script></html>'''
    # Canvas PNG exports commonly RGBA; read_mask accepts only opaque RGBA as well (below).
    for marker,value in [('COLORS',json.dumps(LABELS)),('GRID',str(len(labels))),('SOURCE',json.dumps('data:image/png;base64,'+src)),('DATA',json.dumps(labels.ravel().tolist()))]:html=html.replace(marker,value,1)
    path.write_text(html,encoding='utf8')

def propose_cli(args):
    stage=stage_data(args.stage);root=Path(args.out);require(not root.exists(),'output exists')
    if args.manual: labels=np.zeros((args.grid,args.grid),np.uint8);box=None;details={'reason':'manual blank mask'}
    else: box=args.face or face_box(stage);labels,details=propose(stage,args.grid,box)
    root.mkdir(parents=True);stage.save(root/'stage.png');color_image(labels).save(root/'proposed_mask.png');mask_editor(stage,labels,root/'mask_editor.html')
    overlay=np.asarray(stage.resize((600,600))).astype(float); colors=np.asarray(color_image(labels).resize((600,600),Image.Resampling.NEAREST)); visible=np.any(colors!=0,axis=-1)
    overlay[visible]=.57*overlay[visible]+.43*colors[visible];Image.fromarray(overlay.astype(np.uint8)).save(root/'overlay.png')
    info={'grid':args.grid,'stage_digest':stage_digest(stage),'face_box':box,'method':'manual' if args.manual else 'face localization + conservative Lab connectivity','details':details,'counts':{k:int((labels==i).sum()) for i,k in enumerate(LABELS)},'status':'UNREVIEWED'}
    (root/'proposal.json').write_text(json.dumps(info,indent=2));print('UNREVIEWED mask; inspect overlay, edit if needed, then accept.')

def accept(args):
    root=Path(args.proposal);meta=json.loads((root/'proposal.json').read_text());require(meta['status']=='UNREVIEWED','invalid proposal')
    stage=Image.open(root/'stage.png').convert('RGB');require(stage_digest(stage)==meta['stage_digest'],'proposal stage changed')
    labels=read_mask(Path(args.mask),meta['grid']);require(len(args.notes.strip())>=20,'record concrete region review observations')
    require(np.any(labels==1),'no reviewed skin cells; use legacy candidates instead')
    out=Path(args.out);require(not out.exists(),'output exists')
    plan={'schema':SCHEMA,'grid':meta['grid'],'stage_digest':meta['stage_digest'],'regions':spec(labels),'review_notes':args.notes,'status':'REGION_REVIEWED_NOT_CUSTOMER_APPROVED'}
    out.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8');print('Reviewed region plan only, not customer approval.')

def load_plan(path,stage,n):
    plan=json.loads(Path(path).read_text(encoding='utf8'));return verify_plan(plan,stage,n)

def verify_plan(plan,stage,n):
    require(plan.get('schema')==SCHEMA and plan.get('status')=='REGION_REVIEWED_NOT_CUSTOMER_APPROVED' and plan.get('grid')==n and plan.get('stage_digest')==stage_digest(stage),'mask plan is not bound to this exact padded source/grid')
    require(isinstance(plan.get('review_notes'),str) and len(plan['review_notes'].strip())>=20,'missing mask review notes')
    import region_finish as r
    regions=plan['regions'];require(isinstance(regions,list) and all(isinstance(x,dict) and set(x)=={'kind','grid','runs'} for x in regions),'reviewed plan must use exact raster runs')
    m=r.masks(n,regions);labels=np.zeros((n,n),np.uint8)
    for i,k in enumerate(LABELS):
        if i: labels[m[k]]=i
    require(spec(labels)==regions,'invalid or overlapping noncanonical region runs');require(m['skin'].any(),'reviewed skin region required')
    return plan

def main():
    a=argparse.ArgumentParser(description=__doc__);sub=a.add_subparsers(dest='cmd',required=True)
    b=sub.add_parser('propose');b.add_argument('--stage',required=True);b.add_argument('--grid',type=int,default=87);b.add_argument('--face',nargs=4,type=float);b.add_argument('--manual',action='store_true');b.add_argument('--out',required=True);b.set_defaults(func=propose_cli)
    b=sub.add_parser('accept');b.add_argument('--proposal',required=True);b.add_argument('--mask',required=True);b.add_argument('--notes',required=True);b.add_argument('--out',required=True);b.set_defaults(func=accept)
    args=a.parse_args()
    try: require(not hasattr(args,'grid') or 1<=args.grid<=145,'grid 1..145');args.func(args)
    except (p.PatternError,ValueError,OSError,KeyError) as e:print('ERROR:',e,file=sys.stderr);return 2
    return 0
if __name__=='__main__':raise SystemExit(main())
