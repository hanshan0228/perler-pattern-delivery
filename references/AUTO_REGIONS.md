# v2.8: Reviewed region masks and conservative skin tone refinement

This describes the legacy heuristic/manual route. v2.9 also offers an explicit optional local neural adapter; see [SEMANTIC_REGIONS.md](SEMANTIC_REGIONS.md). The legacy route has no identity recognition, cloud upload, model download, or neural semantic segmentation. OpenCV's bundled Haar cascade supplies an approximate face box, not a skin/hair mask. The remainder is a conservative CIELAB color/connectivity heuristic. It can mistake a brown wall for skin, dark backgrounds for hair, or highlights for cloth. Inspect and correct every proposal; mark uncertain regions unknown. Unknown cells can still change during global palette optimization. Only protect is immutable in the `finish` and `tone` candidates. For dark, cool-lit, stylized, or unusual portraits without reliable warm seeds, manually review or skip this optional step entirely. No assumption of one universal skin color.

## Commands

```bash
# Optional for automatic face localization only
python -m pip install opencv-python-headless
# Use the photo for --mode photo; use the actual cartoon art for --mode cartoon.
python scripts/auto_regions.py propose --stage photo.jpg --grid 87 --out mask_review
# Alternatively provide a manually inspected normalized face box or start with a blank mask.
# python scripts/auto_regions.py propose --stage photo.jpg --grid 87 --face .25 .12 .74 .69 --out mask_review
# python scripts/auto_regions.py propose --stage photo.jpg --grid 87 --manual --out mask_review
```

Open `mask_review/mask_editor.html` locally. Check source and overlay, choose a region, paint using the 1/3/5-cell brush, undo if necessary, choose unknown for ambiguous areas and protect for eyes, mouth, delicate outlines or other features. Download an opaque exact-grid RGB(A) PNG. Do not rescale or antialias. No data leaves your browser through this page. Review the edited mask at full size before accepting. The sample editor is generated locally and contains the input image; never commit it or personal images to a public repository.

```bash
python scripts/auto_regions.py accept --proposal mask_review --mask reviewed_mask.png --notes 'Describe the actual corrections and checked region boundaries here.' --out reviewed_plan.json
python scripts/first_sheet.py prepare --mode photo --image photo.jpg --grid 87 --colors 39 --finish-colors 30 --region-plan reviewed_plan.json --out review
```

In cartoon mode use `--image original.jpg --cartoon-image cartoon.png --mode cartoon`, and propose the mask from **cartoon.png**, not original.jpg. The reviewed plan must match the exact square stage pixels and grid size. The file is a record of declared review, not proof of a human identity or authenticated signature. `--regions` and `--region-plan` cannot be combined. The existing manual polygon input remains supported with six candidates.

## Local tone variant and guardrails

`--region-plan` produces seven candidates. `tone` starts from `finish` and only attempts edits within the reviewed skin interior. Skin boundaries, non-skin, protect cells and source edges (ΔE76 >= 12) stay fixed. Only existing adjacent codes are considered; the actual used palette cannot shrink or grow. Warm-skin eligibility stays in force. Each local edit must not increase smooth-link luminance error, chroma error, seam count or isolation counts, and is bounded in source color error. Final checks reject any regression of smooth-link error, seams, isolation, palette or protected cells, and cap mean skin ΔE76 increase at 0.25 and global mean increase at 0.15. No improvement means exact no-op. No dithering, resampling of the final grid or new color codes.

Compare all variants and the source. These measurements use area-average reference cells and ΔE76, not calibrated physical beads or aesthetic acceptance. Select only after actual visual review using the normal `select` and `verify` commands. `verify` reconstructs the selected grid, recomputes the tone report and validates numbered chart, legend, PDF and both A4 board sets. No existing master is modified.
