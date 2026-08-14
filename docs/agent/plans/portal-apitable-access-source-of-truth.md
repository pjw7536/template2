# ExecPlan: Portal 기준 APITable 접근 권한 동기화

> 상태: 접근 권한 단일 원본과 Outbox 설계는 Grist ACL로 이관되었으며, 현재 실행 계획은 `grist-work-hub-replacement.md`입니다.

## 목표
- Portal account의 현재 소속, 명시 소속 권한, 계정·소속 활성 상태를 APITable 접근 권한의 단일 원본으로 사용한다.
- Portal 소속이나 역할이 바뀌면 이전·신규 APITable Space를 desired-state 방식으로 자동 보정한다.
- APITable 장애 중 발생한 변경은 Outbox에 보존하고 재시도할 수 있게 한다.

## 현재 상태
- `api.account`는 `UserCurrentAffiliation`과 `UserSdwtProdAccess(viewer/member/manager)`를 소유한다.
- `api.work_hub`는 소속별 `APITableSpaceScope`와 이메일 목록 기반 Space 멤버 동기화를 제공한다.
- APITable overlay는 이메일 추가·제거를 수행하지만 Portal 역할을 datasheet 권한으로 반영하지 않는다.
- `sync_apitable_access`는 운영자가 실행하는 전체 reconciliation 명령이며 account 변경 이벤트와 연결되어 있지 않다.

## 범위
- 수정: account 유효 소속 역할 selector, Work Hub access sync/Outbox/signal wiring/command/tests/migration.
- 수정: APITable Portal provisioning payload와 managed datasheet 역할 적용.
- 수정: Work Hub 운영·모듈·API 관련 문서.
- 제외: Portal의 기존 소속 승인 규칙 변경, APITable record 본문 복제, APITable upstream grid 엔진 수정.

## 설계
- Portal 유효 역할은 현재 소속을 최소 `member`로 보고 명시 `manager`는 유지한다. 추가 소속은 `UserSdwtProdAccess` 역할을 그대로 사용한다.
- 역할 우선순위는 `viewer < member < manager`이며 이메일이 중복되면 가장 높은 역할을 사용한다.
- APITable 역할은 managed Equipment/WorkLog/Task datasheet에 `reader/editor/manager`로 투영한다.
- account 모델 변경 signal은 같은 DB 트랜잭션에서 영향받는 Space Outbox를 적재하고, commit 후 즉시 처리한다.
- 실패 항목은 지수 backoff로 재시도하며 management command와 전체 reconciliation을 복구 경로로 유지한다.
- public Work Hub launcher API 응답 계약은 변경하지 않는다.
- 새 Outbox 모델과 migration이 필요하며 env 계약 변경은 없다.

## 실행 단계
- [x] account selector에 소속별 유효 사용자·역할 projection을 추가한다.
- [x] Work Hub Outbox 모델·selector·service·signal wiring·처리 명령을 추가한다.
- [x] APITable client와 Java overlay의 provisioning payload를 역할 기반으로 확장한다.
- [x] 소속/역할/계정 변경과 Outbox 재시도 회귀 테스트를 추가한다.
- [x] 운영 문서와 데이터 모델 문서를 갱신한다.
- [x] migration, 테스트, boundary audit, live dev reconciliation을 검증한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate --noinput`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.work_hub api.account`
- `npm run agent:audit:api-boundary`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py sync_apitable_access --all --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py process_apitable_access_sync`

## 위험과 대응
- 위험: APITable 중단이 Portal 소속 변경 요청을 실패시킬 수 있다.
- 대응: 외부 호출은 commit 후 수행하고 실패를 Outbox에 남긴다.
- 위험: APITable에서 직접 변경한 권한이 Portal과 달라질 수 있다.
- 대응: 변경 이벤트와 정기 전체 reconciliation이 Portal desired state로 덮어쓴다.
- 위험: 권한 회수 전 기존 APITable session이 남을 수 있다.
- 대응: Space 멤버 제거와 node ACL 회수로 기존 session에서도 managed datasheet 접근을 차단한다.

## 진행 기록
- 2026-08-05: Portal account를 단일 원본으로 사용하는 역할 projection, Outbox, APITable node role 동기화 설계를 확정했다.
- 2026-08-05: migration 적용, account 227개와 Work Hub 13개 테스트, backend boundary audit, APITable overlay build를 통과했다.
- 2026-08-05: dev에서 Outbox loop 실행, `DEV_ALPHA` 3개 managed datasheet editor ACL, Portal 역할 변경 이벤트의 자동 완료를 확인했다.
- 2026-08-05: Community fallback의 파일 노드 5개 제한을 확인하고 dev seed가 APITable starter node 3개만 안전하게 정리하도록 보완했다.
