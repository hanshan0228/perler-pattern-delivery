# Perler Pattern Delivery Skill

An executable Agent Skill for creating verified perler/fuse-bead charts and customer-ready sheets without modifying approved pixel data.

- **Immutable master:** Freeze approved color-code grids and palette with SHA-256 checksums.
- **Verified delivery:** Generate pixel-accurate customer sheets, board-split printable PDFs, legends and counts from the same matrix.
- **MARD palette:** Reference color mapping. Physical beads can differ from screen colors.
- **Reproducible:** Command-line workflow, test suite and sample 58×58 / 87×87 matrices.

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