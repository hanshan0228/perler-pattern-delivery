#!/usr/bin/env python3
"""Pixel-exact, immutable-master customer delivery workflow for fuse-bead patterns.

Not a photorealistic rendering system. Each bead position is a single color code.
All visual sheets are deterministic projections of the same canonical CSV.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import zipfile
from collections import deque

from PIL import Image, ImageDraw, ImageFont, ImageChops

ROOT = Path(__file__).resolve().parent.parent
# Keep sibling processors importable even when this script is loaded by an external agent.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
PALETTE = ROOT / "assets" / "mard_palette.json"
EMPTY = "EMPTY"
MANIFEST_NAME = "master_manifest.json"
ROW_LABELS = {"行\\列", "行/列", "row/col", "row\\col", "row"}

class PatternError(Exception):
    pass


def sha_file(p: Path) -> str:
    dig = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            dig.update(block)
    return dig.hexdigest()


def digest_codes(rows: list[list[str]]) -> str:
    data = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf8")).hexdigest()


def load_palette(path: Path) -> dict[str,str]:
    data = json.loads(path.read_text(encoding="utf8"))
    if not isinstance(data, dict) or not data:
        raise PatternError("色卡不是非空 JSON 对象")
    for code, color in data.items():
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", code):
            raise PatternError(f"无效色号: {code!r}")
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise PatternError(f"无效 HEX: {code}={color}")
    return {k: v.upper() for k, v in data.items()}


def read_matrix(path: Path) -> list[list[str]]:
    if not path.is_file():
        raise PatternError(f"矩阵文件不存在: {path}")
    if path.suffix.lower() == '.json':
        parsed=json.loads(path.read_text(encoding='utf-8-sig'))
        data = parsed.get('grid') if isinstance(parsed,dict) else parsed
        if not isinstance(data,list) or not data or not all(isinstance(row,list) for row in data):
            raise PatternError('JSON 需要二维数组，或含 grid 二维数组的工程对象')
        normalized=[]
        for row in data:
            if not all((v is None or isinstance(v,str)) for v in row):
                raise PatternError('JSON 格子必须为色号字符串或 null 空位')
            normalized.append([(v.strip().upper() if isinstance(v,str) else EMPTY) for v in row])
        return validate_rectangular(normalized)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        raw = [[cell.strip().upper() for cell in row] for row in csv.reader(f)]
    if not raw or any(not r for r in raw):
        raise PatternError("输入包含空行或完全为空")
    if raw[0][0].lower() in ROW_LABELS:
        labels = raw[0][1:]
        w = len(labels)
        if not w or labels != [str(i) for i in range(1, w+1)]:
            raise PatternError("列头必须从 1 连续递增")
        data = []
        for i, row in enumerate(raw[1:], start=1):
            if len(row) != w+1 or row[0] != str(i):
                raise PatternError(f"第 {i} 行的行标或列数错误")
            data.append(row[1:])
    else:
        data = raw
    return validate_rectangular(data)


def validate_rectangular(data):
    if len(data) == 0:
        raise PatternError("矩阵没有任何格子")
    width = len(data[0])
    if not 1 <= width <= 200 or not 1 <= len(data) <= 200:
        raise PatternError("图纸尺寸超出支持范围（1..200）")
    for i, row in enumerate(data, start=1):
        if len(row) != width:
            raise PatternError(f"第 {i} 行宽度 {len(row)} 与期望 {width} 不一致")
    return data


def write_matrix(path: Path, rows: list[list[str]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["行\\列"] + list(range(1, len(rows[0])+1)))
        for i, row in enumerate(rows, 1):
            wr.writerow([i] + row)


def stats(rows, palette):
    validate_rectangular(rows)
    counts = collections.Counter(cell for row in rows for cell in row if cell != EMPTY)
    unknown = sorted(set(counts) - set(palette))
    if unknown:
        raise PatternError("矩阵包含色卡未定义色号: " + ", ".join(unknown[:20]))
    h, w = len(rows), len(rows[0])
    empty_count = sum(x == EMPTY for row in rows for x in row)
    if sum(counts.values()) + empty_count != w*h: raise PatternError("豆数与网格数量不一致")
    return counts, empty_count, w, h


def boards(rows, size):
    if not isinstance(size,int) or not 1<=size<=29: raise PatternError("board 必须在 1..29")
    h, w = len(rows), len(rows[0])
    result = []
    for by, y in enumerate(range(0, h, size)):
        for bx, x in enumerate(range(0, w, size)):
            part = [r[x:x+size] for r in rows[y:y+size]]
            result.append((by+1, bx+1, y, x, part))
    return result


def rgb(v):
    return tuple(bytes.fromhex(v[1:]))


def luminance(v):
    rgb0 = [x/255 for x in rgb(v)]
    linear = [c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4 for c in rgb0]
    return 0.2126*linear[0] + 0.7152*linear[1] + 0.0722*linear[2]


def contrast_ink(bg):
    L=luminance("#"+"".join(c*2 for c in bg[1:]) if len(bg)==4 else bg)
    return '#000000' if (L+.05)/.05>=1.05/(L+.05) else '#FFFFFF'


def font(size, bold=False):
    override = os.environ.get('PINDOU_FONT')
    candidates = [override,
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if p:
            try: return ImageFont.truetype(p, size)
            except (OSError, ValueError): pass
    return ImageFont.load_default(size=size)


def fill_for(code, palette):
    return palette[code] if code != EMPTY else "#FFFFFF"


def semantic_image(rows, palette):
    h,w = len(rows), len(rows[0])
    im = Image.new("RGBA", (w,h), (0,0,0,0))
    pixels = im.load()
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if v != EMPTY:
                pixels[c,r] = (*rgb(palette[v]),255)
    return im


def preview_image(rows, palette, size=1044):
    semantic = semantic_image(rows,palette)
    w,h = semantic.size
    scale = max(1, min(size//w, size//h))
    im = semantic.resize((w*scale,h*scale), Image.Resampling.NEAREST)
    bg = Image.new('RGBA', im.size, (255,255,255,255))
    bg.alpha_composite(im)
    return bg.convert('RGB')


def save_preview(rows, palette, path, size=1044):
    preview_image(rows, palette, size).save(path)


def fitted_font(labels, max_width, max_height, desired, bold=True):
    # Fit actual glyph bounding boxes, including three/four-character codes.
    labels=set(map(str,labels))
    for sz in range(max(1,int(desired)),0,-1):
        f=font(sz,bold)
        if all((b:=f.getbbox(label))[2]-b[0]<=max_width and b[3]-b[1]<=max_height for label in labels):
            return f
    raise PatternError('格内字体无法容纳；请增大图纸')


def axis_labels(draw,x,y,w,h,cell,*,gap=25,fill='#63535a'):
    # All coordinates, no sparsely sampled tick labels, all four edges.
    f=fitted_font(range(1,max(w,h)+1),cell-4,cell-4,min(26,int(cell*.48)))
    for c in range(w):
        xp=x+(c+.5)*cell
        for yp in (y-gap,y+h*cell+gap):
            draw.text((xp,yp),str(c+1),font=f,fill=fill,anchor='mm')
    for r in range(h):
        yp=y+(r+.5)*cell
        for xp in (x-gap,x+w*cell+gap):
            draw.text((xp,yp),str(r+1),font=f,fill=fill,anchor='mm')


def verify_png(path, expected):
    # A matching manifest checksum alone does not establish correct rendering.
    with Image.open(path) as image:
        if image.mode!=expected.mode or image.size!=expected.size or any(b.getbbox() for b in ImageChops.difference(image,expected).split()):
            raise PatternError(f'实际图纸与矩阵重新渲染结果不一致: {path.name}')


def render_grid(rows, palette, *, cell=42, bw=False, labeled=True, board_line=29, readable=False):
    h,w = len(rows),len(rows[0])
    margin= max(36,cell)
    canvas = Image.new("RGB", (w*cell+2*margin+1,h*cell+2*margin+1), "#ffffff")
    draw = ImageDraw.Draw(canvas)
    f = fitted_font(("×" if c==EMPTY else c for row in rows for c in row),cell-6,cell-6,max(10,int(cell*.45)))
    for r,row in enumerate(rows):
        for c,code in enumerate(row):
            x0,y0=margin+c*cell,margin+r*cell
            bg = '#FFFFFF' if bw else fill_for(code,palette)
            draw.rectangle((x0,y0,x0+cell-1,y0+cell-1),fill=bg)
            if labeled:
                label = '×' if code==EMPTY else code
                if bw: fg='#202020'
                elif code==EMPTY: fg='#a7a7a7'
                else: fg='#ffffff' if luminance(bg)<0.24 else '#26202a'
                if readable: fg=contrast_ink(bg)
                draw.text((x0+cell/2,y0+cell/2),label,font=f,fill=fg,anchor='mm')
    for c in range(w+1):
        major= board_line>0 and c%board_line==0
        draw.line((margin+c*cell,margin,margin+c*cell,margin+h*cell), fill="#554450" if major else "#aaa3a8",width=3 if major else 1)
    for r in range(h+1):
        major= board_line>0 and r%board_line==0
        draw.line((margin,margin+r*cell,margin+w*cell,margin+r*cell), fill="#554450" if major else "#aaa3a8",width=3 if major else 1)
    axis_labels(draw,margin,margin,w,h,cell,gap=margin/2)
    return canvas


def render_customer(rows, palette, title, board_size, counts, empty, out=None, *, approved=True, readable=False):
    actual,actual_empty,_,_=stats(rows,palette)
    if actual!=counts or actual_empty!=empty or not 1<=board_size<=29:
        raise PatternError("图例统计或拼板规格无效")
    h,w=len(rows),len(rows[0]); n=len(counts)
    W=4960
    maxsize=max(w,h)
    cell = min(90,max(20, int(4290/maxsize)))
    grid_w,grid_h=w*cell,h*cell
    x=(W-grid_w)//2
    y=1030+(4310-grid_h)//2
    leg_y=5545
    coln=6
    leg_rows=math.ceil(n/coln) if n else 0
    row_h = 144
    H=max(7000, 5790+max(1,leg_rows)*row_h+400)
    img=Image.new('RGB',(W,H),'#fcfaf9')
    d=ImageDraw.Draw(img)
    d.rectangle((0,0,W,29),fill='#a45672')
    def t(xy,txt,sz,fill='#30282e',bold=False,anchor=None):
        d.text(xy,str(txt),font=font(sz,bold),fill=fill,anchor=anchor)
    def rr(xy,rad=20,fill='#fff',line='#e8dfe4',lw=3):
        d.rounded_rectangle(xy,radius=rad,fill=fill,outline=line,width=lw)
    rr((228,114,865,753),23)
    thumb=preview_image(rows,palette,580)
    im2=Image.new('RGB',(580,580),'#FFFFFF')
    im2.paste(thumb,((580-thumb.width)//2,(580-thumb.height)//2))
    img.paste(im2,(255,140))
    title=(title or '拼豆图纸').replace('\n',' ').strip()[:30]
    heading='拼豆定制图纸  |  '+title
    d.text((958,150),heading,font=fitted_font([heading],W-958-228,130,95),fill='#30282e')
    t((958,304),'已确认主版本 · 色号与网格数据严格一致' if approved else '待确认图纸 · 色号与网格数据严格一致',48,'#755c67')
    carddata = [f'{w} × {h} 标准网格', f'{n} 种参考色号', f'{sum(counts.values()):,} 颗豆子', f'{math.ceil(w/board_size)*math.ceil(h/board_size)} 块 {board_size}×{board_size} 板']
    xs=[958,1700,2430,3170]; ws=[700,690,690,1540]
    for xpos,width,label in zip(xs,ws,carddata):
        rr((xpos,430,xpos+width,535),22,'#f8eef1','#f8eef1')
        d.text((xpos+24,450),label,font=fitted_font([label],width-48,70,46),fill='#994967')
    t((960,612),'以下颜色和格内编号全部来自已锁定矩阵，非 AI 重新生成。' if approved else '候选矩阵直接绘制 · 请先确认造型与颜色，再冻结为正式版本。',42,'#776b71')
    # Underlying grid cells, with visible label text and line overlay.
    gf=fitted_font(("×" if c==EMPTY else c for row in rows for c in row),cell-8,cell-8,max(11,int(cell*.46)))
    for r,row in enumerate(rows):
        for c,code in enumerate(row):
            x0=x+c*cell; y0=y+r*cell
            bg=fill_for(code,palette)
            d.rectangle((x0,y0,x0+cell-1,y0+cell-1),fill=bg)
            fg=('#a0a0a0' if code==EMPTY else ('#fff' if luminance(bg)<.24 else '#272028'))
            if readable: fg=contrast_ink(bg)
            d.text((x0+cell/2,y0+cell/2),('×' if code==EMPTY else code),font=gf,fill=fg,anchor='mm')
    for c in range(w+1):
        xp=x+c*cell
        major=c%board_size==0; medium=c%10==0
        d.line((xp,y,xp,y+grid_h), fill='#51414a' if major else ('#84747c' if medium else '#afa6ad'),width=5 if major else (3 if medium else 1))
    for r in range(h+1):
        yp=y+r*cell
        major=r%board_size==0; medium=r%10==0
        d.line((x,yp,x+grid_w,yp),fill='#51414a' if major else ('#84747c' if medium else '#afa6ad'),width=5 if major else (3 if medium else 1))
    axis_labels(d,x,y,w,h,cell,gap=30)
    d.line((228,5525,W-228,5525),fill='#e4c4d1',width=7)
    t((228,5600),'配色用量  /  MARD 参考 HEX',63,bold=True)
    t((W-230,5609),f'{n} 种颜色 · 合计 {sum(counts.values()):,} 颗 · 空位 {empty}',44,'#775f6b',anchor='ra')
    rows_per_col=math.ceil(n/coln) if n else 0
    colw=(W-456)//coln
    for j,(code,qty) in enumerate(sorted(counts.items(),key=lambda kv:(-kv[1],kv[0]))):
        col=j//rows_per_col; r=j%rows_per_col
        xp=228+col*colw; yp=5705+r*row_h
        rr((xp,yp,xp+colw-24,yp+row_h-12),15,'#ffffff','#eadfe4',2)
        d.rectangle((xp+14,yp+15,xp+93,yp+row_h-25),fill=palette[code],outline='#7c6a73',width=2)
        t((xp+109,yp+20),code,42,bold=True)
        t((xp+109,yp+75),f'{qty:,} 颗',34,'#716570')
    footer_y=H-330
    d.line((228,footer_y,W-228,footer_y),fill='#ded1d7',width=4)
    t((228,footer_y+45),'严格校验：一格一色号，配色与总数来自相同的已确认原始矩阵。' if approved else '候选图纸：一格一色号，配色与总数来自同一候选矩阵。',38,'#655963')
    t((228,footer_y+110),'说明：屏幕颜色为参考 HEX，实物批次可能有色差；空位标 ×，不需要放豆。',36,'#7c7077')
    t((W-228,H-70),f'{w}×{h} · '+('单页顾客交付' if approved else '单页待确认图纸'),31,'#9b8791',anchor='ra')
    if out is not None: img.save(out,optimize=True,dpi=(300,300))
    return img


def render_board(page, palette, board_r,board_c, yoffset,xoffset, *, bw=False, size=29, global_w=None,global_h=None, readable=False):
    rows=page; h,w=len(rows),len(rows[0]); W,H=2300,3050
    im=Image.new('RGB',(W,H),'#fff'); d=ImageDraw.Draw(im)
    title=f'第 {board_r} 行 · 第 {board_c} 列 | '+('黑白施工稿' if bw else '彩色施工稿')
    d.text((120,95),title,font=font(68,True),fill='#44333e')
    d.text((120,195),f'全局行 {yoffset+1}–{yoffset+h} · 列 {xoffset+1}–{xoffset+w}    ({w}×{h})',font=font(40),fill='#72616a')
    csize=min(68,int(2020/max(size, w, h)))
    ox=(W-w*csize)//2; oy=360
    f=fitted_font(("×" if c==EMPTY else c for row in rows for c in row),csize-8,csize-8,max(18,int(csize*(.54 if readable else .42))))
    for r,row in enumerate(rows):
        for c,cd in enumerate(row):
            x=ox+c*csize; y=oy+r*csize
            fill='#fff' if bw else fill_for(cd,palette)
            d.rectangle((x,y,x+csize-1,y+csize-1),fill=fill)
            label='×' if cd==EMPTY else cd
            fg='#1e1e1e' if bw else ('#a0a0a0' if cd==EMPTY else ('#fff' if luminance(fill)<.24 else '#28212a'))
            if readable: fg=contrast_ink(fill)
            d.text((x+csize/2,y+csize/2),label,font=f,fill=fg,anchor='mm')
    for c in range(w+1):
        x=ox+c*csize
        d.line((x,oy,x,oy+h*csize),fill='#555' if c in (0,w) or c%10==0 else '#aaa', width=3 if c in (0,w) or c%10==0 else 1)
    for r in range(h+1):
        y=oy+r*csize
        d.line((ox,y,ox+w*csize,y),fill='#555' if r in (0,h) or r%10==0 else '#aaa',width=3 if r in (0,h) or r%10==0 else 1)
    fl=font(25,True)
    for c in range(w):
        xp=ox+(c+.5)*csize
        d.text((xp,oy-26),str(xoffset+c+1),font=fl,fill='#333',anchor='mm')
        d.text((xp,oy+h*csize+30),str(xoffset+c+1),font=fl,fill='#333',anchor='mm')
    for r in range(h):
        yp=oy+(r+.5)*csize
        d.text((ox-36,yp),str(yoffset+r+1),font=fl,fill='#333',anchor='mm')
        d.text((ox+w*csize+38,yp),str(yoffset+r+1),font=fl,fill='#333',anchor='mm')
    part_counts=collections.Counter(v for row in rows for v in row if v!=EMPTY)
    d.text((120,2650),f'本板 {sum(part_counts.values())} 颗 · {len(part_counts)} 种颜色 · {w*h-sum(part_counts.values())} 空位',font=font(40),fill='#46353c')
    d.text((120,2720),'× = 空位；颜色代码以总用量清单为准。',font=font(35),fill='#746871')
    return im


def pdf_from_images(paths: list[Path], out: Path, format='A4'):
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4,A2
        from reportlab.lib.utils import ImageReader
    except ImportError as exc:
        raise PatternError('缺少 reportlab；请先执行 pip install -r requirements.txt') from exc
    page=A2 if format=='A2' else A4
    pdf=canvas.Canvas(str(out) if isinstance(out,(str,Path)) else out,pagesize=page,pageCompression=1,invariant=1)
    for p in paths:
        with Image.open(p) as im:
            iw,ih=im.size
            im=im.convert('RGB')
            pw,ph=page
            scale=min(pw/iw,ph/ih)
            w,h=iw*scale,ih*scale
            pdf.drawImage(ImageReader(im), (pw-w)/2,(ph-h)/2,w,h, mask='auto')
            pdf.showPage()
    pdf.save()


def verify_pdf(paths, actual, fmt):
    # Same renderer / environment, deterministic PDF (invariant=1).
    buf=io.BytesIO()
    pdf_from_images(paths,buf,fmt)
    if hashlib.sha256(buf.getvalue()).hexdigest()!=sha_file(actual):
        raise PatternError(f'PDF 与已校验施工图不一致: {actual.name}')


def freeze(args):
    if not 1<=args.board<=29: raise PatternError('board 必须在 1..29')
    palette=load_palette(PALETTE)
    rows=read_matrix(Path(args.matrix))
    counts,empty,w,h=stats(rows,palette)
    output=Path(args.out)
    if output.exists():
        raise PatternError(f'MASTER 目录已存在，禁止覆盖：{output}。请使用新版本目录。')
    output.mkdir(parents=True)
    matrix=output/'master_matrix.csv'
    palout=output/'palette.json'
    write_matrix(matrix,rows)
    shutil.copyfile(PALETTE,palout)
    semantic_image(rows,palette).save(output/'semantic_pixels.png')
    data={
        'format':'perler-pattern-master-v2',
        'name':args.name.strip()[:50],
        'width':w,'height':h,'colors':len(counts),'beads':sum(counts.values()),
        'empty':empty,'board_size':args.board,
        'matrix_file':matrix.name,'matrix_sha256':sha_file(matrix),
        'palette_file':palout.name,'palette_sha256':sha_file(palout),
        'semantic_file':'semantic_pixels.png','semantic_sha256':sha_file(output/'semantic_pixels.png'),
        'codes_sha256':digest_codes(rows),
        'notes':'MARD display HEX reference, not certified measured product colors',
    }
    (output/MANIFEST_NAME).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf8')
    print(f'FROZEN {w}x{h} · {len(counts)} colors · {sum(counts.values())} beads · {empty} EMPTY · master SHA {data["matrix_sha256"][:12]}')


def read_master(master_dir: Path):
    manifest=master_dir/MANIFEST_NAME
    if not manifest.is_file(): raise PatternError('没有 master_manifest.json；请先 freeze')
    meta=json.loads(manifest.read_text(encoding='utf8'))
    if meta.get('format')!='perler-pattern-master-v2': raise PatternError('MASTER schema 不兼容')
    names=['matrix_file','palette_file','semantic_file']
    for name in names:
        if Path(meta[name]).name != meta[name]: raise PatternError('MASTER 路径无效')
        f=master_dir/meta[name]
        if not f.is_file() or sha_file(f)!=meta[name.replace('_file','_sha256')]:
            raise PatternError(f'MASTER 文件 SHA-256 不一致，停止操作：{f}')
    rows=read_matrix(master_dir/meta['matrix_file'])
    palette=load_palette(master_dir/meta['palette_file'])
    counts,empty,w,h=stats(rows,palette)
    if digest_codes(rows)!=meta['codes_sha256'] or (w,h,len(counts),sum(counts.values()),empty)!=(meta['width'],meta['height'],meta['colors'],meta['beads'],meta['empty']):
        raise PatternError('MASTER 统计/像素数据与 manifest 不符')
    compare=semantic_image(rows,palette)
    with Image.open(master_dir/meta['semantic_file']) as orig:
        if orig.mode!='RGBA' or orig.size!=compare.size or orig.tobytes()!=compare.tobytes():
            raise PatternError('MASTER semantic pixels 与矩阵不符')
    return meta,rows,palette,counts,empty


def legend_csv(path,counts,palette):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        wr=csv.writer(f)
        wr.writerow(['品牌','MARD色号','参考HEX','颗数'])
        for code,qty in sorted(counts.items(),key=lambda x:(-x[1],x[0])):
            wr.writerow(['MARD',code,palette[code],qty])


def deliver(args):
    master=Path(args.master)
    meta,rows,palette,counts,empty=read_master(master)
    root=Path(args.out)
    if root.exists():
        raise PatternError('交付目录已存在，禁止覆盖；请选一个新的输出目录')
    n=meta['board_size']
    if not 1<=n<=29: raise PatternError('MASTER board 必须在 1..29')
    root.mkdir(parents=True)
    shutil.copyfile(master/meta['matrix_file'],root/'master_matrix.csv')
    shutil.copyfile(master/meta['palette_file'],root/'palette.json')
    semantic_image(rows,palette).save(root/'semantic_pixels.png')
    save_preview(rows,palette,root/'pixel_preview.png')
    render_grid(rows,palette,cell=min(50,max(24,3800//max(meta['width'],meta['height']))),board_line=n,readable=True).save(root/'pattern_with_codes.png')
    render_customer(rows,palette,meta['name'],n,counts,empty,root/'customer_sheet.png',readable=True)
    pdf_from_images([root/'customer_sheet.png'],root/'customer_sheet_A2.pdf','A2')
    legend_csv(root/'legend.csv',counts,palette)
    boarddir=root/'boards'; boarddir.mkdir()
    images_color=[];images_bw=[]
    for i,(r,c,y,x,part) in enumerate(boards(rows,n),start=1):
        colored=boarddir/f'board_{i:02d}_color.png'; blackwhite=boarddir/f'board_{i:02d}_bw.png'
        render_board(part,palette,r,c,y,x,bw=False,size=n,readable=True).save(colored,optimize=True)
        render_board(part,palette,r,c,y,x,bw=True,size=n,readable=True).save(blackwhite,optimize=True)
        images_color.append(colored);images_bw.append(blackwhite)
    pdf_from_images(images_color,root/'boards_color_A4.pdf')
    pdf_from_images(images_bw,root/'boards_bw_A4.pdf')
    allpaths=sorted(p for p in root.rglob('*') if p.is_file())
    validation={
        'format':'perler-pattern-delivery-validation-v4',
        'master_matrix_sha256':meta['matrix_sha256'],
        'master_palette_sha256':meta['palette_sha256'],
        'codes_sha256':meta['codes_sha256'],
        'width':meta['width'],'height':meta['height'],'colors':len(counts),
        'beads':sum(counts.values()),'empty':empty,'board_size':n,
        'board_count':len(images_color),
        'semantic_verified':True,'files_sha256':{p.relative_to(root).as_posix():sha_file(p) for p in allpaths},
    }
    (root/'validation.json').write_text(json.dumps(validation,indent=2,ensure_ascii=False),encoding='utf8')
    zip_path=root/'customer_delivery.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file() and p!=zip_path:
                z.write(p,p.relative_to(root))
    print(f'DELIVERED {meta["width"]}x{meta["height"]}; {len(counts)} colors; {sum(counts.values())} beads; {empty} EMPTY; {len(images_color)} boards; SHA {meta["matrix_sha256"][:12]}')
    # Full verification using the exact same validation routine.
    verify_master_delivery(master,root)


def verify_master_delivery(master,root):
    meta,rows,palette,counts,empty=read_master(master)
    verpath=root/'validation.json'
    if not verpath.is_file(): raise PatternError('交付目录缺少 validation.json')
    v=json.loads(verpath.read_text(encoding='utf8'))
    if v.get('format') not in ('perler-pattern-delivery-validation-v3','perler-pattern-delivery-validation-v4'):
        raise PatternError('旧交付包不含渲染校验；请用原 MASTER 重新 deliver 到新目录')
    for key,ref in [('master_matrix_sha256','matrix_sha256'),('master_palette_sha256','palette_sha256'),('codes_sha256','codes_sha256')]:
        if v.get(key)!=meta[ref]: raise PatternError('交付与冻结 MASTER 指纹不一致：'+key)
    expect={'width':meta['width'],'height':meta['height'],'beads':sum(counts.values()),'colors':len(counts),'empty':empty,'board_size':meta['board_size'],'board_count':len(boards(rows,meta['board_size']))}
    for key,val in expect.items():
        if v.get(key)!=val: raise PatternError('交付统计不一致：'+key)
    readable=v['format']=='perler-pattern-delivery-validation-v4'
    n=meta['board_size']
    pieces=boards(rows,n)
    required={'master_matrix.csv','palette.json','semantic_pixels.png','pixel_preview.png','pattern_with_codes.png','customer_sheet.png','customer_sheet_A2.pdf','legend.csv','boards_color_A4.pdf','boards_bw_A4.pdf'}
    required.update(f'boards/board_{i:02d}_{kind}.png' for i in range(1,len(pieces)+1) for kind in ('color','bw'))
    if set(v['files_sha256'])!=required: raise PatternError('交付文件清单不完整或有额外文件')
    for rel,claimed_hash in v['files_sha256'].items():
        path=root/rel
        if not path.resolve().is_relative_to(root.resolve()) or not path.is_file() or sha_file(path)!=claimed_hash:
            raise PatternError('交付文件缺失或已被修改：'+rel)
    with Image.open(root/'semantic_pixels.png') as pic:
        if pic.mode!='RGBA' or pic.size!=(meta['width'],meta['height']) or pic.tobytes()!=semantic_image(rows,palette).tobytes():
            raise PatternError('逐格语义像素与 MASTER 不一致')
    actual={}
    with (root/'legend.csv').open('r',encoding='utf-8-sig',newline='') as f:
        allrows=list(csv.DictReader(f))
    for row in allrows:
        cd=row.get('MARD色号');color=row.get('参考HEX');qty=int(row.get('颗数','-1'))
        if row.get('品牌')!='MARD' or cd in actual or cd not in palette or color!=palette[cd]: raise PatternError('清单色号/色块错误')
        actual[cd]=qty
    if actual!=dict(counts): raise PatternError('清单用量与矩阵不一致')
    if sha_file(root/'master_matrix.csv')!=meta['matrix_sha256'] or sha_file(root/'palette.json')!=meta['palette_sha256']:
        raise PatternError('交付包矩阵/色卡与 MASTER 不符')
    verify_png(root/'pixel_preview.png',preview_image(rows,palette))
    verify_png(root/'pattern_with_codes.png',render_grid(rows,palette,cell=min(50,max(24,3800//max(meta['width'],meta['height']))),board_line=n,readable=readable))
    verify_png(root/'customer_sheet.png',render_customer(rows,palette,meta['name'],n,counts,empty,readable=readable))
    color_pages=[]; bw_pages=[]
    for i,(r,c,y,x,part) in enumerate(pieces,1):
        for kind,bw,pages in [('color',False,color_pages),('bw',True,bw_pages)]:
            path=root/'boards'/f'board_{i:02d}_{kind}.png'
            verify_png(path,render_board(part,palette,r,c,y,x,bw=bw,size=n,readable=readable)); pages.append(path)
    verify_pdf([root/'customer_sheet.png'],root/'customer_sheet_A2.pdf','A2')
    verify_pdf(color_pages,root/'boards_color_A4.pdf','A4')
    verify_pdf(bw_pages,root/'boards_bw_A4.pdf','A4')
    if not (root/'customer_delivery.zip').is_file(): raise PatternError('交付 ZIP 缺失')
    if (root/'customer_delivery.zip').is_file():
        with zipfile.ZipFile(root/'customer_delivery.zip') as z:
            if len(z.namelist())!=len(set(z.namelist())) or set(z.namelist())!=(set(v['files_sha256'])|{'validation.json'}): raise PatternError('ZIP 文件清单不一致')
            if z.read('validation.json') != verpath.read_bytes(): raise PatternError('ZIP 内验证记录不一致')
            for rel,exp in v['files_sha256'].items():
                if hashlib.sha256(z.read(rel)).hexdigest()!=exp: raise PatternError('ZIP 内部校验失败 '+rel)
    print('VERIFIED: master lock, 1-cell-1-code, legend counts, re-rendered PNG/PDF, ZIP contents all match')


def verify(args): verify_master_delivery(Path(args.master),Path(args.delivery))


def remove_background(args):
    meta,rows,palette,counts,empty=read_master(Path(args.master))
    code=args.background_code.upper()
    if code not in palette: raise PatternError('背景色号不在固定色卡中')
    h,w=len(rows),len(rows[0]); new=[r[:] for r in rows]
    q=deque(); seen=set()
    for c in range(w):
        for r in (0,h-1):
            if rows[r][c]==code and (r,c) not in seen: seen.add((r,c));q.append((r,c))
    for r in range(h):
        for c in (0,w-1):
            if rows[r][c]==code and (r,c) not in seen: seen.add((r,c));q.append((r,c))
    while q:
        r,c=q.popleft();new[r][c]=EMPTY
        for nr,nc in ((r-1,c),(r+1,c),(r,c-1),(r,c+1)):
            if 0<=nr<h and 0<=nc<w and (nr,nc) not in seen and rows[nr][nc]==code:
                seen.add((nr,nc));q.append((nr,nc))
    out=Path(args.out)
    if out.exists(): raise PatternError('候选 CSV 已存在，禁止覆盖')
    write_matrix(out,new)
    print(f'CANDIDATE ONLY: removed {len(seen)} {code} edge-connected cells; master unchanged. Review then freeze into NEW master directory.')


def srgb_lab(rgb_values):
    import numpy as np
    a=np.asarray(rgb_values,dtype=np.float64)/255.0
    lin=np.where(a<=0.04045,a/12.92,((a+0.055)/1.055)**2.4)
    mat=np.array([[.4124564,.3575761,.1804375],[.2126729,.7151522,.072175],[.0193339,.119192,.9503041]])
    xyz=lin@mat.T
    r=xyz/np.array([.95047,1.0,1.08883])
    d=6/29
    f=np.where(r>d**3,np.cbrt(r),r/(3*d*d)+4/29)
    fx,fy,fz=f[...,0],f[...,1],f[...,2]
    return np.stack([116*fy-16,500*(fx-fy),200*(fy-fz)],axis=-1)


def quantize_pixels(arr, n: int, colors: int, palette):
    """Quantize one RGB sample per logical cell; do not silently interpolate."""
    import numpy as np
    arr=np.asarray(arr,dtype=np.float64).reshape(-1,3)
    if len(arr)!=n*n:
        raise PatternError('RGB samples do not match requested square grid')
    data=srgb_lab(arr)
    k=min(colors,len(data)); rng=np.random.default_rng(42)
    centers=np.empty((k,3)); centers[0]=data[rng.integers(len(data))]
    mind2=np.full(len(data),np.inf)
    for i in range(1,k):
        dist2=np.sum((data-centers[i-1])**2,axis=1)
        mind2=np.minimum(mind2,dist2)
        summ=mind2.sum()
        index=int(rng.choice(len(data),p=mind2/summ)) if summ>0 else int(rng.integers(len(data)))
        centers[i]=data[index]
    group=np.full(len(data),-1)
    for _ in range(30):
        d=np.sum((data[:,None,:]-centers[None,:,:])**2,axis=2)
        a=d.argmin(axis=1)
        if np.array_equal(group,a): break
        group=a
        for j in range(k):
            if np.any(a==j): centers[j]=data[a==j].mean(axis=0)
    # Recompute assignment after final center updates (if last loop moved centroids).
    group=np.sum((data[:,None,:]-centers[None,:,:])**2,axis=2).argmin(axis=1)
    codes=list(palette)
    palrgb=np.array([rgb(palette[c]) for c in codes],dtype=float)
    pallab=srgb_lab(palrgb)
    nearest=np.sum((centers[:,None,:]-pallab[None,:,:])**2,axis=2).argmin(axis=1)
    mapped=[codes[nearest[i]] for i in group]
    return [mapped[i*n:(i+1)*n] for i in range(n)]




def quantize_photo(path: Path, n: int, colors: int, palette):
    from cartoon_pipeline import open_rgb
    im=open_rgb(path, max_side=1200)
    return quantize_image(im, n, colors, palette)


def quantize_image(im, n: int, colors: int, palette):
    from PIL import Image
    im=im.convert('RGB')
    w,h=im.size
    if w>h:
        left=(w-h)//2;im=im.crop((left,0,left+h,h))
    elif h>w:
        top=(h-w)//2;im=im.crop((0,top,w,top+w))
    arr=__import__('numpy').asarray(im.resize((n,n),Image.Resampling.BOX),dtype='float64')
    return quantize_pixels(arr,n,colors,palette)

def generate(args):
    if not 1<=args.grid<=145 or not 1<=args.colors<=120:
        raise PatternError('grid 需为 1..145, colors 需为 1..120')
    source=Path(args.image)
    if not source.is_file(): raise PatternError('输入图片不存在')
    root=Path(args.out)
    if root.exists(): raise PatternError('候选目录已存在，禁止覆盖')
    palette=load_palette(PALETTE)
    mode=getattr(args,'mode','photo')
    filter_level=getattr(args,'filter',None) or ('medium' if mode=='cartoon' else 'none')
    if filter_level not in {'none','low','medium','high'}:
        raise PatternError('filter 仅支持 none, low, medium, high')
    stage=None
    details={}
    if mode=='cartoon':
        from cartoon_pipeline import cartoonize, open_rgb
        style=getattr(args,'cartoon_style','soft')
        engine=getattr(args,'cartoon_engine','offline')
        if engine=='offline':
            stage=cartoonize(open_rgb(source),style=style)
            details={'cartoon_engine':'offline','cartoon_style':style,
                     'cartoon_definition':'edge-preserving smoothing, posterization, and controlled contour overlay'}
        elif engine=='external':
            stage_path=getattr(args,'cartoon_image',None)
            if not stage_path or not Path(stage_path).is_file():
                raise PatternError('external 引擎要求 --cartoon-image，且文件必须存在')
            stage=open_rgb(Path(stage_path))
            details={'cartoon_engine':'external','cartoon_style':'provided_by_external_model',
                     'external_image_sha256':sha_file(Path(stage_path)),
                     'external_image_name':Path(stage_path).name}
        else:
            raise PatternError('未知卡通引擎')
        rows=quantize_image(stage,args.grid,args.colors,palette)
    elif mode=='pixel':
        from candidate_processing import sample_pixel_art
        from cartoon_pipeline import open_rgb
        pixels,alignment=sample_pixel_art(open_rgb(source, max_side=5000),grid=args.grid,
                                           pixel_cell=getattr(args,'pixel_cell',None),
                                           origin_x=getattr(args,'pixel_origin_x',None),
                                           origin_y=getattr(args,'pixel_origin_y',None))
        rows=quantize_pixels(pixels,args.grid,args.colors,palette)
        details={'pixel_alignment':alignment}
    elif mode=='photo':
        rows=quantize_photo(source,args.grid,args.colors,palette)
    else:
        raise PatternError('mode 仅支持 photo, cartoon, pixel')
    from candidate_processing import cleanup
    rows,changes=cleanup(rows,strength=filter_level)
    counts,empty,w,h=stats(rows,palette)
    root.mkdir(parents=True)
    if stage is not None:
        stage.save(root/'cartoon_stage.png')
    write_matrix(root/'candidate_matrix.csv',rows)
    save_preview(rows,palette,root/'candidate_preview.png')
    render_grid(rows,palette,cell=40).save(root/'candidate_codes.png')
    info={'status':'UNAPPROVED','width':w,'height':h,'colors':len(counts),
          'beads':w*h-empty,'empty':empty,'mode':mode,'filter':filter_level,
          'filter_report':changes,'input_image_sha256':sha_file(source),
          'workflow':('cartoon preprocessing -> BOX -> CIELAB K-means -> MARD -> candidate cleanup'
                      if mode=='cartoon' else
                      'central-median pixel alignment -> CIELAB K-means -> MARD -> candidate cleanup'
                      if mode=='pixel' else
                      'BOX -> CIELAB K-means -> closest MARD reference color'),**details}
    if stage is not None: info['cartoon_stage_sha256']=sha_file(root/'cartoon_stage.png')
    (root/'candidate_info.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
    print(f'UNAPPROVED CANDIDATE ({mode}): {w}x{h}, {len(counts)} colors; {changes["modified_cells"]} modified by filter; human approval required before freeze')


def parser():
    ap=argparse.ArgumentParser(description='Perler/MARD cartoon + pixel-locked pattern generation & customer delivery v2.4')
    sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('freeze',help='Save approved matrix as immutable master')
    p.add_argument('--matrix',required=True);p.add_argument('--out',required=True)
    p.add_argument('--name',default='定制拼豆图纸');p.add_argument('--board',type=int,default=29)
    p.set_defaults(func=freeze)
    p=sub.add_parser('deliver',help='Generate one-page customer chart and verified printable sheets')
    p.add_argument('--master',required=True);p.add_argument('--out',required=True);p.set_defaults(func=deliver)
    p=sub.add_parser('verify',help='Detect any matrix/palette/output change or corruption')
    p.add_argument('--master',required=True);p.add_argument('--delivery',required=True);p.set_defaults(func=verify)
    p=sub.add_parser('remove-background',help='Remove edge-connected color, produce UNAPPROVED candidate CSV')
    p.add_argument('--master',required=True);p.add_argument('--background-code',required=True)
    p.add_argument('--out',required=True);p.set_defaults(func=remove_background)
    p=sub.add_parser('generate',help='Produce UNAPPROVED candidate from photo, cartoon, or existing pixel art')
    p.add_argument('--image',required=True);p.add_argument('--grid',type=int,default=58)
    p.add_argument('--colors',type=int,default=28);p.add_argument('--out',required=True)
    p.add_argument('--mode',choices=['photo','cartoon','pixel'],default='photo')
    p.add_argument('--filter',choices=['none','low','medium','high'],default=None)
    p.add_argument('--cartoon-style',choices=['soft','comic','poster'],default='soft')
    p.add_argument('--cartoon-engine',choices=['offline','external'],default='offline')
    p.add_argument('--cartoon-image',help='Image already stylized by your licensed AI model; required by external cartoon engine')
    p.add_argument('--pixel-cell',type=int,help='Pixels per bead cell when importing pixel art')
    p.add_argument('--pixel-origin-x',type=int,help='Grid start X in source pixels')
    p.add_argument('--pixel-origin-y',type=int,help='Grid start Y in source pixels')
    p.set_defaults(func=generate)
    p=sub.add_parser('import-pixel',help='Import pre-pixelated art using central sampling, avoiding resampling color bleed')
    p.add_argument('--image',required=True);p.add_argument('--grid',type=int,default=58)
    p.add_argument('--colors',type=int,default=28);p.add_argument('--out',required=True)
    p.add_argument('--filter',choices=['none','low','medium','high'],default=None)
    p.add_argument('--pixel-cell',type=int)
    p.add_argument('--pixel-origin-x',type=int)
    p.add_argument('--pixel-origin-y',type=int)
    p.set_defaults(func=generate,mode='pixel')

    return ap


def main():
    ap=parser()
    args=ap.parse_args()
    try:
        if getattr(args,'board',29)<1: raise PatternError('board 需为正整数')
        args.func(args)
    except (PatternError, OSError, ValueError, KeyError, ImportError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        return 2
    return 0

if __name__=='__main__':
    raise SystemExit(main())
