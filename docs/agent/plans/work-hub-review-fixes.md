# ExecPlan: Work Hub 재리뷰 발견 사항 수정

## 목표
- 부서 정책으로 승인된 사용자가 Grist ACL batch projection에서 누락되지 않게 한다.
- 신규 document mapping이 저장되면 ACL Outbox를 자동 적재하고 기존 mapping의 `doc_id` 변경을 차단한다.
- `WORK_HUB_ENABLED=0`이면 direct Grist forward-auth도 차단한다.
- 완료된 Webhook receipt를 기본 30일 보존 후 정리한다.

## 현재 상태
- 운영 서버에는 Grist document와 Work Hub migration이 적용되지 않았다.
- batch ACL 경로의 사용자 조회에는 정책 비교용 부서 annotation이 없다.
- mapping 저장은 Outbox를 적재하지 않고 기존 `doc_id`를 덮어쓸 수 있다.
- launcher context만 기능 플래그를 확인하고 forward-auth는 확인하지 않는다.
- 완료 Outbox에는 retention이 있지만 Webhook receipt에는 retention이 없다.

## 범위
- `api.account` batch ACL용 사용자 read model
- `api.work_hub` mapping, 인증, receipt 정리 서비스와 worker
- Work Hub 단일 초기 migration, settings/env, 테스트와 운영 문서
- frontend와 Grist document schema는 변경하지 않는다.

## 설계
- batch 사용자 selector에 PostgreSQL 기준 정규화 부서 annotation을 추가한다.
- mapping 생성·메타데이터 갱신은 같은 transaction에서 현재 document Outbox를 적재한다.
- 이미 저장된 mapping의 `doc_id` 변경은 validation error로 차단해 추적되지 않는 이전 ACL을 만들지 않는다.
- forward-auth 접근 판정의 첫 조건으로 `WORK_HUB_ENABLED`를 적용해 login과 verify를 함께 차단한다.
- worker가 기존 prune 주기마다 보존 기간이 지난 `done` Webhook receipt를 삭제한다.
- 서버 미적용 migration이라는 사용자 확인에 따라 receipt 정리 index를 `0001_initial`에 포함한다.

## 실행 단계
- [x] batch ACL 정책 판정 수정과 회귀 테스트
- [x] mapping Outbox 적재와 `doc_id` 불변성 구현
- [x] forward-auth 기능 플래그 적용과 view 테스트
- [x] Webhook receipt retention과 index 구현
- [x] 설정·문서 갱신
- [x] Docker 테스트, migration check, 경계·Compose·문서 감사 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.work_hub api.account --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:docs`
- dev/OIDC/prod `docker compose ... --profile work-hub config --quiet`
- `git diff --check`

## 위험과 대응
- 위험: mapping 갱신 명령에서 document 교체가 더 이상 암묵적으로 동작하지 않는다.
- 대응: 실제 document가 없는 현재 시점부터 `doc_id`를 불변 식별자로 정하고 메타데이터 갱신만 허용한다.
- 위험: receipt를 너무 빨리 삭제하면 늦은 Webhook 재전송을 다시 처리할 수 있다.
- 대응: 기본 30일을 보존하고 완료 건만 삭제한다.

## 진행 기록
- 2026-08-10: 운영 Grist document가 아직 없다는 사용자 확인을 반영해 이전 document cleanup 대신 `doc_id` 변경 차단을 선택했다.
- 2026-08-10: batch 사용자 read model에 정규화 부서를 포함해 Portal·Work Hub 부서 정책 사용자가 ACL projection에 유지되도록 했다.
- 2026-08-10: mapping 저장 시 ACL Outbox를 적재하고, 기능 플래그 off 상태에서 login과 기발급 ticket을 모두 차단했다.
- 2026-08-10: 완료 Webhook receipt의 기본 30일 retention과 `(status, processed_at)` index를 단일 초기 migration에 반영했다.
- 2026-08-10: Work Hub 39개, Work Hub·Account 267개 테스트와 migration check·SQL render·backend boundary·문서 감사·Compose·compile·diff 검증이 모두 통과했다.

## 재리뷰 후속 단계
- [x] 이메일이 있는 활성 superuser를 모든 document ACL owner로 투영
- [x] 기능 off 상태의 익명 forward-auth를 IdP 호출 전에 차단
- [x] 실패 Webhook receipt를 기본 90일 후 정리
- [x] 회귀 테스트와 설정·문서 갱신
- [x] Docker 테스트, migration check, 경계·Compose·문서 감사 재실행

## 재리뷰 후속 설계
- superuser는 launcher의 전역 manager 계약과 동일하게 모든 활성 document의 `owners` ACL에 포함한다.
- `WORK_HUB_ENABLED=0` 검사는 return URL 검증과 Portal 로그인 시작보다 먼저 수행한다.
- `done` receipt는 30일, 마지막 재시도 이후 `failed` receipt는 90일 보존한다.
- 기존 `(status, processed_at)` index를 함께 사용하므로 schema와 migration은 변경하지 않는다.

## 재리뷰 후속 진행 기록
- 2026-08-10: 이메일이 있는 활성 superuser를 소속 membership과 무관하게 모든 활성 document owner로 포함하고, 생성·상태 변경·삭제 시 전체 ACL Outbox를 적재하도록 했다.
- 2026-08-10: 기능 off 상태의 익명 login 요청을 Portal IdP 호출 전 403으로 차단했다.
- 2026-08-10: 실패 Webhook receipt의 기본 90일 retention을 worker와 설정에 추가하고 기존 index를 재사용했다.
- 2026-08-10: Work Hub 43개, Work Hub·Account 271개 테스트와 migration check·backend boundary·문서 감사·dev/OIDC/prod Compose·compile·diff 검증이 모두 통과했다.

## 최소 수정 후속 목표
- Webhook 인증 정보를 document·table 범위로 제한해 다른 document를 대상으로 재사용할 수 없게 한다.
- 기존 주기를 재사용해 Grist ACL 전체를 정기적으로 원하는 상태와 맞춘다.
- OIDC·운영 Grist가 session secret 없이 시작되지 않게 한다.
- launcher 자동 이동이 브라우저 뒤로 가기 기록을 반복 생성하지 않게 한다.

## 최소 수정 후속 설계
- 기존 `GRIST_WEBHOOK_SECRET`을 마스터 키로 사용하고 HMAC-SHA256으로 document·table 전용 bearer token을 파생한다. DB schema와 migration은 변경하지 않는다.
- worker의 기존 1시간 prune 주기에서 모든 활성 document scope를 직접 동기화한다. 개별 document 실패는 기록하고 나머지는 계속 처리한다.
- OIDC·운영 Compose는 비어 있는 session secret을 허용하지 않는 시작 명령을 사용한다. 개발 Compose의 로컬 기본값은 유지한다.
- 타이머 기반 자동 이동만 `window.location.replace`를 사용하고 수동 버튼은 기존 `assign`을 유지한다.

## 최소 수정 후속 실행 단계
- [x] document 범위 Webhook 인증과 로컬 Webhook 갱신 구현
- [x] 주기적 ACL 전체 정합성 복구 구현
- [x] OIDC·운영 session secret 시작 가드 구현
- [x] launcher 자동 이동 history 처리 구현
- [x] 테스트·문서·Compose 계약 검증

## 최소 수정 후속 위험과 대응
- 위험: 기존 개발 document의 Webhook이 이전 공용 bearer token을 보유할 수 있다.
- 대응: demo seed가 같은 이름의 Webhook도 URL과 인증 정보를 원하는 값으로 갱신한다.
- 위험: 정기 전체 동기화가 문서 수에 비례해 Grist API 호출을 늘린다.
- 대응: 새 짧은 주기를 만들지 않고 기존 기본 1시간 주기를 재사용한다.

## 최소 수정 후속 진행 기록
- 2026-08-10: ROI가 명확한 네 항목만 구현하고 배포 빌드 방식이나 별도 구조 리팩터링은 범위에서 제외했다.
- 2026-08-10: document·table HMAC Webhook 인증, 기존 demo Webhook 보정, 기본 1시간 ACL 전체 복구, 운영 session secret 시작 가드와 자동 이동 history 교체를 반영했다.
- 2026-08-10: Grist 1.7.13 Webhook PATCH 계약을 고정 이미지 구현과 대조했고 Work Hub 48개·Work Hub/Account 275개 테스트, migration·compile·frontend lint/test/build, backend/frontend/UI boundary, 문서, dev/OIDC/prod Compose와 diff 검증이 통과했다.

## 운영 안전 최소 개선 목표
- Work Hub Django Admin을 조회 전용으로 제한해 service 검증과 Outbox 적재 우회를 막는다.
- Grist schema 감사에서 column 존재 여부뿐 아니라 type 계약도 확인한다.
- 완료된 동일 Webhook payload도 멱등 연결 작업을 다시 수행해 사용자가 지운 Task 참조를 복구한다.

## 운영 안전 최소 개선 설계
- 네 Work Hub 모델의 Admin은 상세 조회를 유지하되 추가·수정·삭제 입력을 모두 차단한다.
- `audit_grist_schema`의 기존 필수 column 집합을 기대 type mapping으로 바꾸고 누락과 type 불일치를 함께 실패 처리한다.
- 동일 payload의 `duplicate=true` 응답 계약은 유지하면서 기존 receipt 잠금과 `GristTaskLink`를 재사용해 Task 생성 없이 WorkLog 참조를 다시 기록한다.
- DB schema, migration, 공개 API shape, 외부 설정은 변경하지 않는다.

## 운영 안전 최소 개선 실행 단계
- [x] Admin 조회 전용 정책과 회귀 테스트
- [x] Grist column type 감사와 회귀 테스트
- [x] 동일 Webhook 재처리와 참조 복구 회귀 테스트
- [x] Docker 테스트, migration check, 경계·문서 감사

## 운영 안전 최소 개선 위험과 대응
- 위험: 완료 Webhook 재전송마다 Grist update 호출이 한 번 더 발생할 수 있다.
- 대응: 같은 Task ID를 기록하는 멱등 update로 제한하고 Task 생성은 기존 link와 task key로 차단한다.

## 운영 안전 최소 개선 진행 기록
- 2026-08-10: 네 Work Hub Admin을 조회 전용으로 제한해 mapping 검증과 ACL Outbox 적재 우회를 차단했다.
- 2026-08-10: Grist schema 감사가 필수 column의 누락과 type 불일치를 함께 보고하도록 확장했다.
- 2026-08-10: 완료된 동일 Webhook payload도 기존 Task link를 재사용해 WorkLog 참조를 복구하도록 변경했다.
- 2026-08-10: Work Hub 51개·Work Hub/Account 279개 테스트와 migration check·compile·backend boundary·문서·diff 검증이 모두 통과했다.

## 기능 중단·Task 복구·위젯 안전 후속 목표
- `WORK_HUB_ENABLED=0`이면 Webhook과 ACL worker의 Grist 쓰기도 중단한다.
- Grist에서 Task가 삭제되어 로컬 link가 오래된 경우 같은 `task_key`로 Task를 복구한다.
- Grouped View의 저장 색상 옵션을 제한해 HTML 속성 삽입을 차단한다.

## 기능 중단·Task 복구·위젯 안전 설계
- 비활성 Webhook은 403을 반환하고 service를 호출하지 않는다. worker는 이력 정리를 유지하되 전체 reconciliation과 Outbox 외부 처리를 모두 건너뛴다.
- WorkLog의 Task 참조가 비어 있으면 로컬 row ID를 신뢰하지 않고 원격 `task_key`를 다시 조회하며, 없으면 새 Task를 생성해 link를 갱신한다.
- 저장 색상은 `#RRGGBB`만 허용하고 색상은 `innerHTML` 문자열이 아니라 DOM style property로 적용한다.
- DB schema, migration, 공개 Webhook 응답 shape와 환경변수 계약은 변경하지 않는다.

## 기능 중단·Task 복구·위젯 안전 실행 단계
- [x] 비활성 Webhook·worker 회귀 테스트와 쓰기 차단
- [x] 삭제된 원격 Task 복구 테스트와 service 수정
- [x] Grouped View 색상 정규화와 DOM 안전 적용
- [x] Docker 테스트, migration·경계·문서·Compose 검증

## 기능 중단·Task 복구·위젯 안전 위험과 대응
- 위험: 기존 로컬 Task link가 있을 때도 원격 `task_key` 조회가 한 번 추가된다.
- 대응: WorkLog 참조가 비어 있어 복구가 필요한 Webhook에만 조회하며 정상 참조가 있는 이벤트는 기존처럼 즉시 종료한다.

## 기능 중단·Task 복구·위젯 안전 진행 기록
- 2026-08-10: 기능 off 상태의 Webhook을 service 호출 전에 403으로 차단하고, worker의 이력 정리는 유지하면서 Grist ACL reconciliation과 Outbox 처리를 중단하도록 했다.
- 2026-08-10: WorkLog 참조가 비어 있으면 원격 `task_key`를 재확인하고 삭제된 Task를 같은 key로 다시 생성해 로컬 link를 갱신하도록 했다.
- 2026-08-10: Grouped View 저장 색상을 `#RRGGBB`로 제한하고 `innerHTML`의 style 속성 대신 DOM style property로 적용했다.
- 2026-08-10: Work Hub 54개·Work Hub/Account 282개 테스트와 migration check·compile·backend boundary·문서·widget manifest/script·dev/OIDC/prod Compose·diff 검증이 모두 통과했다.

## 운영 주입·세션 종료·Task 조회 후속 목표
- OIDC·운영 Compose의 외부 Work Hub 설정과 secret을 API·worker에 실제 주입한다.
- Portal 로그아웃이 Grist 세션을 먼저 제거한 뒤 기존 IdP 로그아웃으로 이어지게 한다.
- `WORK_HUB_ENABLED=0`이면 기존 Grist 세션이 있어도 본문과 widget 접근을 차단한다.
- Webhook의 `task_key` 확인을 Task 전체 조회가 아닌 Grist 서버 filter 조회로 바꾼다.

## 운영 주입·세션 종료·Task 조회 설계
- API와 worker가 사용하는 Work Hub 설정을 Compose `environment`에 명시해 shell·secret manager 주입이 tracked env 기본값을 덮어쓰게 한다.
- Portal의 첫 로그아웃 요청은 Grist `/logout`으로 보내고, Grist가 `/auth/logout?grist_cleared=1`로 돌아오면 기존 IdP 로그아웃 URL을 사용한다.
- Nginx template에 주입된 기능 플래그로 일반 Grist·widget 요청을 503 처리하고 `/logout`은 세션 정리를 위해 계속 proxy한다.
- Grist record API의 `filter` query를 사용해 `task_key` 일치 record만 요청한다.
- DB schema와 migration은 변경하지 않는다.

## 운영 주입·세션 종료·Task 조회 실행 단계
- [x] Compose 외부 주입과 로그아웃 연쇄 회귀 테스트
- [x] API·worker·Nginx 환경 계약과 기능 OFF 차단 구현
- [x] 서버 filter 기반 Task 조회와 회귀 테스트
- [x] Docker 테스트, migration·경계·문서·Compose·Nginx 검증

## 운영 주입·세션 종료·Task 조회 위험과 대응
- 위험: Grist logout과 Portal logout이 서로 재호출해 redirect loop가 생길 수 있다.
- 대응: Nginx가 Portal로 돌아올 때 `grist_cleared=1` marker를 붙이고 이 요청에서만 IdP logout으로 진행한다.
- 위험: 기능 OFF 차단이 Grist 세션 제거까지 막을 수 있다.
- 대응: `/logout`과 후속 `/auth/logout` 경로는 기능 플래그와 무관하게 유지한다.

## 운영 주입·세션 종료·Task 조회 진행 기록
- 2026-08-10: dev·OIDC·prod의 API와 worker가 외부 Work Hub 설정을 명시적으로 받고, dev·OIDC web과 Nginx도 기능 플래그와 공개 URL을 같은 계약으로 받도록 했다.
- 2026-08-10: Portal 로그아웃을 Grist 세션 종료 후 기존 IdP 로그아웃으로 연결하고, 기능 OFF 상태에서는 Grist 본문과 widget을 503으로 차단하되 `/logout`은 유지했다.
- 2026-08-10: Grist record 조회에 서버 `filter` query를 추가해 `task_key` 확인 시 Task 전체 table을 내려받지 않도록 했다.
- 2026-08-10: Work Hub·Account·Auth 316개 Docker 테스트, migration check, Python compile, backend·frontend boundary, UI·문서 audit, frontend lint·Work Hub Vitest, dev·OIDC·prod Compose, Nginx syntax·기능 OFF 응답 분기와 diff 검증이 모두 통과했다.

## 선택 실행·세션 정리·환경 정합성 목표
- 기본 `make dev`에서는 선택 profile인 Grist 없이도 Portal 메뉴와 로그아웃이 정상 동작하게 한다.
- Work Hub 본문을 끈 뒤에도 Grist가 살아 있는 정리 기간에는 Portal 로그아웃이 기존 Grist session을 제거하게 한다.
- API·worker·Grist가 외부에서 주입한 Work Hub timeout·보존 기간·조직 설정을 동일하게 사용하게 한다.

## 선택 실행·세션 정리·환경 정합성 설계
- dev Compose의 Work Hub 기본값은 off로 바꾸고 Work Hub Make target만 세 기능 플래그를 명시적으로 on으로 주입해 API·Web·Nginx·worker·Grist를 함께 실행한다.
- `GRIST_LOGOUT_ENABLED`를 본문 기능 플래그와 분리한다. `WORK_HUB_ENABLED` 또는 세션 정리 플래그가 켜진 첫 로그아웃만 Grist를 거치며 marker 이후에는 기존 IdP로 진행한다.
- Django가 읽는 Work Hub timeout·보존 기간·ticket 설정을 API Compose에 명시하고 worker가 사용하는 subset도 명시한다. `GRIST_ORG`는 Grist의 `GRIST_SINGLE_ORG`에도 같은 값으로 주입한다.
- DB schema, migration, 공개 API 응답 shape와 Grist upstream 소스는 변경하지 않는다.

## 선택 실행·세션 정리·환경 정합성 실행 단계
- [x] 비활성 본문·활성 세션 정리 로그아웃 회귀 테스트
- [x] dev 기본값과 Work Hub Make target 전환 구현
- [x] dev·OIDC·prod API·worker·Grist 환경 전달 정합화
- [x] 인증·Compose·문서·경계 전체 검증

## 선택 실행·세션 정리·환경 정합성 위험과 대응
- 위험: 세션 정리 플래그가 켜진 상태에서 Grist를 먼저 중지하면 Portal 로그아웃이 Grist 장애의 영향을 받는다.
- 대응: 운영 절차를 `본문 OFF → 세션 정리 유지 → Grist 중지 → 세션 정리 OFF` 순서로 명시한다.
- 위험: dev 기본값을 off로 바꾸면 기존 Work Hub 전용 명령이 API·Web·Nginx를 다시 켜지 못할 수 있다.
- 대응: Work Hub Make target이 관련 app service까지 같은 환경값으로 `up`하고 seed의 API 재생성도 같은 Compose wrapper를 사용한다.

## 선택 실행·세션 정리·환경 정합성 진행 기록
- 2026-08-10: 비활성 Work Hub에서도 명시적 세션 정리 플래그가 Grist logout을 수행하고, 두 플래그가 모두 꺼지면 Grist를 건너뛰는 회귀 테스트를 추가했다.
- 2026-08-10: 기본 dev는 Work Hub를 숨기고, Work Hub Make target만 API·Web·Nginx·worker·Grist를 동일한 활성 계약으로 재생성하도록 정리했다.
- 2026-08-10: dev·OIDC·prod Compose의 timeout·보존 기간·조직 환경 전달을 맞추고 API·Account·Auth 318개 테스트, migration check, Django check, compile, 경계·UI·문서 audit, frontend lint·Vitest, Compose config와 diff 검증을 통과했다.

## 통합 dev 실행 목표
- `make dev` 한 번으로 Portal app stack, Work Hub worker와 Grist를 모두 실행하고 Navbar 메뉴를 활성화한다.
- raw Compose와 `make dev-app-up`의 비활성 기본값은 유지해 Work Hub 없이 Portal만 점검할 수 있게 한다.

## 통합 dev 실행 설계
- `dev`와 `dev-up`을 기존 `dev-work-hub-up` target에 연결하고 `dev-down`도 대칭적으로 전체 stack을 중지한다.
- DB schema, API·권한 계약, Grist upstream 소스와 OIDC·prod 실행 계약은 변경하지 않는다.

## 통합 dev 실행 단계
- [x] Make 통합 실행·중지 alias 변경
- [x] README·설정·운영·Work Hub 문서 동기화
- [x] Make dry-run·Compose·문서·diff 검증

## 통합 dev 실행 위험과 대응
- 위험: Work Hub 없이 Portal만 실행하려는 개발 흐름이 사라질 수 있다.
- 대응: 명시적 `make dev-app-up`과 raw Compose의 기능 플래그 기본값은 계속 off로 둔다.

## 통합 dev 실행 진행 기록
- 2026-08-10: `make dev`와 `make dev-up/down`을 Work Hub 통합 실행·중지 target에 연결하고 README·설정·운영·모듈 문서를 동기화했다.
- 2026-08-10: Make dry-run에서 세 기능 플래그와 Portal·Grist·worker service 포함을 확인하고 dev Compose config, 문서 audit와 diff 검증을 통과했다.

## 최종 ROI 재리뷰 수정 목표
- 최초 Grist 로그인에서도 launcher가 지정한 document 경로를 유지한다.
- OIDC·prod에서 Work Hub profile service를 빠뜨리지 않는 명시적 실행 진입점을 제공한다.
- 초기 migration 역적용이 기존 `work-hub` 접근 scope를 삭제하지 않게 한다.

## 최종 ROI 재리뷰 수정 설계
- Grist의 `next` 경로는 같은 Grist origin 내부의 절대 경로만 허용하고 Portal ticket payload와 최종 login URL에 함께 넣어 변조를 차단한다.
- 기본 OIDC·prod app 실행은 유지하고, 기능 플래그와 secret이 준비된 배포에서만 선택하는 Work Hub 전용 Make target을 추가한다.
- migration의 reverse data 작업은 no-op으로 바꿔 migration 적용 전에 존재했을 수 있는 접근 scope와 연관 권한 데이터를 보존한다.
- 이론적 edge case와 공개 API·DB schema 변경은 범위에서 제외한다.

## 최종 ROI 재리뷰 수정 실행 단계
- [x] signed `next` 전달·검증과 회귀 테스트
- [x] OIDC·prod Work Hub 실행 target과 운영 문서 동기화
- [x] 비파괴 migration reverse 적용
- [x] Docker 테스트, migration·경계·Compose·Nginx 검증

## 최종 ROI 재리뷰 수정 위험과 대응
- 위험: `next`가 별도 redirect 대상으로 악용될 수 있다.
- 대응: scheme·host·query·fragment·역슬래시가 없는 `/` 시작 Grist 내부 경로만 허용하고 ticket에 결합한다.
- 위험: 선택 profile을 기본 실행에 강제하면 아직 secret이 준비되지 않은 배포가 실패할 수 있다.
- 대응: OIDC·prod 기본 target은 바꾸지 않고 명시적 Work Hub target만 추가한다.

## 최종 ROI 재리뷰 수정 진행 기록
- 2026-08-10: Grist `next`를 내부 경로로 제한하고 ticket에 결합해 최초 Portal 로그인 뒤에도 launcher document로 복귀하며 경로 변조는 거부하게 했다.
- 2026-08-10: `oidc-work-hub-up`과 `prod-work-hub-up`이 Portal app, Grist와 접근 동기화 worker를 같은 profile 실행에 포함하게 했다.
- 2026-08-10: 초기 migration의 reverse data 작업을 no-op으로 바꿔 기존 접근 scope와 연관 권한을 보존하게 했다.
- 2026-08-10: Work Hub·Account·Auth 320개와 최종 View 14개 Docker 테스트, migration check, Django check, compile, 경계·UI·문서 감사, dev·OIDC·prod Compose, dev·prod Nginx 구문과 실제 redirect, diff 검증이 통과했다.

## Portal hostname·Task key 계약 수정 목표
- OIDC와 운영 Portal Nginx virtual host가 각 환경의 공개 URL hostname과 일치하게 한다.
- 허용된 최대 Grist document·table·row 식별자로 생성한 `task_key`를 DB가 잘림 없이 저장하게 한다.

## Portal hostname·Task key 계약 수정 설계
- Portal hostname을 `PORTAL_HOST` 환경변수로 분리하고 OIDC·운영별 기본값을 env와 Compose에서 명시해 Nginx template에 주입한다.
- `PORTAL_PUBLIC_URL`은 redirect origin, `PORTAL_HOST`는 Nginx `server_name`이라는 역할을 문서화하고 두 값의 hostname을 일치시키는 계약으로 둔다.
- 아직 적용 전인 Work Hub 초기 migration과 model의 `GristTaskLink.task_key` 길이를 함께 255자로 확장한다.
- 최대 허용 doc/table ID와 bigint row ID로 Webhook을 처리하는 회귀 테스트를 추가한다.

## Portal hostname·Task key 계약 수정 실행 단계
- [x] ExecPlan과 환경 계약 문서 갱신
- [x] OIDC·운영 Portal hostname 주입과 Nginx virtual host 수정
- [x] `task_key` model·초기 migration·회귀 테스트 수정
- [x] Docker 테스트, migration·경계·문서·Compose·diff 검증

## Portal hostname·Task key 계약 수정 위험과 대응
- 위험: `PORTAL_HOST`와 `PORTAL_PUBLIC_URL`의 hostname이 다르면 redirect와 TLS virtual host가 다시 어긋날 수 있다.
- 대응: 환경별 env 기본값을 나란히 관리하고 Compose render 결과에서 두 값을 함께 검증한다.
- 위험: 이미 적용된 초기 migration을 수정하면 배포 DB schema와 migration state가 달라질 수 있다.
- 대응: 현재 Work Hub 초기 migration이 아직 적용 전이라는 저장소 전제에서만 초기 migration을 함께 고치며 migration drift 검사를 수행한다.

## Portal hostname·Task key 계약 수정 진행 기록
- 2026-08-11: 사용자 지정 리뷰 항목 2·5만 수정 대상으로 확정하고 OIDC/운영 hostname과 최대 `task_key` 저장 계약을 ExecPlan에 추가했다.
- 2026-08-11: `PORTAL_HOST`를 OIDC `stg.plane.samsungds.net`, 운영 `plane.samsungds.net`으로 주입하고 Portal HTTP·HTTPS virtual host를 환경변수 기반으로 변경했다.
- 2026-08-11: `GristTaskLink.task_key`를 255자로 확장하고 227자 최대 식별자 조합의 Webhook 저장 회귀 테스트를 추가했다.
- 2026-08-11: Work Hub 59개 Docker 테스트, migration drift, Django check·compile, backend boundary·문서 audit, OIDC·prod Compose와 hostname 계약, diff 검증이 모두 통과했다.

## 운영 번들·Webhook 트랜잭션 ROI 수정 목표
- `make prod-work-hub-up`이 Work Hub 메뉴가 활성화된 운영 Web bundle을 항상 사용하게 한다.
- Grist Webhook의 느린 외부 HTTP 호출 동안 DB transaction과 row lock을 유지하지 않는다.
- 동일 event와 동일 WorkLog row의 동시 전달에서도 기존 Task 멱등성을 유지한다.

## 운영 번들·Webhook 트랜잭션 ROI 수정 설계
- 운영 Work Hub target이 활성화된 `VITE_WORK_HUB_ENABLED` build arg로 Web image를 먼저 빌드한 뒤 app과 profile service를 기동한다.
- receipt와 Task link는 짧은 transaction에서 처리 권한만 선점하고, 원격 Grist 조회·생성·수정은 transaction 밖에서 수행한다.
- `processed_at`과 `GristTaskLink.updated_at`을 처리 임대 시각으로 활용해 동시 요청은 짧게 대기하고, 중단된 처리는 일정 시간 뒤 회수한다.
- 공개 API 응답, DB schema, migration과 Grist upstream 계약은 변경하지 않는다.

## 운영 번들·Webhook 트랜잭션 ROI 수정 실행 단계
- [x] 운영 Work Hub build·up target 결합과 운영 문서 동기화
- [x] Webhook receipt·Task link의 짧은 처리 임대 구현
- [x] transaction 경계·동시 처리 회귀 테스트
- [x] Docker 테스트, migration·경계·문서·Make dry-run 검증

## 운영 번들·Webhook 트랜잭션 ROI 수정 위험과 대응
- 위험: 외부 호출을 transaction 밖으로 옮기면 같은 row의 동시 요청이 Task를 중복 생성할 수 있다.
- 대응: Task link의 nullable row ID와 갱신 시각을 처리 임대로 사용하고 완료 전 요청은 DB lock 없이 대기한다.
- 위험: 처리 프로세스가 중단되면 receipt나 Task link가 처리 중 상태에 남을 수 있다.
- 대응: Grist client의 요청 상한보다 긴 2분 임대가 지나면 다음 요청이 처리를 회수한다.

## 운영 번들·Webhook 트랜잭션 ROI 수정 진행 기록
- 2026-08-11: `prod-work-hub-up`이 활성 플래그로 운영 Web image를 먼저 빌드하도록 전용 build target을 연결하고 운영 문서를 동기화했다.
- 2026-08-11: Webhook receipt와 Task link를 2분 처리 임대로 선점한 뒤 Grist HTTP 호출을 transaction 밖에서 실행하고, 실패 시 이전 link 상태를 복원하도록 했다.
- 2026-08-11: Work Hub 61개 Docker 테스트, migration drift, Django check·compile, backend boundary·문서 audit, Make dry-run과 활성 prod Compose 계약, diff 검증이 모두 통과했다.

## 운영 owner·배포·비활성화 안전성 수정 목표
- `GRIST_ADMIN_EMAIL`을 Portal 일반 역할과 무관하게 모든 Work Hub document의 명시적 owner로 유지한다.
- 운영 Work Hub 기동 전 같은 release의 API·Web image를 build하고 DB migration을 실행한다.
- OIDC·운영에서 이전 활성 worker가 남지 않는 2단계 비활성화·종료 명령을 제공한다.

## 운영 owner·배포·비활성화 안전성 수정 설계
- 설정된 Grist 관리자를 desired ACL에 `owners`로 먼저 합쳐 누락 시 추가하고 일반 Portal 역할로 강등하지 않는다.
- `prod-work-hub-up`은 API·Web build, API image one-off `migrate --noinput`, 서비스 기동을 순차 실행한다.
- `oidc/prod-work-hub-disable`은 본문·widget·worker 쓰기를 막으면서 Grist logout만 유지하고, 유예 후 `oidc/prod-work-hub-down`이 worker·initializer·Grist를 제거한 뒤 logout도 끄도록 한다.
- DB schema, 공개 API, frontend route와 제외하기로 한 secret·shared-network 항목은 변경하지 않는다.

## 운영 owner·배포·비활성화 안전성 수정 실행 단계
- [x] break-glass owner desired ACL과 회귀 테스트 추가
- [x] 운영 API·Web build·migration·up 순서 구현
- [x] OIDC·운영 2단계 비활성화 target과 runbook 동기화
- [x] Docker 테스트, migration·Django·Compose·Make·경계·문서·diff 검증

## 운영 owner·배포·비활성화 안전성 수정 위험과 대응
- 위험: migration 실패 후 신규 서비스가 기동하면 코드와 DB schema가 어긋날 수 있다.
- 대응: Make 선행 조건으로 migration을 연결해 실패 시 `up`에 진입하지 않게 한다.
- 위험: 세션 정리 전 Grist를 중지하면 기존 Grist session이 남을 수 있다.
- 대응: `disable`과 `down`을 별도 target으로 두고 운영 문서에 유예 순서를 명시한다.

## 운영 owner·배포·비활성화 안전성 수정 진행 기록
- 2026-08-11: ROI 재리뷰에서 확인한 owner 강등, 운영 migration 누락, 잔존 worker 위험을 수정 범위로 확정했다.
- 2026-08-11: 설정 owner를 desired ACL의 `owners`로 강제하고 강등 방지·누락 추가 회귀 테스트를 보강했다.
- 2026-08-11: prod API·Web build→migration→up 순서와 OIDC·prod 2단계 disable→down target을 추가하고 운영·설정 문서와 decision log를 동기화했다.
- 2026-08-11: Work Hub 63개 Docker 테스트, migration drift, Django check, dev·OIDC·prod Compose, Make dry-run, backend boundary·문서 audit, diff 검증을 통과했다.

## Webhook queue·운영 중단 순서 후속 목표
- Webhook HTTP 요청은 인증·검증·DB 적재만 수행하고 `202 Accepted`로 빠르게 종료한다.
- 전용 worker가 저장된 Webhook을 임대해 처리하고, 중복·실패·중단 작업을 polling 없이 재시도한다.
- 운영 migration 전에 구버전 API와 Work Hub worker를 중지한다.
- 긴급 비활성화는 Web build보다 API·Nginx·worker 쓰기 차단을 먼저 수행한다.
- Grist API key bootstrap의 모든 HTTP 요청에 연결·전체 응답 시간 상한을 둔다.

## Webhook queue·운영 중단 순서 후속 설계
- `GristWebhookReceipt`에 검증된 payload와 `available_at`을 저장하고 `received/failed` 작업을 기존 worker가 처리한다. `processing` 임대가 만료된 작업도 worker가 회수한다.
- 동일 payload 재전송은 기존 receipt를 재사용하며 처리 중이면 즉시 중복 접수로 끝낸다. 완료·실패 상태면 다시 `received`로 전환해 기존 Task 참조 복구 계약을 유지한다.
- 같은 WorkLog row의 다른 event가 이미 처리 중이면 DB를 반복 조회하지 않고 짧은 backoff 뒤 receipt 자체를 재시도한다.
- 초기 migration은 수정하지 않고 payload·재시도 필드와 준비 작업 index를 후속 migration으로 추가한다.
- 운영 migration target은 build 뒤 기존 API·worker를 멈추고 one-off migration을 실행한다. 실패하면 신버전 서비스를 기동하지 않는다.
- 운영 disable target은 API·Nginx·worker를 off 설정으로 먼저 재생성한 뒤 비활성 Web bundle을 build·교체한다.
- bootstrap `curl` wrapper에 고정된 연결·전체 응답 timeout을 적용해 initializer와 worker 의존 대기를 유한하게 만든다.

## Webhook queue·운영 중단 순서 후속 실행 단계
- [x] Webhook receipt schema·enqueue·worker batch 구현
- [x] HTTP 202·중복·재시도·임대 회수 회귀 테스트
- [x] 운영 migration·disable 순서와 bootstrap timeout 수정
- [x] API·운영 문서와 decision log 동기화
- [x] Docker 테스트, migration·경계·문서·Compose·Make·diff 검증

## Webhook queue·운영 중단 순서 후속 위험과 대응
- 위험: Webhook 원문을 비동기 처리를 위해 DB에 보관하게 된다.
- 대응: 검증된 최대 200개 record payload만 receipt에 저장하고 기존 완료 30일·실패 90일 정리 정책을 그대로 적용한다.
- 위험: HTTP 202 이후 외부 처리 실패를 Grist가 알 수 없다.
- 대응: worker가 지수 backoff로 재시도하고 처리 이력을 Admin에서 조회할 수 있게 유지한다.
- 위험: 운영 migration 실패 시 API가 중지된 상태로 남는다.
- 대응: DB와 구버전 코드가 섞여 실행되는 것보다 안전한 fail-closed로 두고, 오류 확인 후 명시적으로 이전 release를 복구하도록 문서화한다.

## Webhook queue·운영 중단 순서 후속 진행 기록
- 2026-08-11: ROI 재리뷰의 Webhook 처리 슬롯 고갈, live migration, 늦은 비활성화와 bootstrap 무한 대기 문제를 구현 범위로 확정했다.
- 2026-08-11: Webhook HTTP를 `202 Accepted` queue 적재로 바꾸고 receipt payload·준비 시각·terminal 상태와 worker 임대·backoff 처리를 후속 migration으로 추가했다.
- 2026-08-11: 같은 event와 WorkLog row의 진행 중 작업은 DB polling 없이 즉시 중복 접수 또는 receipt 재시도로 전환하고, row ID 입력 검증을 HTTP 경계에 추가했다.
- 2026-08-11: 운영 migration 전 API·worker 중지, Web build 전 긴급 기능 OFF, bootstrap curl의 연결 3초·전체 15초 timeout을 반영했다.
- 2026-08-11: Work Hub 67개 Docker 테스트, migration drift, Django check·compile, backend boundary·문서 audit, dev/OIDC/prod Compose, Make dry-run, shell·diff 검증이 모두 통과했다.

## 최종 무의미 변경 정리 목표
- API의 group별 `launch_url` 계약으로 대체된 미사용 frontend Grist URL 환경값을 제거한다.
- 실제 호출자가 없는 selector와 중복 서식을 제거하되 동작·공개 API·DB schema는 변경하지 않는다.

## 최종 무의미 변경 정리 실행 단계
- [x] `VITE_GRIST_URL` build·Compose·env 전달 제거
- [x] 미사용 selector 3개와 중복 빈 줄 제거
- [x] Docker 테스트, migration·경계·Compose·frontend 검증

## 최종 무의미 변경 정리 위험과 대응
- 위험: launcher가 frontend 환경 URL에 의존하면 제거 후 이동이 깨질 수 있다.
- 대응: frontend가 API context의 `groups[].launch_url`만 읽는 것을 정적 검색과 테스트로 확인한다.

## 최종 무의미 변경 정리 진행 기록
- 2026-08-11: 호출되지 않는 account 역할 집계 selector와 Work Hub receipt·Task link selector를 제거했다.
- 2026-08-11: API가 반환하는 `groups[].launch_url`과 중복되며 frontend에서 읽지 않는 `VITE_GRIST_URL` 전달을 Dockerfile·Compose·env에서 제거했다.
- 2026-08-11: Work Hub·Account 295개 Docker 테스트, migration drift, Django check·compile, 전체 agent audit, dev·OIDC·prod Compose, frontend lint·Vitest·production build와 diff 검증이 통과했다.

## 반복 수정 잔재 심층 정리 목표
- 비동기 Webhook queue 전환 뒤 운영 서비스에 남은 테스트·수동 즉시 처리 경로를 제거한다.
- Work Hub worker가 읽지 않으면서 `env_file`과 중복되던 명시적 환경 매핑과 Compose에서 항상 덮어쓰는 공통 Grist 값을 제거한다.
- 공개 HTTP/API, DB schema, 인증·권한 계약과 승인된 secret·shared network 설정은 변경하지 않는다.

## 반복 수정 잔재 심층 정리 실행 단계
- [x] Webhook 동기 처리 wrapper와 wrapper 전용 receipt claim 함수 제거
- [x] 테스트 helper를 실제 worker claim 경로로 전환
- [x] 미사용 worker 중복 환경 매핑과 무효 공통 Grist 값 제거
- [x] Docker 테스트, 전체 agent audit, Compose·frontend·shell·diff 검증

## 반복 수정 잔재 심층 정리 위험과 대응
- 위험: 동기 처리 helper 제거가 Webhook 멱등성·동시성 테스트 의도를 약화할 수 있다.
- 대응: 테스트 전용 helper가 queue 적재 후 실제 worker의 next-receipt claim과 처리 함수를 그대로 사용하게 한다.
- 위험: worker의 중복 환경 매핑 제거가 간접 설정 의존성을 누락할 수 있다.
- 대응: worker command와 transitive service의 settings 참조를 정적 추적하고 dev·OIDC·prod Compose 결과를 재검증한다.

## 반복 수정 잔재 심층 정리 진행 기록
- 2026-08-11: 비동기 queue 도입 뒤 테스트·수동 용도로만 남아 있던 `process_grist_webhook`과 전용 event claim 경로를 운영 서비스·파사드에서 제거했다.
- 2026-08-11: 테스트 helper는 별도 운영 경로를 만들지 않고 worker가 사용하는 next-receipt claim과 처리 함수를 직접 재사용하도록 전환했다.
- 2026-08-11: worker가 읽지 않으면서 공통 `env_file`과 중복되던 `GRIST_LOGOUT_ENABLED`·`GRIST_ORG` 명시 매핑과, 세 Compose에서 항상 덮어쓰던 공통 `GRIST_SINGLE_ORG`를 제거했다.
- 2026-08-11: Work Hub 67개·Work Hub/Account 295개 Docker 테스트, migration drift·Django check·compile, 전체 agent audit, dev·OIDC·prod Compose, frontend lint·Vitest·production build, widget·shell·Make dry-run·diff 검증이 모두 통과했다.
