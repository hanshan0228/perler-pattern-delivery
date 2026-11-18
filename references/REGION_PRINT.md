# v2.7 reviewed region and print contract

## Region source

Regions are **reviewed manual polygons**, not model segmentation. Coordinates are normalized to the padded square stage, x rightward and y downward. For a new source, inspect actual image and mask boundaries. Apply clothing/hair/skin after a broad background polygon; later non-protect polygons replace prior non-protect labels. Protect polygons are independent and win over all labels. Use tight polygons around actual eyes, lips, earrings, straps and other distinguishing features, not arbitrary rectangles covering the whole face. Protecting a cell preserves the exact prior coherent candidate color, not the original photo's RGB. If the baseline is already wrong, revise the candidate instead of preserving the mistake.

Example format (illustrative coordinates only, not a reusable mask):

```json
[
  {"kind":"skin","polygon":[[0.4,0.2],[0.65,0.2],[0.65,0.6],[0.4,0.6]]},
  {"kind":"protect","polygon":[[0.5,0.3],[0.6,0.3],[0.6,0.37],[0.5,0.37]]}
]
```

`first_sheet.py prepare --regions regions.json --finish-colors 30 --colors 40 ...` adds a sixth candidate, never overwrites the other five. If a protection budget is impossible, fail instead of dropping protected colors.

## Optimization and limits

`region_finish.py` restricts source-supported warm skin cells (reviewed skin polygon, Lab a* >= 0, b* >= -2, L* >= 30, outside protection) to reference palette entries with a* >= 4 and b* >= 5. This is an optional warm-portrait policy, not a universal skin-color truth or calibrated colorimetry. Cool lighting or intentionally non-warm artwork may need the legacy candidate instead. Warm background and neutral hair/cloth receive soft penalties. Palette selection considers the actual reference palette and locked code budget. Rare colors are removed only if every occurrence can be replaced without violating protection, source-edge or per-cell color-error limits. Local seam refinement uses same-region neighbors; it cannot change a protected cell. No guarantee of lower global Delta E, fewer rare colors or more natural skin: compare the source, old candidate, and finish, including protected details. A zero constraint-violation count means only the explicit mask policy passed.

## Print contract

Choose black or white based on the larger relative-luminance contrast ratio. The theoretical minimum (ideal sRGB foreground and background) exceeds 4.5:1; this does not establish printed glyph legibility or anti-aliased edge contrast. Default new `select` outputs `boards/board_XX_color.png`, `boards/board_XX_bw.png` and both A4 PDFs, all derived from the same candidate. The 29x29 boards have larger fitted labels; use A2 only for overview. Validate all page images and PDFs. New candidate manifest `print_version: 2` and approved delivery `validation-v4` select the readable renderer; old manifests still verify with the prior renderer in its matching dependency/font environment. No change to approved MASTER matrix or palette.
