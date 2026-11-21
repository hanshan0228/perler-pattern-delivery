# v3.0.2 两阶段人物相似度审核（Likeness Review Pack）

这是**额外的人物相似度审核门槛**，不替代 `first_sheet.py` 的真实拼豆矩阵/PNG/PDF 校验，也不代替 v3.0 的 `identity_fidelity.py` 用户确认与冻结入口。

## 解决的问题

“完整图纸数学正确”不代表“卡通拼豆像原人物”。必须区分两次有损转换：

1. **A：原照片 → 卡通底图**。可能改变眼距、眼形、鼻梁、嘴唇、下颌和神态。
2. **B：卡通底图 → 拼豆矩阵**。有限像素可能让眼睛或嘴巴合并、失去表情。必须在小尺寸预览下复查，而不是只看放大的 87×87 总图。

**本工具不进行真人身份识别，也不输出未经校准的人脸相似度百分比。** 审核图是给人判断的证据，不是数字认证。模型生成的视觉审核意见不能冒充顾客本人确认。

## 所需输入

- `--original`：**当前原始照片**，勿使用其他用户或旧项目照片。
- `--cartoon`：无文字、无网格的**真实卡通底图**；不能将生成式 AI 直接绘制的假施工图当成输入。
- `--bead`：与 CSV 完全一致的**逐格纯色无字预览图**；不接受有色号网格的截图。
- `--matrix`：当前候选真实 MARD 色号 CSV。
- `--palette`：与仓库 `assets/mard_palette.json` 一致的固定色卡。
- `--face-original/--face-cartoon/--face-bead`：分别提供 `x0 y0 x1 y1` 四个**归一化（0..1）**坐标，框住各阶段真实的人脸，建议同时包含眉眼、鼻子、嘴巴和下巴。三张图不能简单复制同一脸框，需逐张实际观察。
- **替代手动脸框**：每个阶段可选 `--landmarks-original/--landmarks-cartoon/--landmarks-bead` 传入 v3.0 `identity_fidelity.py extract` 生成的 SHA-256 绑定文件。请人工确认关键点定位正确。无法获得可靠关键点时使用手动框，不得假装已检测成功。

## 一键生成可视化审核包

```bash
python scripts/likeness_review_pack.py prepare \
  --original ./original.png --cartoon ./cartoon_base.png \
  --bead ./candidate_preview.png \
  --matrix ./candidate_matrix.csv --palette ./assets/mard_palette.json \
  --face-original 0.27 0.12 0.76 0.65 \
  --face-cartoon 0.25 0.11 0.77 0.65 \
  --face-bead 0.26 0.11 0.76 0.64 \
  --out ./likeness_review_01

python scripts/likeness_review_pack.py verify \
  --prepared ./likeness_review_01
```

**示例脸框仅用于演示命令格式，必须根据每张真实图片重新指定，严禁直接套用。**

输出包含：

- `likeness_review.png`：三阶段全图、三张面部局部、1/2/4 屏幕像素每颗豆的预览。
- `bead_view_1x.png`、`bead_view_2x.png`、`bead_view_4x.png`：完全由真实色号矩阵对应的纯色图缩放生成。这里的倍率是屏幕像素倍率，**不是**实际 5mm 拼豆的物理尺寸。
- `likeness_report.json`：输入 SHA-256、网格验证、标注来源和审核状态。
- `user_review_TEMPLATE.json`：独立记录 A、B 两个阶段的人工审核。**全部默认 false**。

缺少任一张人脸框时仍可输出对比图，但会标记 `NOT_EVALUATED_MISSING_FACE_BOXES`，不可声称已完成全部审核。

## 双阶段验收原则

- A 检查：眼形与眼距、鼻和唇形、下巴与发际线、头部角度、是否过度美化改变了脸。
- B 检查：按 1px/2px 每颗豆的实际像素密度看五官是否仍清楚，不因为放大有格子就误认为相似；留意鼻梁断裂、双眼不对称和嘴唇糊成块。
- **先考虑面部占格数与构图**，再考虑增加颜色。背景过多时，应生成另一个新的候选裁切；修改已冻结 MASTER 属于错误流程。
- 人工审核必须在 `user_review_TEMPLATE.json` 里逐项真实填写，仅用户明确认可时 `user_confirmed=true`。程序无法验证输入者真实身份，记录只表达声明。

```bash
# 只有经过实际人工审核且用户明确确认，才允许写入通过的 review.json。
python scripts/likeness_review_pack.py attest \
  --prepared ./likeness_review_01 \
  --review ./user_review.json \
  --out ./likeness_attestation.json
```

本工具生成的审核记录**不直接替代** `identity_fidelity.py evaluate` 和 `freeze-reviewed` 的要求；这两项原有用户确认与正式冻结流程继续执行。

## 质量/安全边界

- 所有输出为本地文件；脚本不联网、不上传用户肖像，也不下载模型。
- 不能保证新照片转换后“像某个人”，也不允许用未校准的生物识别分数骗过人工检查。
- SHA-256 验证文件是否改变，**不是电子签名**，无法证明审核者身份。
- 数学、图例、打印校验仍应使用 `chart_release_gate.py` 和原有 `verify`，两种审核不可互相替代。
- 不得将真人原图、带脸的对比示例或任何顾客肖像提交到公开 GitHub 仓库。
