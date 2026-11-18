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
