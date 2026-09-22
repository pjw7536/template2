# AGENTS.md

## 공통 원칙
- 우선순위: 직접 사용자 지시 > AGENTS.md > feature 공개 facade 계약 > 기존 파일 관례.
- 수정 경로의 하위 AGENTS.md도 적용한다. 상세 절차는 해당 작업의 스킬에서 읽는다.
- 기존 구조·명명·공개면을 유지하고 요청 밖 리팩터링을 하지 않는다. 코드는 문법·실제 import 경로가 유효해야 한다.
- 파일 경로는 forward slash를 사용한다. 주석·docstring은 한국어로 쓰고 수정한 영어 주석도 한국어로 바꾼다. 고유명사·외부 규격은 예외다.
- 사내망 연결을 전제하지 않는다. 외부 URL·credential은 env로 주입하며 사내 URL을 하드코딩하지 않는다. 승인된 서버 전용 artifact 예외는 deploy/AGENTS.md를 따른다.

## 소유권과 진입점
- 소스는 apps/<app>, 서버 배포·공통 정의는 deploy/<app>, 외부 PC 설정·mock은 local/<app>이 소유한다.
- Portal 개발: [apps/portal/AGENTS.md](apps/portal/AGENTS.md), 시작 문서: [apps/portal/README.md](apps/portal/README.md).
- Airflow DAG·플러그인·이미지 개발: apps/airflow/AGENTS.md. 설치형 제품 설정·서버 운영: [deploy/AGENTS.md](deploy/AGENTS.md).
- 개발 환경·mock·실행 도구 변경: [local/AGENTS.md](local/AGENTS.md). 공통 정의를 local에 복제하지 않고 deploy를 참조한다.
- 앱 경로·서버 선택 그룹은 deploy/shared/apps.json이 원본이다. 서버 검사·배포는 local과 앱 소스 없이 실행 가능해야 한다.
- 최상위 관리 폴더는 apps, data, deploy, docs, local만 허용한다. 도구 필수 숨김 폴더는 예외다.
- Node package·lockfile·node_modules는 apps/portal/web과 apps/tooling에서 개별 관리한다. 루트 npm workspace를 만들지 않는다.
- 검사 도구는 apps/tooling, 개발용 Compose는 local, CI Compose는 deploy에 둔다. 실행 진입점은 루트 Makefile이며 루트에 중복 정의·호환 Compose를 만들지 않는다.

## 읽기 범위
- 작업 영역에서 시작하고 대상 feature → 관련 공통 코드·공개 facade → 필요한 외부 계약 순서로 탐색한다.
- rg에 대상 경로를 명시한다. 좁은 검색으로 해결되지 않을 때만 범위를 넓히고 이유를 짧게 설명한다.
- 링크된 문서·스킬 전체를 선독하지 않는다. 해당 조건을 만족할 때 필요한 문서만 읽는다.
- 작업 영역 밖 파일을 수정할 때는 그 영역 지침도 확인한다. 경로 제한은 탐색 기본값이며 필요한 연동 확인을 금지하지 않는다.

## 작업 절차
- 구현 전 `.codex/skills/request-intake-gate/SKILL.md`를 적용한다. API·DB·권한·업무 규칙·의존 방향의 정확성이 불명확하면 번호로 질문한다. 사소한 UX는 되돌릴 수 있는 기본값을 쓴다.
- 파일 수정에는 `.codex/skills/safe-file-edit-output/SKILL.md`, 브랜치 병합에는 `.codex/skills/branch-merge-routine/SKILL.md`를 적용한다.
- 3개 이상 파일, API/DB/auth/env 계약, frontend/backend 동시 변경, 중요한 리팩터링은 docs/agent/PLANS.md에 따라 ExecPlan을 작성한다. 작은 단일 파일 수정·명확한 정리는 제외한다.
- 검증은 변경 영역에 맞춰 실행한다. 에이전트 규칙·스킬·스크립트 변경 시 관련 검증 결과를 보고한다. 평가가 필요하면 docs/agent/evals의 해당 시나리오만 사용한다.
- 응답은 경로·핵심 변경·검증 결과 중심으로 작성하고, 요청 없이 파일 전체를 출력하지 않는다.

## Git
- 파일 수정 후 자동 커밋·push하지 않는다. 커밋은 사용자 요청(커밋·push·PR·release-ready Git 마무리)이 있을 때만 한다. Push는 push·PR 요청 또는 명확히 필요한 Git 마무리에 한한다.
- 현재 요청의 변경만 stage하고 기존 사용자 변경은 보존한다. 커밋 전 관련 검증을 실행하며 실행 불가 사유를 보고한다.
- 검증 실패·충돌·인증·remote·브랜치 정책으로 Git 마무리가 막히면 중단하고 원인을 보고한다.
- 커밋 형식은 `[scope] type: summary`, 여러 scope는 의존 순서로 연결한다. type은 feat/fix/refactor/test/docs/chore, summary는 목적을 짧게 쓴다.
- scope 선택 시 [목록](docs/agent/git-scopes.md)을 읽는다. 예: `[api][web] feat: 앱 권한 동기화 추가`.
