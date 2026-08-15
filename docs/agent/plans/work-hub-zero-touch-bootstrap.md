# ExecPlan: Work Hub Grist 무입력 초기화

## 목표
- 새 `grist_data` volume으로 시작하는 OIDC(stage)와 운영(prod) 서버가 별도 secret 입력 없이 Work Hub를 기동한다.
- Grist API key는 첫 기동 시 관리자 계정에 공식 API로 발급하고 API·worker가 공유 파일에서 읽는다.
- session, Webhook, forward-auth ticket secret과 환경별 host를 tracked env에 고정하되 외부 환경 변수로 재정의할 수 있게 한다.

## 현재 상태
- `GRIST_API_KEY`는 Grist 사용자와 `home.sqlite3`에 연결되므로 새 volume에서 기존 문자열을 복사해도 인증되지 않는다.
- OIDC/prod Compose는 `GRIST_SESSION_SECRET`과 API·Webhook·ticket secret을 외부 주입하도록 비워 둔다.
- 확정된 관리자 email은 `jw0509.park@samsung.com`이다.
- Portal origin은 stage `https://stg.plane.samsungds.net`, prod `https://plane.samsungds.net`이다.

## 범위
- Grist 공식 profile API를 이용하는 API key 초기화 script와 공유 key 파일
- Django Grist client의 환경 변수 우선, key 파일 차선 로딩
- OIDC/prod 환경별 Work Hub env, Compose include, API·worker·Grist·Nginx wiring
- Makefile 기동 플래그와 설정·운영 문서
- DB schema, migration, HTTP API contract, dev dummy 로그인 계약은 변경하지 않는다.

## 설계
- Grist host는 stage `worklog.stg.plane.samsungds.net`, prod `worklog.plane.samsungds.net`으로 파생한다.
- widget host는 각 Grist host에 `widgets.` 접두사를 붙이고 Portal origin은 기존 stage/prod origin을 사용한다.
- `grist-api-key-init` one-shot service가 내부 forward-auth로 관리자 session을 만들고 `/api/profile/apikey`에서 기존 key를 읽거나 새 key를 발급한다.
- 발급 key는 `${WORK_HUB_SECRET_HOST_PATH:-../data/work_hub_secrets}/grist_api_key`에 원자적으로 기록한다.
- API와 worker는 `GRIST_API_KEY`가 있으면 우선 사용하고, 비어 있으면 `GRIST_API_KEY_FILE`을 실행 시점에 읽는다.
- stage/prod Compose include는 환경별 tracked env를 interpolation 기본값으로 사용하며 host process env가 이를 재정의할 수 있다.
- OIDC/prod 전용 Work Hub target만 기능 플래그를 켜고 일반 app target은 기존 비활성 기본값을 유지한다.

## 실행 단계
- [x] Grist API key 초기화 script와 Django key-file fallback 구현
- [x] OIDC/prod 환경별 tracked Work Hub env와 Compose wiring 추가
- [x] Work Hub 기동 target과 운영 문서 동기화
- [x] fresh volume 초기화, 인증, 테스트와 정적 감사를 검증

## 검증
- 격리된 새 Grist volume에서 bootstrap script를 실행하고 key 파일 Bearer 인증을 확인한다.
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.work_hub --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `bash scripts/agent/check_backend_boundaries.py`
- `bash scripts/agent/check_docs_inventory.sh`
- dev/OIDC/prod `docker compose ... config --quiet`
- `git diff --check HEAD`

## 위험과 대응
- 위험: bootstrap 완료 전에 worker가 key를 읽을 수 있다.
- 대응: worker가 `grist-api-key-init`의 성공 완료를 기다리도록 Compose dependency를 둔다.
- 위험: key 파일은 남았지만 Grist volume이 교체될 수 있다.
- 대응: bootstrap이 매 실행마다 현재 관리자 API key를 조회하거나 재발급한 뒤 파일을 덮어쓴다.
- 위험: stage/prod DNS 또는 인증서 SAN이 파생 host와 다를 수 있다.
- 대응: 환경별 tracked env는 즉시 사용할 기본값이며 host environment override 우선순위를 유지한다.

## 진행 기록
- 2026-08-10: fresh volume, OIDC·prod 모두, 관리자 email과 Portal origin을 사용자 답변으로 확정했다.
- 2026-08-10: 기존 API key 복사 대신 Grist 공식 API 발급과 공유 파일 fallback을 사용하기로 결정했다.
- 2026-08-10: stage/prod별 host와 session/Webhook/ticket key를 tracked Work Hub env에 추가하고 Compose include 기본값으로 연결했다.
- 2026-08-10: 새 Grist 1.7.13 volume에서 API key 발급, workspace API 인증과 재실행 멱등성을 확인했다.
- 2026-08-10: Work Hub 테스트 58개, migration·Django check, backend boundary·문서·Compose 감사와 diff 검사가 통과했다.
