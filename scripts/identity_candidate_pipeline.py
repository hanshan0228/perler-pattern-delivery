#!/usr/bin/env python3
"""Identity-first portrait candidate framing and comparison for bead charts.

This tool does NOT identify a person, score facial similarity, generate AI art,
or approve a pattern. It provides deterministic framing and source-bound
candidate comparison, validating every displayed bead preview against its
actual MARD matrix.

No network calls, model weights or new algorithmic face identity claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

import perler_delivery as pd
import identity_fidelity as idf

SCHEMA_FRAME = "perler-identity-framing-v1"
SCHEMA_COMPARE = "perler-identity-candidate-review-v1"
MAX_CANDIDATES = 5


def require(predicate, msg):
    if not predicate:
        raise pd.PatternError(msg)


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(obj, dict), "输入 JSON 必须为对象")
    return obj


def fnt(size=18, bold=False):
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{filename}", size)
    except OSError:
        return ImageFont.load_default()


def _rgba_to_rgb(image: Image.Image, color=(255,255,255)) -> Image.Image:
    back=Image.new("RGBA", image.size, (*color,255))
    back.alpha_composite(image.convert("RGBA"))
    return back.convert("RGB")


def box_from_landmarks(path: Path, img_path: Path) -> list[float]:
    p=idf.read_landmarks(path, pd.sha_file(img_path))
    l=min(float(p[k][0]) for k in ('left_cheek','left_eye_outer','left_eye_inner'))
    r=max(float(p[k][0]) for k in ('right_cheek','right_eye_inner','right_eye_outer'))
    t=float(p['forehead'][1]); b=float(p['chin'][1])
    dx=max(0.0,r-l)*0.12; dy=max(0.0,b-t)*0.12
    return validate_box([max(0.,l-dx),max(0.,t-dy),min(1.,r+dx),min(1.,b+dy)])


def validate_box(v) -> list[float]:
    require(isinstance(v,(list,tuple)) and len(v)==4,'人脸框必须是 [x0,y0,x1,y1]')
    require(all(isinstance(x,(int,float)) and math.isfinite(float(x)) and 0.<=x<=1. for x in v),
            '人脸框必须是 0..1 内的有限归一化坐标')
    x0,y0,x1,y1=map(float,v)
    require(x1-x0>=.08 and y1-y0>=.08,'人脸框太小或方向错误')
    return [float(x) for x in v]


def choose_face(image_path: Path, manual, landmarks_path) -> tuple[list[float],str, str|None]:
    require(not (manual and landmarks_path),'不能同时使用手动脸框与关键点文件')
    if landmarks_path:
        p=Path(landmarks_path)
        return box_from_landmarks(p,image_path), 'image_hash_bound_landmarks', pd.sha_file(p)
    require(manual is not None,'必须提供实际人脸框或与图像绑定的关键点，不得自动猜测')
    return validate_box(manual),'manual_face_roi_requires_visual_check',None


def frame_geometry(size: tuple[int,int],box, target=.54, face_x=.50, face_y=.43) -> dict:
    """Choose a square crop which preserves the whole specified face rectangle."""
    W,H=size; x0,y0,x1,y1=validate_box(box)
    require(0.35 <= target <= 0.70, '目标脸高占比仅支持 0.35..0.70')
    require(.25<=face_x<=.75 and .25<=face_y<=.65,'目标脸中心位置超出安全范围')
    left,top,right,bottom=x0*W,y0*H,x1*W,y1*H
    fw=right-left;fh=bottom-top
    side=max(fh/target, fw/.66, fw, fh)
    midx=(left+right)/2; midy=(top+bottom)/2
    crop_left=midx-face_x*side; crop_top=midy-face_y*side
    # Face box must be wholly contained in the planned crop.
    require(crop_left<=left+1e-6 and crop_left+side>=right-1e-6 and
            crop_top<=top+1e-6 and crop_top+side>=bottom-1e-6,
            '选定构图会裁掉部分人脸，请调整中心比例')
    outside_l=max(0,-crop_left);outside_t=max(0,-crop_top)
    outside_r=max(0,crop_left+side-W);outside_b=max(0,crop_top+side-H)
    # Reject an overwhelming synthetic border instead of filling half the picture.
    require(max(outside_l,outside_r,outside_t,outside_b)/side<=.35,
            '面部过于贴边，按当前构图需增加过多填充；请改用较小人像或调整脸框')
    new_box=[(left-crop_left)/side,(top-crop_top)/side,
             (right-crop_left)/side,(bottom-crop_top)/side]
    return {'crop_xyxy':[crop_left,crop_top,crop_left+side,crop_top+side],
            'face_box_on_output':[round(x,6) for x in new_box],
            'face_height_fraction':round(fh/side,6),
            'padding_fraction_max':round(max(outside_l,outside_r,outside_t,outside_b)/side,6),
            'source_size':[W,H]}


def render_frame(image: Image.Image, geo: dict, size: int=1024) -> Image.Image:
    require(256 <= size <= 4096,'输出边长必须在256..4096之间')
    src=ImageOps.exif_transpose(image).convert('RGB')
    # Median corner/background, synthetic padding is provenance-marked.
    pix=np.asarray(src)
    edge=np.concatenate((pix[0],pix[-1],pix[:,0],pix[:,-1]))
    bg=tuple(int(x) for x in np.median(edge,axis=0))
    x0,y0,x1,y1=geo['crop_xyxy'];side=x1-x0
    # Construct a low-frequency border matte from real image CORNERS, not from
    # a blurred full face (which creates ghost hair/skin outside the image).
    # Synthetic padding remains clearly a non-authoritative background extension.
    if geo['padding_fraction_max'] > 0:
        b=max(1,min(src.width,src.height)//22)
        tl=np.median(pix[:b,:b].reshape(-1,3),axis=0)
        tr=np.median(pix[:b,-b:].reshape(-1,3),axis=0)
        bl=np.median(pix[-b:,:b].reshape(-1,3),axis=0)
        br=np.median(pix[-b:,-b:].reshape(-1,3),axis=0)
        corner=Image.new('RGB',(2,2))
        for xy,value in [((0,0),tl),((1,0),tr),((0,1),bl),((1,1),br)]:
            corner.putpixel(xy,tuple(int(round(v)) for v in value))
        target=corner.resize((size,size),Image.Resampling.BICUBIC)
    else:
        target=Image.new('RGB',(size,size),bg)
    region=(max(0,x0),max(0,y0),min(src.width,x1),min(src.height,y1))
    if region[2]>region[0] and region[3]>region[1]:
        # Round the output-space rectangle only once. Determinism matters.
        cx0=int(round((region[0]-x0)*size/side));cy0=int(round((region[1]-y0)*size/side))
        cx1=int(round((region[2]-x0)*size/side));cy1=int(round((region[3]-y0)*size/side))
        sw,sh=cx1-cx0,cy1-cy0
        if sw>0 and sh>0:
            crop=src.crop(region).resize((sw,sh),Image.Resampling.LANCZOS)
            if geo['padding_fraction_max'] > 0:
                alpha=Image.new('L',(sw,sh),255)
                ad=ImageDraw.Draw(alpha)
                # Edge mask fades only the bands adjacent to padded image sides;
                # human facial areas must remain in the opaque interior.
                feather=max(4,round(size*.013))
                for t in range(feather):
                    a=int(255*(t+1)/feather)
                    if x0<0: ad.line((t,0,t,sh-1),fill=a)
                    if y0<0: ad.line((0,t,sw-1,t),fill=a)
                    if x1>src.width: ad.line((sw-1-t,0,sw-1-t,sh-1),fill=a)
                    if y1>src.height: ad.line((0,sh-1-t,sw-1,sh-1-t),fill=a)
                target.paste(crop,(cx0,cy0),alpha)
            else:
                target.paste(crop,(cx0,cy0))
    return target


def draw_frame_debug(image: Image.Image, box, geo: dict) -> Image.Image:
    src=ImageOps.exif_transpose(image).convert('RGB')
    scale=min(1.0,800/max(src.size));view=src.resize((max(1,round(src.width*scale)),max(1,round(src.height*scale))))
    d=ImageDraw.Draw(view)
    crop=geo['crop_xyxy']
    d.rectangle(tuple(int(round(v*scale)) for v in crop),outline='#FFD600',width=4)
    x0,y0,x1,y1=box
    d.rectangle((int(x0*view.width),int(y0*view.height),int(x1*view.width),int(y1*view.height)),outline='#00FFFF',width=3)
    return view


def frame_prepare(args):
    source=Path(args.image);out=Path(args.out)
    require(source.is_file(),'输入图不存在')
    require(not out.exists(),'输出目录已存在，禁止覆盖')
    box,origin,lm_sha=choose_face(source,args.face,args.landmarks)
    with Image.open(source) as im:
        oriented=ImageOps.exif_transpose(im)
        geo=frame_geometry(oriented.size,box,args.target_face_height,args.face_x,args.face_y)
        framed=render_frame(im,geo,args.size)
        debug=draw_frame_debug(im,box,geo)
    out.mkdir(parents=True)
    framed.save(out/'face_first_frame.png');debug.save(out/'framing_debug.png')
    report={'schema':SCHEMA_FRAME,'status':'FRAMING_CANDIDATE_UNREVIEWED',
            'source_path':str(source.resolve()),'source_sha256':pd.sha_file(source),
            'face_roi':box,'roi_origin':origin,
            'landmarks_path':str(Path(args.landmarks).resolve()) if args.landmarks else None,
            'landmarks_sha256':lm_sha,'target_face_height':args.target_face_height,
            'face_x':args.face_x,'face_y':args.face_y,'render_size':args.size,
            'geometry':geo,'expected_face_height_beads':round(geo['face_height_fraction']*args.grid,2),
            'grid':args.grid,'output_hashes':{name:pd.sha_file(out/name) for name in ('face_first_frame.png','framing_debug.png')},
            'note':'Frame plan is a crop proposal, not proof of facial identity or likeness. Check hair/shoulders visually.'}
    write_json(out/'frame_report.json',report)
    print(json.dumps({'status':report['status'],'face_height_beads_estimate':report['expected_face_height_beads'],
                      'framing':str(out/'face_first_frame.png')},ensure_ascii=False))


def frame_verify(out: Path):
    r=load_json(out/'frame_report.json');require(r.get('schema')==SCHEMA_FRAME,'frame manifest invalid')
    source=Path(r['source_path']);require(pd.sha_file(source)==r['source_sha256'],'原图文件发生改变')
    if r['landmarks_path']:
        require(pd.sha_file(Path(r['landmarks_path']))==r['landmarks_sha256'],'关键点文件变化')
        box=box_from_landmarks(Path(r['landmarks_path']),source)
        require(np.allclose(box,r['face_roi'],atol=1e-6),'脸框与关键点不一致')
    with Image.open(source) as im:
        g=frame_geometry(ImageOps.exif_transpose(im).size,r['face_roi'],r['target_face_height'],r['face_x'],r['face_y'])
        require(g==r['geometry'],'记录的构图参数无法重现')
        expected=render_frame(im,g,r['render_size'])
        debug=draw_frame_debug(im,r['face_roi'],g)
    for name,img in [('face_first_frame.png',expected),('framing_debug.png',debug)]:
        require(pd.sha_file(out/name)==r['output_hashes'][name],f'{name}: hash changed')
        with Image.open(out/name) as observed:
            require(observed.size==img.size and observed.convert('RGB').tobytes()==img.tobytes(),
                    f'{name} 无法根据原图重新生成')
    return r


def _resolve(manifest:Path,v: str) -> Path:
    p=Path(v)
    return (p if p.is_absolute() else manifest.parent / p).resolve()


def parse_manifest(manifest:Path) -> dict:
    data=load_json(manifest)
    require(data.get('schema')==SCHEMA_COMPARE,'候选清单 schema 不符合要求')
    require(isinstance(data.get('candidates'),list) and 2<=len(data['candidates'])<=MAX_CANDIDATES,
            f'需要2至{MAX_CANDIDATES}个真实候选')
    require(isinstance(data.get('original'),str) and isinstance(data.get('palette'),str),
            '需要 original 和 palette')
    ids=[];files=[]
    for row in data['candidates']:
        require(isinstance(row,dict),'每个候选必须为对象')
        require(set(['name','cartoon','matrix','preview'])<=set(row),'候选需包含 name, cartoon, matrix, preview')
        name=row['name'];require(isinstance(name,str) and 1<=len(name)<=35,'候选名无效')
        ids.append(name)
        for k in ('cartoon','matrix','preview'):
            require(isinstance(row[k],str),f'{name}: 缺少路径 {k}')
        if row.get('face_box') is not None:validate_box(row['face_box'])
        if row.get('landmarks') and row.get('face_box'):
            raise pd.PatternError('候选脸框与关键点只能选一个')
        if row.get('art_source') is not None:
            require(isinstance(row['art_source'],str),'art_source 必须是源插画路径')
        files.append(_resolve(manifest,row['cartoon']))
    require(len(set(ids))==len(ids),'候选名不得重复')
    require(len(set(files))==len(files),'不能使用同一个卡通底图路径伪装不同候选')
    if data.get('original_face') is not None:validate_box(data['original_face'])
    if data.get('original_landmarks') and data.get('original_face'):
        raise pd.PatternError('原图脸框与关键点只能选一个')
    return data


def collect_candidates(manifest:Path) -> dict:
    m=parse_manifest(manifest)
    original=_resolve(manifest,m['original']);palette=_resolve(manifest,m['palette'])
    require(original.is_file() and palette.is_file(),'缺少原照片或色卡')
    require(pd.load_palette(palette)==pd.load_palette(pd.PALETTE),'色卡与 Skill 固定 MARD 参考色卡不一致')
    osha=pd.sha_file(original)
    if m.get('original_landmarks'):
        roi_o=box_from_landmarks(_resolve(manifest,m['original_landmarks']),original)
        roi_origin='image_hash_bound_landmarks'
    elif m.get('original_face'):
        roi_o=validate_box(m['original_face']);roi_origin='manual'
    else:
        roi_o=None;roi_origin='NOT_PROVIDED'
    entries=[];uniqart=set();dims=set()
    for row in m['candidates']:
        name=row['name']
        art,matrix,bead=(_resolve(manifest,row[k]) for k in ('cartoon','matrix','preview'))
        for path in (art,matrix,bead):require(path.is_file(),f'{name}: 缺少文件 {path}')
        art_sha=pd.sha_file(art)
        require(art_sha not in uniqart,'候选卡通底图内容完全相同，不能伪装为多候选')
        require(art_sha!=osha,'候选卡通图与原图相同，不能认定完成了卡通化')
        uniqart.add(art_sha)
        check=idf.strict_grid_preview(matrix,palette,bead)
        dims.add((check['width'],check['height']))
        if row.get('landmarks'):
            aroi=box_from_landmarks(_resolve(manifest,row['landmarks']),art)
            roi_type='image_hash_bound_landmarks'
        elif row.get('face_box'):
            aroi=validate_box(row['face_box']);roi_type='manual'
        else:
            aroi=None;roi_type='NOT_PROVIDED'
        art_source=_resolve(manifest,row['art_source']) if row.get('art_source') else None
        if art_source:require(art_source.is_file(),f'{name}: art_source 文件不存在')
        entries.append({'name':name,
            'shared_source_art_sha256':pd.sha_file(art_source) if art_source else None,
            'source_art_provenance':str(art_source) if art_source else 'UNDECLARED',
            'paths':{k:str(p.resolve()) for k,p in [('cartoon',art),('matrix',matrix),('preview',bead)]},
            'sha256':{k:pd.sha_file(p) for k,p in [('cartoon',art),('matrix',matrix),('preview',bead)]},
            'grid_validation':check,
            'face_box':aroi,'face_box_origin':roi_type,
            'note':'Face area estimated only from supplied ROI; no automatic similarity claim.'})
    require(len(dims)==1,'同批候选必须使用相同网格尺寸，不能将分辨率差当成画风提升')
    return {'schema':SCHEMA_COMPARE,'status':'HUMAN_COMPARISON_REQUIRED',
            'source_path':str(original.resolve()),'source_sha256':osha,
            'original_face_box':roi_o,'original_face_origin':roi_origin,
            'palette_path':str(palette.resolve()),'palette_sha256':pd.sha_file(palette),
            'grid_size':list(dims.pop()),'entries':entries,
            'notes':['This is a comparison, not a face identity score.',
                     'Faces and palettes must be human-reviewed. No model may self-approve.',
                     'The source photo and customer portrait must not be uploaded to public GitHub.']}


def fit_into(im:Image.Image, size:tuple[int,int], pixel=False)->Image.Image:
    return ImageOps.contain(_rgba_to_rgb(im),size,
                            Image.Resampling.NEAREST if pixel else Image.Resampling.LANCZOS)


def _roi_display(image, box, size, pixel=False):
    if box is None:
        im=Image.new('RGB',size,'#E5EBF3')
        ImageDraw.Draw(im).text((8,size[1]//2-8),'ROI not provided',font=fnt(15),fill='#425063')
        return im
    W,H=image.size
    x0,y0,x1,y1=validate_box(box)
    bounds=(max(0,math.floor(x0*W)),max(0,math.floor(y0*H)),
            min(W,math.ceil(x1*W)),min(H,math.ceil(y1*H)))
    im=image.crop(bounds)
    return fit_into(im,size,pixel)


def render_comparison(report, path:Path):
    """Generate a compact four-column multi-candidate review board."""
    original=Path(report['source_path'])
    entries=report['entries'];n=len(entries)
    CW=344;W=4*CW+48
    ROW_H=320
    canvas=Image.new('RGB',(W,112+n*ROW_H),'#F5F8FC')
    d=ImageDraw.Draw(canvas)
    d.text((20,14),'IDENTITY FIRST / CANDIDATE REVIEW',font=fnt(29,True),fill='#1B2D46')
    d.text((20,55),'Original vs cartoon vs verified MARD bead chart · NO biometric similarity score',font=fnt(17),fill='#526175')
    with Image.open(original) as o:
        orig=o.convert('RGB')
    for i,e in enumerate(entries):
        with Image.open(e['paths']['cartoon']) as image:art=image.convert('RGB')
        with Image.open(e['paths']['preview']) as image: bead=image.convert('RGBA')
        y=106+i*ROW_H
        d.text((22,y),e['name'][:34],font=fnt(19,True),fill='#152139')
        titles=['Original','Cartoon candidate','Validated bead preview','Face ROI (original/cartoon)']
        ims=[fit_into(orig,(308,210)),fit_into(art,(308,210)),fit_into(bead,(308,210),True)]
        ro=_roi_display(orig,report['original_face_box'],(152,206))
        ra=_roi_display(art,e['face_box'],(152,206))
        duo=Image.new('RGB',(308,206),'#E5EBF3');duo.paste(ro,(0,0));duo.paste(ra,(156,0));ims.append(duo)
        for j,(ttl,im) in enumerate(zip(titles,ims)):
            x=18+j*CW
            d.rounded_rectangle((x,y+36,x+326,y+277),radius=8,fill='white',outline='#D3DBE6',width=2)
            d.text((x+9,y+43),ttl,font=fnt(15,True),fill='#2C3B4D')
            canvas.paste(im,(x+9+(308-im.width)//2,y+62+(210-im.height)//2))
        d.text((22,y+287),f"{e['grid_validation']['width']}x{e['grid_validation']['height']} | {e['grid_validation']['colors']} colors | "
                f"{e['grid_validation']['beads']} beads | Human review required",font=fnt(16),fill='#263E61')
    path.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(path)


def compare_prepare(args):
    m=Path(args.manifest).resolve();out=Path(args.out)
    require(m.is_file(),'候选清单不存在');require(not out.exists(),'输出目录已存在，禁止覆盖')
    report=collect_candidates(m)
    report['manifest_path']=str(m)
    report['manifest_sha256']=pd.sha_file(m)
    out.mkdir(parents=True)
    render_comparison(report,out/'candidate_comparison.png')
    report['comparison_sha256']=pd.sha_file(out/'candidate_comparison.png')
    write_json(out/'comparison_report.json',report)
    write_json(out/'human_selection_TEMPLATE.json',{
        'schema':SCHEMA_COMPARE,'comparison_report_sha256':pd.sha_file(out/'comparison_report.json'),
        'candidate_name':None,'stage_A_face_shape_checked':False,
        'stage_B_bead_face_checked':False,'small_view_checked':False,
        'user_confirmed':False,'review_notes':''})
    print(json.dumps({'status':report['status'],'candidates':len(report['entries']),
                      'grid':report['grid_size'],'out':str(out)},ensure_ascii=False))


def compare_verify(out:Path):
    report=load_json(out/'comparison_report.json')
    require(report.get('schema')==SCHEMA_COMPARE and report.get('status')=='HUMAN_COMPARISON_REQUIRED',
            '候选审核报告格式不符')
    manifest=Path(report['manifest_path'])
    require(pd.sha_file(manifest)==report['manifest_sha256'],'候选清单已被修改')
    regenerated=collect_candidates(manifest)
    for k in regenerated:
        require(regenerated[k]==report.get(k),f'候选报告数据发生变化：{k}')
    require(pd.sha_file(out/'candidate_comparison.png')==report['comparison_sha256'],
            '候选对照图哈希变化')
    with tempfile.TemporaryDirectory() as work:
        temp=Path(work)/'recomputed.png'
        render_comparison(report,temp)
        with Image.open(temp) as a,Image.open(out/'candidate_comparison.png') as b:
            require(a.size==b.size and a.mode==b.mode and a.tobytes()==b.tobytes(),
                    '候选对照图不能从真实输入重建')
    return report


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='cmd',required=True)
    f=sub.add_parser('frame',help='Create a reversible source-bound face-first framing candidate')
    f.add_argument('--image',required=True);f.add_argument('--out',required=True)
    f.add_argument('--face',nargs=4,type=float,metavar=('X0','Y0','X1','Y1'))
    f.add_argument('--landmarks');f.add_argument('--grid',type=int,default=87)
    f.add_argument('--target-face-height',type=float,default=.54)
    f.add_argument('--face-x',type=float,default=.5);f.add_argument('--face-y',type=float,default=.43)
    f.add_argument('--size',type=int,default=1024)
    v=sub.add_parser('verify-frame');v.add_argument('--prepared',required=True)
    c=sub.add_parser('compare');c.add_argument('--manifest',required=True);c.add_argument('--out',required=True)
    vc=sub.add_parser('verify-compare');vc.add_argument('--prepared',required=True)
    args=ap.parse_args(argv)
    try:
        if args.cmd=='frame':
            require(29<=args.grid<=145,'grid 29..145')
            frame_prepare(args)
        elif args.cmd=='verify-frame':
            r=frame_verify(Path(args.prepared));print('VERIFIED: face-first crop matches source:',r['source_sha256'][:12])
        elif args.cmd=='compare':compare_prepare(args)
        else:
            r=compare_verify(Path(args.prepared));print('VERIFIED:',len(r['entries']),'true-MARD candidate previews; likeness still requires human review')
    except (pd.PatternError,KeyError,OSError,ValueError,TypeError,IndexError) as e:
        ap.exit(2,'FAILED: '+str(e)+'\n')


if __name__=='__main__':main()
