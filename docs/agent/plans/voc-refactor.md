# ExecPlan: VOC canonical 계약 축소

## 목표
- 게시글·답글·활동 로그와 frontend 상태를 현재 업무 흐름 중심으로 축소한다.
- 값이 `기타` 하나뿐인 `VocPost.app` DB/API/UI 계약을 제거한다.

## 현재 상태
- `VocPost.app`은 migration부터 `기타` 단일 choice이며 frontend도 단일 option/filter를 유지한다.
- 공개 API는 posts collection/detail/replies이고 frontend route는 `/voc`이다.
- 작성자 identity는 Account service facade를 사용한다.

## 범위
- 수정: `api.voc`, frontend voc, VOC migration/docs/tests.
- 유지: `/voc`, title/content/status, author, replies, ordering, 권한과 activity logging.
- 제외: 새로운 category 도입과 시각 개편.

## 설계
- migration 사전 `RunPython` 검사는 모든 `voc_post.app` 값이 `기타` 또는 빈 기본값인지 확인하고 다른 값이 있으면 migration을 실패시킨다.
- 확인 후 새 migration에서 `app` column을 제거한다. 적용 migration은 수정하지 않는다.
- POST/PATCH request와 response에서 `app`을 제거하고 전송 시 400 `invalid_request`의 `fieldErrors.app`을 반환한다.
- frontend category select/filter/default constant와 `app` 기반 derived state를 제거한다.
- post/reply write는 service, 목록/상세는 selector, HTTP parsing은 view에 유지한다.
- rollback은 배포 전 DB backup으로 수행한다. reverse migration은 nullable/default `기타` column을 재생성하도록 작성하되 사용자별 과거 category 복원은 필요하지 않다.

## 실행 단계
- [x] 운영 전 값 분포 query와 API characterization을 추가한다.
- [x] frontend/API에서 app 소비를 제거하고 unexpected field 오류를 고정한다.
- [x] 새 검사+RemoveField migration을 생성한다.
- [x] service/selector/view/test 책임을 정리하고 ActivityLog 회귀를 확인한다.
- [x] 문서와 fixture를 갱신한다.

## 검증
- `SELECT app, COUNT(*) FROM voc_post GROUP BY app;`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.voc api.activity`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- frontend VOC tests/lint/build와 전체 agent audit.

## 위험과 대응
- 위험: 운영 DB에 문서화되지 않은 category가 있다.
- 대응: migration을 fail-closed하고 값 분포를 사용자에게 보고한 뒤 제품 구현을 중단한다.
- 위험: 오래된 browser가 app을 계속 보낸다.
- 대응: 명시적 400 field error를 반환하고 silent ignore하지 않는다.

## 의존성과 복구
- 상위 계약: [마스터 계획](repository-refactor-master-2026-08.md). Account/Common 뒤, Data Movement 앞에 실행한다.
- 복구: 배포 전 backup과 reverse migration으로 `app` column을 `기타` 기본값으로 재생성하고 frontend/API를 함께 이전 계약으로 되돌린다.

## 진행 기록
- 2026-08-18: 사용자 승인으로 단일 app UI/API/DB field 제거를 확정했다.
- 2026-08-18: 개발 DB 사전 분포 query는 0행이었다. `기타`·빈 값 이외 값을 만나면 실패하는 `0002_remove_vocpost_app` migration과 guard test를 추가했다.
- 2026-08-18: migration을 적용해 `voc_post`가 id/title/content/status/timestamps/author만 보유하고 row count 0을 유지함을 확인했다. reverse 시 기존 migration state의 기본값 `기타` column을 재생성한다.
- 2026-08-18: backend model/service/request/response와 frontend category nav/select/filter/table/detail에서 `app`을 제거했다. 오래된 요청은 400 canonical 오류의 `fieldErrors.app`으로 명시적으로 거절한다.
- 2026-08-18: VOC+Activity 36개, 전체 backend 1,122개와 frontend 195개 테스트, lint/build, migration drift·권한 무결성, 전체 agent audit를 통과했다.
