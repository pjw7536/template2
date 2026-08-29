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

## 2026-08-29: Argo CD 준비형 환경 변수 계약

- 환경 변수 파일은 `env/overlays/<profile>`만 사용하고 profile 간 상속을 두지 않는다.
- 각 profile의 `*.config.env`와 `*.secret.env`는 완결된 ConfigMap/Secret 후보로 관리한다.
- Compose는 해당 profile의 config, secret 순서로만 값을 합성한다.
- OIDC/prod key 누락과 파일 내부 중복은 `scripts/validate_env_profile_keys.sh`로 검사한다.
- 운영 Web의 `VITE_*`와 명시적 Web runtime key는 이미지 빌드 시 고정하지 않고 컨테이너 시작 시 `/runtime-env.js`로 생성한다.
- Kubernetes, Kustomize, Helm, Argo CD manifest는 별도 도입 단계에서 이 env 계약을 소비하며 이번 정리 범위에는 포함하지 않는다.

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

## 2026-07-31: Observer 표시·조회 시간대

- Observer의 날짜-only 및 offset 없는 조회 query는 `Asia/Seoul` 현지 시각으로 해석한다.
- offset이 있는 조회 query와 DB aware datetime은 같은 instant의 `Asia/Seoul` 시각으로 변환한다.
- Observer API의 공통 시간 필드는 `+09:00` offset을 포함한 ISO datetime으로 반환한다.
- Timeline 축, Data Log, Log Detail, 날짜 범위 계산은 브라우저 지역과 관계없이 `Asia/Seoul`을 사용한다.
- EQP의 `chg_time`, `last_update_time`과 TIP의 `rule_pkg_update_date`, `gpm_update_date`, `last_update_date`는 timezone 없는 원천값을 KST 벽시계로 해석해 UTC instant로 저장한다.
- 기존 EQP/TIP timestamp는 과거 Log Detail에 표시되던 원천 벽시계를 정답으로 삼아 9시간 앞당기는 data migration으로 보정한다.

## 2026-08-03: Access Stats 외부 사용량 동기화

- 외부 사용량 동기화 요청은 `access-stats` 접근이 허용된 모든 로그인 사용자에게 허용한다.
- 수동 통계 붙여넣기는 기존처럼 `access-stats`의 `admin` 역할만 허용한다.
- 일반 사용자의 실제 외부 API 동기화는 전역 기준 6시간에 한 번만 수행한다.
- `access-stats admin`과 슈퍼유저는 6시간 제한을 적용하지 않는다.
- 성공뿐 아니라 실패한 실제 시도도 일반 사용자의 6시간 제한에 포함해 장애 중 반복 호출을 막는다.
- 제한 기준은 `ExternalAppUsageSyncState.updated_at`이며, 제한된 요청은 외부 API 호출 없이 `skipped=true`와 사유를 반환한다.
- 프런트는 제한된 요청의 서버 사유를 정보 toast로 사용자에게 표시한다.

## 2026-08-12: Assistant 초기 마이그레이션 통합

- 서버 최초 적용 전인 `assistant`의 개발 마이그레이션 체인은 최종 모델 상태를 직접 생성하는 단일 `0001_initial.py`로 통합한다.
- 신규 설치에 불필요한 기존 메시지 연결 및 요약 이전용 data migration은 초기 마이그레이션에 포함하지 않는다.
- 단일 초기 마이그레이션이 배포된 이후의 Assistant schema 변경은 기존 파일을 수정하지 않고 새 migration으로 추가한다.

## 2026-08-12: Portal Assistant 앱 단위 활성 컨텍스트와 방 단위 공유 기억

- 같은 Assistant 대화방의 일반 앱(`assistant:openwebui:<appKey>`), Observer(`observer:*`), Email RAG(`assistant`)는 최근 모델 이력과 rolling summary를 `chatwidget:shared` 기억 그룹으로 공유한다.
- `contextKey`는 기억을 분리하지 않고 요청 sender, 메시지의 앱 출처와 현재 Observer 조회 범위를 보존한다.
- 앱 이동 시 대화방과 기억은 유지하고 현재 앱의 sender·고정 배경지식·화면 데이터만 교체한다.
- OpenWebUI의 앱 배경지식은 클라이언트 문장을 신뢰하지 않고 서버 허용 카탈로그에서 `appKey`를 해석해 system message에 추가한다.
- Observer의 공유 대화와 장기 요약은 질문 의도·용어·후속 질문을 이해하는 배경으로만 사용하고, 사실 판단은 현재 `observer_analysis_context_json`으로 제한한다.
- 기존 `assistant`와 `chatwidget:shared` rolling summary는 통합 전 메시지 집합의 `message_count`를 재사용할 수 없으므로 `0002` data migration에서 삭제하고 원본 메시지로 재생성한다.

## 2026-08-13: Assistant Runtime v2 Profile·partition·권한 provenance

- 이 결정은 2026-08-12의 모든 앱 공유 기억 결정을 대체한다. Portal은 `shared`, Email은 `shared`와 `scope:emails`, Observer는 `shared`와 `scope:observer`만 읽는다.
- 실행 의미는 versioned Profile로 재현하고 권한 하한은 항상 현재 Profile과 Tool 정책을 적용한다.
- `AssistantGeneration`을 Run source of truth로 유지하며 Run, message, summary, 자동 제목에 version 1 `access_requirements`를 저장한다.
- Account scope와 실제 RAG permission group/mailbox claim 중 하나라도 회수되면 답변 전체를 잠그고 내부 data claim 이름은 UI에 노출하지 않는다.
- client `history`를 받는 실행 API는 제공하지 않는다. `appKey`, `contextKey`는 권한 근거로 사용하지 않고 Turn service가 소유 대화방의 current branch를 서버에서 조립한다.
- legacy provenance는 nullable schema 이후 resumable command로 backfill하고 해석 불가능한 데이터는 `legacy-unresolved`로 영구 잠근다.
- 외부 LLM/RAG URL과 payload는 변경하지 않아 offsite dummy/env/Compose contract 수정은 하지 않는다.

## 2026-08-13: Email RAG 답변 Provider OpenWebUI 통합

- 이 결정은 위 Runtime v2 결정 중 Email 답변 Provider 연결을 유지한다는 부분만 대체한다.
- Email RAG의 검색, permission group/mailbox 필터, 구조화 `answer`/`segments`와 출처 계약은 유지한다.
- Email 답변 생성의 URL, model, token, 공통 header와 timeout은 일반 Assistant와 같은 `OPENWEBUI_*` 설정을 사용한다.
- `ASSISTANT_LLM_TEMPERATURE`와 `ASSISTANT_LLM_SYSTEM_MESSAGE`는 Email 구조화 prompt 조정값으로만 유지하고, `ASSISTANT_REQUEST_TIMEOUT`은 RAG 검색 timeout으로 유지한다.
- offsite `adfs_dummy`의 기존 OpenAI 호환 endpoint가 Email 구조화 stream을 지원하므로 mock handler나 Compose 서비스 계약은 변경하지 않는다.

## 2026-08-14: Appstore·ESOP Dashboard 서버 조회 배경지식

- Appstore와 ESOP Dashboard의 변경 가능한 업무 데이터는 RAG 색인 대신 domain selector를 통한 요청 시점 snapshot으로 조회한다.
- 브라우저는 검색·카테고리·선택 앱 또는 line·기간·화면 종류만 보내며 원본 업무 데이터는 보내지 않는다.
- Appstore와 ESOP는 각각 독립 Profile, Tool, `scope:appstore`/`scope:line-dashboard` 기억 partition과 대상 앱 Account scope를 사용한다.
- Appstore 연락처·댓글·이미지와 ESOP 사용자·댓글·수신자·관리자 설정은 snapshot에서 제외한다.
- snapshot은 untrusted read-only JSON으로 OpenWebUI system context에 결합하고 내부 문구를 명령으로 취급하지 않는다.
- 외부 OpenWebUI/RAG endpoint와 env, offsite dummy 계약은 변경하지 않는다.

## 2026-08-15: Assistant 현재 앱 지식 단일 토글

- ChatWidget은 현재 앱 지식 사용 여부만 ON/OFF로 선택한다.
- ON이면 현재 앱의 전용 Profile과 Tool을 바로 실행하며 질문 의도를 다시 분류하거나 다른 앱 지식으로 전환하지 않는다.
- OFF이면 `portal-default` Profile, 빈 Tool 입력, `shared` memory만 사용한다.
- 실행 경로를 설명하는 별도 답변 badge나 공개 metadata는 제공하지 않는다.
- Profile registry에는 현재 실행 version만 두며 삭제된 실행 방식의 재생성 계약은 제공하지 않는다.
- 외부 RAG/OpenWebUI endpoint·env·Compose 계약과 기존 저장 메시지 조회는 변경하지 않는다.
