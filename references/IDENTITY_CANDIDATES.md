# v3.0.3 — 人物相似度优先：构图候选与同条件审查

## 第一原则

**相似度不能靠自己写一个百分比来“保证”。** 先优化面部在最终网格里可用的像素预算，再给候选制作可验证的真实 MARD 网格，最后并排人工比较两次有损转换：原照 → 卡通底图、卡通底图 → 拼豆。

本模块只补充 v3.0.2，**不修改已锁定 MASTER、施工图渲染、配色表、身份审核的 `user_confirmed` 规则**。`frame` 和 `compare` 输出都是未确认候选；没有文件或没有人工检查就不允许声称已通过。

## Step 1：只让图像模型生成无文字的卡通底图

原图作为真实图像参考，不允许凭文字猜人物。提供多个独立候选时须明确来源，不应把不同裁剪冒充独立生成。

身份约束提示词模板（可以直接提供给具有真实参考图功能的模型，不能替代上传原图）：

> Transform the supplied portrait into a clean cel-shaded cartoon illustration while **preserving this person's facial geometry and expression**. Keep the relative eye size and separation, eye tilt, nose width and bridge, mouth shape, cheekbones, chin contour, hairline and head pose as close to the source as possible. Retain hairstyle, clothing silhouette and distinctive features. Do not enlarge the eyes, slim the jaw, alter the age, beautify beyond the original, swap faces or reshape the mouth. No text, grid, labels or bead effects. Plain background with the same dominant lighting mood. Generate distinct candidates rather than repeating a near-identical image.

- 即使提示词写得很严格，生成式模型仍可能改变五官；必须审核实际文件。
- 可选身份保持图像模型需要单独核实**商业许可、权重授权、用户同意、运行环境**；本 Skill 不内置或联网下载这类模型。

## Step 2：构图与面部像素预算

先在**当前文件**上手动标记真实人脸矩形，或用与当前图片 SHA-256 绑定的 `identity_fidelity.py extract` 人脸关键点记录。只有脸框，不代表关键点已识别成功。

```bash
python scripts/identity_candidate_pipeline.py frame \
  --image ./cartoon.png \
  --face 0.22 0.16 0.77 0.61 \
  --grid 87 --target-face-height 0.55 \
  --out ./framed_candidate_A

python scripts/identity_candidate_pipeline.py verify-frame \
  --prepared ./framed_candidate_A
```

以上坐标是**占位示例**，**绝不能套用到其他人脸照片**。也可使用 `--landmarks path/to/image_bound_points.json` 替换 `--face`。脸宽、脸高比例改变时，当前构图可能需要填充背景；程序会保存 `framing_debug.png`、真实边界参数和预测的面部占格数。

`expected_face_height_beads` = *标注脸高像素* ÷ *裁切方形边长* × *拼豆网格边长*。这是手工 ROI 的几何推算，**不是身份分数、也不代表像素后五官必然清晰**。

所有裁切/背景填充只生成新的未批准图片；用户必须检查顶部头发、肩膀、服装是否被截断，不能静默改变已确认的图纸。

## Step 3：先生成每个候选的真实色号矩阵，再比较

用旧版的 `first_sheet.py prepare`（对每个候选的真实艺术底图分别运行）或确定性像素化程序生成真实 CSV 与 PNG。不要让图像模型直接画格子。

创建如下 `comparison_manifest.json`，路径可为相对该清单所在目录的文件路径：

```json
{
  "schema": "perler-identity-candidate-review-v1",
  "original": "../original.png",
  "palette": "../assets/mard_palette.json",
  "original_face": [0.27, 0.15, 0.80, 0.54],
  "candidates": [
    {
      "name": "A: full composition",
      "cartoon": "./candidate_A/art.png",
      "matrix": "./candidate_A/matrix.csv",
      "preview": "./candidate_A/semantic_pixels.png",
      "face_box": [0.22, 0.16, 0.77, 0.61],
      "art_source": "./base_cartoon.png"
    },
    {
      "name": "B: face-priority crop",
      "cartoon": "./candidate_B/art.png",
      "matrix": "./candidate_B/matrix.csv",
      "preview": "./candidate_B/semantic_pixels.png",
      "face_box": [0.25, 0.18, 0.79, 0.68],
      "art_source": "./base_cartoon.png"
    }
  ]
}
```

上面的人脸框均为**格式示例**，请用每张图真实确定的归一化范围替换。`art_source` 记录底层共同来源；两个不同裁剪会被明确记录为同一幅艺术底图的构图变体。

```bash
python scripts/identity_candidate_pipeline.py compare \
  --manifest ./comparison_manifest.json --out ./candidate_review
python scripts/identity_candidate_pipeline.py verify-compare \
  --prepared ./candidate_review
```

导出：
- `candidate_comparison.png`：同屏对照原图、候选底图、真实拼豆预览和脸部局部。
- `comparison_report.json`：全部真实源文件的 SHA、逐格校验、颜色数、实际豆数、来源关系。
- `human_selection_TEMPLATE.json`：**全部默认未审核**；不得由 AI 擅自填 `user_confirmed=true`。

`compare` 对候选强制要求：**同网格尺寸、当前合法 MARD 参考色卡、矩阵与纯色像素预览逐格一致、候选图真实存在**。不能把模拟的格子或成品预览当作已经核验的施工图。

## Step 4：先判断画面是否更像，再冻结 MASTER

**人工复查三项：**
1. 原照 → 卡通底图：眼距、眼型、鼻梁、嘴唇、下颌、姿态有没有不必要改变？
2. 卡通底图 → 拼豆：实际87×87、正常观看尺寸下五官还在不在？
3. 整体构图：脸放大后是否切断发型、衣服等人物识别信息？

即使几何告警低、脸高占格数增加，仍不能声称“自动识别同一人”或“相似度提高 X%”。若没有得到用户明确认可，状态只能是 `HUMAN_COMPARISON_REQUIRED`。

**禁用自动发布路线：** `frame` / `compare` 不会替用户选择候选、不会填审核记录、不会冻结 MASTER。候选被用户确认后，应走已有 `likeness_review_pack.py`、`identity_fidelity.py` 的用户审核和 `first_sheet.py select`、施工图独立验收门槛。

## 边界、隐私与公示

- 本模块不联网、不下载模型，默认仅本地处理肖像。
- 严禁将源人像、带脸示例、顾客肖像矩阵上传公开 GitHub 仓库。
- 示例中的 `art_source` 是来源声明和哈希绑定，不是验证生成模型身份的机制。
- 仅图纸的逐格数据一致性可被程序证明；跨风格人物相似度仍属于需要校准研究与人工审核的问题。
