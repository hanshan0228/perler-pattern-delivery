# Validation report — v2.4.0

Run: `python -m unittest discover -s tests -v`

31 tests passed in the local build environment (24 previous tests and seven new regression tests).

- Continuous coordinates: all 232 labels across the four sides of a 58×58 chart, including 49–51 and 55–57.
- Strict matrix input: missing column 56 and incorrectly numbered row 90 are rejected.
- Actual cell-label drawing and sampled color fills match the supplied codes, including empty cells.
- Wrong candidate chart PNG, numbered-grid PNG and PDF are rejected even after updating their manifest hashes.
- Substituting a wrong color for A1 in the candidate reference palette is rejected even after updating the palette hash.
- Approved delivery PNG replacement is rejected even after rehashing.
- Realistic first-sheet mode runs without a cartoon artifact, creates an unapproved chart and A2 PDF, and verifies both.
- Approved 58×58 and 87×87 matrix fingerprints and counts remain unchanged; all previous tests passed.

Integration: re-exported the approved 58×58 example as 20 MARD reference colors, 3,364 beads, four 29×29 boards. Full PNG/PDF re-render checks, inventory and ZIP verification passed. Rendered and inspected the A2 PDF.

This is render/data validation under the same trusted renderer, font and dependency environment, not a guarantee of artistic likeness, physical bead color or immunity to an agent bypassing the workflow. The new real-photo sample underwent candidate comparison but was not approved because its facial color transitions were unsatisfactory. No new customer image is included.
