# ExecPlan: Grist 원격 서버 분리 배포

## 목표
- stash의 Grist Work Hub 코드를 복원한다.
- `10.172.117.91`에서 Grist, 전용 Nginx, widget, API key initializer를 독립 실행한다.
- 기존 Portal 서버는 Django API, Account DB, Web과 Work Hub worker를 유지하고 원격 Grist API를 호출한다.
- 로컬 개발용 단일 서버 Compose 흐름은 계속 실행 가능하게 유지한다.

## 현재 상태
- Grist 변경 110개 경로는 워크트리에 복원했고 `stash@{0}`은 복구용으로 유지한다.
- 운영 Compose는 Portal worker가 원격 Grist REST API를 사용하고, 새 서버는 독립 Compose project를 사용하도록 분리했다.
- 신규 Grist 서버 주소는 `10.172.117.91`이다.
- 기존 워크트리에는 Assistant/Observer 관련 사용자 변경이 있으므로 보존해야 한다.

## 범위
- Grist stash 복원과 원격 서버용 Compose/Nginx/env/Make target을 추가한다.
- OIDC/prod Portal Compose에서 Grist runtime을 분리하고 worker의 원격 API 계약을 맞춘다.
- 로컬 `docker-compose.dev.yml`의 통합 Grist 실행은 유지한다.
- Account의 역할 계산, Work Hub DB schema와 업무 규칙은 변경하지 않는다.
- 실제 원격 서버 접속, DNS, 방화벽, 인증서 배포는 코드 검증 이후 별도 운영 단계로 둔다.

## 설계
- 신규 서버: Grist OSS, Grist API key initializer, Grist 전용 Nginx와 widget proxy, `grist_data` volume을 소유한다.
- 기존 서버: Portal API와 worker가 `GRIST_API_URL`로 원격 Grist를 호출한다.
- 신규 서버 Nginx는 Portal의 `/auth/grist/verify`를 호출하고 브라우저 로그인은 Portal 공개 URL로 보낸다.
- Grist Webhook callback은 기존 Portal 공개 API URL을 사용한다.
- 운영 API key는 두 서버 간 공유 mount 대신 배포 secret으로 Portal API/worker에 주입한다.
- 원격 URL과 host는 env로 관리하고 코드에 intranet URL을 직접 작성하지 않는다.

## 실행 단계
- [x] Grist stash를 사용자 변경과 함께 안전하게 복원한다.
- [x] 신규 서버용 Compose, Nginx template과 env 계약을 추가한다.
- [x] OIDC/prod Portal Compose와 Make target을 원격 Grist 구조로 조정한다.
- [x] 운영·원복·키 전달 문서를 갱신한다.
- [x] 정적 경계, Compose, frontend, Docker API 테스트를 실행한다.

## 검증
- `docker compose --env-file env/grist.remote.env -f docker-compose.grist.yml config --quiet`
- `docker compose -f docker-compose.dev.yml config --quiet`
- `docker compose -f docker-compose.oidc.yml config --quiet`
- `docker compose -f docker-compose.yml config --quiet`
- `npm run agent:audit:api-boundary`
- `scripts/agent/check_frontend_boundaries.sh`
- `cd apps/web && npm run lint`
- `npm run web:test`
- `npm run web:build`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.work_hub api.account api.auth`

## 위험과 대응
- 위험: 원격 Grist가 Portal 인증 검증 URL에 접근하지 못하면 로그인이 실패한다.
- 대응: Portal verify URL을 필수 env로 두고 배포 전 preflight에서 연결을 확인한다.
- 위험: Grist API key가 두 서버에 불일치할 수 있다.
- 대응: 신규 서버 발급 후 Portal 배포 secret에 같은 값을 주입하고 값 자체는 Git에 저장하지 않는다.
- 위험: 원격 Grist 장애가 worker 재시도를 누적시킬 수 있다.
- 대응: 기존 timeout, terminal/retry, reconciliation 계약을 유지한다.
- 위험: 사용자 작업과 stash 경로가 겹칠 수 있다.
- 대응: stash는 drop하지 않고 apply하며 충돌 시 사용자 변경을 우선 보존한다.

## 진행 기록
- 2026-08-14: 권장 분리 토폴로지와 신규 Grist 서버 `10.172.117.91`을 확정했다.
- 2026-08-14: stash를 apply해 사용자 Assistant/Observer 변경과 함께 복원했고 stash 자체는 삭제하지 않았다.
- 2026-08-14: 원격 Compose, Nginx, env, Make target과 두 서버 운영·원복 문서를 추가했다.
- 2026-08-14: 로컬 임시 원격 project smoke test에서 root 소유 key 파일 문제를 발견해 initializer UID/GID와 key 디렉터리 사전 생성을 보강했다.
- 2026-08-14: Make target 통합 smoke test에서 Grist 상태 응답, 40자 API key 발급, 배포 사용자 소유 `0600`, 비활성화 시 503, down 시 network 제거와 volume·key 보존을 확인한 뒤 임시 자원을 삭제했다.
- 2026-08-14: Compose 4종, backend/frontend/UI/docs 감사, Web lint·181 tests·build, Django check·migration drift·Work Hub/Account/Auth 330 tests가 통과했다.
- 2026-08-14: 현재 작업 환경에서 `10.172.117.91`의 22번과 80번 port가 timeout이어서 실제 원격 복사와 기동은 수행하지 못했다.
