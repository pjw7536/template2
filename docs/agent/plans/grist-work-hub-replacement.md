# ExecPlan: APITable에서 Grist OSS Work Hub로 교체

## 목표
- 현재 APITable 기반 Work Hub를 `gristlabs/grist-oss` 기반으로 교체한다.
- Portal `/work-hub`, 소속별 launcher, Observer 설비 동기화, WorkLog→Task 자동 연결, Portal 기준 접근 권한 Outbox, 로컬 demo seed를 유지한다.
- dev/OIDC/prod Compose와 환경·문서를 Grist 계약으로 동기화한다.
- 외부 Grist boot key 화면과 별도 Grist OIDC 로그인을 제거하고 Portal `account.User`를 forward-auth 인증 원본으로 사용한다.

## 현재 상태
- `api.work_hub`의 실행 경로는 Grist document/table, 공식 REST API, Grist Webhook을 사용한다.
- Portal account 변경은 `GristAccessSyncOutbox`와 API container worker를 통해 Grist ACL에 반영된다.
- Work Hub migration은 실제 서버에 적용되지 않았고, Baserow/APITable 전환 이력은 테스트 환경에서만 사용했다.
- dev Grist에는 `DEV_ALPHA`용 Equipment 3건, WorkLog 3건, Task 2건과 Portal mapping이 준비되어 있다.
- dev/OIDC/prod에서 Grist는 직접 노출되지 않고 전용 Nginx forward-auth proxy를 통해 Portal account로 로그인한다.

## 범위
- 수정: `api.work_hub` 모델·migration·services·commands·tests, Work Hub frontend 문구, Compose/env/Nginx/Make, 관련 문서.
- 제거: APITable runtime/overlay와 활성 APITable 실행·환경 계약, 테스트용 Baserow/APITable 모델 및 migration 중간 이력.
- 유지: `/work-hub`, `/api/v1/work-hub/context`, `work-hub` AccessScope, account/observer 공개 계약.
- 제외: APITable record를 Grist로 자동 이관하는 ETL, Grist 소스 fork/vendor, Portal account의 소속·역할 규칙 변경.

## 설계
- 소속별 `GristDocumentScope`가 `doc_id`, `Equipment`, `WorkLog`, `Task` table ID와 launcher URL을 저장한다.
- 실제 서버에 적용되지 않은 Work Hub migration은 최종 Grist schema와 `work-hub` AccessScope를 만드는 단일 초기 migration으로 통합한다.
- 테스트 전환 과정의 Baserow/APITable 호환 모델과 table은 최종 schema에 포함하지 않는다.
- Django `GristClient`는 공식 REST API와 Bearer credential만 사용한다.
- 브라우저 인증은 Portal callback이 로그인된 `account.User` PK를 30초 ticket으로 서명하고 Nginx 내부 검증이 반환한 email만 Grist forward-auth header로 전달한다.
- Portal 미로그인 사용자는 기존 Portal OIDC 로그인으로 보낸 뒤 ticket 발급 경로로 복귀시키며, 발급과 검증 모두 Portal과 `work-hub` app 접근 승인을 검사한다.
- Grist Webhook은 JSON row 배열을 `/api/v1/work-hub/webhooks/grist?doc_id=...&table_id=WorkLog`로 전송하고 static Authorization secret으로 인증한다.
- payload hash와 WorkLog row별 link를 사용해 retry 시 Task 중복 생성을 방지한다.
- Portal 역할은 Grist ACL의 `viewer → viewers`, `member → editors`, `manager → owners`로 투영한다.
- Grist ACL 대상은 소속 역할뿐 아니라 Portal 및 `work-hub` scope의 최종 접근 판정을 모두 통과한 사용자로 제한한다.
- document ACL의 상속 상한을 `null`로 고정해 workspace/org 권한이 Portal desired state를 우회하지 못하게 한다.
- account 변경 signal은 `GristAccessSyncOutbox`를 같은 DB transaction에 적재하고 commit 후 처리하며, Grist 장애는 지수 backoff로 재시도한다.
- Grist의 재시도 불가능한 4xx·응답 계약 오류는 terminal 상태로 보존하고 새 접근 변경이 발생할 때만 다시 활성화한다.
- Webhook receipt와 WorkLog별 Task link를 DB transaction에서 잠근 채 처리해 동시 전달도 Task를 한 번만 생성한다.
- dev/OIDC/prod는 `gristlabs/grist-oss:1.7.13`, `/persist` volume, `GRIST_IN_SERVICE=true`, 공식 forward-auth env 계약을 사용한다.
- Grist container 8484는 host에 직접 노출하지 않고 Nginx가 외부 header를 제거하며 `/boot`를 차단한다.
- server-to-server schema·record·ACL 작업은 Grist 사용자 API key를 계속 사용하며 boot session fallback은 제거한다.

## 실행 단계
- [x] Grist 모델·client·서비스·Webhook 계약을 복원하고 Portal 역할 Outbox를 이식한다.
- [x] 최종 Grist 모델과 AccessScope를 단일 초기 migration으로 구성한다.
- [x] Grist용 configure/audit/sync/seed/worker 명령과 테스트를 교체한다.
- [x] frontend launcher 문구와 demo URL 기대값을 Grist로 교체한다.
- [x] APITable overlay를 제거하고 Compose/env/Nginx/Make를 Grist OSS와 OIDC 설정으로 교체한다.
- [x] architecture/configuration/integration/operations/module 문서를 현재 Grist 계약으로 갱신한다.
- [x] migration, backend tests, frontend tests/build, Compose config, boundary audits를 실행한다.
- [x] dev Grist demo seed와 Portal launcher mapping을 확인한다.
- [x] Portal account 기반 forward-auth ticket 발급·검증 endpoint와 회귀 테스트를 추가한다.
- [x] dev/OIDC/prod Compose·env·Nginx에서 Grist 자체 OIDC 계약을 forward-auth로 교체한다.
- [x] boot session REST fallback을 제거하고 API key 기반 운영 계약과 문서를 갱신한다.
- [x] backend tests, Compose config, boundary/docs audit와 실제 Portal→Grist 로그인을 최종 검증한다.
- [x] 미적용 Baserow/APITable migration과 호환 모델을 제거하고 최종 Grist schema를 단일 초기 migration으로 통합한다.
- [x] 통합 migration의 clean apply, model consistency, 관련 backend 회귀 테스트를 검증한다.
- [x] Portal/Work Hub 최종 앱 권한 회수와 관련 account 변경 signal을 Grist ACL Outbox에 연결한다.
- [x] 상속 ACL 차단과 비재시도 오류 terminal 처리를 구현한다.
- [x] Webhook receipt·Task link 동시 처리 잠금과 회귀 테스트를 추가한다.
- [x] migration consistency, 관련 backend 테스트와 boundary audit를 재검증한다.

## 검증
- `docker compose -f docker-compose.dev.yml config`
- `docker compose -f docker-compose.oidc.yml config`
- `docker compose -f docker-compose.yml config`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.work_hub api.observer api.account --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_grist_demo`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- frontend Work Hub test 및 build

## 위험과 대응
- 위험: 테스트 DB에만 적용된 과거 Work Hub migration 기록이 통합 migration과 충돌할 수 있다.
- 대응: 실제 서버 배포에는 단일 초기 migration만 사용하고, 검증은 격리된 test DB에서 clean apply한다.
- 위험: Grist Webhook은 별도 event ID를 제공하지 않는다.
- 대응: 문서·테이블·정규화 payload의 SHA-256을 event ID로 사용하고 Task link unique constraint를 함께 적용한다.
- 위험: Portal OIDC와 Grist forward-auth proxy의 공개 URL이 환경별로 다르다.
- 대응: Portal 로그인은 기존 auth 계약을 그대로 사용하고 `PORTAL_PUBLIC_URL`, `GRIST_PUBLIC_URL`, `GRIST_HOST`를 환경변수로 주입한다.
- 위험: Grist 장애가 Portal 소속 변경 요청에 영향을 줄 수 있다.
- 대응: 외부 호출은 commit 후 실행하고 실패를 Outbox에 보존해 worker가 재시도한다.
- 위험: 외부 API 호출 동안 DB 잠금을 유지하면 같은 receipt 또는 WorkLog 처리의 대기 시간이 길어질 수 있다.
- 대응: 잠금 범위를 동일 event·WorkLog row로 제한하고 Grist HTTP timeout을 기존 설정대로 적용한다.
- 위험: forward-auth header를 외부에서 주입하거나 ticket return URL 검증이 느슨하면 사용자 위조 또는 open redirect가 발생한다.
- 대응: Grist direct port를 닫고 일반 proxy header를 제거하며, 내부 auth subrequest·30초 Django 서명·Grist public origin/path 검증을 적용한다.
- 위험: boot session 제거 후 자동화용 REST credential이 없으면 seed와 동기화가 실행되지 않는다.
- 대응: Portal 관리자 account로 Grist에 로그인해 발급한 API key를 `GRIST_API_KEY`에 주입하며, secret과 API key를 저장소에 기록하지 않는다.

## 진행 기록
- 2026-08-04: Baserow를 Grist OSS 1.7.13으로 교체하고 Portal 공개 경로는 유지하기로 결정했다.
- 2026-08-04: Grist 공식 API로 workspace/document/table/record/ACL/Webhook을 구성하고 실제 WorkLog→Task 전달을 검증했다.
- 2026-08-04: Baserow container는 제거했지만 `tailwind_baserow_data` volume은 롤백용으로 보존했다.
- 2026-08-04: backend 297개 테스트, Work Hub frontend 테스트·build, Compose 3종과 boundary/UI/docs audit를 통과했다.
- 2026-08-05: 사용자 요청에 따라 현재 APITable 실행 경로를 Grist로 재교체하고, 최신 Portal 역할·Outbox 동기화까지 Grist ACL에 유지하기로 했다.
- 2026-08-05: `work_hub.0005` 적용, Work Hub 16개와 account·observer 286개 테스트, frontend 테스트·build, Compose 3종, boundary/UI/docs audit를 통과했다.
- 2026-08-05: APITable container만 제거하고 volume은 보존했으며 Grist 1.7.13 기동, demo seed 3/3/2건, schema·ACL·worker를 실제 dev 환경에서 확인했다.
- 2026-08-05: Grist OSS에 GristConnect가 포함되지 않음을 실제 image에서 확인해 공식 forward-auth와 Portal 서명 ticket 방식으로 전환했다.
- 2026-08-05: Grist direct port 차단, 외부 header 제거, `/boot` 차단, Portal account email session 생성을 실제 dev proxy에서 확인했다.
- 2026-08-05: Work Hub 21개와 account·observer 포함 307개 테스트, migration/check, Compose 3종, backend boundary·docs·diff 검증을 통과했다.
- 2026-08-05: dev/prod Nginx 문법, header 위조 차단, `/boot` 404, Portal account email 기반 Grist profile과 session cookie를 최종 확인했다.
- 2026-08-10: 실제 서버에는 Work Hub migration이 적용되지 않았음을 확인해 테스트용 Baserow/APITable 이력과 호환 모델을 제거하고 단일 Grist 초기 migration으로 통합하기로 했다.
- 2026-08-10: `makemigrations --check --dry-run`, 격리 test DB의 Work Hub/account/observer 307개 테스트, backend boundary 및 docs audit를 통과했다.
- 2026-08-10: Portal·Work Hub 최종 접근 판정을 Grist ACL 대상에 포함하고 관련 사용자·정책·scope 변경을 Outbox에 연결했다.
- 2026-08-10: document 상속 ACL을 차단하고 비재시도 오류를 terminal로 분리했으며, receipt·Task link 잠금으로 동시 Webhook 중복 Task를 방지했다.
- 2026-08-10: Work Hub/account/observer 313개 테스트, migration consistency, backend boundary, docs audit와 diff 검증을 통과했다.
