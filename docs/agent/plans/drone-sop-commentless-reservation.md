# ExecPlan: Drone SOP 코멘트 없는 자동 예약

## 목표
- 선택한 `Engr 분임조원 + 설비 + 알림 target` 지정 조합은 Comment 키워드가 없어도 자동 예약 대상으로 계산한다.
- 기존 자동 예약 활성화와 `ENGR_PRODUCTION` 정책은 유지한다.

## 현재 상태
- `DroneSopNeedToSendRule`은 target별 Comment 키워드와 Sample Type 정책을 소유한다.
- `DroneSopTargetMapping`은 `sdwt_prod + user_sdwt_prod` 조합을 target에 연결한다.
- POP3 수집은 target별 규칙 중 하나라도 충족하면 `drone_sop.needtosend`를 계산한다.
- 기존 `drone_sop` 행의 `needtosend`는 POP3 conflict update에서 유지된다.

## 범위
- `drone_sop_target_mapping`에 코멘트 생략 예약 정책 필드를 추가한다.
- mapping 조회/생성/수정 API를 확장한다.
- target 해석 결과에 매칭된 mapping 정책을 포함하고 POP3 계산에 반영한다.
- Line Dashboard 자동 예약 설정 UI에서 mapping별 옵션을 변경할 수 있게 한다.
- 관련 backend 테스트와 정적 frontend 검증을 수행한다.
- 기존 `drone_sop` 행 소급 재계산과 발송 파이프라인 변경은 범위에서 제외한다.

## 설계
- `DroneSopTargetMapping.needtosend_without_comment` Boolean 필드를 기본값 `False`로 추가한다.
- 자동 예약 계산 순서는 `rule.enabled` → Sample Type 정책 → mapping 코멘트 생략 정책 → Comment 키워드 순서로 유지한다.
- target 해석 우선순위는 pair → sdwt only → user only → persisted target 순서를 보존한다.
- persisted target fallback에는 mapping 정책을 적용하지 않는다.
- mapping API 응답에는 `needtosendWithoutComment`를 추가하고 같은 endpoint의 `PATCH`로 갱신한다.
- 기존 mapping 생성 요청은 필드 미지정 시 `False`를 사용한다.
- UI Checkbox는 `sdwt_prod + user_sdwt_prod`가 모두 있는 완전한 지정 조합에만 표시한다.
- 전체 자동 예약이 활성인 상태에서 Comment 키워드와 코멘트 생략 조합이 모두 없어도 허용하며, 이 경우 예약 대상은 없다.
- UI는 선택된 target의 `Engr분임조 → 설비분임조` mapping 행에 접근 가능한 Checkbox를 표시한다.
- API/DB 계약과 migration이 변경되며 auth/env 계약 변경은 없다.

## 실행 단계
- [x] 모델과 migration 추가
- [x] mapping selector/service/view/API 계약 확장
- [x] target resolution과 needtosend 계산 확장
- [x] backend service/view 회귀 테스트 추가
- [x] frontend API/hook/UI 상태 흐름 추가
- [x] Docker Compose backend 검사와 frontend audit 실행

## UI 구조 후속 개선
- [x] mapping 행으로 코멘트 없는 자동 예약 Checkbox 이동
- [x] 자동 예약 규칙 카드의 중복 mapping 목록 제거
- [x] 전체 자동 예약 비활성 상태와 mapping 저장 상태 안내
- [x] mapping 행을 Checkbox 전용 UI와 hover/focus 설명으로 축약
- [x] mapping 목록의 기존 typography·정렬·간격을 유지하고 Checkbox 열만 추가
- [x] 두 번째 컬럼 높이와 카드 UI를 변경 전 상태로 복원
- [x] 완전한 Engr분임조·설비분임조 조합에만 Checkbox 표시
- [x] 키워드·활성 조합이 0개인 전체 자동 예약 ON 상태 허용
- [x] frontend lint/build 및 UI/boundary audit 재검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- frontend package의 기존 lint/build 명령 확인 후 관련 검증 실행

## 위험과 대응
- 위험: mapping 정책이 다른 설비 또는 분임조에 잘못 전파될 수 있다.
- 대응: 매칭된 mapping row의 정책만 target resolution 결과에 포함한다.
- 위험: `always` 의미가 Sample Type 정책까지 우회할 수 있다.
- 대응: 필드명을 `needtosend_without_comment`로 제한하고 Sample Type 검사를 먼저 수행한다.
- 위험: 설정 변경으로 과거 E-SOP이 발송될 수 있다.
- 대응: 기존 `needtosend` conflict 보존 정책을 유지하고 소급 계산을 추가하지 않는다.

## 진행 기록
- 2026-07-14: mapping 소유의 코멘트 생략 예약 정책과 비소급 적용 방식을 확정했다.
- 2026-07-14: migration 적용, `api.drone` 279개 테스트, frontend lint/build, backend/frontend boundary audit를 완료했다.
- 2026-07-14: UI/docs audit의 기존 `l3-spider` 색상 및 inventory 누락 후보는 요청 범위 밖이라 유지했다.
- 2026-07-14: 코멘트 없는 자동 예약 Checkbox를 mapping 행으로 이동하고 중복 UI를 제거했다. frontend lint/build와 boundary audit를 재검증했다.
- 2026-07-14: mapping 행의 표시 문구를 Tooltip으로 이동하고 두 번째 컬럼 UI를 원본 레이아웃으로 복원했다.
- 2026-07-14: mapping 행의 기존 grid와 텍스트 클래스를 복원하고 Checkbox 열만 추가했다.
- 2026-07-14: mapping 카드 헤더와 6열 grid를 원본 DOM으로 복원하고 기존 삭제 액션 칸에 Checkbox만 추가했다.
- 2026-07-14: 부분 mapping에는 Checkbox를 숨기고, 자동 예약 ON 상태에서 키워드·활성 mapping이 없는 구성을 허용하도록 UI 제한을 제거했다.
- 2026-07-14: 기존 DB 데이터를 그대로 사용하기로 하고 `needtosend_without_comment` seed 입력 지원을 범위에서 제외했다.
