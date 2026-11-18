# v2.7.0 test report

- Full regression: `python -m unittest discover -s tests -v`, 50 tests passed, exit 0 (73.244 s). Six new tests cover region constraints, immutable protected cells, insufficient budget, invalid polygons, all 291 palette contrast checks, board rendering/tampering, and regional-report re-computation.
- Pinned MARD palette and approved 58×58/87×87 matrices compared against v2.6: byte-identical. New approved delivery validation uses v4; old v3 rendering remains available.
- Two 87×87 local technical samples were rendered from real matrices, not image-model charts. Each A2 page and 9 color + 9 monochrome A4 pages matched deterministic rerender; both ZIP inventories/hash checks passed. Sample PDFs rendered with Poppler; inspected actual board pages. No new personal images, masks or customer matrices included in the public Skill repository.

## Measured sample trade-offs

These two local samples use manually reviewed polygons. Metrics are diagnostic, not aesthetic or physical-color certifications. Both retain 7,569 cells; the photo budget is deliberately lower (39 → 30) and cartoon retains 33 colors, so the photo comparison is not a same-budget experiment.

| Metric | Photo, old → finish | Cartoon, old → finish |
|---|---:|---:|
| Colors | 39 → 30 | 33 → 33 |
| Rare colors (≤5 beads) | 9 → 5 | 4 → 3 |
| 4-neighbor isolated cells | 378 → 271 | 463 → 415 |
| Flat-source transitions | 2030 → 1686 | 1355 → 1371 |
| Specified warm-skin rule violations | 628 → 0 | 32 → 0 |
| Protected cells changed | 0 / 354 | 0 / 424 |
| Global mean ΔE76 | 7.5695 → 8.0844 | 5.9450 → 6.0292 |

Visual check: photo reduces some inappropriate colors but still has banding; cartoon finish introduced shoulder shading artifacts and is not necessarily superior to the prior candidate. Neither sample is marked approved; the older candidate must remain available. No claim of automatic visual approval.

# v2.6.0 test report

- `python -m unittest discover -s tests -v`: 44 tests passed (56.381 s); 37 prior tests + 7 spatial tests.
- Existing renderer, pinned MARD palette, approved 58×58 and 87×87 matrices compared byte-for-byte with v2.5.0: unchanged.
- Both real-sample candidate sets passed `verify_diagnostics` (all candidate grids, previews, palette, recomputed metrics, refinements and Pareto list). Inputs and outputs contain customer imagery and are not included in the public repository.

## Same-color-count measurements, 87×87

Both spatial comparisons retain the exact same set of MARD codes and protect all specified focus cells and source edges. The two sample results are not claims of general aesthetic improvement.

| Sample | Actual colors | Flat-source transitions, before → after | Isolated cells, before → after | Changed cells | Focus mean ΔE76, before → after | Global mean ΔE76, before → after |
|---|---:|---:|---:|---:|---:|---:|
| Cartoon |33|332 → 319|1096 → 1094|11|5.2448 → 5.2448|4.9123 → 4.9135|
| Photo |39|2330 → 2030|431 → 378|179|7.2767 → 7.2767|7.5555 → 7.5695|

`regional` (same used count, potentially different MARD code set): cartoon weighted RMS ΔE76 6.3384 → 6.3289, one swap, 68 changed cells; photo 8.0215 → 8.0215, no acceptable swap found. This tests a small local search, not global optimality. No change to approved matrices.

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
