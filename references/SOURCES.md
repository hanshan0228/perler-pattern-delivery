# Sources, license & provenance

- Agent Skills open specification: https://agentskills.io/specification and https://github.com/agentskills/agentskills
- Upstream photo-to-MARD pattern workflow and original 291-color HEX palette: https://github.com/ZeweiXu0219/pindou-pattern (MIT License). This Skill is an independently implemented downstream deliverable/verification workflow with compatible color references; the reference HEX swatches are included for offline use.
- `assets/mard_palette.json` is the reference MARD HEX mapping extracted from the previously generated project, whose values correspond to the upstream `scripts/pindou_palette.py`; it is **not a laboratory-measured or manufacturer-certified color profile**.
- `generate` is a first-principles reconstruction of BOX downsampling, CIELAB color clustering, then nearest reference color. It does not promise identical pixels to the upstream code under all versions or environments.
- Board size 29×29 is an operational default, not a claim that every brand/board uses this dimension. Specify another board size when needed.
