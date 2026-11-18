## v2.9.0 — Optional local neural segmentation adapter (runtime unverified)

- Explicit MediaPipe SelfieMulticlass local model entrypoint, SHA-256/TFLite header checks, six-class confidence projection, ambiguity abstention and accessories/face-edge protection.
- Keep stage-bound human review and seven candidates. No silent fallback on requested inference failure; legacy paths and production rendering unchanged.
- Eight focused tests passed with synthetic probability maps and mocked runtime; optional real-model smoke test skipped (weights and runtime unavailable). No claim of empirically improved segmentation or appearance.

## v2.8.0 — Editable region proposals and conservative local tone refinement

- Optional OpenCV face localization; deterministic color/connectivity suggestions with unknown regions. Offline grid-aligned mask editor, exact PNG label import, and reviewed plan bound to stage pixels and grid size.
- Seventh `tone` candidate inside reviewed skin regions, same actual palette as `finish`, protected features locked, non-increasing local luminance/chroma step errors and isolation guards. No-op on regression.
- Six focused regression tests for proposals, exact mask round-trip, source binding, locks, recomputation and tampering. Existing renderer, reference palette and approved fixtures untouched.

## v2.7.0 — Reviewed region color refinement and readable boards

- Optional region-aware `finish` variant with explicit protected polygons, source-dependent warm-skin constraints, localized continuity and conservative rare-color handling.
- Separate finish color budget; keep original candidates and require actual visual review.
- New candidate and approved charts maximize black/white label contrast and include larger A4 color/monochrome board labels. First sheet verification covers both board PDFs and every board PNG. Legacy render verification remains available.
- Six new targeted tests; unchanged MARD dataset and approved matrix fixtures.

## v2.6.0 — Regional palette refinement and spatial coherence

- Five reviewed candidate variants, including bounded actual-count palette swaps and same-code-set source-aware spatial regularization. No-op if hard error/continuity guards fail.
- Adds flat-region transition metrics and Pareto diagnostics; verifies the new reports and candidates, preserves legacy prepared manifests and the production renderer.
- Seven new regression tests for palette count, locks, error caps, no-op, repeatability, Pareto and tamper detection.

## v2.5.0 — Portrait quality candidates

- Added third `portrait` candidate with palette-constrained weighted ΔE76 optimization, optional reviewed focus regions, and conservative low-contrast singleton cleanup.
- Added comparable diagnostic metrics with re-computation in candidate verification. The two legacy variants, verified renderer, MARD palette and approved matrices are unchanged.
- Added six targeted tests; visual review remains mandatory and metric improvements do not imply aesthetic approval.

## v2.4.0 — Deterministic chart-render integrity

- Explicit no-image-model final-chart contract for every output mode.
- Continuous 1..width / 1..height on all four axes, fitted cell labels, accurate legends.
- Actual PNG rerender comparison and deterministic PDF verification even if output hashes are rewritten.
- Realistic first-sheet mode, candidate A2 PDF, and complete approved delivery ZIP with canonical matrix and pinned palette. Reject mismatched reference palette, missing/extra manifest items, duplicate ZIP entries.
- Preserve approved v2 MASTER files and examples; regenerate historical deliveries into a fresh directory for v3 validation. Same renderer/font/dependencies required for rerender verification.

## v2.3.0 — First-sheet quality gate

- Default portrait intent resolves to a real cartoon-based numbered sheet.
- Added independently runnable prepare/select/verify pipeline with two candidates, a review bound to grid and comparison digests, and an unapproved single-page output.
- Preserve existing approved matrices and freeze/deliver APIs.
- Offline filters remain experimental; visual review is required, not automatic aesthetic certification.

# Changelog

## 2.2.0 — Cartoon candidate generation

- New offline cartoon engine (`scripts/cartoon_pipeline.py`) offering `soft`, `comic`, and `poster` styles, with Pillow-only fallback and optional OpenCV bilateral/Canny acceleration.
- Optional external-cartoon file import (`--cartoon-engine external --cartoon-image PATH`): brings already stylized, authorized images into the original candidate-to-MASTER workflow. It does not upload photos or call an AI API.
- New `--mode photo|cartoon|pixel` and `import-pixel` modes.
- New candidate-only cleanup `--filter none|low|medium|high` with modification metrics. Does **not** change approved masters.
- New color-safe center-of-cell sampling for enlarged pixel art; optional explicit cell dimensions and grid origin.
- Updated English and Chinese documentation, Skill metadata and sourcing/license warnings.
- Preserved existing 58×58 and 87×87 approved-master fingerprints.
- Added seven tests for cartoon styles, import, cleanup, master immutability, and full delivery validation, now 17 tests total.

This is not bundled AnimeGANv2/photo2cartoon inference. Those projects' licensing, weights and runtime constraints must be considered separately.
