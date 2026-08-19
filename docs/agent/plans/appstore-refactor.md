# ExecPlan: AppStore 책임·payload 단일화

## 목표
- 대형 view, camel/snake 이중 입력, cover 저장, 댓글·좋아요·정렬 흐름을 책임별로 단순화한다.
- `/appstore` 사용자 흐름과 앱/댓글/좋아요/조회 데이터를 보존한다.

## 현재 상태
- backend `views.py` 1,163줄과 `serializers.py` 609줄이 HTTP, validation, payload 조립을 폭넓게 담당한다.
- serializer는 `manualUrl/manual_url`, `screenshotUrl/screenshot_url`, `screenshotUrls/screenshot_urls`, `coverScreenshotIndex/cover_screenshot_index`, `parentCommentId/parent_comment_id`를 함께 허용한다.
- Assistant가 AppStore snapshot selector를 소비한다.

## 범위
- 수정: `api.appstore`, frontend appstore, Assistant가 사용하는 AppStore public selector contract, docs/tests.
- 유지: `/appstore`, `/api/v1/appstore/**`, display order, cover object, nested comment, like/view 결과.
- 제외: UI 전면 재설계와 scope 정책 변경.

## 설계
- view를 apps/order/cover/reactions/comments module로 나누고 serializer validation과 service 호출만 수행한다.
- request body는 `manualUrl`, `screenshotUrl`, `screenshotUrls`, `coverScreenshotIndex`, `parentCommentId`만 허용하며 snake_case는 400 처리한다.
- response는 camelCase 현재 계약을 유지한다.
- cover는 외부 object storage가 아니라 `AppStoreApp.screenshot_url/screenshot_base64/screenshot_mime_type/screenshot_gallery`에 저장한다. create/update는 정규화된 필드를 단일 DB transaction에서 반영하며 실패 시 기존 row 값을 보존한다.
- 댓글/좋아요 toggle은 unique constraint와 transaction을 유지하고 N+1 없는 selector payload를 사용한다.
- frontend server state는 React Query에만 두고 detail dialog/selected app/form preview만 local state로 둔다.
- DB schema/migration은 변경하지 않는다.

## 실행 단계
- [x] endpoint별 permission/error/storage/ordering characterization을 추가한다.
- [x] snake_case frontend/test 소비자를 camelCase로 전환하고 alias를 제거한다.
- [x] view/service/test를 책임별 module로 분리한다.
- [x] frontend mutation invalidation과 cover preview lifecycle을 검증한다.
- [x] Assistant AppStore snapshot 회귀를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.appstore api.assistant`
- frontend AppStore tests, lint, build.
- cover URL/base64/gallery create/update/delete와 잘못된 base64 응답 회귀.
- backend/frontend/UI audit와 migration drift check.

## 위험과 대응
- 위험: cover 필드 일부만 갱신돼 URL/base64/gallery 조합이 불일치한다.
- 대응: cover 입력을 service에서 한 번에 정규화하고 DB 실패 rollback 및 URL/base64/gallery 전환 회귀를 고정한다.
- 위험: 댓글 count/like 상태가 stale해진다.
- 대응: app detail/comment query key의 최소 invalidation을 mutation test로 고정한다.

## 의존성과 복구
- 상위 계약: [마스터 계획](repository-refactor-master-2026-08.md). Account/Common 뒤에 실행하고 Assistant AppStore tool 계획의 선행 단계다.
- 복구: DB schema가 없으므로 API/service/frontend를 함께 revert한다. 커버 데이터는 기존 AppStore row 안에 있으므로 별도 object 정리는 필요 없다.

## 진행 기록
- 2026-08-18: 다섯 snake_case HTTP alias를 제거 대상으로 확정했다.
- 2026-08-18: 구현 전 재조사에서 커버가 외부 object storage가 아니라 AppStore row의 URL/base64/gallery 필드임을 확인했다. 존재하지 않는 object compensation 설계를 제거하고 단일 DB transaction·기존 row 보존 계약으로 재동결했다.
- 2026-08-18: 1,163줄 view를 apps 204줄, comments 417줄, cover 75줄, detail 244줄, order 105줄, reactions 119줄과 60줄 공용 helper로 분리했다. 파일별 기본 hotspot 기준 이하가 되어 기존 예외 행을 제거했다.
- 2026-08-18: 앱·순서·댓글 request의 snake_case alias와 frontend response fallback을 제거하고 canonical 오류를 적용했다. frontend API가 mutation body의 허용 camelCase 필드만 전송하도록 고정했다.
- 2026-08-18: 커버 URL/base64/gallery 저장 실패 rollback과 제외 필드 거절을 추가했다. base64는 data URL로 보유해 object URL lifecycle이 없음을 확인했고, 기존 React Query cache 동기화·최소 invalidation 흐름을 유지했다.
- 2026-08-18: AppStore+Assistant 95개, 전체 backend 1,121개, frontend 195개 테스트와 lint/build, migration·권한 무결성, 전체 agent audit를 통과했다.
