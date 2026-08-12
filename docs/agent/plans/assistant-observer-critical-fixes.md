# ExecPlan: Assistant·Observer 우선 결함 수정

## 목표
- 분기 편집 뒤 오래된 대화 요약이 재사용되지 않도록 한다.
- Observer Assistant 문맥 키가 API 길이 제한을 넘지 않도록 한다.
- Observer 질문 길이 계약을 frontend/backend 2,400자로 통일한다.
- Assistant 답변 저장이 성공한 뒤 generation을 완료 처리한다.

## 현재 상태
- Assistant 메시지 분기를 바꿔도 기존 rolling summary가 남아 있다.
- Observer 문맥 키가 조회 scope JSON 전체를 포함한다.
- frontend 질문 제한은 2,400자이고 backend 검증·프롬프트 제한은 1,000자다.
- frontend가 assistant 메시지 저장보다 먼저 generation을 completed로 변경한다.

## 범위
- Assistant 대화 저장 서비스와 관련 backend/frontend 테스트를 수정한다.
- Observer 분석 질문 serializer/service, 문맥 키 유틸리티와 관련 테스트를 수정한다.
- API 문서에 질문 길이 제한을 기록한다.
- DB schema, migration, auth, env 계약은 변경하지 않는다.

## 설계
- 새 메시지가 기존 current message가 아닌 부모에서 시작할 때만 summary 필드를 초기화한다.
- 정규화한 Observer scope를 SHA-256으로 해시해 고정 길이 문맥 키를 만든다.
- 질문 최대 길이는 양쪽 모두 2,400자로 맞춘다.
- assistant 메시지 저장 실패 시 generation을 failed로 종료하고 completed를 보내지 않는다.

## 실행 단계
- [x] Assistant 분기 변경 시 요약 무효화 및 회귀 테스트 추가
- [x] Observer 질문 길이 계약 통일 및 회귀 테스트 추가
- [x] Observer 고정 길이 문맥 키 유틸리티와 테스트 추가
- [x] generation 완료 순서 수정 및 저장 실패 테스트 추가
- [x] backend/frontend 검증 실행

## 검증
- `docker compose -f docker-compose.dev.yml run --rm --entrypoint python api manage.py test api.assistant api.observer`
- `docker compose -f docker-compose.dev.yml run --rm --entrypoint python api manage.py makemigrations --check --dry-run`
- `npm --prefix apps/web test -- --run`
- `npm --prefix apps/web run lint`

## 위험과 대응
- 위험: idempotent 메시지 재전송이 새로 생성된 요약을 다시 지울 수 있다.
- 대응: 실제로 새 메시지가 생성된 경우에만 분기 변경을 판단한다.
- 위험: scope 배열 순서 차이로 같은 조회 조건이 다른 키가 될 수 있다.
- 대응: 배열을 중복 제거·정렬한 뒤 해시한다.

## 진행 기록
- 2026-08-12: 코드리뷰에서 확인한 우선 결함 4건을 수정 범위로 확정했다.
- 2026-08-12: 우선 결함 4건을 수정하고 backend 107개, frontend 117개 테스트와 lint, migration, boundary audit를 통과했다.
