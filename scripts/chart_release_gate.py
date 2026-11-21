#!/usr/bin/env python3
"""Fail-closed verification of customer Perler pattern sheets.

Never accepts an image-only 'pattern' without its structured color-code matrix.
Checks real image pixels, the per-code ledger, geometry, valid MARD colors, and
optionally lossless PDF embedding; strict mode rerenders every glyph from data.
This verifier is NOT a facial-identity or aesthetic-quality classifier.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
from pathlib import Path

from PIL import Image
import perler_delivery as p


def require(ok, message):
    if not ok:
        raise p.PatternError(message)


def checked_legend(path: Path, counts, palette):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        rows=list(csv.reader(f))
    require(rows and rows[0]==['品牌','MARD色号','参考HEX','颗数'], '图例列头不正确')
    observed={}
    for r in rows[1:]:
        require(len(r)==4 and r[0]=='MARD','图例行格式错误')
        code=r[1].strip().upper()
        require(code not in observed,'图例重复色号')
        try: qty=int(r[3])
        except ValueError: raise p.PatternError('图例颗数不是整数')
        require(qty>=0,'图例颗数负数')
        observed[code]=(r[2].strip().upper(),qty)
    expected={c:(palette[c].upper(),qty) for c,qty in counts.items()}
    require(observed==expected, '图例色号、HEX或颗数与真实矩阵不匹配')
    return observed


def verify_background_pixels(path:Path, rows, palette, *, board=29):
    """Check all logical cell fills, not a generative approximation."""
    h,w=len(rows),len(rows[0]); n=max(w,h)
    with Image.open(path) as im:
        require(im.mode=='RGB' and im.width==4960, '施工图格式/宽度不是预期的程序输出')
        cell=min(90,max(20,int(4290/n)))
        grid_w=w*cell;grid_h=h*cell
        x=(4960-grid_w)//2
        y=1030+(4310-grid_h)//2
        require(im.height>=y+grid_h,'施工图网格区域不完整')
        pixels=im.load()
        checked=0
        for r,row in enumerate(rows):
            for c,code in enumerate(row):
                expected=p.rgb(palette[code]) if code!=p.EMPTY else (255,255,255)
                # Avoid symbol glyph and border strokes: ink occupies cell center,
                # board lines occupy up to ~5px at edge.
                sample=(x+c*cell+7,y+r*cell+7)
                if pixels[sample]!=expected:
                    raise p.PatternError(f'格子底色不一致：第{r+1}行第{c+1}列，{code}，像素{pixels[sample]} != {expected}')
                checked+=1
    return checked


def verify_pdf_images(pdf:Path, pngs:list[Path]):
    """Compare each embedded print bitmap pixel-for-pixel, without OCR."""
    try: import fitz
    except ImportError as exc: raise p.PatternError('PDF 独立检查需安装 pymupdf: pip install pymupdf') from exc
    doc=fitz.open(pdf)
    try:
        require(len(doc)==len(pngs), f'{pdf.name}: PDF页数错误')
        for i,(page,path) in enumerate(zip(doc,pngs),1):
            imgs=page.get_images(full=True)
            require(len(imgs)==1,f'{pdf.name}: 第{i}页不是单张可核验施工图')
            obj=doc.extract_image(imgs[0][0])
            with Image.open(io.BytesIO(obj['image'])) as found,Image.open(path) as expected:
                a=found.convert('RGB');b=expected.convert('RGB')
                require(a.size==b.size and a.tobytes()==b.tobytes(),f'{pdf.name}: 第{i}页内嵌图案与源PNG不一致')
    finally: doc.close()


def check(args):
    matrix=Path(args.matrix);palette_path=Path(args.palette)
    rows=p.read_matrix(matrix)
    palette=p.load_palette(palette_path)
    # Never trust a supplied "MARD" palette that differs from pinned project.
    require(palette==p.load_palette(p.PALETTE), '参考色卡与仓库291色MARD基准不一致')
    counts,empty,w,h=p.stats(rows,palette)
    require(sum(counts.values())+empty==w*h,'实际豆数不匹配')
    chart=Path(args.chart);legend=Path(args.legend)
    checked_legend(legend,counts,palette)
    checked=verify_background_pixels(chart,rows,palette)
    if args.title is not None:
        exact=p.render_customer(rows,palette,args.title,args.board,counts,empty,approved=False,readable=True)
        p.verify_png(chart,exact)  # full re-render verifies symbols and EVERY axis label
    if args.pdf:
        verify_pdf_images(Path(args.pdf),[chart])
    if args.color_boards:
        parts=p.boards(rows,args.board)
        directory=Path(args.color_boards_dir)
        require(directory.is_dir(),'彩色分板PNG目录不存在')
        color=[directory/f'board_{i:02d}_color.png' for i in range(1,len(parts)+1)]
        verify_pdf_images(Path(args.color_boards),color)
    if args.bw_boards:
        parts=p.boards(rows,args.board)
        directory=Path(args.color_boards_dir)
        bw=[directory/f'board_{i:02d}_bw.png' for i in range(1,len(parts)+1)]
        verify_pdf_images(Path(args.bw_boards),bw)
    report={
        'status':'DATA_VERIFIED_VISUAL_LIKENESS_UNASSESSED',
        'grid':[w,h],'colors':len(counts),'beads':sum(counts.values()),
        'empty':empty,'verified_cell_fills':checked,
        'legend_matches_matrix':True,'mard_palette_matches_fixed_reference':True,
        'symbol_axes_full_rerender':args.title is not None,
        'pdf_embedded_images_checked':bool(args.pdf),
        'board_pdfs_checked':bool(args.color_boards or args.bw_boards),
        'matrix_sha256':p.sha_file(matrix),
        'limits':'不能以此报告证明脸像原照片或艺术质量合格。'
    }
    if args.report:Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return report


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--matrix',required=True)
    ap.add_argument('--palette',required=True)
    ap.add_argument('--chart',required=True)
    ap.add_argument('--legend',required=True)
    ap.add_argument('--title',help='Exact title for the strict full PNG symbol/axis re-render. Omit for fast data checks.')
    ap.add_argument('--pdf',help='Optional A2 print PDF for lossless image comparison')
    ap.add_argument('--color-boards',help='Optional A4 colored boards PDF')
    ap.add_argument('--bw-boards',help='Optional A4 black/white boards PDF')
    ap.add_argument('--color-boards-dir',default='boards')
    ap.add_argument('--board',type=int,default=29)
    ap.add_argument('--report')
    args=ap.parse_args(argv)
    try:check(args)
    except (OSError,ValueError,p.PatternError) as exc:
        ap.exit(2,f'FAILED VALIDATION: {exc}\n')


if __name__=='__main__':main()
