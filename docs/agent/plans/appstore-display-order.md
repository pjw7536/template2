# ExecPlan: Appstore 앱 노출 순서 관리

## 목표
- Appstore 앱 카드의 전역 노출 순서를 DB에 저장한다.
- Appstore `admin`만 전체 앱 순서를 편집하고 저장할 수 있게 한다.
- 신규 앱은 현재 순서의 마지막에 배치한다.

## 현재 상태
- `AppStoreApp.display_order`와 관리자 전용 전체 순서 저장 API가 구현되어 있다.
- 프론트엔드는 전체 앱 draft를 inline drag-and-drop으로 재배치한다.
- 순서 편집 진입 시 검색과 카테고리를 초기화해 전체 앱만 표시한다.
- 카테고리 표시 순서는 프론트엔드 상수로 관리되며 이번 범위에 포함하지 않는다.

## 범위
- Backend 모델, 신규 migration, selector/service/serializer/view/URL과 appstore 테스트를 수정한다.
- Frontend appstore API, React Query mutation, 관리자 inline 순서 편집과 페이지 연결을 수정한다.
- Appstore API/모듈 문서를 갱신한다.
- 기존 앱 CRUD, 댓글, 좋아요, 카테고리 정렬 계약은 변경하지 않는다.

## 설계
- `AppStoreApp.display_order`를 추가하고 `display_order`, `id` 순으로 정렬한다.
- 기존 데이터는 현재 최신순을 유지하도록 `1..N`으로 backfill한다.
- 신규 앱 생성과 앱 삭제, 전체 순서 변경은 같은 PostgreSQL transaction advisory lock으로 직렬화한다.
- 신규 앱은 잠금 안에서 현재 최대 `display_order + 1`로 생성한다.
- `PUT /api/v1/appstore/apps/order`가 전체 앱 ID 순서를 교체한다.
- 요청에는 목록 변경 충돌을 감지할 `orderVersion`을 포함한다.
- 서비스는 transaction과 행 잠금을 사용하고, 전체 ID 집합 검증 후 `bulk_update`한다.
- 순서 변경 권한은 Appstore scope `admin`으로 명시하고, 일반 사용자에게는 UI를 렌더링하지 않는다.
- UI는 관리자에게만 순서 편집 버튼을 노출하고, 기존 앱 카드 grid에서 native drag-and-drop으로 draft 순서를 편집한다.
- 편집 진입 시 검색어만 초기화하고 선택 카테고리는 유지·고정한다.
- 특정 카테고리에서는 해당 앱들이 차지한 전역 슬롯만 삽입 정렬하고, 다른 카테고리 앱의 슬롯은 유지한다.
- `전체`에서는 기존과 동일하게 전체 draft를 삽입 정렬한다.
- 우측 pane 상단에 저장/취소 toolbar를 고정하고 카드 목록만 기존 세로 스크롤을 소유한다.
- `409`에서는 최신 목록과 버전을 inline draft에 명시적으로 다시 적재하면서 오류 안내를 유지한다.

## 실행 단계
- [x] 모델과 데이터 migration 추가
- [x] 정렬 selector와 순서 변경 service 추가
- [x] 목록/순서 변경 API 계약과 권한 처리 추가
- [x] backend 서비스/selector/view 테스트 추가
- [x] frontend API normalization과 React Query mutation 추가
- [x] 관리자 순서 편집 UI와 페이지 연결 추가
- [x] appstore 문서 갱신
- [x] 테스트, build, boundary/UI audit 실행
- [x] 생성/삭제/재정렬 공유 잠금과 동시 생성 회귀 테스트 추가
- [x] Appstore `admin` 역할 명시 및 인증/권한 회귀 테스트 강화
- [x] 순서 편집 draft 유지와 `409` 최신 목록 복구 테스트 추가
- [x] 개선사항 전체 검증
- [x] Sheet를 inline drag-and-drop 순서 편집으로 교체
- [x] drag/keyboard 이동과 저장·취소·409 복구 테스트 추가
- [x] inline 편집 UI 검증
- [x] 카테고리 슬롯 보존 정렬 유틸과 회귀 테스트 추가
- [x] 선택 카테고리를 유지하는 순서 편집 연결
- [x] 카테고리 내 정렬 문서와 프런트 검증 갱신

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.appstore`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check`
- `npm run web:test`
- `npm run web:build`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `npm run agent:audit:docs`

## 위험과 대응
- 위험: 두 관리자가 동시에 순서를 저장하면 나중 요청이 앞선 변경을 덮어쓸 수 있다.
- 대응: 현재 앱 ID 순서에서 생성한 `orderVersion`을 잠금 후 비교하고 불일치 시 409를 반환한다.
- 위험: 앱 추가/삭제로 편집 중인 전체 ID 집합이 달라질 수 있다.
- 대응: 저장 시 전체 ID 집합을 비교하고 불일치 시 409와 새로고침 안내를 반환한다.
- 위험: migration 후 기존 노출 순서가 달라질 수 있다.
- 대응: 현재 `-created_at`, `-id` 순서를 그대로 순번으로 backfill한다.
- 위험: 동시 앱 생성이 같은 `display_order`를 배정할 수 있다.
- 대응: 순서에 영향을 주는 생성/삭제/재정렬을 동일한 transaction advisory lock으로 직렬화한다.
- 위험: React Query refetch가 inline 편집 draft와 충돌할 수 있다.
- 대응: 편집 시작 시점에만 draft를 만들고 충돌 refetch 결과만 명시적으로 반영한다.
- 위험: 필터된 앱만 별도 배열로 저장하면 다른 카테고리의 전역 순서가 손상될 수 있다.
- 대응: 전체 draft에서 선택 카테고리의 기존 슬롯만 교체하고 항상 전체 앱 ID 배열을 저장한다.

## 진행 기록
- 2026-08-07: 권장안(전역 앱 카드 순서, admin 전용, 신규 앱 마지막)을 사용자 확인으로 확정했다.
- 2026-08-07: migration, admin 전용 순서 API, React Sheet와 충돌 복구 처리를 구현했다.
- 2026-08-07: appstore backend 26개 테스트, web 58개 테스트, build, lint, 전체 agent audit 통과를 확인했다.
- 2026-08-08: 동시 생성 순번 중복과 Sheet 충돌 안내 초기화 리뷰 지적을 개선 범위에 추가했다.
- 2026-08-08: 공유 advisory lock, admin 전용 권한 검증, Sheet 충돌 복구를 구현했다.
- 2026-08-08: appstore backend 29개 테스트, web 59개 테스트, migration check, build, lint, 전체 agent audit 통과를 확인했다.
- 2026-08-08: 별도 Sheet 대신 기존 카드 grid의 native drag-and-drop 편집 방식으로 단순화하기로 결정했다.
- 2026-08-08: inline native drag-and-drop, 키보드 이동, 저장·취소 toolbar를 구현했다. web 61개 테스트와 lint, build, frontend boundary/UI/docs audit를 모두 통과했다.
- 2026-08-08: 하나의 `display_order`에서 선택 카테고리의 전역 슬롯만 재배치하는 정렬 규칙을 확정했다.
- 2026-08-08: 카테고리 슬롯 보존 정렬과 화면 연결을 구현했다. web 64개 테스트, lint, build, frontend boundary/UI/docs audit를 모두 통과했다.
