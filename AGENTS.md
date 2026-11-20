# 저장소 공통 지침

사내 관리 호스트의 opencode `ops` agent로 실행 중이면 이 문서의 개발 규칙(구현 전 요청 분류, ExecPlan, 개발용 스킬, 파일 수정 절차)을 적용하지 않는다. [agent 정의](.opencode/agents/ops.md)와 [운영 agent 지침](deploy/AGENTS.md#사내-운영-agent), `.opencode/skills/`의 운영 스킬만 따른다.

## 우선순위와 작성

- 직접 사용자 지시 > 해당 경로의 AGENTS.md > feature 공개 facade 계약 > 기존 파일 관례 순으로 적용한다. 수정 경로의 하위 지침도 확인한다.
- 기존 구조·명명·공개면과 사용자 변경을 보존하고 요청 밖 리팩터링을 하지 않는다. 문법·실제 import 경로를 검증한다.
- 경로는 forward slash, 주석·docstring은 한국어를 사용한다. 수정한 영어 주석도 한국어로 바꾸며 고유명사·외부 규격은 예외다.
- Markdown에는 현재 구성·동작·사용법·제약·남은 확인을 쓴다. 확인 날짜·변경 경위·완료 기록·이전 값은 Git 이력으로 관리한다. 현재 필요한 이전·복구·호환 절차, 버전·만료일·데이터 예시는 유지한다.
- 사내망 연결을 전제하지 않는다. 외부 URL·credential은 env로 주입하고 사내 URL을 하드코딩하지 않는다. 서버 전용 artifact 예외는 deploy 지침을 따른다.

## 소유권과 진입점

| 작업 영역 | 지침·원본 |
| --- | --- |
| Portal 소스 | [Portal 지침](apps/portal/AGENTS.md), [시작 문서](apps/portal/README.md) |
| Airflow DAG·플러그인·이미지 | [Airflow 지침](apps/airflow/AGENTS.md) |
| 서버 배포·공통 정의 | [deploy 지침](deploy/AGENTS.md) |
| 외부 PC 설정·mock·실행 도구 | [local 지침](local/AGENTS.md) |
| 사내 서버 운영·배포 agent(opencode `ops`) | [운영 agent 지침](deploy/AGENTS.md#사내-운영-agent) |

- 소스는 `apps/<app>`, 서버 정의는 `deploy/<app>`, 개발 PC 설정은 `local/<app>`이 소유한다. local은 공통 정의를 복제하지 않고 deploy를 참조한다.
- 앱 경로·서버 선택 그룹의 원본은 `deploy/shared/apps.json`이다. 서버 정적 검사는 local·앱 소스 없이 실행 가능해야 하고, 이미지 빌드와 배포는 저장소 전체 checkout에서 실행한다.
- 최상위 관리 폴더는 `apps`, `data`, `deploy`, `docs`, `local`만 허용한다. 도구 필수 숨김 폴더는 예외다.
- Node package·lockfile·node_modules는 `apps/portal/web`, `apps/tooling`에서 개별 관리한다. 루트 npm workspace를 만들지 않는다.
- 검사 도구는 `apps/tooling`, 개발용 Compose는 `local`, CI Compose는 `deploy`에 둔다. 실행 진입점은 루트 Makefile이며 중복 정의·호환 Compose를 루트에 만들지 않는다.

## 탐색과 작업

- 매 작업 시작 시 [사내 인프라 정보](deploy/shared/docs/infrastructure/README.md)를 읽는다. 운영값을 받거나 변경하면 해당 주제 원본과 하위 지침에 따라 현재 값·연결 관계·설정 원본·확인 상태를 갱신한다. 저장소 선언과 실제 운영 적용은 구분한다.
- 대상 feature → 관련 공통 코드·공개 facade → 필요한 외부 계약 순서로 탐색한다. `rg`에 대상 경로를 명시하고 좁은 검색으로 해결되지 않을 때만 이유를 설명하고 확대한다.
- 문서·스킬은 해당 작업에 필요한 것만 읽는다. 영역 밖을 수정하면 그 지침도 확인한다. 탐색 범위는 필요한 연동 확인을 금지하는 경계가 아니다.
- 구현 전 `.codex/skills/request-intake-gate/SKILL.md`를 적용한다. API·DB·권한·업무 규칙·의존 방향의 정확성에 필요한 정보만 번호로 질문하고, 사소한 UX는 되돌릴 수 있는 기본값으로 진행한다.
- 파일 수정은 `safe-file-edit-output`, 브랜치 병합은 `branch-merge-routine` 스킬을 따른다. 스킬 원본은 `.codex/skills/<name>/SKILL.md`이며 Claude Code는 `.claude/skills` 링크로 같은 원본을 읽는다. 사내 opencode 운영 스킬만 `.opencode/skills/<name>/SKILL.md`가 원본이며 개발용 스킬과 연결하지 않는다. 스킬을 추가·삭제·이름 변경하면 [링크 규칙](docs/agent/README.md#codex-설정과-스킬)도 따른다.
- 3개 이상 파일, API/DB/auth/env 계약, frontend/backend 동시 변경, 중요한 리팩터링은 [ExecPlan 규칙](docs/agent/PLANS.md)을 따른다. 작은 단일 수정·명확한 정리는 제외한다.
- 변경 영역에 맞는 검사를 실행하고 에이전트 규칙·스킬·스크립트 변경도 검증 결과를 보고한다. 평가가 필요하면 `docs/agent/evals`의 해당 시나리오만 사용한다.
- 응답은 경로·핵심 변경·검증 결과 중심으로 작성하고 요청 없이 파일 전체를 출력하지 않는다.

## Git

- 자동 commit·push하지 않는다. Commit은 사용자 요청(커밋·push·PR·release-ready Git 마무리)이 있을 때만, push는 push·PR 요청 또는 명확히 필요한 Git 마무리에 한한다.
- 현재 요청의 변경만 stage한다. 커밋 전 관련 검증을 실행하고 실행 불가 사유를 보고한다. 검증 실패·충돌·인증·remote·브랜치 정책으로 Git 마무리가 막히면 중단하고 원인을 보고한다.
- 형식은 `[scope] type: summary`이며 여러 scope는 의존 순서로 연결한다. Type은 feat/fix/refactor/test/docs/chore, summary는 목적을 짧게 쓴다. Scope는 [목록](docs/agent/02-git-scopes.md)을 확인한다.
