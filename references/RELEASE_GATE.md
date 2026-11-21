# 严格图纸交付门槛（增量模块）

**任何 AI 直接画出的色号/网格/统计图都不具备施工图资格。** 必须先实际生成合法 CSV 色号矩阵，再由 `perler_delivery.py` 的确定性绘图模块出图，最后由独立门槛 `chart_release_gate.py` 校验。

## 最短命令

```bash
python scripts/chart_release_gate.py \
  --matrix path/to/87x87_完整色号矩阵.csv \
  --palette path/to/MARD_291色_参考色卡.json \
  --chart path/to/单页高清施工图.png \
  --legend path/to/采购配色清单.csv \
  --title '精致卡通拼豆图纸' \
  --pdf path/to/A2单页施工图.pdf \
  --color-boards path/to/boards_color_A4.pdf \
  --bw-boards path/to/boards_bw_A4.pdf \
  --color-boards-dir path/to/boards \
  --report path/to/release_gate.json
```

如无需逐字核对，可省略 `--title` 进行快速验证；但**正式顾客交付必须提供 `--title` 并运行完整重渲染校验**。PDF独立验证需安装 `pymupdf`。

验证包含：CSV坐标从 1 连续；每个格子色号属于固定 MARD 色卡；每格底色像素与矩阵一致；图例色号、HEX、豆数精确一致；若提供 `--title`，程序重画全图并逐像素比较坐标、格内色号和图例；PDF的每页嵌入图像必须与 PNG 字节级解码后一致。

**边界：** 实际画质与人物相似度需要独立审核。所有新肖像一律标记 UNAPPROVED，不得只因本校验通过就冻结 MASTER。不能将 HEX 当作实体珠子的实测颜色。
