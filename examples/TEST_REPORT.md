# Validation report — v2.5.0

Local command: `python -m unittest discover -s tests -v` — 37 tests passed (31 existing, 6 new). Exit status 0.

New regressions: deterministic actual-palette selection and color budget; weighted objective before cleanup; normalized focus validation and weighting; conservative singleton cleanup outside protected focus cells; high-contrast eye-like cell preservation; three variant generation and re-computed metric tamper rejection. The existing continuous-axis, numbered-cell, pinned-palette, re-rendered PNG/PDF, approved-matrix and ZIP checks remain enabled. The production renderer, palette, and two approved matrices are byte-identical to v2.4.0.

Two local 87×87 image trials generated all three candidates and passed `verified_variant` (six matrices, each 7,569 beads). No new customer images are published in this repository. Aesthetic approval was not inferred from the diagnostic checks.

Comparison to legacy area-mean variant; ΔE76 measured against the same area-average stage. A smaller metric means closer to the chosen digital reference, not better identity or aesthetics.

| Trial | Legacy actual colors | New actual colors | Legacy focus mean ΔE76 | New focus mean ΔE76 | New at equal actual color budget | Legacy / new isolated cells |
|---|---:|---:|---:|---:|---:|---:|
| Cartoon, max 33 | 28 | 33 | 6.1771 | 5.2448 | 5.4361 (28 colors) | 1060 / 1096 |
| Photo, max 40 | 14 | 39 | 7.7478 | 7.2767 | 7.3740 (14 colors) | 269 / 431 |

The fair same-actual-color comparison is a supplemental offline comparison, not an additional default variant. Results are specific to these two images and manually selected focus regions. New palette selection can increase isolated cells and palette inventory; neither metric claims physical bead accuracy or general visual superiority. Manual visual review remains mandatory. The photo sample still exhibits visible color banding; it has not been approved or frozen.
