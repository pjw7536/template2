"""배포 문서(사람과 사내 운영 agent가 함께 읽는 한 벌)가 앱 목록·Makefile·서로의 링크와 어긋나지 않는지 검사한다."""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILLS = ROOT / '.opencode/skills'
AGENT = ROOT / '.opencode/agents/ops.md'
COMMON = ROOT / 'deploy/README.md'
# 사람과 저성능 agent가 같은 순서로 찾도록 고정한 앱 가이드의 절 제목.
REQUIRED_SECTIONS = ('## 한눈에 보기', '## 구성', '## 사람이 하는 일', '## 입력', '## A. 최초 설치', '## B. 업데이트',
                     '## C. 배포 후 확인', '## 문제 해결과 멈춤 조건', '## 상세 문서')
# 공통 가이드에서 앱 가이드가 가리키는 절.
COMMON_SECTIONS = ('### 단계 표시', '## 실행 규칙', '## 앱 설치 순서', '## 모든 작업 공통 시작', '## 공용 TLS 등록', '## 사내 CA 묶음',
                   '## 공용 Traefik 검사·갱신', '## 이미지 빌드 도구', '## 배포 후 공통 마무리', '## 장애 조회')
# 운영 agent가 쓰는 스킬과 각 스킬이 절차의 원본으로 가리켜야 하는 문서 위치.
SKILL_SOURCES = {
    'server-deploy-routine': 'deploy/README.md',
    'deploy-drift-check': '04-drift.md#대조-실행',
    'server-state-report': '04-drift.md#서버-상태-보고',
    'incident-triage': 'deploy/README.md#장애-조회',
    'server-readiness-check': 'deploy/README.md#설치-준비-점검',
    'infra-record-sync': 'infrastructure/README.md',
}
IPV4 = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')


def slug(heading):
    """GitHub 방식 앵커를 만든다."""
    return re.sub(r'[^\w\- ]', '', heading.strip().lower().replace('`', '')).replace(' ', '-')


def prose(path):
    """코드 블록을 뺀 본문. 블록 안의 `#` 줄과 괄호를 제목·링크로 오인하지 않는다."""
    return re.sub(r'```.*?```', '', path.read_text(), flags=re.S)


def make_targets():
    """Makefile에 정의된 타깃 이름을 모은다."""
    return set(re.findall(r'^([A-Za-z0-9_.-]+):(?!=)', (ROOT / 'Makefile').read_text(), re.M))


def markdown_files(*folders):
    """Git이 추적하거나 새로 만든 Markdown 파일."""
    listed = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', *folders], cwd=ROOT, capture_output=True, text=True, check=True)
    return [ROOT / name for name in listed.stdout.split() if name.endswith('.md') and (ROOT / name).is_file()]


class DeployGuideTests(unittest.TestCase):
    def setUp(self):
        self.apps = json.loads((ROOT / 'deploy/shared/apps.json').read_text())['apps']

    def guide(self, app):
        return ROOT / f'deploy/{app}/README.md'

    def test_every_app_guide_has_fixed_sections_in_order(self):
        skill = (SKILLS / 'server-deploy-routine/SKILL.md').read_text()
        for app in self.apps:
            text = self.guide(app).read_text()
            positions = [text.find('\n' + section + '\n') for section in REQUIRED_SECTIONS]
            missing = [section for section, position in zip(REQUIRED_SECTIONS, positions) if position == -1]
            self.assertEqual(missing, [], f'{app}: 가이드 절 누락')
            self.assertEqual(positions, sorted(positions), f'{app}: 가이드 절 순서')
            self.assertIn(f'deploy/{app}/README.md', skill, f'스킬의 앱 가이드 색인 누락: {app}')

    def test_common_guide_has_sections_that_app_guides_reference(self):
        text = COMMON.read_text()
        for section in COMMON_SECTIONS:
            self.assertIn('\n' + section + '\n', text, f'공통 가이드 절 누락: {section}')
        for mark in ('[조회]', '[검사]', '[변경]', '[승인]', '[사람]'):
            self.assertIn(f'| {mark} |', text, f'단계 표시 설명 누락: {mark}')
        self.assertIn('| [변경] | 클러스터·서버를 바꿈 | 바로 실행', text)
        for target in ('make build-tools-check', 'make build-tools-install', 'make ops-preflight ', 'make drift-check '):
            self.assertIn(target, text)

    def test_guides_use_single_deploy_entry_and_no_host_specific_values(self):
        for app, entry in self.apps.items():
            text = self.guide(app).read_text()
            self.assertIn(f'make ops-deploy APP={app} KUBE_CONTEXT="<context>"', text, f'{app}: 일괄 배포 명령 누락')
            self.assertIn(f'make {app}-smoke KUBE_CONTEXT="<context>"', text, f'{app}: smoke 확인 누락')
            self.assertIsNone(IPV4.search(text), f'{app}: 가이드에 IP 주소')
            for word in ('kubernetes-admin@kubernetes', '$KUBE_CONTEXT', 'read -r'):
                self.assertNotIn(word, text, f'{app}: 가이드에 실행 환경에 묶인 표현 {word}')
            # 가이드의 배포 명령 설명은 apps.json의 단계와 같아야 한다.
            for step in entry['steps']:
                self.assertIn(f'`{step}`', text, f'{app}: 가이드에 없는 배포 단계 {step}')
        self.assertIsNone(IPV4.search(COMMON.read_text()), '공통 가이드에 IP 주소')

    def test_every_command_block_in_guides_says_who_runs_it(self):
        # 운영 agent는 표시가 있는 명령만 실행한다. 가이드의 모든 명령 블록은 바로 앞 설명에 단계 표시가 있어야 한다.
        marker = re.compile(r'\[(조회|검사|변경|승인|사람)\]')
        for path in (COMMON, *(self.guide(app) for app in self.apps)):
            whole_section, context = False, ''
            in_block = False
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if line.lstrip().startswith('```'):
                    if not in_block and line.strip() != '```text':
                        self.assertTrue(whole_section or marker.search(context),
                                        f'{path.relative_to(ROOT)}:{number}: 명령 블록 앞에 단계 표시가 없음')
                    in_block = not in_block
                    if not in_block:
                        context = ''
                    continue
                if in_block:
                    continue
                if line.startswith('#'):
                    whole_section, context = False, ''
                elif re.search(r'모두 \[(조회|검사)\]입니다', line):
                    whole_section = True
                else:
                    context += line + '\n'

    def test_human_marker_is_used_only_where_agent_must_stop(self):
        # 사람이 하는 작업은 표시가 없는 것이 기본이다. [사람]은 agent가 멈춰야 하는 자리에만 남긴다.
        agent_marker = re.compile(r'\[(조회|검사|변경|승인)\]')
        host_command = re.compile(r'kubectl --context|(^|\s|\|\s*)make [a-z-]|python3 deploy/', re.M)
        rules = {ROOT / 'deploy/AGENTS.md', COMMON}
        for path in markdown_files('deploy'):
            if path in rules:
                continue
            guide = path.name == 'README.md' and path.parent.parent == ROOT / 'deploy'
            for section in re.split(r'(?m)^(?=#{1,6} )', re.sub(r'```.*?```', lambda m: '\x00' + m[0].replace('\n#', '\n\x01#'), path.read_text(), flags=re.S)):
                if '[사람]' not in re.sub(r'\x00```.*?```', '', section, flags=re.S):
                    continue
                title = section.split('\n', 1)[0].strip('# ').strip()
                where = f'{path.relative_to(ROOT)} "{title}"'
                if guide:
                    if title == '사람이 하는 일':
                        self.assertNotRegex(section, r'(?m)^\| \[사람\] ', f'{where}: 표의 행에 [사람]이 중복됨')
                    continue
                prose = re.sub(r'\x00```.*?```', '', section, flags=re.S)
                blocks = ''.join(re.findall(r'\x00```.*?```', section, flags=re.S))
                self.assertTrue(agent_marker.search(prose) or host_command.search(blocks),
                                f'{where}: 사람 작업만 있는 절에는 [사람]을 붙이지 않는다')

    def test_app_docs_are_numbered_consecutively(self):
        for app in self.apps:
            names = sorted(path.name for path in (ROOT / f'deploy/{app}/docs').glob('*.md'))
            self.assertEqual([name[:3] for name in names], [f'{index:02d}-' for index in range(1, len(names) + 1)], f'{app}: {names}')

    def test_make_targets_in_deploy_docs_exist(self):
        targets = make_targets()
        for path in markdown_files('deploy', '.opencode'):
            for target in re.findall(r'\bmake (?:-s )?([a-z][a-z0-9-]+)', path.read_text()):
                self.assertIn(target, targets, f'{path.relative_to(ROOT)}: Makefile에 없는 타깃 {target}')

    def test_relative_links_and_anchors_resolve(self):
        headings = {}
        for path in markdown_files('deploy', '.opencode', 'docs/agent'):
            for target, anchor in re.findall(r'\]\(([^)#\s]*)(#[^)\s]+)?\)', prose(path)):
                if target.startswith(('http://', 'https://', 'mailto:')):
                    continue
                linked = (path.parent / target).resolve() if target else path
                self.assertTrue(linked.exists(), f'{path.relative_to(ROOT)}: 없는 링크 {target}')
                if anchor and linked.suffix == '.md':
                    if linked not in headings:
                        headings[linked] = {slug(h) for h in re.findall(r'^#+\s+(.*)$', prose(linked), re.M)}
                    self.assertIn(anchor[1:], headings[linked], f'{path.relative_to(ROOT)}: 없는 앵커 {target}{anchor}')

    def test_procedures_live_in_deploy_docs_not_in_skills(self):
        # 스킬은 읽는 순서와 보고 형식만 둔다. 절차를 복제한 런북 폴더를 다시 만들지 않는다.
        self.assertFalse((SKILLS / 'server-deploy-routine/runbooks').exists())
        self.assertEqual(sorted(path.parent.name for path in SKILLS.glob('*/SKILL.md')), sorted(SKILL_SOURCES))
        for name, source in SKILL_SOURCES.items():
            text = (SKILLS / name / 'SKILL.md').read_text()
            self.assertIn(source, text, f'{name}: 절차의 원본 문서를 가리키지 않음')
            self.assertRegex(text, rf'(?m)^name: {name}$')
            description = re.search(r'(?m)^description: (.+)$', text)[1]
            # 요청 문구로 스킬을 고르므로 설명에 적용할 요청 예시가 있어야 한다.
            self.assertIn('요청', description, f'{name}: 설명에 적용할 요청이 없음')
            # 스킬은 명령 블록으로 절차를 복제하지 않는다. 한 줄 명령 인용만 둔다.
            self.assertNotIn('```', text, f'{name}: 스킬에 명령 블록이 있음')
        self.assertIn('ops-diagnose', (SKILLS / 'incident-triage/SKILL.md').read_text())
        procedure = (ROOT / 'deploy/shared/docs/operations/04-drift.md').read_text()
        for required in ('make ops-report ', 'make -s ops-redact', 'aliases.json'):
            self.assertIn(required, procedure)
        for path in (*SKILLS.glob('*/SKILL.md'), AGENT):
            self.assertNotIn('kubernetes-admin@kubernetes', path.read_text(), path.name)

    def test_image_build_is_first_deploy_step_for_built_apps(self):
        for app in ('airflow', 'portal'):
            self.assertEqual(self.apps[app]['steps'][0], f'{app}-image')

    def test_agent_never_waits_for_approval_by_default(self):
        definition = AGENT.read_text()
        self.assertNotIn('effect: ask', definition)
        for skill in SKILL_SOURCES:
            self.assertIn(f'resource: "{skill}"', definition, f'{skill}: 사용 권한 누락')
            self.assertIn(f'| `{skill}` |', definition, f'{skill}: 요청별 스킬 표 누락')
        for denied in ('*delete namespace*', '*delete pv*', '*helm*uninstall*', 'git push*', 'git reset*'):
            block = definition.split(f'resource: "{denied}"')[1].split('- action')[0]
            self.assertIn('effect: deny', block, denied)
        # 같은 문서를 사람도 보므로, agent는 표시가 있는 단계만 실행한다는 경계를 정의에 둔다.
        self.assertIn('[사람] 단계와 표시가 없는 명령 블록은 실행하지 않는다', definition)

    def test_agent_definition_and_skills_use_aliases_only(self):
        table = json.loads((ROOT / 'deploy/shared/docs/infrastructure/aliases.json').read_text())
        real = [item[key] for group in ('nodes', 'addresses') for item in table[group].values() for key in ('name', 'ip') if key in item]
        for path in (AGENT, *SKILLS.glob('*/SKILL.md')):
            text = path.read_text()
            self.assertEqual([value for value in real if value in text], [], path.name)


if __name__ == '__main__':
    unittest.main()
