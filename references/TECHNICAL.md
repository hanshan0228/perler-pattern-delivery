# Technical contract

## Data

- Accepted matrix CSV: UTF-8 / UTF-8 BOM with first row `行\\列,1,...,W`, then labeled rows `1,<code>,...` OR bare rectangular CSV cells. Also accepts editor JSON as a nested list or `{ "grid": [[...]] }` with null converted to EMPTY.
- Color token: one exact code present in the pinned palette, or `EMPTY` for deliberately unoccupied position.
- No fallback to most-common color, nearest color, blank white or fuzzy guessed codes when reading a master.
- `freeze` creates canonical CSV + pinned palette + SHA-256 manifest. `deliver` performs a trust check before working; `verify` checks generated checksums and grid semantics.
- New approval = new master location, never mutate an existing one.

## Rendering

- Main sheet includes a pixel-perfect preview and the same matrix with cell codes, plus legends and quantities.
- Underlying grid cells use exact RGB palette values, no gradient, opacity or bilinear interpolation.
- Grid lines are a visual layer. Label text sits on top of each cell. To verify color, use semantic_pixels.png, not OCR on the illustrated chart.
- Preserve empty cells as transparent in semantic_pixels.png, and as a white checker-free blank in practical charts.
- A2 customer sheet is one-page overview; A4 board output is for actual placing.

## Lifecycle

```
new photo -> generate candidate -> review/optional human pixel edits -> approve -> freeze v1
                                                        |
                                                  immutable master
                                                        |
                                         deliver as many layout variants as desired

approved master -> remove-background -> new candidate -> review -> freeze v2
```

## Security & privacy

- Scripts run locally; no images, customers, matrices or fingerprints are sent to network.
- Never overwrite input images, original matrix, or a frozen master.
- Avoid including personally identifying original photos in publicly shared skill ZIP archives or published repositories.

## Fail closed

- On a mismatch, stop with an error message. Never silently regenerate a different figure, substitute a source image or pick a different color palette.

## v2.4 deterministic rendering verification

- All four chart axes contain every integer from 1 to the actual row/column count. Codes use fitted glyph bounds; each occupied cell uses its exact pinned MARD code and fill. Empty cells use × and do not count as beads.
- Candidate validation v2 and delivery validation v3 compare actual PNG pixels to an independent re-execution of the deterministic renderer; PDFs are recreated with ReportLab invariant mode and compared byte-for-byte. Candidate palette is checked against the repository reference. Approved delivery uses its frozen palette and matrix.
- Approved ZIP now contains the canonical matrix and palette, with a complete expected inventory. ZIP duplicate paths and missing ZIP are rejected.
- Verification requires the same renderer/font/dependency environment. Use the trusted original MASTER and regenerate if environment or format differs. Older delivery manifests remain usable as historical records but do not meet this new render-validation contract.
- These checks detect output mismatch even with a rewritten output hash manifest. They cannot secure an attacker-controlled renderer, altered trusted MASTER or fabricated visual review. Store approved master fingerprints independently when needed.

## v2.5 candidate-only optimization

`portrait_quality.py` operates on area-average square-grid RGB samples. It selects actual color codes with a deterministic greedy weighted squared CIELAB ΔE76 objective, considers the legacy flat palette as a fallback, then assigns each sample to its nearest selected color. Focus rectangles multiply weights by three; source edge weights are capped. One synchronous cleanup pass skips focus regions, strong source edges, borders and non-singletons; replacement requires three agreeing four-neighbors, at most 1.5 extra ΔE76, and at most 8 ΔE76 between bead colors. No dithering or model downloads. `prepare` v3 diagnostics are recomputed during verification; previous v2 prepared manifests remain readable. The metric is not CIEDE2000, physical color validation or a likeness measure. The production rendering core is unchanged.
