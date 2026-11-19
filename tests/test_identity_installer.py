"""Installer must be idempotent and preserve all unrelated content."""
from pathlib import Path
import tempfile
import unittest
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from install_identity_fidelity import upgrade,MARKER

class InstallerTests(unittest.TestCase):
    def test_upgrade_idempotent_and_preserves_existing_skill(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);source='---\nname: perler-pattern-delivery\nmetadata:\n  version: "2.9.1"\n---\n# 原始 Skill\n## 其它重点\n保留全部旧规则\n'
            (p/'SKILL.md').write_text(source,encoding='utf-8')
            upgrade(p);once=(p/'SKILL.md').read_text()
            upgrade(p);twice=(p/'SKILL.md').read_text()
            self.assertEqual(once,twice)
            self.assertIn('version: "3.0.0"',once)
            self.assertIn('保留全部旧规则',once)
            self.assertEqual(once.count(MARKER),1)
    def test_never_downgrades_future_metadata(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'SKILL.md').write_text('---\nmetadata:\n  version: "3.2.1"\n---\n# Skill\n')
            upgrade(p)
            self.assertIn('version: "3.2.1"',(p/'SKILL.md').read_text())
if __name__=='__main__': unittest.main()
