# Sources, license & provenance

- Agent Skills open specification: https://agentskills.io/specification and https://github.com/agentskills/agentskills
- Upstream photo-to-MARD pattern workflow and original 291-color HEX palette: https://github.com/ZeweiXu0219/pindou-pattern (MIT License). This Skill is an independently implemented downstream deliverable/verification workflow with compatible color references; the reference HEX swatches are included for offline use.
- `assets/mard_palette.json` is the reference MARD HEX mapping extracted from the previously generated project, whose values correspond to the upstream `scripts/pindou_palette.py`; it is **not a laboratory-measured or manufacturer-certified color profile**.
- `generate` is a first-principles reconstruction of BOX downsampling, CIELAB color clustering, then nearest reference color. It does not promise identical pixels to the upstream code under all versions or environments.
- Board size 29×29 is an operational default, not a claim that every brand/board uses this dimension. Specify another board size when needed.


## v2.2 design references (conceptual only; no source code or weights copied)

- Minivision `photo2cartoon` — https://github.com/minivision-ai/photo2cartoon — research reference for portrait alignment and generation. Existing model weights are not included and not invoked by the offline engine.
- `TachibanaYoshino/AnimeGANv2` — https://github.com/TachibanaYoshino/AnimeGANv2 — neural style transfer reference; upstream README states non-commercial use by default and requires additional commercial authorization. No code or weights copied.
- `LunarXuan/Pindo` — https://github.com/LunarXuan/Pindo — pixel-art/palette/size UI reference, GPLv3; no source code copied.
- `Alightinggc/Perler-Beads-Blueprint-Generator` — https://github.com/Alightinggc/Perler-Beads-Blueprint-Generator — pixel-grid alignment and color matching workflow reference. No source code copied.
- OpenCV bilateral and Canny APIs (optional offline accelerator) — https://docs.opencv.org/4.x/d4/d86/group__imgproc__filter.html and https://docs.opencv.org/4.x/da/d22/tutorial_py_canny.html

The offline cartoon filters and pixel-grid samplers in this repository are independently implemented using Pillow/NumPy and optionally OpenCV.

## v2.9 optional neural backend

- Google MediaPipe SelfieMulticlass: https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter ; official model card states Apache 2.0 and cautions against pixel-perfect-mask use: https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Multiclass%20Segmentation.pdf ; upstream SDK https://github.com/google-ai-edge/mediapipe . No weights or upstream source bundled. Optional runtime not verified in this environment. See SEMANTIC_REGIONS.md.
