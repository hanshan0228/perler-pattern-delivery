#!/usr/bin/env python3
"""Non-destructive v3.0 Skill metadata upgrade for an existing repository.

Never overwrites algorithms, palettes, examples or approved matrices.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

MARKER='<!-- PERLER_IDENTITY_FIDELITY_V3 -->'
SECTION=f'''\n{MARKER}\n## P0：人物相似度优先验收（v3.0 Identity Fidelity）\n\n新建真人肖像拼豆图纸时，任何照片→卡通→拼豆流程都必须在用户确认前按下列步骤执行：\n\n1. **AI 只制作精致卡通底图**；不让图像模型绘制最终施工网格、色号、坐标或图例。\n2. 用原始照片、卡通底图、真实矩阵派生的 `pixel_preview.png` 执行 `scripts/identity_fidelity.py prepare`，产生三阶段对比与 `identity_report.json`。必须严格核查预览的每格真实色号。\n3. 如果具备真实且本地可用的 MediaPipe Face Landmarker 模型，可选 `extract` 检查眼距、嘴型、下颌等关键点几何差异；**几何指标不是身份认证，也不是相似度百分比**。模型缺失、卡通人脸识别失败时写 `NOT_EVALUATED`，不得伪造分数。\n4. 如果拼豆预览具备与图像哈希绑定的关键点记录，先检查 `bead_face_resolution_budget` 中眼距、嘴宽、脸宽及脸高占用的真实拼豆格。低分辨率警告只能提示放大人物/增加格数，**不是身份相似度评分**。缺少有效关键点时报告 `NOT_EVALUATED`，不得自行编造。\n5. 真实用户在看过最终拼豆尺寸的预览后，亲自确认眼型、鼻嘴、脸型、姿态、发型与辨识度；如果不能确认，就先修正候选，不得批量写 `true`。\n6. 用户确认后执行 `identity_fidelity.py attest`，再由 `identity_fidelity.py freeze-reviewed` 冻结 MASTER；其后由既有 `perler_delivery.py deliver/verify` 严格交付。旧版 `freeze` 可用于既有工程导入，但绕过此审查不得称为 v3.0 身份保真交付。\n\n这是**人物保真工作流与人工批准记录**，不是对任意人脸“100% 相似”的承诺。执行细节、实际调用命令、论文与许可风险见 [身份保真说明](references/IDENTITY_FIDELITY.md) 与 [底图提示词](references/IDENTITY_PROMPT_TEMPLATE.md)。\n<!-- /PERLER_IDENTITY_FIDELITY_V3 -->\n'''


def upgrade(root: Path):
    skill=root/'SKILL.md'
    if not skill.is_file():raise RuntimeError(f'SKILL.md not found at {skill}')
    text=skill.read_text(encoding='utf-8')
    if MARKER not in text:
        match=re.search(r'^# .+$',text,flags=re.MULTILINE)
        if not match:raise RuntimeError('SKILL.md has no top-level title')
        text=text[:match.end()]+SECTION+text[match.end():]
    m=re.search(r'(?m)^(\s{2}version:\s*["\']?)(\d+)\.(\d+)\.(\d+)(["\']?)$',text)
    if not m:raise RuntimeError('No normal version metadata in SKILL.md; refuse to guess')
    current=tuple(map(int,m.group(2,3,4)))
    if current<(3,0,0):
        text=text[:m.start()]+m.group(1)+'3.0.0'+m.group(5)+text[m.end():]
    skill.write_text(text,encoding='utf-8')
    for name,title in [('README.md','v3.0 Identity fidelity workflow'),('README_CN.md','v3.0 人物相似度优先工作流')]:
        p=root/name
        if not p.is_file():continue
        original=p.read_text(encoding='utf-8')
        heading='## '+title
        if heading not in original:
            original+='\n'+heading+'\n\nFor custom portraits, run `scripts/identity_fidelity.py prepare` on the original, cartoon and verified bead preview. Require actual customer approval before `freeze-reviewed`; details: [`references/IDENTITY_FIDELITY.md`](references/IDENTITY_FIDELITY.md). Geometric landmark deviation is **not** a validated identity score.\n'
            p.write_text(original,encoding='utf-8')
    return str(root)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    args=ap.parse_args()
    print('UPGRADED:',upgrade(Path(args.root)))


if __name__=='__main__':main()
