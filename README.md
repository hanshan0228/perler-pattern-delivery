# Perler Pattern Delivery Skill v2.2.0

An executable Agent Skill for creating verified perler/fuse-bead charts and customer-ready sheets without modifying approved pixel data.

- **Immutable master:** Freeze approved color-code grids and palette with SHA-256 checksums.
- **Verified delivery:** Generate pixel-accurate customer sheets, board-split printable PDFs, legends and counts from the same matrix.
- **MARD palette:** Reference color mapping. Physical beads can differ from screen colors.
- **Reproducible:** Command-line workflow, test suite and sample 58×58 / 87×87 matrices.

## New: Cartoon Mode (v2.2)

- **Offline cartoony preprocessing** (edge-preserving smoothing + posterization + controlled linework), styles `soft`, `comic`, `poster`.
- **External AI artwork ingestion** (bring your own legally licensed cartoonized image; no automatic network calls or model downloads).
- **Pixel-art import** with median central-cell sampling, to avoid grid-line color bleed.
- **Candidate-only cleanup** with `none`, `low`, `medium`, `high` strengths.
- Frozen customer-approved matrices remain **byte-for-byte** stable in delivery.

```bash
# Free offline cartoon preprocessing
python scripts/perler_delivery.py generate --image photo.jpg --mode cartoon --cartoon-style soft --grid 87 --colors 33 --filter medium --out ./candidate_cartoon

# From an externally generated illustration (provided by the user)
python scripts/perler_delivery.py generate --image photo.jpg --mode cartoon --cartoon-engine external --cartoon-image illustration.png --grid 87 --colors 33 --out ./candidate_ai

# Import already pixelated drawings with exact cells
python scripts/perler_delivery.py import-pixel --image pixel.png --grid 58 --colors 24 --pixel-cell 16 --out ./candidate_pixel
```

See `references/CARTOON_STYLES.md` for human-friendly prompts, model limitations and workflow.

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
