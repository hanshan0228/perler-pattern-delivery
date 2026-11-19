#!/usr/bin/env python3
"""Three-stage, provenance-bound portrait fidelity review for fuse-bead candidates.

This is NOT face identification and never emits an uncalibrated identity score.
It checks the actual bead color grid, compares optional human/MediaPipe facial
geometry across photo -> cartoon -> bead, and requires explicit human review.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps, ImageFont
import perler_delivery as pd

SCHEMA = 'perler-identity-fidelity-v1'
LANDMARK_SCHEMA = 'perler-face-points-v1'
REVIEW_CHECKS = (
    'original_to_cartoon_recognizable',
    'cartoon_to_bead_recognizable',
    'face_proportions_preserved',
    'pose_and_expression_preserved',
    'critical_features_readable_at_actual_grid',
)
# Stable MediaPipe Face Mesh indices, not a face embedding / identity model.
INDICES = {
    'left_eye_outer': 33, 'left_eye_inner': 133,
    'right_eye_inner': 362, 'right_eye_outer': 263,
    'nose_tip': 1,
    'mouth_left': 61, 'mouth_right': 291,
    'upper_lip': 13, 'lower_lip': 14,
    'chin': 152, 'forehead': 10,
    'left_cheek': 234, 'right_cheek': 454,
}
LABELS = ['original', 'cartoon', 'bead']
GEOMETRIC_SCREENING = {
    # Exploratory normalized geometry alerts, NOT calibrated identity thresholds.
    'original_to_cartoon': 0.28,
    'cartoon_to_bead': 0.32,
    'original_to_bead': 0.38,
}


def require(ok: bool, msg: str):
    if not ok:
        raise pd.PatternError(msg)


def write_json(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def read_json(p: Path):
    return json.loads(p.read_text(encoding='utf-8'))


def file_sha(p: Path):
    require(p.is_file(), f'找不到文件: {p}')
    return pd.sha_file(p)


def palette_rgb(pal, code: str):
    if code == 'EMPTY': return (255, 255, 255, 255)
    h = pal[code].lstrip('#')
    return (*[int(h[i:i + 2], 16) for i in (0, 2, 4)], 255)


def strict_grid_preview(matrix: Path, palette: Path, preview: Path) -> dict:
    """Verify a pure pixel preview, NOT a rendered chart that has labels/gridlines."""
    rows = pd.read_matrix(matrix)
    pal = pd.load_palette(palette)
    counts, empty, w, h = pd.stats(rows, pal)
    expected = pd.semantic_image(rows, pal).convert('RGBA')
    with Image.open(preview) as src:
        require(src.format == 'PNG', '拼豆预览必须为 PNG，不能使用 JPEG')
        require(src.width >= w and src.height >= h and src.width % w == 0 and src.height % h == 0,
                f'预览尺寸 {src.size} 不是矩阵 {w}x{h} 的整数倍，无法保证逐格一致')
        sw, sh = src.width // w, src.height // h
        require(sw == sh, '预览的水平/垂直格子缩放比例不同，禁止使用变形图像')
        require(sw <= 100, '预览比例过大，拒绝潜在的异常输入')
        # Source may contain an RGB image of the same cells, or RGBA transparency.
        actual = np.asarray(src.convert('RGBA'), dtype=np.uint8)
        exp = np.asarray(expected, dtype=np.uint8)
        # If cells are all solid RGB, compare canonical RGBA for non-empty cells,
        # and permit white rendered background for explicit EMPTY cells.
        mismatch = 0
        for y, row in enumerate(rows):
            for x, code in enumerate(row):
                block = actual[y*sw:(y+1)*sw, x*sw:(x+1)*sw]
                wanted = np.asarray(palette_rgb(pal, code), dtype=np.uint8)
                if code == 'EMPTY':
                    # only transparent or opaque white, not colored pixel noise
                    valid = ((block[:, :, 3] == 0) | ((block[:, :, :3] == 255).all(axis=2) & (block[:, :, 3] == 255))).all()
                else:
                    valid = bool((block == wanted).all())
                mismatch += 0 if valid else 1
        require(mismatch == 0, f'拼豆图像与真实矩阵不一致: {mismatch} 格; 拒绝视觉审核')
    return {
        'width':w,'height':h,'colors':len(counts),'beads':sum(counts.values()),
        'empty':empty,'cells_checked':w*h,'mismatched_cells':mismatch,
        'matrix_digest':pd.digest_codes(rows),
        'preview_scale':sw,'preview_verified':True,
    }


def read_landmarks(path: Path, image_sha: str):
    data = read_json(path)
    require(data.get('schema') == LANDMARK_SCHEMA, f'关键点文件版本不匹配: {path}')
    require(data.get('image_sha256') == image_sha, f'关键点文件与图像哈希不匹配: {path}')
    require(data.get('source') in {'mediapipe','manual'},'未知关键点来源')
    require(data.get('face_count') == 1,'必须仅检测到一张人脸')
    pts = data.get('points')
    require(isinstance(pts, dict) and set(pts) == set(INDICES),'关键点命名不完整或存在未知项')
    out = {}
    for k, xy in pts.items():
        require(isinstance(xy,list) and len(xy)==2,'关键点必须为 [x,y] 数组')
        require(all(isinstance(t,(int,float)) and math.isfinite(float(t)) and 0<=t<=1 for t in xy),
                '关键点坐标必须是 0..1 的有限数')
        out[k] = np.asarray(xy,dtype=np.float64)
    lo = (out['left_eye_outer'] + out['left_eye_inner']) / 2
    ro = (out['right_eye_outer'] + out['right_eye_inner']) / 2
    require(float(np.linalg.norm(lo-ro))>0.025,'眼间距太小，无法进行几何归一化')
    return out


def _normalized_points(pts, width: int, height: int):
    """Normalize geometry in original pixel aspect, using eye spacing and angle.

    A rotation and uniform scale align the eyes, but do not arbitrarily warp
    face components. Thus shape differences remain measurable.
    """
    coords = {k: np.array([v[0]*width,v[1]*height], dtype=np.float64) for k,v in pts.items()}
    left = (coords['left_eye_outer']+coords['left_eye_inner'])/2
    right=(coords['right_eye_outer']+coords['right_eye_inner'])/2
    vec=right-left
    scale=float(np.linalg.norm(vec))
    require(scale>1e-6,'眼间距为零')
    angle=math.atan2(float(vec[1]),float(vec[0]))
    rot=np.array([[math.cos(angle),math.sin(angle)],[-math.sin(angle),math.cos(angle)]])
    mid=(left+right)/2
    return {k:rot @ ((v-mid)/scale) for k,v in coords.items()}


def _feature_ratios(points):
    eye_l=(points['left_eye_outer']+points['left_eye_inner'])/2
    eye_r=(points['right_eye_outer']+points['right_eye_inner'])/2
    eye_mid=(eye_l+eye_r)/2
    def distance(a,b):return float(np.linalg.norm(a-b))
    return {
        'mouth_width_over_eye_spacing':distance(points['mouth_left'],points['mouth_right']),
        'cheek_width_over_eye_spacing':distance(points['left_cheek'],points['right_cheek']),
        'eye_to_nose_over_eye_spacing':distance(eye_mid,points['nose_tip']),
        'eye_to_mouth_over_eye_spacing':distance(eye_mid,(points['mouth_left']+points['mouth_right'])/2),
        'eye_to_chin_over_eye_spacing':distance(eye_mid,points['chin']),
        'upper_lower_lip_gap_over_eye_spacing':distance(points['upper_lip'],points['lower_lip']),
    }


def geometry_compare(a: dict, b: dict, shape_a: tuple[int,int], shape_b: tuple[int,int], stage: str):
    pa=_normalized_points(a,*shape_a)
    pb=_normalized_points(b,*shape_b)
    diffs={k:round(float(np.linalg.norm(pa[k]-pb[k])),5) for k in INDICES}
    vals=np.array(list(diffs.values()))
    ra, rb=_feature_ratios(pa),_feature_ratios(pb)
    ratios={k:{'reference':round(ra[k],5),'candidate':round(rb[k],5),
               'relative_change':round((rb[k]-ra[k])/max(ra[k],1e-6),5)} for k in ra}
    rmse=round(float(np.sqrt(np.mean(vals*vals))),5)
    return {
        'metric':'landmark_geometry_eye_aligned_normalized_rmse_not_identity_similarity',
        'rmse':rmse,
        'max_landmark_displacement':round(float(vals.max()),5),
        'landmark_displacement':diffs,
        'feature_ratios':ratios,
        'screening_threshold_uncalibrated':GEOMETRIC_SCREENING[stage],
        'screening_alert':rmse > GEOMETRIC_SCREENING[stage],
    }


def pixel_resolution_budget(points: dict | None, grid_w: int, grid_h: int) -> dict:
    """Count how many REAL BEAD CELLS facial structures occupy.

    These are practical resolution diagnostics, not calibrated recognition scores.
    Require a genuine landmark record bound to the bead-preview SHA.
    """
    if points is None:
        return {'status': 'NOT_EVALUATED_LANDMARKS_MISSING',
                'reason': '缺少与当前拼豆预览哈希绑定的有效人脸关键点；不可估计五官像素预算'}
    def pt(name):
        xy = points[name]
        return np.array([float(xy[0]) * grid_w, float(xy[1]) * grid_h], dtype=float)
    def dist(a, b):
        return float(np.linalg.norm(a - b))
    left_eye = (pt('left_eye_outer') + pt('left_eye_inner')) / 2
    right_eye = (pt('right_eye_outer') + pt('right_eye_inner')) / 2
    eye_gap = dist(left_eye, right_eye)
    mouth_width = dist(pt('mouth_left'), pt('mouth_right'))
    face_width = dist(pt('left_cheek'), pt('right_cheek'))
    face_height = dist(pt('forehead'), pt('chin'))
    features = {
        'eye_center_spacing_beads': round(eye_gap, 2),
        'mouth_width_beads': round(mouth_width, 2),
        'cheek_span_beads': round(face_width, 2),
        'forehead_to_chin_beads': round(face_height, 2),
    }
    # Heuristic inspection warnings only; never determine resemblance automatically.
    limits = {
        'eye_center_spacing_beads': 7,
        'mouth_width_beads': 4,
        'cheek_span_beads': 14,
        'forehead_to_chin_beads': 20,
    }
    alerts = [f'{k} below indicative {limits[k]}-bead budget'
              for k, v in features.items() if v < limits[k]]
    return {
        'status': 'HEURISTIC_SCREEN_ONLY',
        'features': features,
        'illustrative_thresholds_beads': limits,
        'warnings': alerts,
        'note': ('Face resolution is not a face-ID score. Such warnings help decide whether '
                 'to crop tighter or increase grid dimensions; thresholds are NOT validated.'),
    }


def make_contact_sheet(images: dict, output: Path):
    W,H=1650,790
    canvas=Image.new('RGB',(W,H),'#F7F3EF')
    d=ImageDraw.Draw(canvas)
    titles={'original':'01 ORIGINAL PHOTO','cartoon':'02 CARTOON REFERENCE','bead':'03 VERIFIED BEAD GRID'}
    for i,k in enumerate(LABELS):
        img=Image.open(images[k]).convert('RGBA')
        bg=Image.new('RGBA',img.size,'white')
        bg.alpha_composite(img)
        comp=ImageOps.contain(bg.convert('RGB'),(515,650),Image.Resampling.NEAREST if k=='bead' else Image.Resampling.LANCZOS)
        x=16+i*548+(515-comp.width)//2; y=52+(650-comp.height)//2
        canvas.paste(comp,(x,y))
        d.text((24+i*548,20),titles[k],fill='#29252C')
    d.text((18,733),'Geometry alerts are NOT identity scores. Human resemblance review is required.',fill='#492F3B')
    canvas.save(output)


def prepare(args):
    original, cartoon, bead = (Path(args.original),Path(args.cartoon),Path(args.bead))
    matrix,palette,out=Path(args.matrix),Path(args.palette),Path(args.out)
    require(not out.exists(),f'输出目录已存在: {out}; 不覆盖历史审计')
    hashes={k:file_sha(p) for k,p in zip(LABELS,(original,cartoon,bead))}
    require(hashes['original']!=hashes['cartoon'],'原照与卡通图文件完全一致，不是卡通化结果')
    matrix_hash,palette_hash=file_sha(matrix),file_sha(palette)
    chart=strict_grid_preview(matrix,palette,bead)
    pictures={k:Path(x) for k,x in zip(LABELS,(original,cartoon,bead))}
    dimensions={}
    for k, v in pictures.items():
        with Image.open(v) as img:
            dimensions[k]=img.size
    landmarks={
        'original':args.landmarks_original,
        'cartoon':args.landmarks_cartoon,
        'bead':args.landmarks_bead,
    }
    parsed={}
    for key,p in landmarks.items():
        if p:
            parsed[key]=read_landmarks(Path(p),hashes[key])
    geometry={}
    for name,first,second in [('original_to_cartoon','original','cartoon'),
                              ('cartoon_to_bead','cartoon','bead'),
                              ('original_to_bead','original','bead')]:
        if first in parsed and second in parsed:
            geometry[name]=geometry_compare(parsed[first],parsed[second],dimensions[first],dimensions[second],name)
        else:
            geometry[name]={'status':'NOT_EVALUATED_LANDMARKS_MISSING',
                            'reason':f'需要 {first}、{second} 的有效关键点文件（与当前图像SHA一致）'}
    budget=pixel_resolution_budget(parsed.get('bead'),chart['width'],chart['height'])
    out.mkdir(parents=True)
    make_contact_sheet(pictures,out/'three_stage_comparison.png')
    report={
        'schema':SCHEMA, 'status':'REVIEW_REQUIRED',
        'image_sha256':hashes,'matrix_sha256':matrix_hash,'palette_sha256':palette_hash,
        'input_paths':{**{k:str(v.resolve()) for k,v in pictures.items()},
                       'matrix':str(matrix.resolve()),'palette':str(palette.resolve())},
        'landmark_paths':{k:str(Path(v).resolve()) if v else None for k,v in landmarks.items()},
        'landmark_sha256':{k:file_sha(Path(v)) if v else None for k,v in landmarks.items()},
        'matrix_file_digest':chart['matrix_digest'],
        'chart':chart,'geometry':geometry,'bead_face_resolution_budget':budget,
        'landmark_source':{k:read_json(Path(v))['source'] if v else 'NOT_PROVIDED' for k,v in landmarks.items()},
        'comparison_sha256':file_sha(out/'three_stage_comparison.png'),
        'limitations':[
            'Normalized facial geometry is not person identification or a validated identity score.',
            'Cartoon and low-resolution bead faces may make automatic landmark detection unreliable.',
            'No objective threshold replaces explicit human judgment on real resemblance.',
        ],
    }
    write_json(out/'identity_report.json',report)
    review={
        'schema':SCHEMA, 'comparison_sha256':report['comparison_sha256'],
        'matrix_digest':chart['matrix_digest'], 'image_sha256':hashes,
        'checks':{k:False for k in REVIEW_CHECKS},
        'notes':'', 'reviewer_type':'human', 'user_confirmed':False,
        'acknowledge_geometry_alerts':False,
        'acknowledge_resolution_warnings':False,
    }
    write_json(out/'human_review_TEMPLATE.json',review)
    print('REVIEW REQUIRED: real grid checked; image comparison prepared; facial geometry needs valid landmarks and human assessment.')


def evaluate(args):
    root=Path(args.prepared)
    report=read_json(root/'identity_report.json')
    review=read_json(Path(args.review))
    inputs=report.get('input_paths',{})
    for key,sha in report.get('image_sha256',{}).items():
        require(file_sha(Path(inputs.get(key,'')))==sha, f'源图发生变化: {key}')
    require(file_sha(Path(inputs.get('matrix','')))==report['matrix_sha256'],'原矩阵发生变化')
    require(file_sha(Path(inputs.get('palette','')))==report['palette_sha256'],'原色卡发生变化')
    strict_grid_preview(Path(inputs['matrix']),Path(inputs['palette']),Path(inputs['bead']))
    for key,path in report.get('landmark_paths',{}).items():
        if path:
            require(file_sha(Path(path))==report['landmark_sha256'][key],f'关键点文件发生变化: {key}')
    require(report.get('schema')==SCHEMA and report.get('status')=='REVIEW_REQUIRED','invalid identity assessment')
    for key in ('schema','comparison_sha256','matrix_digest','image_sha256'):
        expected=report['matrix_file_digest'] if key=='matrix_digest' else report[key]
        require(review.get(key)==expected,'人工审核记录与当前图像/矩阵版本不一致')
    require(file_sha(root/'three_stage_comparison.png')==report['comparison_sha256'],'对照图被修改')
    require(all(review.get('checks',{}).get(x) is True for x in REVIEW_CHECKS),
            '人工审核未全部通过，禁止宣称人物相似')
    require(review.get('reviewer_type')=='human' and review.get('user_confirmed') is True,
            '必须获得真实用户确认；模型不能自动替用户批准')
    require(isinstance(review.get('notes'),str) and len(review['notes'].strip())>=20,
            '需要填写具体的五官/姿态相似性观察，不接受空白审核')
    alerts=[k for k,v in report['geometry'].items() if v.get('screening_alert')]
    budget_warnings=report.get('bead_face_resolution_budget',{}).get('warnings',[])
    if budget_warnings:
        require(review.get('acknowledge_resolution_warnings') is True,
                '拼豆五官分辨率过低的提示需用户明确确认，建议放大主体或增加格数')
    if alerts:
        require(review.get('acknowledge_geometry_alerts') is True,
                '出现几何偏差预警，需要用户明确确认，不得自动放行')
    destination=Path(args.out)
    require(not destination.exists(),'审核结果文件已存在，不允许覆盖')
    result={
        'schema':SCHEMA,'status':'HUMAN_ATTESTED_NOT_AUTOMATICALLY_CERTIFIED',
        'reviewed_image_sha256':report['image_sha256'],
        'matrix_digest':report['matrix_file_digest'],
        'comparison_sha256':report['comparison_sha256'],
        'assessment_sha256':file_sha(root/'identity_report.json'),
        'review_file_sha256':file_sha(Path(args.review)),
        'geometry_warnings':alerts, 'resolution_budget_warnings':budget_warnings,
        'note':'Records claimed human approval; software cannot independently verify the reviewer or true identity.',
    }
    destination.parent.mkdir(parents=True,exist_ok=True)
    write_json(destination,result)
    print('REVIEW RECORD CREATED; no claim of algorithmic identity certification; original MASTER untouched.')



def freeze_reviewed(args):
    """Production entrypoint: freeze only a chart with bound human attestation.

    This enforces workflow provenance, NOT absolute biometric identity.
    The older low-level `perler_delivery.py freeze` remains for legacy imports.
    """
    root = Path(args.prepared)
    report = read_json(root/'identity_report.json')
    attested = read_json(Path(args.attested))
    review = read_json(Path(args.review))
    require(report.get('schema')==SCHEMA and attested.get('schema')==SCHEMA,
            '身份审核文件版本不匹配')
    require(attested.get('status')=='HUMAN_ATTESTED_NOT_AUTOMATICALLY_CERTIFIED',
            '尚未取得人工审核记录，拒绝冻结 MASTER')
    require(attested.get('assessment_sha256')==file_sha(root/'identity_report.json'),
            '人工确认后原始审计报告被修改')
    require(attested.get('matrix_digest')==report.get('matrix_file_digest') and
            attested.get('comparison_sha256')==report.get('comparison_sha256') and
            attested.get('reviewed_image_sha256')==report.get('image_sha256'),
            '人工确认对象与准备数据不一致')
    require(attested.get('review_file_sha256')==file_sha(Path(args.review)),
            '人工确认后复核记录被修改')
    require(review.get('user_confirmed') is True and review.get('reviewer_type')=='human' and
            all(review.get('checks',{}).get(k) is True for k in REVIEW_CHECKS),
            '用户确认信息不完整，拒绝冻结')
    inputs=report.get('input_paths',{})
    for key,sha in report['image_sha256'].items():
        require(file_sha(Path(inputs[key]))==sha,f'{key} 图像已改变，拒绝冻结')
    require(file_sha(root/'three_stage_comparison.png')==report['comparison_sha256'],
            '原始三阶段对照图已改变')
    require(file_sha(Path(inputs['matrix']))==report['matrix_sha256'] and
            file_sha(Path(inputs['palette']))==report['palette_sha256'],
            '冻结前原始矩阵/色卡发生变化')
    require(file_sha(pd.PALETTE)==report['palette_sha256'],
            '审核色卡与技能内置色卡不同，不能冻结为默认 MARD MASTER')
    actual = strict_grid_preview(Path(inputs['matrix']),Path(inputs['palette']),Path(inputs['bead']))
    require(actual['matrix_digest']==report['matrix_file_digest'],
            '图纸重新验证后摘要不一致')
    out=Path(args.out)
    require(not out.exists(),'MASTER 输出位置已存在，禁止覆盖')
    pd.freeze(argparse.Namespace(matrix=inputs['matrix'],out=str(out),
                                 name=args.name,board=args.board))
    proof={'schema':SCHEMA,'status':'REVIEWED_WORKFLOW_NOT_BIOMETRIC_PROOF',
           'assessment_sha256':file_sha(root/'identity_report.json'),
           'attestation_sha256':file_sha(Path(args.attested)),
           'matrix_digest':report['matrix_file_digest'],
           'notes':'Record only; SHA-256 is integrity evidence, not a signature or identity proof.'}
    write_json(out/'identity_review_provenance.json',proof)
    print('FROZEN AFTER EXPLICIT USER REVIEW; this is not algorithmic identity certification.')


def extract(args):
    img,model,out=Path(args.image),Path(args.model),Path(args.out)
    require(img.is_file() and model.is_file(),'图像或本地 MediaPipe Face Landmarker 模型不存在')
    require(not out.exists(),'关键点结果文件已存在，不覆盖')
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
    except ImportError:
        raise pd.PatternError('缺少 mediapipe，请显式安装可选依赖。不会自动下载模型/上传照片')
    options=vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(model)),
        running_mode=vision.RunningMode.IMAGE, num_faces=2)
    with vision.FaceLandmarker.create_from_options(options) as detector:
        result=detector.detect(mp.Image.create_from_file(str(img)))
    require(len(result.face_landmarks)==1,
            f'人脸识别结果有 {len(result.face_landmarks)} 张脸; 必须单人并人工检查')
    pts=result.face_landmarks[0]
    require(len(pts)>=max(INDICES.values())+1,'模型关键点数量不足')
    mapped={k:[round(float(pts[i].x),7),round(float(pts[i].y),7)] for k,i in INDICES.items()}
    info={
        'schema':LANDMARK_SCHEMA,'source':'mediapipe','face_count':1,
        'image_sha256':file_sha(img),'model_sha256':file_sha(model),
        'points':mapped,
        'note':'Detection may be unreliable on cartoons or 87x87 bead art; human review required.',
    }
    write_json(out,info)
    # validate extraction before emitting completion
    read_landmarks(out,info['image_sha256'])
    print(f'EXTRACTED {len(mapped)} keypoints with explicit model provenance; no identity verdict.')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='command',required=True)
    a=subs.add_parser('prepare',help='Strict grid validation plus 3-stage comparison and optional geometry screening')
    a.add_argument('--original',required=True)
    a.add_argument('--cartoon',required=True)
    a.add_argument('--bead',required=True,help='Pure nearest-neighbor preview, not a numbered/overlaid chart')
    a.add_argument('--matrix',required=True)
    a.add_argument('--palette',required=True)
    a.add_argument('--landmarks-original')
    a.add_argument('--landmarks-cartoon')
    a.add_argument('--landmarks-bead')
    a.add_argument('--out',required=True)
    a.set_defaults(fn=prepare)
    a=subs.add_parser('extract',help='Optional MediaPipe Face Landmarker extraction with explicit local model')
    a.add_argument('--image',required=True)
    a.add_argument('--model',required=True)
    a.add_argument('--out',required=True)
    a.set_defaults(fn=extract)
    a=subs.add_parser('attest',help='Requires real human/user-reviewed checks, bound to image/matrix digests')
    a.add_argument('--prepared',required=True)
    a.add_argument('--review',required=True)
    a.add_argument('--out',required=True)
    a.set_defaults(fn=evaluate)
    a=subs.add_parser('freeze-reviewed',help='Freeze a MASTER only after a provenance-bound human approval')
    a.add_argument('--prepared',required=True)
    a.add_argument('--review',required=True)
    a.add_argument('--attested',required=True)
    a.add_argument('--out',required=True)
    a.add_argument('--name',default='身份保真拼豆肖像')
    a.add_argument('--board',type=int,default=29)
    a.set_defaults(fn=freeze_reviewed)
    args=parser.parse_args(argv)
    try:args.fn(args)
    except (pd.PatternError, OSError, ValueError, KeyError, TypeError) as e:
        parser.exit(2,f'ERROR: {e}\n')


if __name__=='__main__': main()
