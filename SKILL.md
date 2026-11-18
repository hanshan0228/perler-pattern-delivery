---
name: perler-pattern-delivery
description: "Use for 拼豆图纸、真人照片转卡通拼豆、AI cartoon mode、MARD color matching, pre-pixelated images, pixel grid alignment, or verified customer bead pattern delivery. First-sheet workflow defaults to a real cartoon illustration and a programmatically verified numbered chart; strictly locks user-approved MASTER matrices for every customer sheet and printable chart."
license: MIT
compatibility: "Python 3.9+; Pillow, NumPy for photo generation; ReportLab for PDFs; macOS, Linux, Windows"
metadata:
  version: "2.5.0"
---

# 拼豆图纸标准交付（可执行 Skill）

## P0 最高优先级：最终施工图只能由程序绘制

**绝对禁止让生成式图像模型绘制最终图纸、格子、数字坐标、色号、图例、豆数或 PDF。** 图像模型只可生成无网格无文字的艺术底图。用户要求一张图纸也必须执行 Python 生产线，而非调用生图工具直接返回成品。以下要求同时适用于卡通版、写实版、双版本及已确认图纸。

- 只有 `first_sheet.py select` + `verify` 成功生成的待确认单页，或 `perler_delivery.py deliver` + `verify` 成功生成的已确认单页，才可作为最终施工图发给用户。`generate`、`import-pixel`、任何纯图片模型输出均不能替代该验收。缺少 Python/文件工具则说明无法制造可验证图纸，不要伪造。
- 单页 PNG/PDF、真实矩阵 CSV、固定 MARD 色卡、图例及校验记录必须实际存在；核对本次命令退出状态，不得仅凭文字声称通过。交付前检查图纸原尺寸和局部，特别检查第 48–51 行、第 55–58 列（若存在）、长色号与深浅底色文字。
- `verify` 必须从矩阵重新渲染并比较真实 PNG 像素及同环境确定性 PDF，不仅验证 PNG 文件的哈希。所有坐标从 1 连续编号到实际宽高，每个格子只能引用真实色卡。禁止用 OCR 或手工补几个乱码来挽救模型生成的假图纸。
- 提交新肖像时只使用 `UNAPPROVED`，取得用户明确认可后才 `freeze`。用户一次要卡通和写实，应分别完成两套独立候选与校验，不能共享或虚构矩阵。交付链接必须指向本次已验收文件。
- 旧版交付包没有重渲染校验，需从原有 MASTER 重新 `deliver` 到新目录；禁止更改 MASTER 或仅修改旧校验文件来通过。重渲染验收需使用相同代码、字体、Pillow 与 ReportLab 版本。环境不同则用可信 MASTER 在新环境重新导出。

## P0 默认入口：卡通风格拼豆图纸，不是卡通插画

**调用者不需要另写长提示词。** 听到“卡通版”“卡通拼豆图纸”“做成拼豆图纸”“再给我一个成品”且上下文是制作拼豆图纸，默认最终产物为顾客单页**有色号的施工图**。新肖像默认精致平涂卡通；用户明确要求写实才用 photo 模式。只有明确要求“卡通底图”“只要效果预览/实物模拟”才仅交付相应图。用户要改已确认图纸排版则优先使用 MASTER，不重新卡通化。

### 新肖像的必经生产线（v2.5，首次使用先读这里）

1. 使用实际上传的原照片作为图像模型编辑参考。按 [首稿规范](references/FIRST_SHEET.md) 生成**无网格、无色号、无标题**的精致平涂卡通底图。必须用真正的图像生成/编辑模型或用户提供的卡通原稿；离线滤镜只能是用户明确选择的实验模式。没有图像工具和真实底图就说明缺口，不能偷偷改用滤镜，也不能伪造图纸。
2. 运行首稿生产线（默认 87×87、最多 33 色；用户指定值优先）：

```bash
python scripts/first_sheet.py prepare --image original.jpg --cartoon-image cartoon.png --grid 87 --colors 33 --out ./review_v1
```

3. **自己先检查** `review_comparison.png` 和候选大图。比较三个候选、参考原照片和已有基准。若造型不对、五官丢失、花饰/关键轮廓被切掉或存在明显噪声，重新生成卡通底图/候选并比较；最多两轮修正，不得无限重试。在仍不合格时明确说明失败，不把差稿当合格首稿。禁止仅依据像素 hash 宣称画质合格。
4. 复制 `visual_review_TEMPLATE.json` 为 `review.json`，选择实际通过视觉检查的 `detail`、`flat` 或 `portrait`，复制 `prepare.json` 中该候选 `codes_sha256`，保留 `comparison_sha256`，逐项填写真实检查结果和具体观察记录。不得批量默认填 true。执行：

```bash
python scripts/first_sheet.py select --prepared ./review_v1 --variant flat --review ./review.json --name '卡通定制肖像' --out ./first_sheet
python scripts/first_sheet.py verify --prepared ./review_v1 --sheet ./first_sheet
```

5. **首次用户可见回复**以 `candidate_sheet.png` 为主（包含效果预览、真实网格、每格色号、坐标、MARD 配色与数量）；附 A2 PDF、高清图/可放大总图和 CSV。不以纯插画、过程图或实物模拟代替图纸，不要求用户反复提醒。说明它是待确认图纸，未获确认不得称正式已批准版本。只有用户确认后才运行 `freeze` / `deliver` / `verify`，不得覆盖旧 MASTER。

程序 `select` 会拒绝缺失或失败的视觉检查、过时的候选哈希；它检查的是审核记录而不是自动识别美学质量。`verify` 校验矩阵、固定参考色卡、语义像素、数量、实际 PNG/PDF 重渲染结果与文件哈希。任何检查失败则不交付。


### v2.5 人像视觉优化（只对新候选生效）

- `prepare` 同时生成 `detail`（原中央中位采样）、`flat`（原面积平均采样）、`portrait`（直接从固定 MARD 色卡选色，重点区域加权）。旧候选算法及已确认 MASTER 原样保留。
- `--focus X0 Y0 X1 Y1` 可重复指定经实际观察确认的重点区域（0–1 的归一化坐标，相对于补边后的方形底图），例如 `--focus .30 .15 .70 .64`。这不是自动人脸识别。坐标不能照抄到其他照片，应先看本次底图。没有重点区域时仅按图像边缘强度加权。
- `portrait` 使用真实 MARD 色号内的贪心组合选色；以加权 CIELAB ΔE76 平方误差为优化目标，不用无效的聚类中心冒充色卡。仅在重点区域以外、低反差、至少三个邻格同色且替换色差增加很小时清理单格杂点。不得承诺眼睛自动正确。
- `prepare.json` 的 `quality_metrics` 给出同一面积平均底图上的色差、重点区域色差、孤立格数和实际颜色数。它们是诊断指标，不是审美或相似度评分；颜色数、色差和孤立格之间有取舍。验证会重新计算主要指标。禁止仅凭数值自动指定获胜候选。
- 三个候选都不够自然时，停止交付；征得用户允许再尝试更大网格、改底图或手工精修，绝不虚构画质合格。所有 V2.4 确定性渲染校验照常执行。

## 第一原则：先固定数据，再制作所有视觉交付物

**MASTER = 被用户确认的逐格色号矩阵 + 固定色卡 + SHA-256 校验清单。**

- 用户要求“再排版、给顾客一张图、带图例、打印版、高清版”时，**只能运行 `deliver`**。不能把已确认图纸丢给图片生成模型重画，不能偷偷降分辨率、换色号、清杂点或去背景。
- 用户要求改变眼睛/花朵、减少颜色/去背景时，那是**新候选版本**；生成候选并请求用户确认后单独 `freeze`。绝不覆盖 MASTER。
- 用户只提供新照片而无 MASTER 时，可运行 `generate` 生成**候选**，然后人工检查、用户确认、`freeze`。候选不是可证明的成品；不要承诺转换后的辨识度一定足够。
- 图中出现的“成品效果”如为图像模拟，必须标识为模拟，不能冒充真实实拍；顾客施工图应始终以原色号矩阵为准。

## 环境与入口

在本 Skill 所在目录安装依赖；推荐虚拟环境，不污染 Agent 运行环境：

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python scripts/perler_delivery.py --help
```

目录由当前 `SKILL.md` 的绝对路径确定。不要假设当前工作目录或图片上传路径。

### 模式 A：顾客已确认图纸（必须优先使用）

```bash
python scripts/perler_delivery.py freeze \
  --matrix /path/to/approved_matrix.csv \
  --out /path/to/customer_project/master \
  --name '花朵少女'

python scripts/perler_delivery.py deliver \
  --master /path/to/customer_project/master \
  --out /path/to/customer_project/delivery

python scripts/perler_delivery.py verify \
  --master /path/to/customer_project/master \
  --delivery /path/to/customer_project/delivery
```

`freeze` 拒绝写入已经存在的 MASTER。`deliver` 只写到新目录并拒绝覆盖已有交付件。要升级版本就使用新的项目目录（v2、v3）。

### 模式 B：明确要求写实（同一强制验收流程）

```bash
python scripts/first_sheet.py prepare --mode photo --image original.jpg --grid 87 --colors 40 --out ./realistic_review
# 实际观察 review_comparison.png，填写 visual_review_TEMPLATE.json 的真实检查结果、选中候选及其哈希，保存为 realistic_review.json
python scripts/first_sheet.py select --prepared ./realistic_review --variant flat --review ./realistic_review.json --name '写实定制肖像' --out ./realistic_sheet
python scripts/first_sheet.py verify --prepared ./realistic_review --sheet ./realistic_sheet
```

写实模式直接采样原照片（不接受卡通底图参数），三种候选方案和全套首稿验收与卡通版一致。`candidate_sheet.png` 和 `candidate_sheet_A2.pdf` 是待确认施工图。视觉审核须确认真实风格、原姿态、五官及重要细节。写实版不强制卡通化。

### 模式 C：底层卡通实验工具（非默认首稿入口）

**优先使用卡通预处理，再映射拼豆色号，不允许只靠缩小照片来冒充 AI 卡通。**

只有用户明确接受传统滤镜效果时才使用离线卡通实验模式（本地、免费、不访问云 API、无需模型权重）：

```bash
python scripts/perler_delivery.py generate \
  --image /path/to/photo.jpg --mode cartoon --cartoon-style soft \
  --grid 87 --colors 33 --filter medium --out ./candidate_cartoon_v1
```

可选预设：`soft`（默认、柔和平涂/肖像）、`comic`（更明显的描边）、`poster`（平涂海报、较少描边）。三者均是真正的图像预处理：边缘保持滤波 → 平涂减色 → 可控描边，再转换成真实色号矩阵。`cartoon_stage.png` 是**预处理阶段图**，不是顾客施工图。

**外部 AI 插画化是高质量肖像的默认上游步骤（必须使用已授权模型/服务）。** 对首次完整单页图纸优先使用前述 `first_sheet.py`；以下是兼容旧流程的低层命令。 若执行环境有图像生成工具，可先使用 [卡通风格说明](references/CARTOON_STYLES.md) 转换照片，待输出文件实际存在后输入到 Skill：

```bash
python scripts/perler_delivery.py generate \
  --image /path/to/original.jpg --mode cartoon \
  --cartoon-engine external --cartoon-image /path/to/licensed_cartoon.png \
  --grid 87 --colors 33 --filter medium --out ./candidate_ai_v1
```

`external` **不会自行调用任何付费 API**，也**不会下载 GitHub 模型权重**：它严格读取你已经生成的卡通 PNG。保存输入文件 SHA-256 和 `cartoon_stage.png`，以支持回溯。不能保证外部模型一定保留身份、面部比例和姿势；仍需人工检查。

### 模式 D：已像素化的图 → 拼豆图（v2.2.0）

```bash
python scripts/perler_delivery.py import-pixel \
  --image /path/to/pixel_art.png --grid 58 --pixel-cell 16 \
  --pixel-origin-x 0 --pixel-origin-y 0 --colors 24 \
  --filter low --out ./candidate_pixel_v1
```

逐块提取**中央 40% 区域的中位色**，避免把现成图纸的黑色网格线误采成拼豆颜色。可省略 `--pixel-cell`，按图像长宽等比例抽样；如果截图带边距/坐标，需要明确指定尺寸与原点，自动偏移仅为尽力估计。禁止宣称任意截图都可 100% 恢复格点。

### 候选过滤参数

`--filter none|low|medium|high`，仅作用于 **UNAPPROVED 候选**。默认 photo / pixel 为 none，cartoon 为 medium。`high` 减少更多小孤立块但可能伤及眼睛、嘴巴和花瓣细节；如果用户已有满意的图纸，必须保持原 MASTER 不变。

### 模式 E：制作可撤销去背景候选

```bash
python scripts/perler_delivery.py remove-background \
  --master /path/to/master --background-code H19 \
  --out /path/to/transparent_candidate.csv
```

只移除与边缘 **4 邻接连通**的指定背景色，写入新候选 CSV；不修改现有 MASTER。空格记为 `EMPTY`，不算豆子。可能产生悬空拼豆区域，人工检查结构后再确认。

## 核心输出契约

`deliver` 固定生成：

- `customer_sheet.png` — 单页顾客图（预览、色号网格、尺寸、豆数、板数、图例），内容严格从 MASTER 构建
- `customer_sheet_A2.pdf` — 单页 A2 版本
- `pattern_with_codes.png` — 带色号的全图
- `pixel_preview.png` — 无字纯色像素预览
- `semantic_pixels.png` — **真实网格尺寸**（例如 87×87），逐像素对应每格的颜色；用于机器校验，禁止插值
- `legend.csv` — MARD 色号、HEX、颗数
- `boards/board_XX_color.png`、`boards/board_XX_bw.png` — 分板图及黑白色号版
- `boards_color_A4.pdf`、`boards_bw_A4.pdf` — 每板单独 A4 页面
- `validation.json` — MASTER、色卡、派生交付文件 SHA-256 校验记录

## P0 验收门槛（不得跳过）

1. **原图纸数据一致：** `deliver` 前后 MASTER 矩阵 SHA-256 相同；顾客版与施工版均从同一份内存矩阵读取，不把生成图片当数据源。
2. **单格单色：** 每个格子是一个已注册色号，或明确的 `EMPTY` 空位；`semantic_pixels.png` 的每个坐标严格匹配色卡 HEX。
3. **色号一致：** 图例色号全部可在固定色卡里找到；不能擅自把参考色号换算成不同品牌的色号。
4. **用量一致：** sum(各色颗数) = rows×cols − EMPTY数量；不能把透明格算成豆子。
5. **分板一致：** 各板按矩阵切片，所有格子恰好覆盖一次；边缘不足 29×29 时明确标注部分板。
6. **排版不变图：** 标题、图例、品牌名称、排版尺寸、字体和坐标可以变化；矩阵数据不可以变化。渲染中允许色号文字和网格线覆盖在底色上，所谓“一格一色”指**底层拼豆颜色**，不意味着文字像素必须同色。
7. **文件可靠性：** `verify` 必须成功；若出现 hash 错误、未知色号、行列不齐、生成图未校验，则停止交付，不能自动兜底重新绘制。
8. **打印可读性：** A2 单页用于概览；实际制作推荐分板 A4 PDF。打印后检查色号字号，必要时逐板使用原尺寸打印。纸张比例不代表实际熔豆尺寸。
9. **商业诚实：** MARD HEX 是开源项目提供的**参考数字色卡**，并非经过实物分光测色校准；显示器与实际拼豆颜色可能有差异，不得保证完全一致。

## 关于版本和异常

- 用户说“这个版本满意”→ 立即 `freeze` → 只用 `deliver` 派生客户版。
- 用户说“这个版不如以前”→ 比对旧版 MASTER SHA；若不是同一矩阵，回退到已确认版本，不允许图片模型“尽量画得像”。
- 只有 JPG/PNG 而没有矩阵 → 不能承诺逐格重建完全无损；优先查找源 CSV/JSON。对截图反推需标注“重新识别、未经确认”。
- 对旧项目的 `APPROVED` 版本进行背景抠除、颜色合并或放大像素，必须产生新候选及新 MASTER；不得用 `deliver` 暗中修改。

## 最终回复格式

简要报告：当前使用的 MASTER 版本（SHA-256 前 12 位）、网格尺寸、空格数、实际豆数、颜色种数、板块数量、校验是否通过、链接到顾客单页图 / PDF / 分板施工图 / 清单，并说明参考色卡与实物的差异风险。

遇到技术和兼容问题查看 [技术说明](references/TECHNICAL.md)；来源与许可证说明见 [来源](references/SOURCES.md)。

## 底层卡通/像素模式验收要求（兼容 v2.2）

- 保留照片模式旧行为；不可将默认 `generate` 偷偷升级为卡通。
- 本地离线卡通是传统图像处理，不得自称等同于 photo2cartoon 或 AnimeGANv2 的神经网络效果。
- 高质量 AI 卡通候选必须标注外部来源，不下载或捆绑未授权模型，不默默传输私人人像。
- 底层 `generate` / `import-pixel` 候选输出 `candidate_matrix.csv`、`candidate_preview.png`、`candidate_codes.png`、`candidate_info.json`；cartoon 额外输出 `cartoon_stage.png`。
- 像素导入必须以格子中心统计颜色，禁止 BOX 重采样把黑网格线混进豆色。
- 所有新生成图均需要确认，然后单独 `freeze`；冻结后的生产交付依然由旧版 `deliver` 和 `verify` 完成。
- 每次修改脚本后运行 `python -m unittest discover -s tests -v`，且必须保留已确认 58×58 和 87×87 的哈希回归测试。
- 商业使用遵守第三方模型和数据的许可证；参见 `references/SOURCES.md`。
