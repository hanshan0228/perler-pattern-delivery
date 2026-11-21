#!/usr/bin/env python3
"""Idempotently activate v3.0.2 likeness review in the existing Skill.

Run from any directory; operates only on the containing skill root.
Never overwrites the MASTER matrix, fixed palette or existing chart renderer.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'SKILL.md'
START = '<!-- LIKENESS_REVIEW_PACK_V302_BEGIN -->'
END = '<!-- LIKENESS_REVIEW_PACK_V302_END -->'
TEXT = f'''{START}
## v3.0.2 首稿人物相似度强制两阶段检查

当任务包含真人肖像的 **卡通风格拼豆图纸** 时，禁止只凭单张放大预览判断人物像不像。
在实际原照片、无字卡通底图、真实色号矩阵和纯色拼豆预览均产生后，**先运行**：

```bash
python scripts/likeness_review_pack.py prepare \\
  --original ORIGINAL.png --cartoon CARTOON.png --bead PREVIEW.png \\
  --matrix GRID.csv --palette assets/mard_palette.json \\
  --face-original X0 Y0 X1 Y1 --face-cartoon X0 Y0 X1 Y1 \\
  --face-bead X0 Y0 X1 Y1 --out ./likeness_review_01
python scripts/likeness_review_pack.py verify --prepared ./likeness_review_01
```

三个人脸框均应针对**当前图片**分别手动标注，或提供图像 SHA 绑定的关键点文件。
检查 `likeness_review.png` 的两个阶段：A 原图→卡通底图（眼距、眼形、鼻唇、下颌、神态）；
B 卡通底图→真实拼豆图（五官在1px和2px/豆的小尺寸预览仍辨识）。
**不允许 AI 自行将 `user_review_TEMPLATE.json` 的 false 变为 true 或虚报顾客已确认。**
没有三个可核实的人脸区域，必须标记“未完成身份相似度视觉审核”；不能以此声称画质合格。
这项检查**不替代**原 `first_sheet.py select+verify`、`chart_release_gate.py` 和
`identity_fidelity.py freeze-reviewed`；只有用户确实认可时才继续旧版确认与冻结流程。
指令和限制见 [人物相似度审核包](references/LIKENESS_REVIEW_PACK.md)。
{END}
'''


def install():
    if not SKILL.exists():
        raise SystemExit('SKILL.md 不存在；请在现有 Skill 根目录合并补丁')
    required = [ROOT/'scripts/identity_fidelity.py',ROOT/'scripts/likeness_review_pack.py',
                ROOT/'references/LIKENESS_REVIEW_PACK.md']
    for file in required:
        if not file.is_file():
            raise SystemExit(f'缺少依赖文件: {file}')
    old=SKILL.read_text(encoding='utf-8')
    if START in old or END in old:
        if old.count(START)!=1 or old.count(END)!=1:
            raise SystemExit('已有半截安装标记，请人工检查 SKILL.md')
        begin=old.index(START);end=old.index(END)+len(END)
        new=old[:begin]+TEXT.rstrip()+old[end:]
    else:
        # Insert after YAML frontmatter if present, otherwise before the first heading.
        match=re.match(r'^---\n.*?\n---\n',old,flags=re.S)
        offset=match.end() if match else 0
        new=old[:offset]+'\n'+TEXT+'\n'+old[offset:]
    if new==old:
        print('ALREADY INSTALLED')
        return
    backup=SKILL.with_name('SKILL.before_likeness_v302.md')
    if not backup.exists():backup.write_text(old,encoding='utf-8')
    SKILL.write_text(new,encoding='utf-8')
    print('INSTALLED: likeness two-stage review. Existing color-card, charts and MASTER unchanged.')


if __name__=='__main__':install()
