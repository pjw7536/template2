# ExecPlan: ct_process_comment OpenWebUI summary batch

## 목표
- `ct_process_comment.update_flag='Y'` row를 최근 업데이트 순으로 OpenWebUI에 요약 요청한다.
- 성공 시 `llm_summary`를 저장하고 `update_flag='N'`으로 변경한다.
- Observer CTTTM log detail에서 기존 `summary` 필드로 저장된 요약을 사용한다.

## 현재 상태
- `ct_process_comment`에는 `contents_text`, `llm_summary`, `update_flag`, `updated_at` 컬럼이 있다.
- loader는 신규/변경 row의 `update_flag`를 `Y`로 설정하고, `contents_text` 변경 시 `llm_summary`를 `NULL`로 초기화한다.
- Observer CTTTM selector는 `ct_process_comment.llm_summary as summary`를 이미 조회한다.
- CTTTM detail UI는 `log.summary`를 이미 표시한다.
- OpenWebUI가 `stream=false` 요청에도 `chat.completion.chunk`와 빈 `content`를 반환하는지
  현재 Airflow 오류만으로는 구분할 수 없다.
- non-stream 최초 오류 후 streaming 재시도가 실패하면 최초 오류 정보가 최종 예외에서 유실된다.
- Airflow DAG는 실패 outcome 전체를 JSON으로 만든 뒤 4,000자로 잘라 반복 오류의 핵심 진단이 유실될 수 있다.

## 범위
- 수정: `ct_process_comment` selector/service/management command/tests, data movement summary trigger API, Airflow DAG, Django settings, env/docs.
- 제외: Observer UI 구조 변경, 파일 적재 직후 자동 요약 실행, DB schema 변경.

## 설계
- 별도 `OPENWEBUI_*` 설정을 사용해 Assistant LLM 설정과 분리한다.
- 조회 순서는 `updated_at DESC, id DESC`로 고정한다.
- OpenWebUI 호출은 OpenAI 호환 chat completions 응답을 전제로 한다.
- prompt는 고정 출력 형식을 강제한다.
- gpt-oss 요청은 권장 sampling인 `temperature=1.0`, `top_p=1.0`과
  `reasoning_effort=low`를 사용해 reasoning-only 종료를 줄인다.
- reasoning 계산은 유지하되 응답에는 `include_reasoning=false`를 적용해 최종 content만 저장한다.
- 성공 row만 `llm_summary`와 `update_flag='N'`을 갱신한다.
- 실패 row는 `update_flag='Y'`를 유지해 다음 배치에서 재시도한다.
- `contents_text`가 비어 있는 row는 외부 호출 없이 skip하고 flag는 유지한다.
- 로컬 dev는 `adfs_dummy`의 `/v1/chat/completions`를 `OPENWEBUI_URL`로 사용한다.
- 초기 구현에서는 Airflow `data_movement_file_load` DAG가 `load_ct_process_comment` 성공 후 요약 trigger API를 호출했다.
- 오류에는 진단 버전, 요청 mode, attempt, endpoint, model, timeout, HTTP status와 안전한 응답 header,
  JSON 응답 shape를 포함하고 prompt/인증 token/authorization/응답 본문은 포함하지 않는다.
- 요청/응답 모순과 reasoning-only 상태는 `diagnosis_hints`로 자동 분류한다.
- non-stream과 streaming이 모두 실패하면 두 attempt의 오류를 하나의 최종 오류에 순서대로 보존한다.
- Airflow는 반복 실패를 원인별로 집계해 발생 건수, 대표 오류, workorder 샘플을 출력한다.

## 실행 단계
- [x] ExecPlan 작성
- [x] OpenWebUI settings/env/docs 추가
- [x] pending summary selector 추가
- [x] OpenWebUI 요약 service 추가
- [x] `summarize_ct_process_comment` command 추가
- [x] Airflow summary trigger API/DAG 추가
- [x] 테스트 추가/수정
- [x] 검증 명령 실행
- [x] gpt-oss 권장 sampling 및 low reasoning 요청 계약 적용
- [x] reasoning-only 회귀 테스트와 migration/boundary 검증 실행
- [x] OpenWebUI transport/response 진단 정보 보강
- [x] 최초 non-stream 오류와 streaming 재시도 오류 동시 보존
- [x] Airflow 반복 실패 원인 집계 및 대표 오류 출력
- [x] 상세 오류 회귀 테스트와 DAG compile 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.data_movement.ct_process_comment api.observer --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run agent:audit:api-boundary`

## 위험과 대응
- 위험: 외부 API 장애가 적재 lifecycle을 막을 수 있다.
- 대응: 파일 적재와 요약을 별도 command로 분리한다.
- 위험: LLM이 입력에 없는 내용을 생성할 수 있다.
- 대응: 고정 prompt와 명시적 "확인 불가" 규칙을 유지하고, 테스트로 요청 계약과 저장 형식을 검증한다.
- 위험: gpt-oss가 reasoning만 생성하고 final content 없이 종료할 수 있다.
- 대응: 공식 권장 sampling과 `reasoning_effort=low`를 요청 최상위 파라미터로 전달한다.
- 위험: 실패 row가 처리 완료로 잘못 표시될 수 있다.
- 대응: 성공 응답을 받은 row만 `update_flag='N'`으로 변경한다.
- 위험: 상세 오류에 prompt, 응답 본문, 인증 token이 노출될 수 있다.
- 대응: allowlist 기반 transport header와 타입/길이/필드명만 기록하고 본문과 인증값은 기록하지 않는다.
- 위험: 반복 오류 100건이 Airflow 오류 길이 제한을 소진할 수 있다.
- 대응: 원인별 발생 건수와 대표 오류 한 건으로 집계하고 생략된 원인 그룹 수를 명시한다.

## 진행 기록
- 2026-07-06: 사용자 결정에 따라 command 분리, `OPENWEBUI_*` 별도 설정, `updated_at DESC, id DESC` 순서로 계획했다.
- 2026-07-06: OpenWebUI 요약 service/command/env/docs/tests를 추가했고 대상 테스트, migration check, backend boundary audit을 통과했다.
- 2026-07-06: Airflow 주기 실행을 위해 `ct_process_comment/summarize/` trigger API와 DAG task를 추가했다.
- 2026-07-06: 요약 trigger는 별도 `ct_process_comment_summary` DAG로 분리했다.
- 2026-08-06: gpt-oss reasoning-only 응답 대응을 위해 권장 sampling과 명시적 low reasoning 요청 계약으로 변경했다.
- 2026-08-06: `ct_process_comment` 테스트 41건, migration check, backend boundary audit이 모두 통과했다.
- 2026-08-06: 동일 빈 content 오류 재발에 따라 시도별 transport 진단과 Airflow 실패 집계를 보강하기로 했다.
- 2026-08-06: 진단 버전 `ctpc-openwebui-v2`, 두 attempt의 안전한 transport/response metadata,
  반복 실패 원인별 대표 오류를 추가했다.
- 2026-08-06: Django 관련 테스트 52건, Airflow 오류 포맷 테스트 2건, migration check,
  Python compile, backend boundary audit이 모두 통과했다.
