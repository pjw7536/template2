# Agent Decisions

이 문서는 반복 설명 비용을 줄이기 위한 확정 결정만 기록한다.

## 확정된 운영 결정
- 프로젝트 전용 skill은 `.codex/skills/*/SKILL.md`에 둔다.
- `.codex/skills/.system/**`은 로컬 시스템 skill로 보고 추적/공유 대상에서 제외한다.
- frontend UI 변경 후에는 `npm run agent:audit:ui` 또는 `scripts/agent/check_ui_consistency.sh`를 실행한다.
- frontend feature import/export/routing 변경 후에는 `npm run agent:audit:web-boundary` 또는 `scripts/agent/check_frontend_boundaries.sh`를 실행한다.
- backend domain boundary/import/view/selector 변경 후에는 `npm run agent:audit:api-boundary` 또는 `scripts/agent/check_backend_boundaries.py`를 실행한다.
- PR에서는 `.github/workflows/feature-guardrails.yml`의 frontend boundary, backend boundary, lint, build, backend syntax 검사를 통과해야 한다.
- AI가 feature 작업을 수행할 때는 `docs/agent/ai-feature-workflow.md`의 기본 프롬프트와 검증 절차를 따른다.
- 큰 작업은 `docs/agent/PLANS.md`의 ExecPlan 기준을 따른다.
- eval은 `docs/agent/evals/*`의 작업/성공 기준을 기준으로 누적한다.
- OIDC 개발과 운영 Compose의 외부 registry image는 `repository.samsungds.net`를 사용하고, 외부 dev Compose는 public image 이름을 유지한다.

## 보류된 결정
- multi-agent orchestration은 eval에서 병렬 검토 효과가 확인될 때까지 도입하지 않는다.

## 2026-06-19: backend boundary audit 1차 도입

- backend boundary audit은 `scripts/agent/check_backend_boundaries.py`의 AST 기반 검증으로 운영한다.
- 1차 실패 기준은 cross-domain internal import, test cross-domain internal import, `views.py` 직접 ORM, `selectors.py` write ORM, backend app 구조 위반이다.
- 기존 service direct read ORM 후보는 범위가 넓어 CI 실패 기준에 넣지 않고 별도 debt로 관리한다.
- CI backend job은 boundary audit 후 Python compile을 실행한다.

## 2026-05-17: 앱 문서 상세화 구조

- 문서 홈은 `docs/README.md`로 유지하고, 실제 route/model/env/command 색인은 `docs/inventory.md`로 분리한다.
- 주제별 상세 문서는 `docs/backend.md`, `docs/frontend.md`, `docs/data-model.md`, `docs/configuration.md`로 분리해 문서가 길어져도 읽기 흐름을 유지한다.
- 모듈 문서는 업무 흐름과 운영 포인트를 담당하고, API 문서는 endpoint 계약을 담당한다.
- 문서 drift를 줄이기 위해 `scripts/agent/check_docs_inventory.sh`로 backend endpoint, frontend route, model, command, env group의 문서 반영 여부를 검증한다.

## 2026-05-29: data_movement 테이블별 중첩 앱 구조

- 파일 기반 DB 적재 기능은 `apps/api/api/data_movement/<table_name>` 아래에 테이블별 Django app으로 둔다.
- `<table_name>` 폴더명은 실제 target table 이름과 일치시킨다.
- 테이블별 app은 자기 model, migration, loader service, tests, management command만 소유한다.
- 공통 파일 탐색, deflate CSV 파싱, PostgreSQL COPY 유틸은 `apps/api/api/data_movement/common`에 둔다.

## 2026-07-27: Portal·앱 고정 역할 접근 권한

- Portal과 모든 하위 scope의 역할은 `UserAccess.role`의 `user`/`admin` 두 값으로 통일한다.
- canonical `portal` key 이외의 모든 scope는 Portal 접근을 선행 조건으로 사용한다.
- 자동 정책과 일괄 승인은 `user`만 부여하고 `admin`은 사용자별 명시 권한으로만 부여한다.
- `pending`·`denied` 행은 `user`만 저장하며, 역할 없는 승인·부여도 기존 역할 대신 `user`를 사용한다.
- Portal `admin`은 전역 접근 관리, 앱 `admin`은 해당 앱의 관리자 기능만 담당한다.
- 역할 판정은 요청 단위 일괄 resolver를 사용하고 전역 캐시는 사용하지 않는다.
- 별도 소비처가 없는 사용자 프로필 운영 역할은 제거하고 권한 역할은 `UserAccess.role`만 사용한다.
- 인증 응답의 접근 정보는 Portal과 모든 활성 scope를 포함한 `scope_access` 하나만 사용한다.
- 접근 신청은 `/account/access/request`, 관리 결정은 `/account/access/users/<user_id>/decision`만 사용한다.
- 접근 관리 요청 body와 query는 camelCase canonical 필드만 허용하고 이전 별칭은 400으로 거절한다.
- 접근 차단 오류는 scope 종류와 관계없이 `scope_access_required`, `scope`, `access` 형태를 사용한다.
- 제거된 `portal_access`, `app_access`, Portal 전용 승인 API, 정책 가상 역할, `canManage` 호환 계층은 복구하지 않는다.
- `AccessScope`는 migration으로만 추가하고 `key`·유형을 변경하거나 행을 물리 삭제하지 않는다.
- canonical Portal은 `key=portal`과 `scope_type=portal`을 DB 제약조건으로 함께 고정한다.
- 권한 매트릭스는 Portal과 모든 활성 app·feature scope를 같은 결정 API로 관리한다.
- 사용자와 scope는 비활성화로 수명을 관리하고 감사 로그가 참조하는 행은 `PROTECT`한다.

## 2026-07-29: 소속 역할과 앱별 데이터 범위

- 소속 역할 capability는 `viewer=조회`, `member=조회·일반 변경`, `manager=조회·일반 변경·삭제·소속 승인·권한 관리`로 고정한다.
- 소속 변경 승인·거절은 대상 소속 manager만 가능하며 요청자는 자신의 요청을 처리할 수 없다.
- 마지막 manager는 강등하거나 회수할 수 없고, 현재 소속 접근 자체도 회수하지 않는다.
- 앱 접근, 앱별 소속 데이터 범위, 소속 역할 capability는 서로 독립적으로 판정한다.
- Emails 이동은 source와 target 모두 member 이상, 삭제는 대상 소속 manager를 요구한다.
- Emails 전역 운영 특권은 Emails `admin` 역할과 `data_scope_mode=all`을 모두 가진 경우에만 활성화한다.

## 2026-07-30: 소속 권한 동시성·감사 불변조건

- 사용자별 `PENDING` 소속 변경 요청은 DB 조건부 unique constraint로 한 건만 허용한다.
- 소속 변경 승인·거절과 소속 역할 관리는 대상 `Affiliation` 잠금을 공통 직렬화 지점으로 사용하고 잠금 뒤 최신 manager 역할을 재검사한다.
- 소속 역할 부여·변경·회수와 `data_scope_mode`의 실질적 변경은 원본 권한 변경과 같은 transaction에서 `AccessAuditLog`로 기록한다.
- 비활성 `Affiliation`은 현재 소속·소속 역할·앱별 grant 계산에서 모두 제외하며,
  연결 설정은 삭제하지 않고 전역 일시중지 상태로 보존한다.
- 여러 `Affiliation`을 잠그는 쓰기 경로는 항상 `Affiliation.id` 오름차순을 사용한다.
- Django Admin은 현재 소속과 소속 변경 요청을 직접 저장하지 않고 서비스 action만 사용한다.
- 소속 기준정보의 생성·자동 동기화 변경·활성 상태 변경은 모두 같은 transaction에서 lifecycle 감사 로그를 남긴다.
- Admin 소속 일괄 활성 상태 변경은 운영자 사유를 필수로 받고 선택 행 전체를 하나의 transaction으로 처리한다.
- `UserSdwtProdChange`는 상태별 승인 시각·승인자·거절 사유 조합까지 DB CheckConstraint로 강제한다.
- 여러 소속의 capability 판정은 활성 소속과 명시 역할을 일괄 조회하고 현재 소속의 암묵적 member 규칙을 합산한다.
