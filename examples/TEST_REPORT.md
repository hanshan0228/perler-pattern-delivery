# Validation report — v2.2.0

Run locally with:

```bash
python -m unittest discover -s tests -v
```

**17 tests passed** in this build environment. Checks include:

- MARD 291 reference colors, approved 58×58 (20 colors) and 87×87 (33 colors) matrices, SHA-256 row-code digests unchanged.
- Strict CSV/JSON reading, transparent EMPTY, 29×29 board partitioning.
- Master freeze, mutation rejection, unchanged customer delivery verification.
- Offline `soft`, `comic`, and `poster` generate new visual stages on a textured synthetic portrait.
- Cartoon CLI produces a real one-code-per-cell 29×29 matrix and a reference stage PNG.
- External stylized-image import requires an actual file and records its SHA-256.
- Central cell sampling avoids a synthetic grid line; cleanup operates on copies and preserves input.
- End-to-end candidate→master→deliver→verify succeeded.

This suite validates data integrity, not universal portrait likeness or physical bead color calibration. Manual review of facial features, hair, flowers and thin structural details is mandatory before freezing any new design.
