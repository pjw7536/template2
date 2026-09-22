# Agent Decisions

이 문서는 반복 설명 비용을 줄이기 위한 확정 결정만 기록한다.

## 2026-09-17: Kubernetes 기준 저장소·로컬 배포 소유권

- 직접 개발하는 Portal·Airflow 소스는 apps, 설치형 제품의 서버 원본은 deploy, 개발 차이는 local이 소유한다. tooling과 mock은 각각 apps/tooling과 local/adfs_dummy에 유지한다.
- 로컬 집계는 local/shared/k8s이며 Portal·Keycloak·Headlamp·mock의 앱별 원본을 참조한다. 공통 namespace·Traefik·외부 PostgreSQL Service는 shared가 소유한다.
- 9월 16일의 이전 Compose 실행 보존 방침을 대체한다. 현재 Compose는 로컬 DB·API 검사·CI 세 구성만 유지하며 폐기된 경로·빈 폴더를 제거한다.
- 리소스 식별자·포트·권한·스토리지·DB·실제 설정과 기존 Make 진입점은 유지한다. 서버 선택 checkout은 local과 앱 소스를 요구하지 않는다.
- [실행·검증 기록](plans/kubernetes-repository-cleanup.md)을 참고한다.

## 2026-09-14: Keycloak 배포 경로 단순화

- CP1 배포는 기존 stack·claim-mappers YAML 두 개로 통일한다. 중복 Python 도구는 제거한다.
- 서버 원본은 deploy/keycloak/k8s/stack.yaml로 통합하며 생성된 배포 내용은 유지한다.
- make k8s-export는 Keycloak YAML 두 개만 생성한다. Portal client는 Portal 원본에서 필요할 때 별도로 생성한다.
- 사내 OIDC 연결 설정은 새 연결 준비에 필요한 선택 원본으로 유지한다.

## 2026-09-14: account_user 기준 Keycloak 프로필

- 사용자는 기존 커스텀 User Profile 정의를 프로젝트 신원 필드 기준으로 교체하기로 했다.
- 사용자가 사내 userid(EPID)의 유일성·불변성·재사용 금지를 확인했다. Keycloak username은 LOCAL/FORCE mapper로 EPID를 사용하며 기존 연결 계정은 사내 재로그인 때 갱신한다.
- 사람 이름은 display_name에 저장해 Portal token의 username으로 전달하고, knox_id·sabun 계약은 유지한다.
- Keycloak부터 정비한다. 중복 avatarid 프로필과 IdP userid 속성 mapper는 제거하고 Portal userid는 기본 username property를 읽는다. Django·프론트엔드는 후속 정비하며 기존 사용자 속성값은 일괄 삭제하지 않는다.
- 성·이름은 기본 firstName·lastName에 저장하고 Portal에는 first_name·last_name으로 전달한다. 같은 이름의 커스텀 프로필 정의는 제거한다.
- 로그인 ID·부서·이메일 등은 account_user 이름으로 저장하고 Portal claim 계약은 유지한다.
- mapper 전달 YAML은 ConfigMap과 Job을 함께 포함해 서버 네트워크 설정 재적용 없이 갱신한다.

## 2026-09-14: Keycloak 단독 라우팅 복원

- 단독 스택은 `etch-sso`만 감시하고 기존 Ingress TLS Secret 참조를 유지한다. 사용자 후속 지시에 따라 `websecure` entrypoint와 TLS annotation을 명시한다.
- Portal 감시 확장은 Portal overlay로 RBAC를 준비한 뒤 `traefik-watch-patch.json`으로 별도 적용한다. 아래 9월 11일의 공유 감시 기본값을 대체한다.
- 실제 HTTPS 장애 원인은 운영 로그로 확정하지 않았으며, 이번 변경은 사용자가 제공한 정상 구성으로 네트워크 차이를 복원한다.

## 2026-09-11: Keycloak 식별 속성 보호와 Portal 운영 라우팅

- 사번·로그인 ID 등 미정의 사내 속성은 ADMIN_EDIT로 보존하고 일반 사용자 편집을 차단한다. 이전 Keycloak 스택 계획의 ENABLED 정책을 대체한다.
- IdP 속성 mapper 19개와 Portal token mapper 19개는 각 소유 Job으로 등록한다. 완료된 Job은 ConfigMap 변경만으로 재실행되지 않는다.
- 공유 Traefik은 etch-sso와 tailwind-internal을 감시하며 Portal 접근 권한은 Portal 운영 overlay의 namespace Role로 부여한다.
- Portal Nginx는 내부 Ingress의 원래 HTTP/HTTPS 정보를 유지한다. 검증 기록은 [수정 계획](plans/fix-keycloak-production-routing.md)에 둔다.

## 확정된 운영 결정
- 프로젝트 전용 skill은 `.codex/skills/*/SKILL.md`에 둔다.
- `.codex/skills/.system/**`은 로컬 시스템 skill로 보고 추적/공유 대상에서 제외한다.
- frontend UI 변경 후에는 `make audit-ui` 또는 `apps/tooling/agent/check_ui_consistency.sh`를 실행한다.
- frontend feature import/export/routing 변경 후에는 `make audit-web-boundary` 또는 `apps/tooling/agent/check_frontend_boundaries.sh`를 실행한다.
- backend domain boundary/import/view/selector 변경 후에는 `make audit-api-boundary` 또는 `apps/tooling/agent/check_backend_boundaries.py`를 실행한다.
- PR에서는 `.github/workflows/feature-guardrails.yml`의 frontend boundary, backend boundary, lint, build, backend syntax 검사를 통과해야 한다.
- AI가 feature 작업을 수행할 때는 `docs/agent/ai-feature-workflow.md`의 기본 프롬프트와 검증 절차를 따른다.
- 큰 작업은 `docs/agent/PLANS.md`의 ExecPlan 기준을 따른다.
- eval은 `docs/agent/evals/*`의 작업/성공 기준을 기준으로 누적한다.
- OIDC 개발과 운영 Compose의 외부 registry image는 `repository.samsungds.net`를 사용하고, 외부 dev Compose는 public image 이름을 유지한다.

## 보류된 결정
- multi-agent orchestration은 eval에서 병렬 검토 효과가 확인될 때까지 도입하지 않는다.

## 2026-09-11: Portal 운영은 Kubernetes prod

- Portal의 env와 overlay는 각각 `deploy/portal/env/prod`, `deploy/portal/k8s/overlays/prod`를 사용한다. internal 경로는 통합하고 리소스 Namespace는 변경하지 않는다.
- Portal 로그인은 준비한 Keycloak 입력을 사용한다. local/oidc/test의 기존 설정과 개발 Compose는 유지한다.
- 실제 prod env와 전환 전 복구용 사본은 Git에서 제외하며 공개 예시만 관리한다.
- Portal prod의 필수 입력 검사는 oidc Compose와 분리한다. Airflow·RAG 등 선택 업무 연동은 실제 연결 시 별도로 확인한다.
- 기존 운영 Compose 시작·빌드 명령은 안내 후 중단한다. 전체 업무 서비스의 Kubernetes 이식과 실제 배포 완료를 뜻하지 않는다.

## 2026-08-29: Argo CD 준비형 환경 변수 계약

- 환경 변수 파일은 앱별 `deploy/portal/env/<profile>`, `deploy/keycloak/env`, `deploy/airflow/env`, `deploy/monitoring/env`에서 관리하고 profile 간 상속을 두지 않는다. 로컬 K8s의 실행 차이만 `portal/local/api-k8s.env`로 명시한다.
- 각 profile은 서비스별 `<service>.env` 한 파일에 설정과 credential을 함께 관리한다.
- Compose는 해당 profile의 서비스 env 파일만 직접 주입한다.
- OIDC/prod key 누락과 파일 내부 중복은 `deploy/shared/scripts/validate_env_profile_keys.sh`로 검사한다.
- 운영 Web의 `VITE_*`와 명시적 Web runtime key는 이미지 빌드 시 고정하지 않고 컨테이너 시작 시 `/runtime-env.js`로 생성한다.
- 2026-09-11 후속 결정: Kubernetes는 credential 입력을 Secret으로 소비한다. Keycloak 서버, 사내 OIDC와 Portal client 등록은 필요한 key만 선택해 별도 적용한다.
- 외부 Secret 저장소를 도입할 때만 credential 분리를 새 계약으로 다시 설계한다.

## 2026-06-19: backend boundary audit 1차 도입

- backend boundary audit은 `apps/tooling/agent/check_backend_boundaries.py`의 AST 기반 검증으로 운영한다.
- 1차 실패 기준은 cross-domain internal import, test cross-domain internal import, `views.py` 직접 ORM, `selectors.py` write ORM, backend app 구조 위반이다.
- 기존 service direct read ORM 후보는 범위가 넓어 CI 실패 기준에 넣지 않고 별도 debt로 관리한다.
- CI backend job은 boundary audit 후 Python compile을 실행한다.

## 2026-05-17: 앱 문서 상세화 구조

- 문서 홈은 `docs/README.md`로 유지하고, 실제 route/model/env/command 색인은 `docs/inventory.md`로 분리한다.
- 주제별 상세 문서는 `docs/backend.md`, `docs/frontend.md`, `docs/data-model.md`, `docs/configuration.md`로 분리해 문서가 길어져도 읽기 흐름을 유지한다.
- 모듈 문서는 업무 흐름과 운영 포인트를 담당하고, API 문서는 endpoint 계약을 담당한다.
- 문서 drift를 줄이기 위해 `apps/tooling/agent/check_docs_inventory.sh`로 backend endpoint, frontend route, model, command, env group의 문서 반영 여부를 검증한다.

## 2026-05-29: data_movement 테이블별 중첩 앱 구조

- 파일 기반 DB 적재 기능은 `apps/portal/api/api/data_movement/<table_name>` 아래에 테이블별 Django app으로 둔다.
- `<table_name>` 폴더명은 실제 target table 이름과 일치시킨다.
- 테이블별 app은 자기 model, migration, loader service, tests, management command만 소유한다.
- 공통 파일 탐색, deflate CSV 파싱, PostgreSQL COPY 유틸은 `apps/portal/api/api/data_movement/common`에 둔다.

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

## 2026-09-14: 배포 파일과 env의 앱별 소유권 통합

- Keycloak·Portal·Airflow·Monitoring의 배포 정의와 env 원본은 `deploy/<app>/`에 둔다.
- 공통 Compose 조합·클러스터 설정·env 검사 도구만 `deploy/shared/`에 둔다. Portal client 입력은 Portal이 소유한다.
- 루트 Makefile·Compose 및 기존 단독 Airflow 실행 진입점은 유지한다. CP1의 외부 실제 설정·인증서·DB 경로는 변경하지 않는다.
- 상세 경로와 운영 명령은 [배포 안내](../../deploy/README.md)를 따른다. 과거 계획의 경로는 당시 상태를 기록한 것이다.

## 2026-09-14: 외부 PC local과 사내 deploy 분리

- 외부 PC 전용 env·mock·Compose·kind·실행 도구는 `local/`에 두고 사내 oidc/prod와 CI test는 deploy에 유지한다.
- local은 공통 배포 정의를 참조하며 원본을 복제하지 않는다. 사내 검사·배포는 local 없이 실행한다.
- 서버는 앱별 sparse checkout과 `make server-check APP=<앱>`을 사용한다. 전체 env·Kubernetes 검사는 전체 개발 checkout에서 수행한다.
- 서버 clone 절차는 [선택 체크아웃 안내](../../deploy/SERVER_CHECKOUT.md), 로컬 개발은 [local 안내](../../local/README.md)를 따른다.

## 2026-09-14: 사내 Kubernetes 전용

- 사내 배포 방식은 Kubernetes만 지원한다. 로컬·CI Compose는 유지하며 과거 사내 Compose 정의는 참고용으로 보존한다.
- Keycloak·Portal의 prod K8s 원본만 현재 서버 검사 대상이다. Airflow·Monitoring과 과거 oidc 환경은 K8s 정의가 없어 검사 실패로 표시한다.
- 사내 Compose 시작·빌드는 차단하고 전체 down은 로컬만 종료한다. 이전 컨테이너 정리는 명시적인 legacy 종료 명령으로만 수행한다.

## 2026-09-14: Airflow 단일 서버 공식 Helm 배포

- Airflow는 공식 chart 1.22.0과 기존 실행 버전 2.11.0/LocalExecutor를 사용한다. 버전·checksum을 고정하고 오프라인 반입을 지원한다.
- PostgreSQL 16은 같은 Kubernetes 노드에서 Helm release 밖 StatefulSet으로 관리한다. DB·로그 local PV는 Retain과 명시적 노드 affinity를 사용한다.
- 실행 입력은 deploy/airflow/env/k8s.env, 이미지 빌드 입력은 build.env로 관리한다. 실제 파일은 Git에서 제외하고 기존 Compose env는 자동 병합하지 않는다.
- 신규 DAG는 일시정지로 시작하며 기존 DB 이전·키 교체·메이저 업그레이드는 별도 운영 절차로 수행한다.
- APP=airflow 서버 검사는 Helm·고정 chart 준비 후 가능하다. Monitoring과 PROFILE=oidc는 여전히 미전환이다.

## 2026-09-14: Airflow 사내 구성과 Kubernetes 실행 기본값 정렬

- 사용자의 기존 사내 설정 유지 요청에 따라 build.env 예시에 기존 internal Compose의 모든 build arg를 옮기고 PostgreSQL 사내 이미지도 동일하게 지정한다. 로컬 Dockerfile 기본값과 Compose는 변경하지 않는다.
- ODBC 기본 전달 방식은 단일 노드의 기존 디렉터리 전체를 /usr/local/odbc에 읽기 전용 hostPath로 마운트하는 방식이다. 실제 경로는 ODBC_HOST_PATH로 받고 Secret 방식과 동시에 사용하지 않는다.
- 최초 Helm 구성에서 조정했던 값을 기존 Compose/Airflow 2.11.0과 같게 정렬한다: 신규 DAG 활성, parallelism=32, DAG task/run=16/16, web worker=4, default_pool=-1, 로그 자동 삭제 비활성. CPU·메모리 제한은 별도 Kubernetes 운영 설정으로 유지한다.
- 사내 driver 다운로드·ODBC 대상 접속은 실제 사내 환경에서 확인해야 하며 외부 PC 검증으로 성공을 주장하지 않는다.

## 2026-09-14: 기존 Keycloak과 Airflow 우선 기동

- 공용 Traefik 소스는 deploy/shared/ingress가 소유하며 기존 etch-sso 리소스 이름·노드·포트와 Keycloak 단독 렌더 결과는 유지한다.
- 두 앱 재적용은 make server-up을 사용한다. 기존 Traefik 감시 namespace를 보존하고 Airflow namespace 접근 권한을 먼저 연결한다. Keycloak Secret과 OIDC/mapper Job은 갱신하지 않는다.
- Airflow 공개 URL은 실제 env로 지정하며 기존 TLS Secret의 인증서 도메인·만료를 확인한다. 다른 namespace 인증서는 명시한 원본에서 대상 Secret이 없을 때만 복사한다.
- Portal 없는 UI 기동 단계에는 신규 DAG 일시정지 override를 사용한다. 일반 Airflow 배포 기본값과 기존 DB의 DAG 활성 상태는 유지한다.
- 최초 서버 준비와 이후 pull·실행 절차는 [서버 기동 안내](../../deploy/shared/docs/operations/server-start.md)에 모은다. 선택 checkout은 keycloak-airflow를 지원한다.

## 2026-09-15: APP VIP와 두 Worker의 443 연결

- 인프라팀이 APP VIP 10.172.26.150을 10.172.40.117:443과 10.172.40.87:443에 연결했다. NodePort 대신 기존 hostPort 443을 사용한다.
- server-up의 VIP_BACKENDS 입력으로 실제 Node InternalIP를 확인하고 기존 Traefik Deployment를 두 Worker에 하나씩 배치한다. Backend 목록은 Deployment annotation에 유지해 후속 실행에서도 보존한다.
- maxSurge=0/maxUnavailable=1의 순차 교체를 사용하며 LB Health Check로 비정상 Backend를 제외한다. Keycloak·Airflow·DB 배치는 확장하지 않는다.
- 업무 URL은 https://etch.samsungds.net/airflow이며 실제 env와 도메인 인증서로 입력한다. 기존 Keycloak 도메인·issuer·인증서는 유지하고 DNS 전환은 VIP 경유 로그인 검증 이후 수행한다.

## 2026-09-15: 앱별 Kubernetes 배포 진입점

- Keycloak부터 순차 배포하도록 keycloak-check/up과 airflow-check/up을 앱별 스크립트로 제공한다. server-up은 기존 통합 실행 호환용으로 유지한다.
- Keycloak은 env/certs로 최초 Secret을 만들며 기존 Secret 불일치는 자동 덮어쓰지 않는다. 공용 Traefik의 namespace 감시와 VIP 배치를 유지한다.
- Airflow 배포는 Keycloak 원본을 읽거나 다시 적용하지 않고 자신의 리소스와 필요한 공용 ingress 연결만 처리한다. 앱별 배포에는 DB 삭제·초기화가 포함되지 않는다.

## 2026-09-15: Keycloak Kubernetes 파일 역할별 정리

- 원본은 k8s/server, k8s/oidc, k8s/claims로 분리하고 k8s/kustomization.yaml 진입점을 유지한다.
- ConfigMap 키·컨테이너 마운트 경로·리소스 이름은 유지하며 정리 전후 생성 YAML이 동일함을 검증했다. 기본 배포는 설정 파일을 준비하고 OIDC·claim Job은 별도로 실행한다.

## 2026-09-15: Kubernetes Monitoring 신규 구성

- 기존 Compose Monitoring의 서버 이전은 kube-prometheus-stack으로 대체한다.
- Portal·Keycloak과 독립 설치하며, 초기 Grafana 접속은 port-forward, 외부 알림 수신자는 미설정이다.
- chart와 checksum을 고정하고 사내 미러·노드·데이터 경로·관리자 Secret 참조는 외부 env로 받는다.
- 상세: [실행 계획](plans/monitoring-kube-prometheus-stack.md), [배포 안내](../../deploy/monitoring/README.md).

## 2026-09-15: 앱별 소스·배포 경계

- Portal은 `apps/portal/{api,web}`, Airflow 소스·이미지는 `apps/airflow`에서 관리합니다.
- `deploy/shared/apps.json`을 앱 경로 원본으로 사용하며 기본 서버 checkout은 배포 전용, `--with-source`는 빌드 소스 추가입니다.
- 기존 Compose 진입점과 참고용 정의는 유지합니다. Airflow 로그는 새 `data/airflow/logs`를 사용하며 이전 로그는 이관하지 않습니다.
- 자세한 실행·검증 기록은 [ExecPlan](plans/app-source-deployment-layout.md)에 있습니다.

## 2026-09-15: 최상위 관리 폴더 다섯 개

관리 폴더는 apps·data·deploy·docs·local로 제한합니다. 저장소 도구는 apps/tooling,
개발 Compose 조합은 local/compose, CI·이전 서버 Compose는 deploy가 소유합니다.
실행은 Makefile을 기준으로 하며 루트 Compose는 호환 연결만 유지합니다.
[실행 기록](plans/five-root-folders.md)을 참고합니다.

## 2026-09-15: 루트 package·Compose 연결 제거

루트 npm workspace와 Compose 연결 파일을 제거합니다. Web과 tooling은 독립 lockfile·node_modules를 사용하며 실행은 Makefile로 통일합니다. 이전 구조 결정의 호환 연결 보존 방침을 대체합니다. [작업 기록](plans/root-entrypoint-cleanup.md)을 참고합니다.

## 2026-09-15: 로컬 env 준비와 공통 적용의 의존 방향

로컬 API env 합성은 `local/portal/scripts/apply-env.sh`가 담당하고 공통 배포 도구에는 합성 파일을 전달합니다. 기존 Makefile 진입점은 유지하며 공통 도구의 로컬 API 직접 호출은 명시적 파일을 요구합니다. 폴더·배포 회귀 검사는 Feature Guardrails의 별도 tooling 작업에서 실행합니다. [작업 기록](plans/layout-review-followup.md)을 참고합니다.

## 2026-09-16: 전체 로컬 앱의 Kubernetes 기본 실행

- `make dev/down`은 한 PC의 kind 전체 앱과 별도 Docker PostgreSQL을 관리합니다. 이전 Compose 실행은 `compose-dev/compose-down`으로 유지합니다.
- 새 DB volume에 Portal·Airflow·Keycloak DB와 계정을 분리하며, 기존 DB는 이관하거나 초기화하지 않습니다. 파일은 호스트에 유지해 kind 재생성 후에도 보존합니다.
- Portal·FTP·Airflow·Monitoring은 deploy의 공통 정의를 재사용하고 로컬 연결·자원 차이만 local에 둡니다. 서버는 local 없이 검사·배포할 수 있습니다.
- 소스 변경은 이미지 재빌드·재배포로 반영합니다. 백엔드 검사는 같은 이미지의 일회성 Compose api에서 실행하며 전체 테스트에는 표준 test env를 적용합니다.
- [로컬 실행 안내](../../local/README.md), [실행·검증 기록](plans/local-all-apps-k8s.md)을 참고합니다.

## 2026-09-16: Portal 중심 에이전트 작업 범위

- 저장소·소스 경로·실행 환경을 유지하고 에이전트 시작 위치는 apps/portal을 기본으로 한다.
- 루트는 공통 규칙·영역 진입점, Portal은 개발 탐색, Web·API는 각 경계, deploy·local은 운영·개발 환경 상세를 소유한다.
- 대상 feature부터 탐색하고 외부 계약 변경 시에만 관련 설정으로 확장한다. Git scope 상세·스킬·문서는 필요할 때 읽는다.
- 기본 Portal 지침 합계는 바이트 기준 31.1% 감소했다. 실제 토큰 절감과 새 세션 행동은 별도 평가 대상으로 남긴다.
- [실행·검증 기록](plans/portal-agent-scope.md), [평가 시나리오](evals/portal-agent-scope.md)를 참고한다.

## 2026-09-22: 서버 Headlamp Keycloak 로그인

- 서버 Headlamp는 Keycloak OIDC를 사용하고 최상위 `headlamp-viewers` 그룹에 기존 조회 권한만 부여합니다.
- Kubernetes OIDC의 username·groups prefix는 `headlamp:`이며 사용자별 ID token으로 인증합니다. 공용 viewer ServiceAccount는 제거합니다.
- client secret은 외부 Kubernetes Secret으로 주입하며 로컬 개발 토큰 구성은 유지합니다.
- 제어면 OIDC는 설치 방식과 기존 인증 계약에 맞춰 운영자가 반영합니다. 서버 접속이 없는 환경에서 자동 변경하지 않습니다.
- [실행 계획](plans/headlamp-keycloak.md), [전환 안내](../../deploy/headlamp/OIDC.md).
