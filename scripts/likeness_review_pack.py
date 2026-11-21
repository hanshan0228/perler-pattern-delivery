#!/usr/bin/env python3
"""Two-stage likeness review pack for cartoon fuse-bead portrait candidates.

This tool never identifies a person or claims an identity similarity score.
It checks the *real* color-code matrix, displays source -> cartoon -> bead
at controlled comparison scales, and requires separate human approval for
both lossy stages. A SHA-256 is an integrity fingerprint, not a signature.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import perler_delivery as pd
import identity_fidelity as idf

SCHEMA = "perler-likeness-review-v1"
REVIEW_A = (
    "facial_geometry_preserved",
    "eyes_nose_mouth_proportions_preserved",
    "expression_pose_and_hairline_preserved",
    "no_unwanted_beautification_or_face_swap",
)
REVIEW_B = (
    "recognizable_at_full_pattern_size",
    "recognizable_at_small_preview_size",
    "eyes_nose_mouth_remain_distinct",
    "silhouette_and_hair_remain_readable",
)
DISPLAY_SIZES = (1, 2, 4)  # screen pixels per bead, NOT physical scale


def require(ok: bool, message: str):
    if not ok:
        raise pd.PatternError(message)


def _font(n: int, bold: bool = False):
    p = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans" + ("-Bold.ttf" if bold else ".ttf"))
    try:
        return ImageFont.truetype(str(p), n)
    except OSError:
        return ImageFont.load_default()


def parse_box(values: list[float] | None, label: str):
    if values is None:
        return None
    require(len(values) == 4, f"{label}: face-box 需要 4 个归一化坐标")
    require(all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in values),
            f"{label}: face-box 坐标必须在 0..1")
    x0, y0, x1, y1 = values
    require(x1 > x0 + 0.08 and y1 > y0 + 0.08,
            f"{label}: 人脸矩形太小或顺序错误")
    return [round(v, 6) for v in values]


def box_from_landmarks(path: Path, image_sha: str):
    pts = idf.read_landmarks(path, image_sha)
    x = [float(pts[k][0]) for k in ("left_cheek", "right_cheek", "left_eye_outer", "right_eye_outer")]
    y = [float(pts[k][1]) for k in ("forehead", "chin", "left_cheek", "right_cheek")]
    lx, rx = min(x), max(x)
    ty, by = min(y), max(y)
    dx = (rx - lx) * 0.12
    dy = (by - ty) * 0.13
    return parse_box([max(0.0, lx - dx), max(0.0, ty - dy),
                      min(1.0, rx + dx), min(1.0, by + dy)], "landmark face")


def resolve_boxes(args, hashes):
    boxes, sources, landmark_hashes = {}, {}, {}
    for k in ("original", "cartoon", "bead"):
        manual = getattr(args, f"face_{k}", None)
        landmarks = getattr(args, f"landmarks_{k}", None)
        require(not (manual and landmarks), f"{k}: 请在手工脸框和关键点之间选择一种")
        if manual:
            boxes[k] = parse_box(manual, k)
            sources[k] = "manual_normalized_roi"
            landmark_hashes[k] = None
        elif landmarks:
            path = Path(landmarks)
            boxes[k] = box_from_landmarks(path, hashes[k])
            sources[k] = "image_sha_bound_landmarks"
            landmark_hashes[k] = pd.sha_file(path)
        else:
            boxes[k] = None
            sources[k] = "NOT_PROVIDED"
            landmark_hashes[k] = None
    return boxes, sources, landmark_hashes


def _box_pixels(box, size):
    w, h = size
    x0, y0, x1, y1 = box
    return (max(0, math.floor(x0 * w)), max(0, math.floor(y0 * h)),
            min(w, math.ceil(x1 * w)), min(h, math.ceil(y1 * h)))


def _opaque(im: Image.Image) -> Image.Image:
    rgba = im.convert("RGBA")
    base = Image.new("RGBA", rgba.size, "white")
    base.alpha_composite(rgba)
    return base.convert("RGB")


def _fit(im, size: tuple[int,int], is_bead=False):
    return ImageOps.contain(_opaque(im), size,
                            Image.Resampling.NEAREST if is_bead else Image.Resampling.LANCZOS)


def _tile(canvas, img, xy, wh, source, draw, title):
    x, y = xy; w, h = wh
    draw.rectangle((x, y, x+w-1, y+h-1), fill="white", outline="#d7dce6", width=2)
    draw.text((x+14,y+12), title, font=_font(19, True), fill="#202a42")
    thumb=_fit(img, (w-24,h-52), source == "bead")
    xx=x+(w-thumb.width)//2; yy=y+42+(h-52-thumb.height)//2
    canvas.paste(thumb,(xx,yy))


def make_montage(original: Path, cartoon: Path, bead: Path, boxes: dict, output: Path, sizes=(87,87)):
    images={k:Image.open(p) for k,p in (("original",original),("cartoon",cartoon),("bead",bead))}
    W,H=1600,1560
    canvas=Image.new("RGB",(W,H),"#f6f8fc")
    draw=ImageDraw.Draw(canvas)
    draw.text((45,20), "LIKENESS REVIEW / TWO-STAGE CHECK",font=_font(30,True),fill="#17213b")
    draw.text((45,63),"Stage A: Original vs cartoon. Stage B: Cartoon vs actual bead matrix.",
              font=_font(18),fill="#444b59")
    keys=("original","cartoon","bead")
    for i,k in enumerate(keys):
        x=34+527*i
        _tile(canvas,images[k],(x,100),(500,530),k,draw,
              {"original":"01  Original photo","cartoon":"02  AI cartoon base","bead":"03  Verified bead preview"}[k])
    draw.text((45,656),"FACIAL DETAIL / Matched regions (manual or image-bound landmarks)",
              font=_font(23,True),fill="#17213b")
    for i,k in enumerate(keys):
        x=34+527*i
        roi=boxes.get(k)
        if roi is None:
            im=Image.new("RGB",(240,240),"#e5eaf0")
            ImageDraw.Draw(im).text((15,110),"ROI NOT PROVIDED",fill="#49515e",font=_font(18,True))
            title="Not assessed: face crop missing"
        else:
            im=images[k].crop(_box_pixels(roi,images[k].size))
            title="ROI: " + ",".join(f"{v:.2f}" for v in roi)
        _tile(canvas,im,(x,692),(500,360),k,draw,title)
    draw.text((45,1076),"SMALL-PREVIEW CHECK: exact nearest-neighbor bead grid, no new pixels",
              font=_font(23,True),fill="#17213b")
    with Image.open(bead) as bg:
        grid=_opaque(bg).resize(sizes,Image.Resampling.NEAREST)
    for i,scale in enumerate(DISPLAY_SIZES):
        view=grid.resize((sizes[0]*scale,sizes[1]*scale),Image.Resampling.NEAREST)
        x=(95,550,1080)[i]; y=1130
        canvas.paste(view,(x,y))
        draw.text((x,y+view.height+8),f"{scale}px / bead (screen only)",
                  font=_font(15),fill="#26354b")
    draw.text((45,1530),"NO FACE-ID SCORE. Human must review both stages. 5 mm beads != screen pixels.",
              font=_font(17),fill="#8c3d32")
    output.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(output)
    for obj in images.values(): obj.close()


def prepare(args):
    paths={k:Path(getattr(args,k)) for k in ("original","cartoon","bead","matrix","palette")}
    out=Path(args.out)
    require(not out.exists(),"审核目录已存在，不能覆盖")
    for k,p in paths.items():
        require(p.is_file(),f"缺少 {k} 文件: {p}")
    hashes={k:pd.sha_file(p) for k,p in paths.items()}
    require(hashes["original"]!=hashes["cartoon"],"照片与卡通底图相同；不能作为两阶段图")
    # Never accept only a fabricated pattern image. Bead render MUST equal true matrix.
    checked=idf.strict_grid_preview(paths["matrix"],paths["palette"],paths["bead"])
    require(pd.load_palette(paths['palette'])==pd.load_palette(pd.PALETTE),
            '色卡与仓库固定MARD参考色卡不一致')
    boxes,sources,lm_hashes=resolve_boxes(args,hashes)
    out.mkdir(parents=True)
    montage=out/'likeness_review.png'
    make_montage(paths['original'],paths['cartoon'],paths['bead'],boxes,montage,
                 (checked['width'],checked['height']))
    with Image.open(paths['bead']) as im:
        native=im.resize((checked['width'],checked['height']),Image.Resampling.NEAREST)
    require(native.size==(checked['width'],checked['height']),'原子预览尺寸不一致')
    for scale in DISPLAY_SIZES:
        native.resize((checked['width']*scale,checked['height']*scale),
                      Image.Resampling.NEAREST).save(out/f'bead_view_{scale}x.png')
    report={
        'schema':SCHEMA,'status':'HUMAN_REVIEW_REQUIRED',
        'input_paths':{k:str(v.resolve()) for k,v in paths.items()},
        'sha256':hashes,
        'chart':checked,
        'face_boxes':boxes,'face_box_sources':sources,'landmark_file_sha256':lm_hashes,
        'landmark_paths':{k:str(Path(getattr(args,f'landmarks_{k}')).resolve()) if getattr(args,f'landmarks_{k}',None) else None
                          for k in ('original','cartoon','bead')},
        'face_crop_status':'READY_FOR_MANUAL_COMPARISON' if all(boxes.values()) else 'NOT_EVALUATED_MISSING_FACE_BOXES',
        'outputs':{p.name:pd.sha_file(p) for p in sorted(out.glob('*.png'))},
        'notes':[
            'Full portrait, face crop and 1/2/4 pixel-per-bead previews are descriptive, not validated likeness tests.',
            'Bounding boxes are manually provided or derived from image-bound points; both require visual inspection.',
            'Matrix-to-image agreement checks construction data, never identity, beauty or biometric similarity.',
            'This tool never authenticates the reviewer. User confirmation must occur outside this script.'
        ],
    }
    idf.write_json(out/'likeness_report.json',report)
    template={
        'schema':SCHEMA,'report_sha256':pd.sha_file(out/'likeness_report.json'),
        'stage_A_original_to_cartoon':{k:False for k in REVIEW_A},
        'stage_B_cartoon_to_bead':{k:False for k in REVIEW_B},
        'small_preview_reviewed':False,
        'reviewer_type':'human', 'user_confirmed':False,
        'notes_original_to_cartoon':'', 'notes_cartoon_to_bead':'',
    }
    idf.write_json(out/'user_review_TEMPLATE.json',template)
    print(json.dumps({'status':report['status'],'checked_cells':checked['cells_checked'],
                      'face_crops':report['face_crop_status'],'out':str(out)},ensure_ascii=False))


def verify(prepared: Path):
    report=idf.read_json(prepared/'likeness_report.json')
    require(report.get('schema')==SCHEMA and report.get('status')=='HUMAN_REVIEW_REQUIRED',
            '审核报告版本或状态不符合要求')
    paths={k:Path(v) for k,v in report['input_paths'].items()}
    for key,path in paths.items():
        require(pd.sha_file(path)==report['sha256'][key],f'{key} 文件已发生变化')
    checked=idf.strict_grid_preview(paths['matrix'],paths['palette'],paths['bead'])
    require(checked==report['chart'],'当前拼豆矩阵与审核报告不一致')
    for name,path in report.get('landmark_paths',{}).items():
        if path:
            require(pd.sha_file(Path(path))==report['landmark_file_sha256'][name],
                    f'{name} 关键点文件已发生变化')
    expected_output_files={'likeness_review.png',*(f'bead_view_{s}x.png' for s in DISPLAY_SIZES)}
    require(set(report['outputs'])==expected_output_files,'审核预览清单不完整')
    for filename,sha in report['outputs'].items():
        require(pd.sha_file(prepared/filename)==sha,f'审核预览已改变：{filename}')
    # Revalidate thumbnail pixels even if a malicious JSON rewrite recalculates hashes.
    rows=pd.read_matrix(paths['matrix']);pal=pd.load_palette(paths['palette'])
    expected_pixels=pd.semantic_image(rows,pal).convert('RGBA')
    for scale in DISPLAY_SIZES:
        target=prepared/f'bead_view_{scale}x.png'
        with Image.open(target) as actual:
            reference=expected_pixels.resize((expected_pixels.width*scale,expected_pixels.height*scale),
                                              Image.Resampling.NEAREST)
            require(actual.size==reference.size and
                    actual.convert('RGBA').tobytes()==reference.tobytes(),
                    f'小尺寸像素预览不符合真实矩阵: {scale}x')
    # Defense against re-hashing a tampered montage inside the report: regenerate.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        expected=Path(tmp)/'expected.png'
        make_montage(paths['original'],paths['cartoon'],paths['bead'],
                     report['face_boxes'],expected,(checked['width'],checked['height']))
        with Image.open(expected) as e,Image.open(prepared/'likeness_review.png') as actual:
            require(e.mode==actual.mode and e.size==actual.size and e.tobytes()==actual.tobytes(),
                    '审核大图无法从已绑定的图像重现')
    return report


def attest(args):
    root=Path(args.prepared)
    report=verify(root)
    review=idf.read_json(Path(args.review))
    require(report['face_crop_status']=='READY_FOR_MANUAL_COMPARISON',
            '缺少全部三张图的人脸区域标注，禁止把审核标为完整')
    require(review.get('schema')==SCHEMA and
            review.get('report_sha256')==pd.sha_file(root/'likeness_report.json'),
            '审核记录与准备数据不匹配或过期')
    for phase,keys in [('stage_A_original_to_cartoon',REVIEW_A),('stage_B_cartoon_to_bead',REVIEW_B)]:
        entries=review.get(phase,{})
        require(set(entries)==set(keys) and all(entries.get(x) is True for x in keys),
                f'{phase} 未经完整人工检查；不能批准')
    require(review.get('small_preview_reviewed') is True, '实际小尺寸预览未经人工检查')
    require(review.get('reviewer_type')=='human' and review.get('user_confirmed') is True,
            '用户尚未明确确认；模型不得自动代填')
    for note in ('notes_original_to_cartoon','notes_cartoon_to_bead'):
        require(isinstance(review.get(note),str) and len(review[note].strip())>=20,
                f'{note}: 必须提供具体视觉观察')
    target=Path(args.out)
    require(not target.exists(),'审核确认记录不可覆盖')
    proof={'schema':SCHEMA,'status':'HUMAN_ATTESTATION_RECORDED_NOT_BIOMETRIC_VERIFICATION',
           'review_sha256':pd.sha_file(Path(args.review))}
    # Do not assume the caller is authenticated; this is only a recorded claim.
    proof['report_sha256']=pd.sha_file(root/'likeness_report.json')
    proof['chart_digest']=report['chart']['matrix_digest']
    proof['limits']='Software cannot prove the person pictured is the same individual or authenticate who reviewed it.'
    idf.write_json(target,proof)
    print('Human attestation recorded (not biometric identity certification).')


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='cmd',required=True)
    pp=sub.add_parser('prepare')
    for k in ('original','cartoon','bead','matrix','palette','out'):
        pp.add_argument('--'+k,required=True)
    for k in ('original','cartoon','bead'):
        pp.add_argument('--face-'+k,nargs=4,type=float,metavar=('X0','Y0','X1','Y1'))
        pp.add_argument('--landmarks-'+k)
    vv=sub.add_parser('verify');vv.add_argument('--prepared',required=True)
    aa=sub.add_parser('attest');aa.add_argument('--prepared',required=True)
    aa.add_argument('--review',required=True);aa.add_argument('--out',required=True)
    args=ap.parse_args(argv)
    try:
        if args.cmd=='prepare':prepare(args)
        elif args.cmd=='verify':
            verified=verify(Path(args.prepared))
            print(json.dumps({'status':'INTEGRITY_VERIFIED','face_roi':verified['face_crop_status']},ensure_ascii=False))
        else:attest(args)
    except (pd.PatternError,OSError,KeyError,ValueError,TypeError) as ex:
        ap.exit(2,'FAILED: '+str(ex)+'\n')


if __name__=='__main__':main()
