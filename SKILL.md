---
name: perler-pattern-delivery
description: "Use for 拼豆图纸、Perler/MARD/Hama bead patterns, photo-to-bead conversion, verified pixel-grid charts, customer delivery sheets, board-split printable PDFs, or revisions of an approved bead design. Locks approved color matrices and prevents AI redraws during layout changes."
license: MIT
compatibility: "Python 3.9+; Pillow, NumPy for photo generation; ReportLab for PDFs; macOS, Linux, Windows"
metadata:
  version: "2.0.0"
---

# 拼豆图纸标准交付（可执行 Skill）

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

### 模式 B：从全新照片生成候选（不是已确认图）

```bash
python scripts/perler_delivery.py generate \
  --image /path/to/photo.png --grid 87 --colors 35 \
  --out /path/to/candidate
```

处理过程：居中裁剪 → BOX 降采样 → Lab 颜色聚类 → 最接近的 MARD 参考色号。输出候选 CSV 和像素预览。**必须审查五官、花瓣、颗粒噪声，再由顾客确认后单独 freeze**。需要更精细的卡通化时使用外部图像工具，但只能用于生成候选，不得替代已确认 MASTER。

### 模式 C：制作可撤销去背景候选

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
