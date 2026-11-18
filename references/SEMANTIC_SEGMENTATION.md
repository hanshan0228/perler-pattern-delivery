# Semantic segmentation (v2.8)

## Technical basis

- [Official MediaPipe Image Segmenter documentation](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter): SelfieMulticlass category indices 0 background, 1 hair, 2 body-skin, 3 face-skin, 4 clothes, 5 others/accessories. The ordinary binary selfie model is **not** compatible.
- [Official Python task setup](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter?tab=Python): install `mediapipe` in a supported Python environment and provide a local model asset. Models are not packaged in this repository. Confirm model licensing for your use case.

## Usage: actual model inference (when available)

```bash
python -m pip install mediapipe
python scripts/first_sheet.py prepare \
  --image portrait.png --mode photo --grid 87 --colors 39 \
  --mediapipe-model /absolute/path/to/selfie_multiclass_256x256.tflite \
  --out review_model
```

This invokes MediaPipe locally on the padded square portrait stage. The CLI does **not** fetch models from the internet. Missing models, missing package, unsupported category IDs, unexpected mask dimensions, or implausible skin/hair coverage fail with errors.

## Usage: import externally computed indexed category mask

```bash
python scripts/first_sheet.py prepare \
  --image portrait.png --mode photo --grid 87 --colors 39 \
  --segmentation-mask /absolute/path/to/segmentation_classes.png \
  --out review_mask
```

`segmentation_classes.png` must be indexed/grayscale (`P`/`L`) and **same width and height as the pipeline's padded square stage** (saved as `photo_stage.png` or `cartoon_stage.png`). For non-square image, the stage is padded rather than cropped. Derive mask for exactly that stage, not the unpadded original. A colored preview such as an RGB overlay is *not* a valid class mask. Never auto-align guesses.

The importer records `model_inference_executed:false`; a mask imported from hand-reviewed polygons remains manually sourced even if it follows MediaPipe's category indexing. It is incorrect to claim that importing it executed any AI model.

## Sampling and downstream optimization

- Convert stage class mask into an `N×N` categorical bead map with **nearest-neighbor categorical votes** over central cell locations. Never use BOX/bilinear filtering on category IDs.
- Run 6th optional region candidate `finish` using semantic cells. Protect category boundaries, accessory cells and high-contrast face feature cells. Constraints apply to region color choices; the preexisting five candidates remain available.
- No universal skin tone is imposed. The optional warm-skin palette rule activates only where the source itself passes the defined CIELAB warm condition; a cool-lit photo can still need human artistic intervention.
- `--finish-colors` cannot be lower than the number of distinct colors in automatically protected cells. If the budget is impossible, the pipeline fails instead of removing protected eye/outline colors.
- This produces a **proposal**, not aesthetic certification. Neither multi-class segmentation nor numeric ΔE is a reliable identity or expression similarity metric.

## Mandatory visual review and fail-closed verification

Inspect `segmentation_overlay.png` next to `review_comparison.png`, source image and `segmentation_cells.png`. Look for incorrect hair/background classification, spurious skin regions, eroded eyes or mouth, missing accessories, and garment edges. Candidate `select` will refuse until `segmentation_overlay_checked` is explicitly true in the review JSON, and the review is also bound to the candidate matrix and comparison image hashes. The verifier rechecks imported stage-mask SHA, bead-grid mask SHA, overlay SHA, stage alignment, category counts and deterministic downstream output. Do not mark inspection true unless a person or agent has actually inspected the visuals.

## Privacy and dependency limitations

- No human portraits, manually reviewed polygons or proprietary weights are committed to the public repository.
- Standard tests use synthetic category maps, **not** a pretrained-model accuracy benchmark.
- To evaluate actual segmentation accuracy, separately run inference with the official local model on consented sample images and perform mask quality evaluation. Until then, make no general accuracy or visual-improvement claim.
