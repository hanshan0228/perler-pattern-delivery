#!/usr/bin/env python3
"""Quality-gated first cartoon bead sheet; never approves or mutates a MASTER.

The image model creates ONLY a reference illustration. This local pipeline creates
all grid data, previews, labels and counts from actual MARD color codes.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps
import perler_delivery as p
from cartoon_pipeline import open_rgb

SCHEMA = 'first-sheet-v4'
PREVIOUS_SCHEMA = 'first-sheet-v3'
LEGACY_SCHEMA = 'first-sheet-v2'
PHOTO_CHECKS = ('recognizable_subject', 'realistic_not_cartoon', 'framing_and_silhouette',
                'key_features_readable', 'clean_regions_and_no_artifacts')

def checks_for(mode):
    if mode=='photo': return PHOTO_CHECKS
    if mode=='cartoon': return CHECKS
    raise p.PatternError('invalid portrait mode')
VARIANTS = ('detail', 'flat', 'portrait', 'regional', 'coherent')
ALL_VARIANTS = VARIANTS + ('finish', 'tone')

def active_variants(meta):
    return VARIANTS + (('finish',) if 'region_spec' in meta else ()) + (('tone',) if 'region_plan' in meta else ())
CHECKS = ('recognizable_subject', 'cartoon_not_photo_filter', 'framing_and_silhouette',
          'key_features_readable', 'clean_regions_and_no_artifacts')


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def require(condition, message):
    if not condition:
        raise p.PatternError(message)


def fit_square(im):
    """Preserve the entire illustration, never silently cut off hair or flowers."""
    im = im.convert('RGB')
    w,h = im.size
    # Use median border color for neutral padding (once, never per-grid blending).
    arr = np.asarray(im)
    border=np.concatenate((arr[0],arr[-1],arr[:,0],arr[:,-1]))
    bg=tuple(int(x) for x in np.median(border,axis=0))
    canvas=Image.new('RGB',(max(w,h),)*2,bg)
    canvas.paste(im,((canvas.width-w)//2,(canvas.height-h)//2))
    return canvas


def samples(stage, n, variant):
    if variant=='flat':
        return np.asarray(stage.resize((n,n),Image.Resampling.BOX),dtype=float)
    # Median of each cell's central 3x3 samples: avoids tiny antialiasing slivers.
    a=np.asarray(stage.resize((n*5,n*5),Image.Resampling.BOX),dtype=float)
    return np.median(a.reshape(n,5,n,5,3)[:,1:4,:,1:4,:],axis=(1,3))


def map_candidate(stage, n, colors, palette, variant):
    data=samples(stage,n,variant)
    return p.quantize_pixels(data,n,colors,palette)


def make_comparison(root, original, stage, variants, palette, mode="cartoon"):
    labels=['Original reference','AI cartoon base' if mode=='cartoon' else 'Photo source',
            'Detail - central median','Flat - area mean','Portrait - MARD constrained','Regional - palette swaps','Coherent - spatial refinement']
    benchmark=p.semantic_image(p.read_matrix(p.ROOT/'examples'/'approved_87x87.csv'),palette)
    images=[original,stage,*[p.semantic_image(variants[v],palette) for v in VARIANTS]]
    if 'finish' in variants:
        images.append(p.semantic_image(variants['finish'],palette)); labels.append('Region-aware finish')
    if 'tone' in variants:
        images.append(p.semantic_image(variants['tone'],palette)); labels.append('Local skin tone refinement')
    images.append(benchmark)
    labels.append('Approved style benchmark (87)')
    canvas=Image.new('RGB',(1830,70+510*((len(images)+3)//4)),'#f7f3ef');d=ImageDraw.Draw(canvas)
    d.text((25,15),'FIRST SHEET / VISUAL REVIEW - compare actual pixel candidates',font=p.font(26,True),fill='#30282e')
    for i,(im,label) in enumerate(zip(images,labels)):
        x=25+(i%4)*450;y=65+(i//4)*510
        resample=Image.Resampling.NEAREST if i>=2 else Image.Resampling.LANCZOS
        thumb=ImageOps.contain(im.convert('RGB'),(430,430),resample)
        canvas.paste(thumb,(x+(430-thumb.width)//2,y+(430-thumb.height)//2))
        d.text((x,y+445),label,font=p.font(20,True),fill='#30282e')
    canvas.save(root/'review_comparison.png')


def prepare(args):
    original,root=Path(args.image),Path(args.out)
    mode=getattr(args,'mode','cartoon'); checks=checks_for(mode)
    require(original.is_file(),'需要实际原始照片文件')
    art_arg=getattr(args,'cartoon_image',None)
    if mode=='cartoon':
        require(art_arg and Path(art_arg).is_file(),'需要实际生成的卡通底图文件；不允许用离线滤镜冒充 AI 底图')
        art=Path(art_arg)
        require(p.sha_file(original)!=p.sha_file(art),'卡通底图与原图相同，不能作为卡通化结果')
    else:
        require(not art_arg,'写实模式禁止传入卡通底图')
        art=original
    stage_file='cartoon_stage.png' if mode=='cartoon' else 'photo_stage.png'
    require(1<=args.grid<=145 and 1<=args.colors<=120,'grid 1..145, colors 1..120')
    require(not root.exists(),'候选目录已存在，请用新目录')
    photo=open_rgb(original,max_side=1200);stage=fit_square(open_rgb(art,max_side=1200))
    require(len(stage.getcolors(maxcolors=2) or [])!=1,'卡通底图是单色，请重新生成')
    import portrait_quality as quality
    import spatial_quality as spatial
    regions=getattr(args,'focus',None) or []
    quality.focus_mask(args.grid,regions)
    palette=p.load_palette(p.PALETTE);root.mkdir(parents=True)
    shutil.copyfile(p.PALETTE,root/'palette.json')
    stage.save(root/stage_file)
    reference=samples(stage,args.grid,'flat')
    variants={}; metadata={}; scores={}
    region_arg=getattr(args,'regions',None)
    plan_arg=getattr(args,'region_plan',None)
    require(not (plan_arg and region_arg),'choose either reviewed region plan or manual polygons')
    region_plan=None
    if plan_arg:
        import auto_regions
        region_plan=auto_regions.load_plan(plan_arg,stage,args.grid)
    region_spec=region_plan['regions'] if region_plan else (load(Path(region_arg)) if region_arg else None)
    if region_spec is not None:
        import region_finish
        require(isinstance(region_spec,list) and bool(region_spec),'regions must be a nonempty region list')
        region_finish.masks(args.grid,region_spec)
    finish_colors=getattr(args,'finish_colors',None) or args.colors
    require(1<=finish_colors<=args.colors,'finish-colors must not exceed overall budget')
    active=VARIANTS + (('finish',) if region_spec is not None else ()) + (('tone',) if region_plan else ())
    for v in active:
        if v=='tone':
            import tone_quality
            rows,tone_report=tone_quality.refine(reference,variants['finish'],palette,region_spec)
        elif v=='finish':
            rows,finish_report=region_finish.optimize(reference,variants['coherent'],palette,region_spec,max_colors=finish_colors)
        elif v=='regional':
            rows,regional_report=spatial.refine_palette(reference,variants['portrait'],palette,regions)
        elif v=='coherent':
            rows,spatial_report=spatial.regularize(reference,variants['portrait'],palette,regions)
        else:
            rows=(quality.optimize(reference,args.colors,palette,variants['flat'],regions)
                  if v=='portrait' else map_candidate(stage,args.grid,args.colors,palette,v))
        if v=='portrait':
            rows,edits=quality.conservative_cleanup(reference,rows,palette,regions)
        else: edits=0
        scores[v]=quality.metrics(reference,rows,palette,regions)
        scores[v].update(spatial.continuity(reference,rows,palette))
        scores[v]['conservative_cleanup_edits']=edits
        counts,empty,w,h=p.stats(rows,palette)
        require(len(counts)>=2,'转换后不足两种颜色，不能交付肖像候选')
        target=root/v;target.mkdir()
        p.write_matrix(target/'candidate_matrix.csv',rows)
        p.save_preview(rows,palette,target/'candidate_preview.png')
        p.semantic_image(rows,palette).save(target/'semantic_pixels.png')
        variants[v]=rows
        metadata[v]={'codes_sha256':p.digest_codes(rows),'colors':len(counts),'beads':sum(counts.values()),
                     'files':{f.name:p.sha_file(f) for f in target.iterdir()}}
    make_comparison(root,photo,stage,variants,palette,mode)
    manifest={'schema':SCHEMA,'status':'UNAPPROVED','grid':args.grid,'max_colors':args.colors,
              'mode':mode,'stage_file':stage_file,'original_sha256':p.sha_file(original),'source_art_sha256':p.sha_file(art),
              'stage_sha256':p.sha_file(root/stage_file),'palette_sha256':p.sha_file(root/'palette.json'),
              'comparison_sha256':p.sha_file(root/'review_comparison.png'),'variants':metadata,
              'focus_regions':regions,'quality_metrics':scores,
              'spatial_report':spatial_report,'regional_report':regional_report,'pareto_diagnostics':spatial.pareto(scores),
              'quality_metric_reference':'all variants versus same area-average stage; weighted Delta E76, not likeness score'}
    if region_spec is not None:
        manifest.update(region_spec=region_spec,finish_report=finish_report,finish_colors=finish_colors)
    if region_plan is not None:
        manifest.update(region_plan=region_plan,tone_report=tone_report)
    dump(root/'prepare.json',manifest)
    dump(root/'visual_review_TEMPLATE.json',{'variant':'detail','codes_sha256':metadata['detail']['codes_sha256'],
         'comparison_sha256':manifest['comparison_sha256'],'checks':{k:False for k in checks},'notes':''})
    print('PREPARED: inspect review_comparison.png and chosen candidate at full resolution; then record actual visual review. No master created.')


def verified_variant(root, v):
    require(v in ALL_VARIANTS,'unknown variant')
    meta=load(root/'prepare.json')
    require(meta['schema'] in (SCHEMA,PREVIOUS_SCHEMA,LEGACY_SCHEMA) and meta['status']=='UNAPPROVED','invalid prepare manifest')
    mode=meta['mode']; checks_for(mode)
    require(meta['stage_file']==('cartoon_stage.png' if mode=='cartoon' else 'photo_stage.png'),'invalid stage file')
    require(p.sha_file(root/'palette.json')==p.sha_file(p.PALETTE),'candidate palette differs from pinned MARD reference')
    for file,key in [('palette.json','palette_sha256'),(meta['stage_file'],'stage_sha256'),('review_comparison.png','comparison_sha256')]:
        require(p.sha_file(root/file)==meta[key],f'{file} changed')
    target=root/v; info=meta['variants'][v]
    require(set(info['files'])=={'candidate_matrix.csv','candidate_preview.png','semantic_pixels.png'},'missing variant file')
    for fn,sha in info['files'].items():
        require(Path(fn).name==fn and p.sha_file(target/fn)==sha,f'{v}/{fn} changed')
    rows=p.read_matrix(target/'candidate_matrix.csv');palette=p.load_palette(root/'palette.json')
    counts,empty,w,h=p.stats(rows,palette)
    require(p.digest_codes(rows)==info['codes_sha256'],'matrix digest mismatch')
    require((w,h)==(meta['grid'],meta['grid']) and len(counts)<=meta['max_colors'],'grid/color limit mismatch')
    require(len(counts)==info['colors'] and sum(counts.values())==info['beads'],'statistics mismatch')
    with Image.open(target/'semantic_pixels.png') as pixels:
        require(pixels.mode=='RGBA' and pixels.size==(w,h) and pixels.tobytes()==p.semantic_image(rows,palette).tobytes(),'semantic pixels mismatch')
    p.verify_png(target/'candidate_preview.png',p.preview_image(rows,palette))
    if meta['schema'] in (SCHEMA,PREVIOUS_SCHEMA):
        import portrait_quality as quality
        with Image.open(root/meta['stage_file']) as stage:
            stage=stage.convert('RGB')
            reference=samples(stage,meta['grid'],'flat')
            if 'region_plan' in meta:
                import auto_regions
                plan=auto_regions.verify_plan(meta['region_plan'],stage,meta['grid'])
                require(plan['regions']==meta['region_spec'],'reviewed plan differs from used regions')
        reported=meta['quality_metrics'][v]
        recomputed=quality.metrics(reference,rows,palette,meta['focus_regions'])
        if meta['schema']==SCHEMA:
            import spatial_quality as spatial
            recomputed.update(spatial.continuity(reference,rows,palette))
            if v=='regional':
                _,baseline,_,_,_=verified_variant(root,'portrait')
                expected,report=spatial.refine_palette(reference,baseline,palette,meta['focus_regions'])
                require(rows==expected and meta['regional_report']==report,'regional refinement mismatch')
            if v=='finish':
                import region_finish
                _,baseline,_,_,_=verified_variant(root,'coherent')
                expected,report=region_finish.optimize(reference,baseline,palette,meta['region_spec'],max_colors=meta['finish_colors'])
                require(rows==expected and meta['finish_report']==report,'region finish mismatch')
            if v=='tone':
                import tone_quality
                _,baseline,_,_,_=verified_variant(root,'finish')
                expected,report=tone_quality.refine(reference,baseline,palette,meta['region_spec'])
                require(rows==expected and meta['tone_report']==report,'tone refinement mismatch')
            if v=='coherent':
                _,baseline,_,_,_=verified_variant(root,'portrait')
                expected,report=spatial.regularize(reference,baseline,palette,meta['focus_regions'])
                require(rows==expected and meta['spatial_report']==report,'spatial refinement mismatch')
        require(all(reported.get(k)==value for k,value in recomputed.items()),'candidate quality metrics mismatch')
    return meta,rows,palette,counts,empty


def review_ok(review,meta,v):
    require(review.get('variant')==v and review.get('codes_sha256')==meta['variants'][v]['codes_sha256'] and review.get('comparison_sha256')==meta['comparison_sha256'],'review not bound to current candidate/comparison')
    require(all(review.get('checks',{}).get(k) is True for k in checks_for(meta['mode'])),'visual review incomplete or failed; correct the illustration or regenerate candidate before showing the chart')
    require(isinstance(review.get('notes'),str) and len(review['notes'].strip())>=12,'record concrete visible features and comparison; no boilerplate approvals')


def verify_diagnostics(root, meta):
    if meta['schema']!=SCHEMA: return
    import spatial_quality as spatial
    active=active_variants(meta)
    require(set(meta['variants'])==set(active) and set(meta['quality_metrics'])==set(active),'incomplete candidate set')
    for variant in active:
        verified_variant(root,variant)
    require(meta['pareto_diagnostics']==spatial.pareto(meta['quality_metrics']),'Pareto diagnostics mismatch')


def select(args):
    root,out=Path(args.prepared),Path(args.out)
    meta,rows,palette,counts,empty=verified_variant(root,args.variant)
    review=load(Path(args.review));review_ok(review,meta,args.variant)
    verify_diagnostics(root,meta)
    require(not out.exists(),'output exists; refuse overwrite')
    out.mkdir(parents=True)
    p.write_matrix(out/'candidate_matrix.csv',rows)
    shutil.copyfile(root/'palette.json',out/'palette.json')
    p.semantic_image(rows,palette).save(out/'semantic_pixels.png')
    p.save_preview(rows,palette,out/'pixel_preview.png')
    p.legend_csv(out/'legend.csv',counts,palette)
    p.render_grid(rows,palette,cell=min(50,max(24,3800//meta['grid'])),readable=True).save(out/'pattern_with_codes.png')
    p.render_customer(rows,palette,args.name,29,counts,empty,out/'candidate_sheet.png',approved=False,readable=True)
    p.pdf_from_images([out/'candidate_sheet.png'],out/'candidate_sheet_A2.pdf','A2')
    import print_contract as printing
    printing.make_boards(out,rows,palette)
    dump(out/'visual_review.json',review)
    info={'schema':SCHEMA,'status':'UNAPPROVED','mode':meta['mode'],'variant':args.variant,'grid':meta['grid'],
          'codes_sha256':p.digest_codes(rows),'name':args.name,'colors':len(counts),'beads':sum(counts.values()),'empty':empty,
          'board_count':len(p.boards(rows,29)),'visual_review':'recorded, NOT customer approval',
          'print_version':2,'files':{f.relative_to(out).as_posix():p.sha_file(f) for f in out.rglob('*') if f.is_file()}}
    dump(out/'candidate_validation.json',info)
    verify(args=argparse.Namespace(prepared=str(root),sheet=str(out)))
    print('FIRST SHEET READY: candidate_sheet.png. Await explicit customer approval before freeze.')


def verify(args):
    root,out=Path(args.prepared),Path(args.sheet)
    info=load(out/'candidate_validation.json')
    require(info['schema'] in (SCHEMA,PREVIOUS_SCHEMA,LEGACY_SCHEMA) and info['status']=='UNAPPROVED','invalid candidate status')
    v=info['variant'];meta,rows,palette,counts,empty=verified_variant(root,v)
    require(info.get('mode')==meta['mode'],'mode mismatch')
    verify_diagnostics(root,meta)
    review_ok(load(out/'visual_review.json'),meta,v)
    required={'candidate_matrix.csv','palette.json','semantic_pixels.png','pixel_preview.png','legend.csv','pattern_with_codes.png','candidate_sheet.png','candidate_sheet_A2.pdf','visual_review.json'}
    readable=info.get('print_version')==2
    if readable:
        import print_contract as printing
        required.update(printing.board_paths(rows))
    require(set(info['files'])==required,'incomplete first sheet file list')
    for fn,sha in info['files'].items(): require(p.sha_file(out/fn)==sha,f'{fn} changed')
    require(p.read_matrix(out/'candidate_matrix.csv')==rows and p.digest_codes(rows)==info['codes_sha256'],'selected matrix changed')
    require(p.load_palette(out/'palette.json')==palette,'selected palette changed')
    with Image.open(out/'semantic_pixels.png') as im:
        require(im.mode=='RGBA' and im.size==(meta['grid'],)*2 and im.tobytes()==p.semantic_image(rows,palette).tobytes(),'selected semantic pixels mismatch')
    require((info['grid'],info['colors'],info['beads'],info['empty'],info['board_count'])==(meta['grid'],len(counts),sum(counts.values()),empty,len(p.boards(rows,29))),'selected counts changed')
    import csv
    with (out/'legend.csv').open(encoding='utf-8-sig',newline='') as f:
        legend=list(csv.reader(f))[1:]
    require(len(legend)==len(counts) and {r[1]:(r[0],r[2],int(r[3])) for r in legend}=={c:('MARD',palette[c],n) for c,n in counts.items()},'legend mismatch')
    p.verify_png(out/'pixel_preview.png',p.preview_image(rows,palette))
    p.verify_png(out/'pattern_with_codes.png',p.render_grid(rows,palette,cell=min(50,max(24,3800//meta['grid'])),readable=readable))
    p.verify_png(out/'candidate_sheet.png',p.render_customer(rows,palette,info['name'],29,counts,empty,approved=False,readable=readable))
    p.verify_pdf([out/'candidate_sheet.png'],out/'candidate_sheet_A2.pdf','A2')
    if readable: printing.verify_boards(out,rows,palette)
    print('VERIFIED: candidate matrix, palette, pixels, counts, re-rendered PNG/PDF and generated file hashes. Visual review is a declared human/agent check, not algorithmic aesthetic certification.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('prepare');a.add_argument('--image',required=True);a.add_argument('--mode',choices=['cartoon','photo'],default='cartoon');a.add_argument('--cartoon-image');a.add_argument('--out',required=True);a.add_argument('--grid',type=int,default=87);a.add_argument('--colors',type=int,default=33);a.add_argument('--focus',nargs=4,type=float,action='append',metavar=('X0','Y0','X1','Y1'),help='Optional reviewed region in normalized padded-stage coordinates; repeatable');a.add_argument('--finish-colors',type=int,help='Optional lower color budget for regional finish only');a.add_argument('--regions',help='Reviewed normalized polygon JSON: skin, hair, cloth, background, protect');a.add_argument('--region-plan',help='Source-bound reviewed mask plan from auto_regions.py accept');a.set_defaults(func=prepare)
    a=sub.add_parser('select');a.add_argument('--prepared',required=True);a.add_argument('--variant',choices=ALL_VARIANTS,required=True);a.add_argument('--review',required=True);a.add_argument('--out',required=True);a.add_argument('--name',default='卡通定制肖像');a.set_defaults(func=select)
    a=sub.add_parser('verify');a.add_argument('--prepared',required=True);a.add_argument('--sheet',required=True);a.set_defaults(func=verify)
    args=parser.parse_args()
    try: args.func(args)
    except (p.PatternError,OSError,ValueError,KeyError,TypeError) as exc:
        print('ERROR:',exc,file=sys.stderr);return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
