"""Readable A4 board output for unapproved first sheets; exact same matrix."""
from pathlib import Path
import perler_delivery as p

def board_paths(rows):
    return {'boards_color_A4.pdf','boards_bw_A4.pdf'} | {f'boards/board_{i:02d}_{k}.png' for i in range(1,len(p.boards(rows,29))+1) for k in ('color','bw')}

def make_boards(root,rows,palette):
    root=Path(root);(root/'boards').mkdir()
    for kind in ('color','bw'):
        pages=[]
        for i,(r,c,y,x,part) in enumerate(p.boards(rows,29),1):
            fn=root/'boards'/f'board_{i:02d}_{kind}.png'
            p.render_board(part,palette,r,c,y,x,bw=kind=='bw',readable=True).save(fn,optimize=True); pages.append(fn)
        p.pdf_from_images(pages,root/f'boards_{kind}_A4.pdf')

def verify_boards(root,rows,palette):
    root=Path(root)
    for kind in ('color','bw'):
        pages=[]
        for i,(r,c,y,x,part) in enumerate(p.boards(rows,29),1):
            path=root/'boards'/f'board_{i:02d}_{kind}.png';p.verify_png(path,p.render_board(part,palette,r,c,y,x,bw=kind=='bw',readable=True));pages.append(path)
        p.verify_pdf(pages,root/f'boards_{kind}_A4.pdf','A4')
