"""사내 운영 agent 배포 런북이 앱 목록·Makefile·원본 문서와 어긋나지 않는지 검사한다."""

import json
import re
import shutil
import subprocess
import tempfile
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
        sources = [ROOT / '.opencode/agents/ops.md', ROOT / '.opencode/skills/deploy-drift-check/SKILL.md',
                   SKILL, *self.runbook_files()]
        for path in sources:
            for target, anchor in re.findall(r'\]\(([^)#\s]*)(#[^)\s]+)?\)', path.read_text()):
                if target.startswith(('http://', 'https://')):
                    continue
                linked = (path.parent / target) if target else path
                if linked.suffix == '.md':
                    relative = linked.resolve().relative_to(ROOT).as_posix()
                    self.assertTrue(relative.startswith(('.opencode/', 'deploy/shared/docs/infrastructure/')),
                                    f'{path.name}: 운영 checkout 밖의 문서 {target}')
                self.assertTrue(linked.exists(), f'{path.name}: 없는 링크 {target}')
                if anchor and linked.suffix == '.md':
                    headings = {slug(h) for h in re.findall(r'^#+\s+(.*)$', linked.read_text(), re.M)}
                    self.assertIn(anchor[1:], headings, f'{path.name}: 없는 앵커 {target}{anchor}')

    def test_sparse_checkout_keeps_only_ops_instructions_and_shared_facts(self):
        patterns = 'deploy/shared/ops-checkout.patterns'
        script = 'deploy/shared/scripts/apply-ops-checkout.sh'
        keep = [patterns, script, 'Makefile', '.gitignore', '.opencode/agents/ops.md',
                '.opencode/skills/deploy-drift-check/SKILL.md',
                '.opencode/skills/server-deploy-routine/runbooks/portal.md',
                'deploy/shared/docs/infrastructure/operations.md', 'deploy/shared/scripts/deploy_state.py',
                'deploy/portal/k8s/overlays/prod/kustomization.yaml', 'deploy/airflow/env/k8s.env']
        omit = ['AGENTS.md', 'deploy/AGENTS.md', 'deploy/README.md', 'deploy/ftp/docs/01-install.md',
                'docs/agent/README.md', 'local/AGENTS.md', 'apps/portal/AGENTS.md',
                '.claude/skills/demo/SKILL.md', '.chatgpt/config.md', '.codex/skills/demo/SKILL.md']
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            def git(*args, data=None):
                subprocess.run(['git', *args], cwd=checkout, input=data, text=True, capture_output=True, check=True)
            git('init', '-q')
            for name in keep + omit:
                path = checkout / name
                path.parent.mkdir(exist_ok=True, parents=True)
                path.write_text('fixture')
            shutil.copy2(ROOT / script, checkout / script)
            shutil.copy2(ROOT / patterns, checkout / patterns)
            (checkout / '.gitignore').write_text('*.local\n')
            git('add', '-f', '.')
            git('-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
            command = [checkout / script]
            tracked = checkout / '.claude/skills/demo/SKILL.md'
            tracked.write_text('local edit')
            blocked = subprocess.run(command, cwd=checkout, capture_output=True)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertEqual(tracked.read_text(), 'local edit')
            self.assertTrue((checkout / 'AGENTS.md').exists())
            tracked.write_text('fixture')
            (checkout / '.chatgpt/session.local').write_text('ignored')
            (checkout / '.chatgpt/notes').write_text('untracked')
            for _ in range(2):
                subprocess.run(command, cwd=checkout / 'deploy', capture_output=True, check=True)
                self.assertFalse((checkout / '.claude').exists())
                self.assertFalse((checkout / '.chatgpt').exists())
            backup, = (checkout / '.git').glob('ops-agent-files.*')
            self.assertEqual((backup / '.chatgpt/session.local').read_text(), 'ignored')
            self.assertEqual((backup / '.chatgpt/notes').read_text(), 'untracked')
            git('diff', '--exit-code', 'HEAD')
            self.assertEqual([name for name in keep if not (checkout / name).is_file()], [])
            self.assertEqual([name for name in omit if (checkout / name).exists()], [])

    def test_commands_use_selected_context_and_shared_migration_targets(self):
        for path in [SKILL, *self.runbook_files()]:
            self.assertNotIn('kubernetes-admin@kubernetes', path.read_text(), path.name)
        portal = (RUNBOOKS / 'portal.md').read_text()
        for target in ('portal-migrate', 'portal-precheck', 'portal-postcheck'):
            self.assertIn(f'make {target} ', portal)
            self.assertIn(f'make {target} ', (ROOT / 'deploy/portal/docs/01-install.md').read_text())
        self.assertNotIn('source <(sed', portal)

    def test_runbooks_never_print_secret_values(self):
        forbidden = re.compile(r'kubectl[^\n]*get secret[^\n]*-o (yaml|json)|base64 -d|config view --raw')
        for path in self.runbook_files():
            self.assertIsNone(forbidden.search(path.read_text()), f'{path.name}: Secret·kubeconfig 값 출력 명령')


if __name__ == '__main__':
    unittest.main()
