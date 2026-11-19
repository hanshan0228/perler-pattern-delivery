# v3.0 人物身份保真 / Identity Fidelity Gate

> 这是一套 **可核验的审查生产线**，不是“AI 人物一定相似”的保证。当前没有经过标注基准校准的跨风格身份识别器，不得对外宣称 95%/99% 相似、同一人物自动验证通过。

## 为什么必须独立检查三阶段

- **原始照片 → 卡通底图**：生成式图像模型可能改变眼间距、嘴型、脸宽、面部朝向和气质，后续的 MARD 调色无法恢复已经丢失的特征。
- **卡通底图 → 拼豆矩阵**：87×87 像素、有限色卡和可拼豆边界会压缩眼鼻口的信息；即使一格不差，也不能推导人物相似。
- **矩阵 → 施工图**：色号和坐标准确属于独立验证维度。必须从同一份真实矩阵渲染 PDF/PNG，禁止让图像生成模型自由绘制数字和网格。

## 正式推荐工作流（禁止跳过关键阶段）

### 0. 制作候选图：不要先冻结

原照片与卡通底图应来自不同文件，先用已有 `first_sheet.py` 制作未确认候选及 `pixel_preview.png`、`candidate_matrix.csv`；必须有具体的 MARD `palette.json`。

### 1. 开始三阶段身份与施工数据审查

```bash
python scripts/identity_fidelity.py prepare \
  --original /path/to/source_photo.png \
  --cartoon /path/to/cartoon_base.png \
  --bead /path/to/pixel_preview.png \
  --matrix /path/to/candidate_matrix.csv \
  --palette /path/to/palette.json \
  --out /path/to/identity_review
```

输出：
- `three_stage_comparison.png`：原照片 / 卡通底图 / **真实像素矩阵**并列可视化（非生成式伪图纸）。
- `identity_report.json`：输入 SHA-256、真实豆数、色号数量、逐格预览一致性、人脸几何检查状态。
- `human_review_TEMPLATE.json`：五项全部默认为 `false`；必须实际观察后由真人填写。

**一个重要区别**：缺少人脸关键点时报告写 `NOT_EVALUATED_LANDMARKS_MISSING`，绝不会用其他指标冒充人脸相似度。检查通过表示图纸真实，**不等于**原人物辨识度合格。

### 2. 可选：人脸关键点几何筛查（MediaPipe）

仅在本地装有实际 MediaPipe Face Landmarker 模型及依赖时启用：

```bash
python -m pip install mediapipe
python scripts/identity_fidelity.py extract \
  --image /path/to/source_photo.png \
  --model /path/to/licensed/face_landmarker.task \
  --out /path/to/landmarks_original.json

python scripts/identity_fidelity.py extract \
  --image /path/to/cartoon_base.png \
  --model /path/to/licensed/face_landmarker.task \
  --out /path/to/landmarks_cartoon.json
```

之后重新运行 `prepare`，传入 `--landmarks-original`、`--landmarks-cartoon`；如果拼豆预览中也能正确检测人脸，可加 `--landmarks-bead`。MediaPipe 对严重卡通化、低分辨率或侧脸可能失败；识别失败时**不准编造结果**。模型权重不随 Skill 打包，也不会自动从网络下载。

`identity_report.json` 中的几何指标：
- 以双眼中心连线旋转、平移，并以眼间距缩放后的人脸关键点均方根位移。
- 嘴宽/眼间距、脸宽/眼间距、眼鼻距离、眼唇距离、下巴高度和唇开合的相对变化。
- 仅作**偏差预警**，预设界限是工程筛查值而非经验证的身份概率；不应把任何指标输出为“相似度百分比”。

### 3. 必须请真人判断（尤其是付费定制）

对照图应实际检查：
- 原人物和卡通版是否可以看成相同的人，还是变成通用网红脸。
- 眼型和眼距是否保持；鼻翼、嘴宽、唇形、颌线和表情是否改变。
- 87×87 实际像素预览中是否依然能辨认人；不要仅看高清卡通底图。
- 是否保留回眸、耳环、发型、肩带等更容易辨认的特征。
- 有疑问直接保留 `false`；无法识别就返回重新生成卡通底图，不允许假装通过。

把 `human_review_TEMPLATE.json` 复制为 `my_review.json`，确认后填写 checks、具体 notes、`reviewer_type="human"`、`user_confirmed=true`。不要在 AI 脚本中批量设置 true 冒充用户批准。

```bash
python scripts/identity_fidelity.py attest \
  --prepared /path/to/identity_review \
  --review /path/to/my_review.json \
  --out /path/to/approved_review.json
```

### 4. 冻结已确认图纸（推荐入口）

```bash
python scripts/identity_fidelity.py freeze-reviewed \
  --prepared /path/to/identity_review \
  --review /path/to/my_review.json \
  --attested /path/to/approved_review.json \
  --name '卡通定制肖像' \
  --out /path/to/master

python scripts/perler_delivery.py deliver --master /path/to/master --out /path/to/delivery
python scripts/perler_delivery.py verify --master /path/to/master --delivery /path/to/delivery
```

此路径会复查全部原始输入、真实 MARD 色卡、逐格预览和审核记录，并创建新 MASTER。旧版 `freeze` 仍可用于导入旧项目，但**不能把绕过这道检查的操作宣传成 v3.0 身份保真交付**。

## 防止误判的技术原则

1. **不要假设 ArcFace 在卡通域上与真人域同分布**。真实—卡通跨域相似度可能偏低而人物仍很像；普通脸识别分数不能直接转成身份真实性或概率。
2. 478 面部关键点是 *形状与姿态估计*，不是人脸身份认证；当前代码仅比较13个代表性关键点和6个比例，无法涵盖所有辨识特征。
3. 边缘、高光、黑发背景对比、配色误差和五官几何可以优化，但 **最可靠的最后验收仍是用户本人看真实格子尺寸的图**。
4. 所有 SHA-256 只保证文件一致性与出处绑定，不证明真正的主观相似度，也不是防恶意伪造的数字签名。
5. 画像属于顾客的个人素材，不要把原照片、关键点文件、审核对照图放到公开 GitHub 仓库；处理过程默认在本机离线完成。

## 实证与文档来源（英文）

- Google MediaPipe Face Landmarker (478 3D face landmarks): https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker
- Peng et al., **Stylized-Face: A Million-level Stylized Face Dataset for Face Recognition**, ICCV 2025: https://openaccess.thecvf.com/content/ICCV2025/html/Peng_Stylized-Face_A_Million-level_Stylized_Face_Dataset_for_Face_Recognition_ICCV_2025_paper.html
- StyleID (cross-style identity perception evaluation): https://doi.org/10.1145/3811360
- NIST FRTE 1:1 verification evaluation: https://pages.nist.gov/frvt/html/frvt11.html


## v3.0.0 补充：面部像素预算 (Face resolution budget)

`identity_fidelity.py prepare` 会在真实拼豆预览**提供了有效的**、与该图片 SHA-256 绑定的人脸关键点文件时，另行报告 `bead_face_resolution_budget`：

- `eye_center_spacing_beads`：双眼中心距离折算成拼豆格
- `mouth_width_beads`：嘴宽折算成拼豆格
- `cheek_span_beads`：双颊宽度折算成拼豆格
- `forehead_to_chin_beads`：前额到下巴的格数

示例预警阈值（未经过数据集校准）：眼距 <7 格、嘴宽 <4 格、脸宽 <14 格、脸高 <20 格。它们仅作为**构图和分辨率检查提示**，不能被宣传为面部身份认证或 70%/90% 的相似度。若有低分辨率预警，用户必须通过 `acknowledge_resolution_warnings: true` 明确确认后，方可记录审核通过。缺少真实关键点时报告 `NOT_EVALUATED_LANDMARKS_MISSING`，不要编造这些数字。

这不替代两次独立的人工观察：原照片 vs 卡通底图、卡通底图 vs 真实拼豆预览。优先检查眼型、鼻口位置、下颌、发际线和姿态，而非颜色色差。已经确认的 MASTER 不受新候选算法影响。
