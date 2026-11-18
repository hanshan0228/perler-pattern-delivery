# Perler Pattern Delivery · 拼豆图纸严格交付 Skill v2.8.0

## v2.8：区域蒙版建议与局部色阶精修

可选本地人脸定位、颜色及连通区域启发式建议、离线逐格蒙版编辑、绑定底图的人工审核计划，并增加同色卡的局部肤色色阶候选。不是全自动语义分割，不自动批准画质。详见 [AUTO_REGIONS.md](references/AUTO_REGIONS.md)。

## v2.7：区域配色与打印可读性

支持经过人工检查的归一化多边形 `--regions`（皮肤/头发/衣服/背景/锁定细节），新增 `finish` 候选和可选 `--finish-colors` 采购预算。不是自动人脸分割，不能保证审美提升。既有候选保留。新首稿及 MASTER 派生交付自动生成高对比色号和 A4 彩色、黑白分板，逐页重渲染验证。已冻结矩阵不变。详见 [REGION_PRINT.md](references/REGION_PRINT.md)。

## v2.6 人像视觉优化

保留 `portrait` 候选，直接在真实 MARD 色卡内进行预算约束选色，并支持手工指定重点区域 `--focus X0 Y0 X1 Y1`。保留 `detail` 与 `flat`，只在低反差、非重点区域谨慎处理孤立格。质量报告是辅助诊断，不是审美认证。新增 `regional`（相同实际色数的区域加权换色）及 `coherent`（相同色号组合，受源图边缘及色差约束的连续性精修）。五候选多指标比较，仍需实际视觉审核。旧 MASTER 与生产渲染代码保持不变。

## v2.4 强制施工图验收（保留）

禁止 AI 直接绘制带坐标、色号、图例的最终图纸。卡通和写实均由 Python 根据真实矩阵生成。写实首稿入口：`python scripts/first_sheet.py prepare --mode photo --image portrait.jpg --grid 87 --colors 40 --out review`；卡通需真实卡通底图。审核、select、verify 后才可交付单页 PNG/PDF。校验会重新渲染比对实际图纸，而非仅验证文件哈希。已确认 MASTER 保持不变，旧交付包从原 MASTER 导出到新目录即可。重渲染校验须使用相同字体和依赖版本。

## 默认首稿流程（v2.6）

新照片默认输出卡通风格、有格内 MARD 色号的单页施工图；不再默认走离线滤镜。先用图像模型制作真实卡通底图，再用 `scripts/first_sheet.py prepare` 生成五个候选，实际检查后 `select`，最后 `verify`。详见 [首稿规范](references/FIRST_SHEET.md) 与 [SKILL.md](SKILL.md)。待确认图纸不等于已冻结 MASTER。


这是实际可运行的 Agent Skill，而不是提示词合集。

## 安装

下载并解压 `perler-pattern-delivery` 整个文件夹，放到：

- Codex 用户级：`~/.agents/skills/perler-pattern-delivery/`
- Codex 项目级：`<project>/.agents/skills/perler-pattern-delivery/`
- Claude Code：放到你的 Claude Code 支持的 Skills 目录（常见为 `.claude/skills/`），安装位置以当前客户端文档为准。

进入 Skill 目录创建虚拟环境，安装 `requirements.txt`。Skill 需要访问本地 Python 和读写文件工具才能执行脚本；在纯聊天环境只有说明、没有执行工具时，不能声称已做到了文件验证。

## 快速执行（以已确认 87×87 图纸为例）

```bash
python scripts/perler_delivery.py freeze --matrix examples/approved_87x87.csv --name '花朵少女' --out ./project/master
python scripts/perler_delivery.py deliver --master ./project/master --out ./project/delivery
python scripts/perler_delivery.py verify --master ./project/master --delivery ./project/delivery
```

## 可选底层工具（兼容 v2.2，非默认首稿入口）

内置离线滤镜：柔和卡通 `soft`、漫画描边 `comic`、平涂海报 `poster`。这是无网络/无模型的传统算法，**不等同于生成式 AI 卡通人像**。

```bash
python scripts/perler_delivery.py generate --image /path/photo.jpg --mode cartoon \
  --cartoon-style soft --grid 87 --colors 33 --filter medium --out ./candidate_cartoon
```

如果需要之前那种更精细的 AI 插画风格，先用你有权使用的图像模型生成卡通 PNG，再交给本 Skill：

```bash
python scripts/perler_delivery.py generate --image /path/photo.jpg --mode cartoon \
  --cartoon-engine external --cartoon-image /path/cartoon.png \
  --grid 87 --colors 33 --out ./candidate_ai
```

可选安装 `python -m pip install opencv-python-headless` 提升离线轮廓处理效果；未安装时自动使用 Pillow 实现。

**当前 CLI 不会自动访问图片 API，不需要配置 API Key，不会把私人照片上传到网络。** 对外部图片的模型/服务商业授权需要自行核查。优先人工审核候选图的五官、嘴型、头发与花朵，选定版本后冻结。

已像素化的图片支持：

```bash
python scripts/perler_delivery.py import-pixel --image /path/pixel.png --grid 58 \
  --pixel-cell 16 --pixel-origin-x 0 --pixel-origin-y 0 --colors 24 \
  --filter low --out ./candidate_pixel
```

所有新候选都保存预处理阶段、CSV 色号矩阵和信息记录；已有 MASTER 不能随意修改。

## 新图片流程

```bash
python scripts/perler_delivery.py generate --image /path/to/new_photo.jpg --grid 58 --colors 24 --out ./candidate
# 检查 candidate/candidate_matrix.csv 和 candidate/candidate_preview.png，必要时修图、编辑 CSV 并征求确认
python scripts/perler_delivery.py freeze --matrix ./candidate/candidate_matrix.csv --out ./project-v1/master --name '定制头像'
python scripts/perler_delivery.py deliver --master ./project-v1/master --out ./project-v1/delivery
```

## 功能边界

- 承诺的是 **逐格和色号的数据一致性**，不是人脸画质自动达到某种审美效果。
- 颜色 HEX 为开源参考色卡，非品牌实物测色保证。
- 图片只有“预览截图”时，无法严格证明与未知原始图纸一致，应该先获得 CSV/JSON。
- 绝不自动覆盖 MASTER；更换分辨率或换色必须生成新版本。
- `freeze --matrix` 支持带行列号 CSV、纯矩阵 CSV，以及旧工作台 `{"grid": [["色号", null, ...], ...]}` 的 JSON 工程（`null` 表示空位）。
- `examples/` 内附你已经确认过的 58×58 和 87×87 色号矩阵，供首次跑通与回归核对。

源代码、算法参考与正式规范见 `references/SOURCES.md`。
