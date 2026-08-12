# ExecPlan: Assistant 신뢰성 보강

## 목표
- 생성 답변 저장과 생성 상태 종료를 일관되게 처리한다.
- 저장 실패 시 AI를 다시 호출하지 않고 답변 저장만 재시도할 수 있게 한다.
- CSV 수식 주입과 과도한 요청 크기를 최소한의 제한으로 방어한다.

## 현재 상태
- Assistant 대화/생성 영속화 기능과 프론트엔드 재시도 흐름이 현재 워크트리에 구현되어 있다.
- 답변 메시지 저장 뒤 생성 완료 API가 실패하면 lease가 남을 수 있다.
- 답변 저장 실패에는 저장 전용 복구 동작이 없고, CSV 내보내기 값은 그대로 기록된다.

## 범위
- `apps/api/api/assistant`의 serializer, 대화 저장, CSV 내보내기와 테스트를 수정한다.
- `apps/web/src/features/assistant`의 입력 제한, 저장 전용 재시도 UI/상태와 테스트를 수정한다.
- DB schema, migration, auth, env contract는 변경하지 않는다.
- Assistant/Observer의 공개 facade와 다른 도메인 기능은 변경하지 않는다.

## 설계
- Assistant 메시지가 generation과 함께 저장되면 동일 DB transaction에서 generation을 완료한다.
- 답변 저장 실패 payload를 메모리에 보관하고, 복구 버튼은 동일 payload 저장만 다시 호출한다.
- CSV에서 수식으로 해석될 수 있는 셀 앞에 작은따옴표를 붙인다.
- 메시지와 prompt는 10,000자, 한 번에 저장하는 메시지는 20개, sources는 50개/50KB, context snapshot은 100KB로 제한한다.
- migration/env/auth 영향은 없다.

## 실행 단계
- [x] 백엔드 생성 완료 원자성, CSV 안전 처리, 요청 제한과 회귀 테스트 추가
- [x] 프론트엔드 답변 저장 전용 재시도와 입력 제한, 회귀 테스트 추가
- [x] 관련 테스트와 경계/UI 일관성 검증 실행

## 검증
- `docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -T api python manage.py test api.assistant api.observer`
- `npm --prefix apps/web test -- --run`
- `scripts/agent/check_backend_boundaries.sh`
- `scripts/agent/check_frontend_boundaries.sh`
- `scripts/agent/check_ui_consistency.sh`

## 위험과 대응
- 위험: 기존 idempotency 요청을 다시 저장할 때 generation 상태가 잘못 바뀔 수 있다.
- 대응: 실제 저장된 assistant 메시지의 generation 일치 여부를 확인하고 terminal 전이는 기존 서비스에 맡긴다.
- 위험: 저장 재시도가 AI 응답 재생성으로 연결될 수 있다.
- 대응: 생성 함수가 아닌 메시지 append mutation만 호출하는 별도 callback으로 분리한다.

## 진행 기록
- 2026-08-12: 사용자 승인에 따라 권장 제한값과 최소 복구 기능으로 범위를 확정했다.
- 2026-08-12: 백엔드 원자적 종료·CSV 보호·요청 제한과 프론트엔드 저장 전용 재시도를 구현했다.
- 2026-08-12: 백엔드 109개와 프론트엔드 120개 테스트, ESLint, migration check, 경계/UI audit가 모두 통과했다.
