# ExecPlan: Work Hub ACL worker 운영 보강

## 목표
- Portal 권한 변경 요청이 Grist HTTP 응답을 기다리지 않도록 한다.
- ACL worker 장애가 API container 뒤에 숨지 않고 자동 재시작되도록 한다.
- 문서 ACL 판정 쿼리를 사용자 수와 무관한 batch 조회로 바꾼다.
- 완료 Outbox를 기본 30일 보존 후 정리한다.

## 현재 상태
- `transaction.on_commit` callback이 같은 요청 스레드에서 Grist 동기화를 실행한다.
- API entrypoint가 worker를 background child로 실행해 worker 단독 종료를 감지하지 못한다.
- 문서 구성원마다 앱 접근과 소속 grant를 반복 조회한다.
- 완료된 Outbox를 정리하는 서비스와 보존 기간 계약이 없다.

## 범위
- `api.account`의 Work Hub용 소속 역할 batch projection
- `api.work_hub` Outbox enqueue/worker/prune 서비스와 테스트
- dev/OIDC/prod Compose worker 서비스, Makefile, 설정·운영 문서
- DB schema와 HTTP 응답 계약은 변경하지 않는다.

## 설계
- 요청 transaction은 Outbox 행만 commit하고 외부 호출은 하지 않는다.
- `work-hub-access-worker`를 profile 서비스로 추가하고 `restart: unless-stopped`를 적용한다.
- target affiliation, Portal/Work Hub scope, 정책, UserAccess, current affiliation, grant를 일괄 조회해 메모리에서 ACL을 계산한다.
- worker는 시작 시와 설정된 주기마다 `done`이면서 보존 기한을 지난 행만 삭제한다.
- `failed`, `terminal`, `processing`은 자동 삭제하지 않는다.

## 실행 단계
- [x] 요청 경로의 동기 외부 호출 제거
- [x] batch ACL projection 구현
- [x] 완료 Outbox retention 구현
- [x] 전용 worker Compose 서비스 구성
- [x] 회귀 테스트와 문서 갱신
- [x] Docker 테스트, migration check, 경계·Compose·문서 감사 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.work_hub api.account --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:docs`
- dev/OIDC/prod `docker compose ... config --quiet`
- `git diff --check`

## 위험과 대응
- 위험: batch 판정이 기존 단건 권한 우선순위와 달라질 수 있다.
- 대응: 기존 current/grant/전체 범위와 Portal 차단 테스트를 유지하고 query 상한 회귀 테스트를 추가한다.
- 위험: worker image와 API image가 달라질 수 있다.
- 대응: 환경별 API service와 worker가 같은 `API_IMAGE` tag를 사용하도록 고정한다.

## 진행 기록
- 2026-08-10: 재리뷰에서 확인한 요청 지연, worker 생존성, N+1, Outbox 누적을 구현 범위로 확정했다.
- 2026-08-10: 요청 transaction은 Outbox 저장까지만 수행하고, Grist 호출은 전용 worker가 처리하도록 분리했다.
- 2026-08-10: ACL projection을 batch 조회로 변경하고, 사용자 6명 기준 쿼리 수가 10회 이하인지 검증하는 회귀 테스트를 추가했다.
- 2026-08-10: 완료 Outbox의 기본 30일 보존과 주기적 정리를 구현했다. 실패·종료·처리 중인 행은 자동 삭제 대상에서 제외했다.
- 2026-08-10: Work Hub 테스트 34개와 Work Hub/Account 테스트 262개가 통과했고, migration check에서 변경 없음이 확인됐다.
- 2026-08-10: backend boundary·문서 감사, dev/OIDC/prod Compose config, `git diff --check`가 모두 통과했다.
