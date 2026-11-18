# Cartoon-style source guide for reliable bead patterns

For new portrait charts, follow [FIRST_SHEET.md](FIRST_SHEET.md) first. These legacy options are not the recommended first-sheet entry point.

## Engine selection

- `--mode cartoon --cartoon-engine offline` (legacy low-level experimental mode; NOT the Skill default): reproducible local edge-preserving smoothing, posterization and optional contour overlay. No downloads or network; cannot alter head/body proportions like a trained generative model.
- `--mode cartoon --cartoon-engine external --cartoon-image <PNG>`: import an already stylized image from a tool the user has the right to use. The CLI **does not** invoke a remote model or download a model. It stores a SHA-256 fingerprint of that image and its rendered copy for repeatability.
- `--mode photo`: preserve the original downsample + Lab palette mapping pipeline.
- `--mode pixel` or `import-pixel`: for already-pixelated grid art, central-median sampling avoids including grid borders.

## Recommended prompt for an image-generation agent

If the image-generation tool is available and the user authorizes a cartoon transformation, use the uploaded source image as the reference and request an edited image (not a bead chart yet):

> Transform this supplied portrait into a clean, recognizable bust-length hand-drawn cartoon illustration suitable for a fuse-bead pattern. Preserve the subject's pose, expression, hair silhouette, eye alignment, mouth expression, pink flower placement and clothing features. Simplify background and remove distracting overlaid text from the illustrative output where allowed. Prefer distinct contiguous flat-color regions, limited shading, crisp facial features, smooth but high-contrast silhouettes, and no fine textures or gradients. Do not draw a grid, bead holes, color labels, words, or watermarks; the bead pattern generator will add the exact grid and real MARD palette later. Do not invent additional facial features or change the subject's proportions.

After the model generates an actual image file, use `--cartoon-engine external --cartoon-image path/to/edited.png` to produce the real bead matrix, then inspect and approve the candidate. Preserve the source photo privately; do not put it in the public repository.

## Quality gates

1. The pre-pixel image (`cartoon_stage.png`) must look recognizable and coherent at thumbnail size.
2. Sample at fixed 58x58 or 87x87, then map each grid location to exactly one registered MARD code.
3. Use controlled candidate cleanup (`--filter low|medium|high`) and compare with the unfiltered candidate. For facial details prefer `low` or `medium` first.
4. Review face, lips, eyes, curls, flowers and contours manually. Freezing a pixel matrix is an explicit approval step, **not** an automatic styling step.
5. For any typography/layout request after approval, do not call `generate` again: use `deliver` with the saved MASTER.

## Commercial use

This project's code does not contain pretrained model weights, scraped images, or directly copied source from referenced GitHub projects. External generation services have their own conditions; check commercial licenses independently before using customer images in a paid workflow.
