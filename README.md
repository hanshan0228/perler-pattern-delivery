# Perler Pattern Delivery Skill v2.7.0

## v2.7: Reviewed regions and readable print output

Provide reviewed normalized polygons via `--regions` to add an optional `finish` candidate; optionally lower its budget with `--finish-colors`. Skin constraints apply only to source-supported warm cells, with protected features locked. This is not automatic segmentation. New first sheets and approved deliveries use contrast-maximizing text and color/monochrome A4 board pages, verified by rerendering. Existing master data and legacy verification are preserved. See [REGION_PRINT.md](references/REGION_PRINT.md).

## v2.6: Portrait candidate optimization

Retains the `portrait` candidate: actual-palette constrained color selection, optional reviewed focus rectangles (`--focus X0 Y0 X1 Y1`), and strictly limited low-contrast singleton cleanup outside focus regions. Diagnostic CIELAB ΔE76 and isolation counts support visual comparison; they are not aesthetic certifications. Adds `regional` (bounded equal-count palette swaps) and `coherent` (same palette, source-aware spatial smoothing with hard detail/color-error guards). Five candidates; Pareto diagnostics are not a winner selection. The previous candidates and renderer remain unchanged.

## v2.4: Render integrity gate (retained)

Never ask an image model to draw the final chart. The same deterministic Python renderer produces the numbered grid, color legend and counts for cartoon and realistic portraits. `first_sheet.py prepare --mode photo --image portrait.jpg --grid 87 --colors 40 --out review` uses the original photo; cartoon mode requires an actual artwork file. Review, select and verify before sharing the resulting PNG/PDF. For both candidate and approved sheets, verify checks actual rendered PNG/PDF content, not only hashes. Approved masters are unchanged; use a new output directory for the new validation format. Exact rerender checks require the same font and dependencies.

## Default first-sheet workflow (v2.6)

For new portrait requests, create a real cartoon illustration using an authorized image editor, then run `scripts/first_sheet.py prepare`, review all five candidates, `select`, and `verify`. The deliverable is a numbered, palette-accurate **unapproved** single-sheet chart rather than an illustration or bead mockup. See [first-sheet contract](references/FIRST_SHEET.md) and [SKILL.md](SKILL.md). Offline filters are explicitly experimental.


An executable Agent Skill for creating verified perler/fuse-bead charts and customer-ready sheets without modifying approved pixel data.

- **Immutable master:** Freeze approved color-code grids and palette with SHA-256 checksums.
- **Verified delivery:** Generate pixel-accurate customer sheets, board-split printable PDFs, legends and counts from the same matrix.
- **MARD palette:** Reference color mapping. Physical beads can differ from screen colors.
- **Reproducible:** Command-line workflow, test suite and sample 58×58 / 87×87 matrices.

## Optional low-level tools (legacy v2.2)

- **Offline cartoony preprocessing** (edge-preserving smoothing + posterization + controlled linework), styles `soft`, `comic`, `poster`.
- **External AI artwork ingestion** (bring your own legally licensed cartoonized image; no automatic network calls or model downloads).
- **Pixel-art import** with median central-cell sampling, to avoid grid-line color bleed.
- **Candidate-only cleanup** with `none`, `low`, `medium`, `high` strengths.
- Frozen customer-approved matrices remain **byte-for-byte** stable in delivery.

```bash
# Experimental offline cartoon preprocessing (only on explicit request)
python scripts/perler_delivery.py generate --image photo.jpg --mode cartoon --cartoon-style soft --grid 87 --colors 33 --filter medium --out ./candidate_cartoon

# From an externally generated illustration (provided by the user)
python scripts/perler_delivery.py generate --image photo.jpg --mode cartoon --cartoon-engine external --cartoon-image illustration.png --grid 87 --colors 33 --out ./candidate_ai

# Import already pixelated drawings with exact cells
python scripts/perler_delivery.py import-pixel --image pixel.png --grid 58 --colors 24 --pixel-cell 16 --out ./candidate_pixel
```

See `references/CARTOON_STYLES.md` for prompts, model limitations and workflow. Optional quality enhancement: `python -m pip install opencv-python-headless`; a pure-Pillow fallback works without it.

## Quick start

```bash
python -m pip install -r requirements.txt
python scripts/perler_delivery.py freeze --matrix examples/approved_87x87.csv --name "Flower Portrait" --out ./project/master
python scripts/perler_delivery.py deliver --master ./project/master --out ./project/delivery
python scripts/perler_delivery.py verify --master ./project/master --delivery ./project/delivery
```

For Agent Skills use `SKILL.md`. Full Chinese usage instructions are in [README_CN.md](README_CN.md).

## Source and licensing

The color dataset and image matching approach are based on the project linked in [SOURCES.md](references/SOURCES.md); see the attribution details there. This repository includes an MIT license.
