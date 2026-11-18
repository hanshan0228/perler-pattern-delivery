# v2.9 — Optional neural region proposals (MediaPipe)

This adapter is candidate-only and **opt-in**. Use it for a new photo or the actual AI cartoon art, before `first_sheet.py prepare`. It does not edit a MASTER, perform identity recognition, upload images, download model weights, certify visual quality, or bypass region/visual review. The normal heuristic and manual routes remain available. Never silently fall back after a requested neural inference fails.

## Model choice and limitations

Google MediaPipe SelfieMulticlass (256×256, float32) is a pretrained six-class Vision Transformer model. Its official model card specifies Apache License 2.0. Follow the upstream license and attribution for the model and runtime; neither is bundled. The official documentation lists class order (0–5): background, hair, body-skin, face-skin, clothes, others/accessories. The model card explicitly excludes applications requiring pixel-perfect masks; our use is an editable region *proposal*, not a pixel-perfect semantic truth. It does not separately detect eyes, nose, lips, individual flowers, or earrings. Cartoons, stylized images, odd lighting, occlusion and multiple people can fail. Do not automatically mark a mask approved.

- Official API/model: https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter
- Model card/license: https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Multiclass%20Segmentation.pdf
- Official model download: https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite
- Python API: https://developers.google.com/edge/api/mediapipe/python/mp/tasks/vision/ImageSegmenter
- Upstream project: https://github.com/google-ai-edge/mediapipe

## Install and run

Use a compatible Python/OS combination (check current upstream MediaPipe installation support). Ordinary Skill operation needs only `requirements.txt`. Explicitly install the optional dependencies in an environment you control and download the model from the official link above. Record the exact downloaded file's SHA-256 and keep that model fixed for reproducibility. A hash pins file contents; it is not an upstream digital signature or proof of authenticity. No `latest` download is done by the Skill itself. For commercial use, comply with the separate licenses and make sure you have permission to use customer imagery.

```bash
python -m pip install -r requirements-semantic.txt
python -c "import hashlib; print(hashlib.sha256(open('selfie_multiclass_256x256.tflite','rb').read()).hexdigest())"
# Replace SHA_FROM_PREVIOUS_COMMAND with the actual 64-digit SHA-256.
python scripts/auto_regions.py propose --stage photo.jpg --grid 87 \
  --model selfie_multiclass_256x256.tflite --model-sha256 SHA_FROM_PREVIOUS_COMMAND \
  --out neural_mask_review
```

For cartoon generation, give the actual cartoon base to `--stage`, not the original portrait. Both paths use exactly the padded square stage used by `first_sheet.py`, with all probabilities projected onto the intended bead grid. A proposal writes `stage.png`, `proposed_mask.png`, `overlay.png`, `mask_editor.html` and `proposal.json`. The latter records the model hash, runtime version, class order, thresholds, and projection counts. The output is **UNREVIEWED**.

## Projection and safety

Six model confidence maps must be finite, square, sized at least as large as the target grid, and in [0,1]. Each probability map is area-averaged into exact bead cells. The winner must exceed three independent default gates: mean score ≥0.70, lead over runner-up ≥0.15, and ≥70% of source samples having the same winning class. These are conservative engineering thresholds, not calibrated probabilities of accuracy. The corresponding CLI overrides are `--min-confidence`, `--min-margin`, `--min-coverage`; decreasing them trades abstention for more possible mislabels. Inspect every result. Body and face skin collapse to the existing skin label, accessories to protect, uncertain cells to unknown. A source-edge heuristic inside face-supported regions conservatively adds a one-cell protective margin. This is NOT landmark detection. Unknown is not a fixed cell during global optimization; explicitly paint protect where preservation is required.

Open and inspect the local mask editor. Correct misclassified regions, protect delicate eyes, lips, ears, accessories and silhouette, and use unknown for uncertain cells. Export the exact-grid PNG and bind it to the stage using the existing workflow:

```bash
python scripts/auto_regions.py accept --proposal neural_mask_review \
  --mask reviewed_mask.png --notes 'Record the real inspected boundaries and manual corrections.' \
  --out reviewed_plan.json
python scripts/first_sheet.py prepare --mode photo --image photo.jpg \
  --grid 87 --colors 39 --finish-colors 30 --region-plan reviewed_plan.json --out review
```

The accepted plan retains model/proposal/mask digests for traceability; this is a declared review record, not an authenticated signature. All previous non-neural `finish` and `tone` checks remain active. Compare the original and all candidates visually before `select`; continue with the previously documented numbered-chart verification gate. Do not claim eight candidates; the neural model supplies masks to the existing seven candidate routes.

## Validation status

The probability projection, model file validation, mocked MediaPipe API integration, review gate and source binding are covered by tests. **Real model inference was not executed during v2.9 development because the runtime and weights were unavailable. No actual segmentation-accuracy or visual-improvement claim is made.** To run the additional real-runtime smoke test, set `PERLER_SELFIE_MODEL` and `PERLER_SELFIE_SHA256` to the local model and its hash, then run `python -m unittest discover -s tests -p test_semantic_regions.py -v`. This only confirms runtime compatibility, not photo-segmentation quality. Test representative photos and illustrations, inspect the masks, and compare actual output before adopting the optional backend in production.
