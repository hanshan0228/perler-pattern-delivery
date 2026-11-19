# 身份保真卡通底图提示词 / identity-preserving illustration prompt

For a licensed image model capable of reference-image editing:

> Transform the supplied portrait into a clean, flat-color cartoon illustration. Preserve the person's specific face proportions and the original head pose: eye shapes and spacing, nose width and bridge, lip width and shape, jawline, cheek proportions, hairline, expression, hairstyle, and visible distinctive accessories. Avoid generic beautification, enlarging the eyes, narrowing the jaw, reshaping the nose, exaggerated makeup, face swapping, text, borders, grids, bead textures and logos. Keep the photo's important silhouette and clothing readable at 87×87 pixels. Plain background with limited colors. This is only a cartoon base image; the bead grid, codes and chart are created by deterministic software, never by the image model.

Prompts improve the instruction signal, but do **not** establish identity accuracy. The pipeline must compare the real output to the original and to the final bead preview, then require explicit human approval.

For side-profile photos, preserve the original yaw and expression. Do not force both eyes to be visible when the photo shows only one. Do not invent accessories or change shoulder pose.
