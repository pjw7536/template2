# ExecPlan: Assistant 추가 리뷰 후속 수정

## 목표
- 생성 결과와 저장 API 제한을 일치시켜 영구 저장 실패 상태를 방지한다.
- Observer 분석 prompt가 설정된 180,000자 예산을 항상 지키게 한다.
- 불완전한 SSE 응답, history 과다 입력, 고정 대화 pagination 오류를 막는다.

## 현재 상태
- Assistant 메시지 저장은 content 10,000자, sources 50개/50KB, context snapshot 100KB 제한을 사용한다.
- 생성 결과는 같은 제한으로 정규화되지 않아 재시도 불가능한 저장 실패가 발생할 수 있다.
- Observer prompt 축소는 context rows에만 적용되어 TIP 통계 중심 payload가 약 290만 자까지 커지는 사례가 확인됐다.
- SSE는 `done` 없이 종료돼도 누적 delta를 성공으로 반환한다.
- history는 raw JSONField이며, 고정 대화 정렬은 frontend의 현재 page 안에서만 적용된다.

## 범위
- Assistant serializer, selector와 Observer 분석 service를 수정한다.
- Assistant frontend 생성 결과 정규화, 저장 실패 답변 제거, SSE 완료 검증을 수정한다.
- 관련 backend/frontend 테스트와 API 문서를 갱신한다.
- DB schema, migration, auth, env contract는 변경하지 않는다.

## 설계
- history는 최대 20개, 각 role/content를 명시적으로 검증한다.
- 생성 답변은 화면 표시와 저장 전에 content/sources/context snapshot을 저장 한도에 맞게 축소한다.
- 저장 실패 답변은 사용자 동작으로 화면에서 제거하고 마지막 저장된 user 메시지부터 계속할 수 있게 한다.
- SSE는 `done` event를 받은 경우에만 성공으로 간주한다.
- Observer prompt는 context rows, target events, recorded causes, TIP 통계를 순서대로 축소하고 최종 크기를 검증한다.
- 고정 대화는 server cursor pagination의 첫 정렬 기준으로 포함한다.

## 실행 단계
- [x] backend history 검증·고정 대화 pagination·Observer prompt 예산 수정 및 테스트
- [x] frontend 생성 결과 정규화·저장 실패 제거·SSE 완료 검증 및 테스트
- [x] 문서 갱신과 전체 회귀·경계·UI 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant api.observer`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm --prefix apps/web test -- --run`
- `npm --prefix apps/web run lint`
- `npm run agent:audit:api-boundary`
- `scripts/agent/check_frontend_boundaries.sh`
- `scripts/agent/check_ui_consistency.sh`

## 위험과 대응
- 위험: 생성 결과 축소로 화면과 저장 내용이 달라질 수 있다.
- 대응: 화면에 추가하기 전에 동일한 정규화 결과를 사용하고 생략 안내를 본문에 포함한다.
- 위험: pinned 정렬을 cursor 조건과 다르게 구현하면 page 누락이 생길 수 있다.
- 대응: pinned bucket, updatedAt, createdAt, id를 동일 순서로 cursor에 저장하고 동률 테스트를 추가한다.
- 위험: prompt 축소 loop가 더 줄일 수 없는 목록에서 반복될 수 있다.
- 대응: 각 축소 단계가 반드시 항목 수를 줄이도록 하고 최종 최소 payload fallback을 둔다.

## 진행 기록
- 2026-08-12: 추가 코드리뷰에서 확인한 5개 결함의 수정 범위와 검증 방법을 확정했다.
- 2026-08-12: backend Assistant/Observer 111개와 최종 Observer 68개, frontend 전체 124개 테스트를 통과했다.
- 2026-08-12: frontend 전체 lint, migration 누락 검사, API/frontend/UI/docs 감사를 통과했다.
