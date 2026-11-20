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
ACCESS = ROOT / 'deploy/shared/docs/infrastructure/access.md'
# 사람과 저성능 agent가 같은 순서로 찾도록 고정한 앱 가이드의 절 제목.
REQUIRED_SECTIONS = ('## 한눈에 보기', '## 구성', '## 사전 준비', '## 입력', '## A. 최초 설치', '## B. 업데이트',
                     '## C. 배포 후 확인', '## 문제 해결과 멈춤 조건', '## 상세 문서')
# 공통 가이드에서 앱 가이드가 가리키는 절.
COMMON_SECTIONS = ('### 단계 표시', '## 실행 규칙', '## 앱 설치 순서', '## 모든 작업 공통 시작', '## 공용 TLS 등록', '## 사내 CA 묶음',
                   '## 공용 Traefik 검사·갱신', '## 이미지 빌드 도구', '## 이미지 빌드와 발행', '## 설치 준비 점검',
                   '## 배포 후 공통 마무리', '## 장애 조회')
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
MARKER = re.compile(r'\[(조회|검사|변경|승인)\]')
# 절차가 아닌 문서는 이 문장으로 표시한다. 운영 agent는 이 문서의 명령을 실행하지 않는다.
REFERENCE_NOTE = '참고 문서입니다. 운영 agent가 실행하는 절차가 아닙니다.'
# 접근 방법은 접근 경로 표 한 곳에 적는다. 정의가 없는 표현으로 단계를 쓰지 않는다.
UNDEFINED_ACCESS = re.compile(r'승인된 [^\n|]{0,24}(경로|입력|계정|파일|수단|세션|채널|위치|데이터|기록|env|값)|관리 경로|보안 입력|입력 채널'
                              r'|접근 가능한 관리자 세션|허용된 클라이언트 경로')
# 역할을 나눠 쓰던 표현. 요청 조건은 실행 규칙과 접근 경로 표로 통일한다.
OLD_ROLES = ('[사람]', '사람이 하는 일', '#사람이-하는-일', '사용자 보고', '사람에게', '사람이 직접', '담당자가', '담당자에게', '담당자는',
             '운영자가 판단', '운영 agent는 실행하지 않습니다', '현장 확인 필요')
INTERACTIVE = re.compile(r'(^|[\s;(|])read -[a-z]|(^|[\s;(|])(sudo )?(vi|vim|nano) |\$KUBE_CONTEXT|\$\{KUBE_CONTEXT')


def slug(heading):
    """GitHub 방식 앵커를 만든다."""
    return re.sub(r'[^\w\- ]', '', heading.strip().lower().replace('`', '')).replace(' ', '-')


def prose(path):
    """코드 블록을 뺀 본문. 블록 안의 `#` 줄과 괄호를 제목·링크로 오인하지 않는다."""
    return re.sub(r'```.*?```', '', path.read_text(), flags=re.S)


def catalog():
    return json.loads((ROOT / 'deploy/shared/apps.json').read_text())['apps']


def make_targets():
    """Makefile의 명시적 타깃과, 패턴 규칙이 카탈로그의 앱마다 제공하는 타깃."""
    text = (ROOT / 'Makefile').read_text()
    targets = set(re.findall(r'^([A-Za-z0-9_.-]+):(?!=)', text, re.M))
    for suffix in re.findall(r'^%-([a-z]+):', text, re.M):
        targets.update(f'{name}-{suffix}' for name in catalog())
    return targets


def markdown_files(*folders):
    """Git이 추적하거나 새로 만든 Markdown 파일."""
    listed = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', *folders], cwd=ROOT, capture_output=True, text=True, check=True)
    return [ROOT / name for name in listed.stdout.split() if name.endswith('.md') and (ROOT / name).is_file()]


def procedure_files():
    """운영 agent가 절차로 읽는 배포 문서. 참고 문서와 개발 agent 지침은 제외한다."""
    return [path for path in markdown_files('deploy')
            if path.name != 'AGENTS.md' and REFERENCE_NOTE not in path.read_text()]


def bash_blocks(path):
    """(시작 줄 번호, 블록 앞 문맥, 블록 내용, 절 전체 표시 여부)를 차례로 낸다. 문맥은 같은 절에서 앞 블록 뒤의 본문이다."""
    whole_section, context, block, start = False, '', None, 0
    for number, line in enumerate(path.read_text().splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            if block is None:
                block, start, language = [], number, stripped[3:]
            else:
                if language in ('bash', 'sh', 'shell', ''):
                    yield start, context, '\n'.join(block), whole_section
                block, context = None, ''
            continue
        if block is not None:
            block.append(line)
        elif line.startswith('#'):
            whole_section, context = False, ''
        elif re.search(r'모두 \[(조회|검사)\]입니다', line):
            whole_section = True
        else:
            context += line + '\n'


class DeployGuideTests(unittest.TestCase):
    def setUp(self):
        self.apps = catalog()

    def guide(self, app):
        """앱 가이드는 카탈로그 deployPath의 README다."""
        return ROOT / self.apps[app]['deployPath'] / 'README.md'

    def test_every_app_guide_has_fixed_sections_in_order(self):
        skill = (SKILLS / 'server-deploy-routine/SKILL.md').read_text()
        for app in self.apps:
            text = self.guide(app).read_text()
            positions = [text.find('\n' + section + '\n') for section in REQUIRED_SECTIONS]
            missing = [section for section, position in zip(REQUIRED_SECTIONS, positions) if position == -1]
            self.assertEqual(missing, [], f'{app}: 가이드 절 누락')
            self.assertEqual(positions, sorted(positions), f'{app}: 가이드 절 순서')
            self.assertIn(self.guide(app).relative_to(ROOT).as_posix(), skill, f'스킬의 앱 가이드 색인 누락: {app}')
            self.assertIn(self.guide(app).relative_to(ROOT / 'deploy').as_posix(), COMMON.read_text(), f'공통 가이드의 설치 순서 표 누락: {app}')

    def test_common_guide_has_sections_that_app_guides_reference(self):
        text = COMMON.read_text()
        for section in COMMON_SECTIONS:
            self.assertIn('\n' + section + '\n', text, f'공통 가이드 절 누락: {section}')
        for mark in ('[조회]', '[검사]', '[변경]', '[승인]'):
            self.assertIn(f'| {mark} |', text, f'단계 표시 설명 누락: {mark}')
        self.assertIn('| [변경] | 클러스터·서버를 바꿈 | 바로 실행', text)
        self.assertIn('표시가 없는 명령 블록은 실행하지 않습니다', text)
        for target in ('make build-tools-check', 'make build-tools-install', 'make ops-preflight ', 'make drift-check '):
            self.assertIn(target, text)
        # ops-deploy 요약의 필드를 가이드가 모두 설명한다.
        for field in ('failedStep', 'driftResultCode', 'blocked', 'pending'):
            self.assertIn(f'`{field}`', text, f'ops-deploy 요약 필드 설명 누락: {field}')

    def test_guides_use_single_deploy_entry_and_no_host_specific_values(self):
        for app, entry in self.apps.items():
            text = self.guide(app).read_text()
            self.assertIn(f'make ops-deploy APP={app} KUBE_CONTEXT="<context>"', text, f'{app}: 일괄 배포 명령 누락')
            if entry['runtime']:
                self.assertIn(f'make {app}-smoke KUBE_CONTEXT="<context>"', text, f'{app}: smoke 확인 누락')
            self.assertIsNone(IPV4.search(text), f'{app}: 가이드에 IP 주소')
            for word in ('kubernetes-admin@kubernetes', 'read -r'):
                self.assertNotIn(word, text, f'{app}: 가이드에 실행 환경에 묶인 표현 {word}')
            # 가이드의 배포 명령 설명은 apps.json의 단계와 같아야 한다.
            for step in entry['steps']:
                self.assertIn(f'`{step}`', text, f'{app}: 가이드에 없는 배포 단계 {step}')
            # 저장소 밖 env를 쓰는 변수 이름을 입력 표가 알려 준다.
            for declared in entry['inputs'][:1]:
                self.assertIn(f'`{declared["variable"]}`', text, f'{app}: 입력 표에 없는 env 변수 {declared["variable"]}')
        self.assertIsNone(IPV4.search(COMMON.read_text()), '공통 가이드에 IP 주소')

    def test_every_command_block_in_procedures_declares_its_effect(self):
        # 운영 agent는 표시가 없는 명령 블록을 실행하지 않는다. 절차 문서의 모든 명령 블록은 바로 앞 설명에 단계 표시가 있어야 한다.
        for path in procedure_files():
            for number, context, _, whole_section in bash_blocks(path):
                self.assertTrue(whole_section or MARKER.search(context),
                                f'{path.relative_to(ROOT)}:{number}: 명령 블록 앞에 단계 표시가 없음')

    def test_procedures_can_run_without_a_terminal_session(self):
        # 명령마다 새 셸이 열린다. 입력을 기다리거나 앞 블록에서 정한 변수에 의존하는 명령은 agent가 실행할 수 없다.
        for path in procedure_files():
            for number, _, block, _ in bash_blocks(path):
                found = INTERACTIVE.search(block)
                self.assertIsNone(found, f'{path.relative_to(ROOT)}:{number}: 대화형 명령 또는 셸 상태 의존 `{found[0].strip() if found else ""}`')

    def test_node_steps_do_not_use_ssh(self):
        # 사내 서버는 노드 사이의 SSH를 쓸 수 없다. 노드 명령은 node_exec.py로 실행한다.
        remote = re.compile(r'(^|[\s;(|&])(ssh|scp|sftp|rsync)\s')
        for path in procedure_files():
            for number, _, block, _ in bash_blocks(path):
                found = remote.search(block)
                self.assertIsNone(found, f'{path.relative_to(ROOT)}:{number}: SSH에 의존하는 명령 `{found[0].strip() if found else ""}`')
        access = ACCESS.read_text()
        for heading in ('## 노드 명령 실행', '## 가입 전 노드'):
            self.assertIn('\n' + heading + '\n', access)
        self.assertIn('deploy/shared/scripts/node_exec.py', access)
        self.assertTrue((ROOT / 'deploy/shared/scripts/node_exec.py').is_file())
        definition = AGENT.read_text()
        self.assertIn('node_exec.py', definition)
        self.assertIn('SSH는 쓸 수 없다', definition)

    def test_off_cluster_steps_point_to_the_access_table(self):
        for path in procedure_files():
            if path == ACCESS:
                continue
            for number, line in enumerate(prose(path).splitlines(), 1):
                found = UNDEFINED_ACCESS.search(line)
                self.assertTrue(found is None or 'access.md' in line,
                                f'{path.relative_to(ROOT)}: 접근 경로 표를 가리키지 않는 표현 `{found[0] if found else ""}`')

    def test_procedures_have_no_stages_reserved_for_people(self):
        for path in markdown_files('deploy', '.opencode', 'docs/agent'):
            contents = path.read_text()
            records = 'deploy/shared/docs/infrastructure' in path.as_posix()
            for marker in OLD_ROLES:
                # 인프라 기록의 `담당자` 열과 책임 기록은 운영 정보다.
                if records and marker.startswith('담당자'):
                    continue
                self.assertNotIn(marker, contents, f'{path.relative_to(ROOT)}: 이전 역할 구분 {marker}')

    def test_prerequisite_rows_say_how_to_confirm_completion(self):
        # 사전 준비 표의 완료 확인 칸은 실행할 명령이거나 접근 경로·상세 절의 링크다.
        for app in self.apps:
            text = self.guide(app).read_text()
            section = text.split('\n## 사전 준비\n', 1)[1].split('\n## ', 1)[0]
            rows = [line for line in section.splitlines() if line.startswith('|') and not re.match(r'^\|\s*(-|준비 작업)', line)]
            for row in rows:
                cells = [cell.strip() for cell in re.split(r'(?<!\\)\|', row.strip().strip('|'))]
                self.assertGreaterEqual(len(cells), 2, f'{app}: 사전 준비 행 형식 {row[:40]}')
                self.assertRegex(cells[-1], r'`[^`]+`|\]\(', f'{app}: 완료 확인에 명령이나 링크가 없음 — {cells[0][:40]}')

    def test_app_docs_are_numbered_consecutively(self):
        for app, entry in self.apps.items():
            names = sorted(path.name for path in (ROOT / entry['deployPath'] / 'docs').glob('*.md'))
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

    def test_transition_runbook_is_reachable_from_the_start_of_every_task(self):
        # 이미 배포된 서버가 새 checkout을 받으면 공통 시작에서 전환 런북으로 간다.
        runbook = ROOT / 'deploy/shared/docs/operations/05-transition.md'
        self.assertTrue(runbook.is_file())
        start = COMMON.read_text().split('\n## 모든 작업 공통 시작\n', 1)[1].split('\n## ', 1)[0]
        self.assertIn('05-transition.md', start)
        self.assertIn('05-transition.md', (SKILLS / 'server-deploy-routine/SKILL.md').read_text())
        self.assertIn('## 적용 여부 확인', runbook.read_text())

    def test_agent_never_waits_for_approval_by_default(self):
        definition = AGENT.read_text()
        self.assertNotIn('effect: ask', definition)
        for skill in SKILL_SOURCES:
            self.assertIn(f'resource: "{skill}"', definition, f'{skill}: 사용 권한 누락')
            self.assertIn(f'| `{skill}` |', definition, f'{skill}: 요청별 스킬 표 누락')
        for denied in ('*delete namespace*', '*delete pv*', '*helm*uninstall*', 'git push*', 'git reset*'):
            block = definition.split(f'resource: "{denied}"')[1].split('- action')[0]
            self.assertIn('effect: deny', block, denied)
        self.assertIn('표시가 없는 명령 블록은 실행하지 않는다', definition)
        self.assertIn('deploy/shared/docs/infrastructure/access.md', definition)

    def test_agent_definition_and_skills_use_aliases_only(self):
        table = json.loads((ROOT / 'deploy/shared/docs/infrastructure/aliases.json').read_text())
        real = [item[key] for group in ('nodes', 'addresses') for item in table[group].values() for key in ('name', 'ip') if key in item]
        for path in (AGENT, *SKILLS.glob('*/SKILL.md')):
            text = path.read_text()
            self.assertEqual([value for value in real if value in text], [], path.name)


if __name__ == '__main__':
    unittest.main()
