# ExecPlan: Assistant 최신 리뷰 수정

## 목표
- 불완전한 OpenWebUI stream을 성공으로 저장하지 않는다.
- 추가로 불러온 대화 목록이 첫 페이지 재조회 뒤 사라지지 않게 한다.
- 장기 요약을 `contextKey`별로 분리하고 Observer 분석에 해당 요약을 전달한다.
- 만료·종료된 generation을 활성 또는 재사용 가능한 요청으로 취급하지 않는다.
- Observer prompt 축소 시 실제로 줄어든 section과 건수를 보고한다.

## 현재 상태
- upstream SSE가 `[DONE]` 없이 끝나도 누적 delta를 성공으로 반환한다.
- 대화 목록 query 재조회가 로컬 pagination 결과를 첫 페이지로 덮어쓴다.
- 대화방 하나에 summary 한 개만 있어 서로 다른 업무 문맥이 덮어쓴다.
- generation 활성 조회와 동일 request ID 재사용이 lease 만료·종료 상태를 엄격히 구분하지 않는다.
- Observer coverage는 prompt 축소 여부만 표시하고 축소 대상과 전후 건수를 남기지 않는다.

## 범위
- Assistant 모델·migration·selector·service·view와 관련 테스트를 수정한다.
- Observer 요청 serializer·view·분석 service와 관련 테스트를 수정한다.
- Assistant/Observer frontend hook·API 전달과 관련 테스트를 수정한다.
- 외부 URL, 인증 정책, UI 레이아웃은 변경하지 않는다.

## 설계
- `AssistantConversationSummary`를 `(conversation, context_key)` unique 구조로 추가하고 기존 summary를 data migration으로 이전한 뒤 기존 단일 summary 필드를 제거한다.
- Observer 분석 요청은 선택적인 `roomId`, `contextKey`를 받고, 인증 사용자 소유 대화의 일치 요약만 prompt에 포함한다.
- 대화 목록은 동일 목록 조건의 첫 페이지 재조회 시 이미 불러온 후속 페이지를 ID 기준으로 병합하고 다음 cursor를 보존한다.
- generation lease 조회는 현재 시각보다 늦은 `expires_at`만 활성으로 간주하며, 종료·만료·계약 불일치 request ID는 `409`로 거절한다.
- prompt coverage에 각 축소 가능 section의 `before`/`after` 건수를 기록한다.

## 실행 단계
- [x] 모델·migration과 context별 summary 조회/갱신 흐름 수정
- [x] stream 완료와 generation lease 규칙 수정
- [x] Observer summary 전달과 prompt 축소 metadata 수정
- [x] frontend 대화 pagination 보존과 Observer 요청 문맥 전달 수정
- [x] backend/frontend 테스트와 경계·migration 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant api.observer`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm --prefix apps/web test -- --run`
- `npm --prefix apps/web run lint`
- `npm run agent:audit:api-boundary`
- `scripts/agent/check_frontend_boundaries.sh`
- `scripts/agent/check_ui_consistency.sh`

## 위험과 대응
- 위험: 기존 단일 summary의 context 정보가 유실될 수 있다.
- 대응: 새 모델 생성과 data migration을 같은 새 migration에 두고 값이 있는 row만 이전한다.
- 위험: 첫 페이지 병합으로 삭제된 대화가 남을 수 있다.
- 대응: 현재 mutation은 대상 대화를 먼저 로컬 목록에서 제거하며, 목록 조건 변경 시에는 첫 페이지로 완전히 초기화한다.
- 위험: Observer prompt에 summary가 추가되어 예산을 초과할 수 있다.
- 대응: summary 길이를 제한하고 전체 message payload 예산 계산에 포함한다.

## 진행 기록
- 2026-08-12: 사용자가 context별 별도 요약 테이블과 data migration 권장안을 승인했다.
- 2026-08-12: 기존 단일 요약을 새 문맥별 테이블로 이전하는 `0004` migration과 API/Observer 연동을 구현했다.
- 2026-08-12: Assistant·Observer 113개, frontend 125개 테스트와 lint, migration 누락 검사, 전체 agent 감사를 통과했다.
