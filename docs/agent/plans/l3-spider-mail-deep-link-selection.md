# ExecPlan: L3 Spider 메일 Deep Link 상위 선택 복원

## 목표
- L3 Spider 메일 이벤트 링크로 Chart를 열 때 line_name, process_id, eds_step과 하위 필터를 모두 선택한다.
- 기존 `lineId` 기반 파일 조회와 일반 URL 진입 동작은 유지한다.

## 현재 상태
- 메일 링크는 `lineId`, `processId`, `edsStep`과 하위 필터를 포함하지만 `lineName`은 포함하지 않는다.
- 프론트 deep link parser는 `lineIds`, `processIds`, `edsSteps`만 복원하고 `lineNames`를 읽지 않는다.
- line_name 모드의 Process/EDS 후보는 선택된 lineName에서 계산되므로 상위 패널이 비어 보인다.

## 설계
- 메일 이벤트에 이미 계산된 `line_name`을 `lineName` query parameter로 추가한다.
- 프론트는 camelCase/snake_case 및 단수/복수 `lineName` query를 모두 Set으로 복원한다.
- `lineId`와 `lineName`을 함께 유지해 원본 경로 필터와 표시용 규칙 매핑을 모두 충족한다.

## 실행 단계
- [x] 메일 event URL builder에 `lineName` 추가
- [x] URL selection parser에 `lineNames` 추가
- [x] 메일 HTML query 회귀 테스트 보강
- [x] API·frontend 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb`
- L3 Spider mail deep link query 생성과 frontend parser 결과 확인
- `npm run web:build`
- 변경 파일 ESLint, frontend/backend boundary audit, `git diff --check`

## 위험과 대응
- 위험: lineName만 추가하고 lineId를 제거하면 파일 경로 조회가 실패할 수 있다.
- 대응: 두 parameter를 모두 유지한다.
- 위험: 기존 일반 deep link가 깨질 수 있다.
- 대응: 기존 key alias를 유지하고 lineName alias만 추가한다.

## 진행 기록
- 2026-07-14: 상위 선택 누락 원인이 mail URL의 lineName 부재와 frontend parser 미지원임을 확인했다.
- 2026-07-14: 전체 query parser에서 lineNames, lineIds, processIds, edsSteps와 하위 필터 복원을 확인했다.
- 2026-07-14: L3 Spider 테스트 50개, Django check, migration check, 웹 빌드, ESLint, frontend/backend boundary audit를 통과했다.
