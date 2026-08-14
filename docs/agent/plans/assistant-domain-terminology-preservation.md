# ExecPlan: Assistant 영문 업무 용어 보존

## 목표
- ChatWidget과 Observer 분석이 영문 업무 용어를 한국어로 번역하거나 음역하지 않고 canonical 표기로 출력하도록 한다.

## 현재 상태
- 일반 Assistant와 Observer prompt는 한국어 답변과 기술 용어 원문 유지를 함께 지시하지만 구체적인 용어와 금지 표기가 없다.
- 모델이 `interlock`을 `인터록`으로, `wafer lot`을 `웨이퍼 로트`로 바꾸는 사례가 있다.

## 범위
- 공통 영문 업무 용어 보존 guide를 추가하고 일반 답변·Email RAG·제목·대화 요약·Observer 분석 prompt에 적용한다.
- Assistant와 Observer prompt 회귀 테스트 및 Assistant 모듈 문서를 갱신한다.
- 모델 응답 후 문자열 치환, DB schema, migration, auth, env, OpenWebUI endpoint는 변경하지 않는다.

## 설계
- 공통 service facade에서 immutable prompt guide와 결합 helper를 명시적으로 노출하고 Email RAG의 구조화 출력 제약에도 같은 guide를 포함한다.
- 설명 문장은 한국어로 작성하되 지정 영문 용어는 철자·띄어쓰기·대소문자를 canonical 표기로 고정한다.
- 우선 보존 용어는 `interlock`, `wafer`, `lot`, `wafer lot`, `sample wafer`, `production wafer`, `recipe`, `step`, `sensor`, `offline`이다.
- 금지 예시를 함께 제공해 한글 음역이 원문 유지로 오인되지 않게 한다.
- Observer prompt 변경은 prompt version을 올려 분석 provenance에 반영한다.
- 신규 회귀 테스트는 기존 hotspot test class를 키우지 않도록 전용 `test_*.py` 모듈에 둔다.

## 실행 단계
- [x] 공통 영문 업무 용어 guide와 facade export를 추가한다.
- [x] Assistant 답변·Email RAG·제목·요약과 Observer 분석 prompt에 guide를 적용한다.
- [x] prompt 구성과 Observer version 회귀 테스트를 갱신한다.
- [x] 문서와 검증 결과를 반영한다.

## 검증
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint python api manage.py test api.common api.assistant api.observer`
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint python api manage.py makemigrations --check --dry-run`
- `npm run agent:audit`
- 기대 결과: 모든 Assistant system prompt에 canonical/금지 용어가 포함되고 기존 기능 회귀가 없다.

## 위험과 대응
- 위험: prompt 지시만으로 일부 모델이 드물게 음역할 수 있다.
- 대응: 먼저 prompt와 회귀 테스트로 계약을 고정하고, 실제 위반이 계속되면 streaming과 원문 인용을 고려한 별도 출력 정규화를 후속 적용한다.
- 위험: canonical 용어 목록이 업무 변화와 함께 낡을 수 있다.
- 대응: 공통 guide 한 곳에서만 목록을 관리하고 prompt version으로 변경을 추적한다.

## 진행 기록
- 2026-08-14: 공통 canonical guide를 모든 Assistant 출력 경로에 적용하고 강제 문자열 치환은 보류하기로 했다.
- 2026-08-14: 회귀 테스트를 전용 모듈로 분리하고 공통 prompt 결합 helper를 사용해 source hotspot 증가를 제거했다.
- 2026-08-14: 관련 backend 테스트 141건, migration check와 전체 agent audit 통과를 확인했다.
