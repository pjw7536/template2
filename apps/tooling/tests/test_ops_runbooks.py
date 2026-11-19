"""사내 운영 agent 배포 런북이 앱 목록·Makefile·원본 문서와 어긋나지 않는지 검사한다."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNBOOKS = ROOT / '.opencode/skills/server-deploy-routine/runbooks'
SKILL = ROOT / '.opencode/skills/server-deploy-routine/SKILL.md'
# 런북마다 저성능 agent가 같은 순서로 찾도록 고정한 절 제목.
REQUIRED_SECTIONS = ('## 한눈에 보기', '## 사람이 해야 하는 일', '## 입력', '## A. 최초 설치', '## B. 업데이트',
                     '## C. 배포 후 확인', '## 멈추고 사람에게 묻는 조건')


def slug(heading):
    """GitHub 방식 앵커를 만든다."""
    return re.sub(r'[^\w\- ]', '', heading.strip().lower()).replace(' ', '-')


def make_targets():
    """Makefile에 정의된 타깃 이름을 모은다."""
    text = (ROOT / 'Makefile').read_text()
    return set(re.findall(r'^([A-Za-z0-9_.-]+):(?!=)', text, re.M))


class RunbookTests(unittest.TestCase):
    def runbook_files(self):
        return sorted(RUNBOOKS.glob('*.md'))

    def test_every_app_has_runbook_with_fixed_sections(self):
        apps = json.loads((ROOT / 'deploy/shared/apps.json').read_text())['apps']
        for app in apps:
            path = RUNBOOKS / f'{app}.md'
            self.assertTrue(path.exists(), f'런북 누락: {path}')
            text = path.read_text()
            for section in REQUIRED_SECTIONS:
                self.assertIn(section, text, f'{path.name}: {section} 절 누락')
            self.assertIn(f'runbooks/{app}.md', SKILL.read_text(), f'SKILL.md 색인 누락: {app}')

    def test_make_targets_exist(self):
        targets = make_targets()
        for path in [SKILL, *self.runbook_files()]:
            for target in re.findall(r'\bmake (?:-s )?([a-z][a-z0-9-]+)', path.read_text()):
                self.assertIn(target, targets, f'{path.name}: Makefile에 없는 타깃 {target}')

    def test_relative_links_and_anchors_resolve(self):
        for path in [SKILL, *self.runbook_files()]:
            for target, anchor in re.findall(r'\]\(([^)#\s]*)(#[^)\s]+)?\)', path.read_text()):
                if target.startswith(('http://', 'https://')):
                    continue
                linked = (path.parent / target) if target else path
                self.assertTrue(linked.exists(), f'{path.name}: 없는 링크 {target}')
                if anchor and linked.suffix == '.md':
                    headings = {slug(h) for h in re.findall(r'^#+\s+(.*)$', linked.read_text(), re.M)}
                    self.assertIn(anchor[1:], headings, f'{path.name}: 없는 앵커 {target}{anchor}')

    def test_runbooks_never_print_secret_values(self):
        forbidden = re.compile(r'kubectl[^\n]*get secret[^\n]*-o (yaml|json)|base64 -d|config view --raw')
        for path in self.runbook_files():
            self.assertIsNone(forbidden.search(path.read_text()), f'{path.name}: Secret·kubeconfig 값 출력 명령')


if __name__ == '__main__':
    unittest.main()
