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
- 상세 진단은 요청 mode와 transport, 응답 shape, token usage를 호출별로 보존한다.
- Airflow DAG는 반복 실패를 원인별로 묶어 발생 건수와 대표 오류를 출력한다.
- 운영 진단 결과 non-stream 응답도 HTTP 200/`finish_reason=stop`이지만 completion token만 소비하고
  최종 `content`가 `null`인 사례가 9% 발생하며, streaming 재시도도 빈 chunk로 종료된다.
- `contents_text`에 인식 가능한 시간 헤더가 없으면 timestamp 형식 강제 prompt와 원문이 충돌할 수 있다.

## 범위
- 수정: `ct_process_comment` selector/service/management command/tests, data movement summary trigger API, Airflow DAG, Django settings, env/docs.
- 제외: Observer UI 구조 변경, 파일 적재 직후 자동 요약 실행, DB schema 변경.

## 설계
- 별도 `OPENWEBUI_*` 설정을 사용해 Assistant LLM 설정과 분리한다.
- 조회 순서는 `updated_at DESC, id DESC`로 고정한다.
- OpenWebUI 호출은 OpenAI 호환 chat completions 응답을 전제로 한다.
- prompt는 고정 출력 형식을 강제한다.
- gpt-oss 요청은 권장 sampling인 `temperature=1.0`, `top_p=1.0`과
  단순 요약에 맞는 `reasoning_effort=low`를 사용한다.
- 응답 확장 필드 제어가 final 채널 변환에 개입하지 않도록 `include_reasoning`은 요청에서 생략하고,
  서비스가 최종 `content`만 추출해 저장한다.
- 시간순 요약에 성공한 row는 `llm_summary`와 `update_flag='N'`을 갱신한다.
- 시간순 요약 이후 핵심요약 또는 검수의 final content만 비어 있으면 시간순 요약을 저장하고
  `llm_core_summary=NULL`로 완료 처리한다.
- `contents_text`에 인식 가능한 시간 헤더가 하나도 없으면 원문 줄바꿈을 유지하면서
  맨 앞에 row의 `create_date` timestamp만 추가한다.
- `create_date`도 비어 있으면 시간을 추정하지 않고 기존 원문 fallback을 유지한다.
- 시간순 요약이나 그 밖의 OpenWebUI 요청에 실패한 row는 `update_flag='Y'`를 유지해 다음 배치에서 재시도한다.
- 처리된 모든 row가 실패한 경우에만 API와 management command를 실패 처리하고,
  일부라도 성공·skip·dry-run이면 실패 상세를 보존한 채 성공 처리한다.
- `contents_text`가 비어 있는 row는 외부 호출 없이 skip하고 flag는 유지한다.
- 로컬 dev는 `adfs_dummy`의 `/v1/chat/completions`를 `OPENWEBUI_URL`로 사용한다.
- 초기 구현에서는 Airflow `data_movement_file_load` DAG가 `load_ct_process_comment` 성공 후 요약 trigger API를 호출했다.
- 오류에는 진단 버전, 요청 mode, attempt, endpoint, model, timeout, HTTP status와 안전한 응답 header,
  JSON 응답 shape를 포함하고 prompt/인증 token/authorization/응답 본문은 포함하지 않는다.
- 요청/응답 모순과 reasoning-only 상태는 `diagnosis_hints`로 자동 분류한다.
- 요약 호출은 non-stream JSON 요청 한 번만 수행하며, SSE parser·응답 방식 fallback·prompt 변경 재시도를 사용하지 않는다.
- 시간순 요약의 빈 final content는 upstream 오류로 반환하고 해당 row의 `update_flag='Y'`를 유지한다.
- 핵심요약 또는 검수의 빈 final content는 경고로 기록하고 시간순 요약만 저장한다.
- completion token을 소비했는데 final content가 없으면 upstream 출력 변환 문제임을 진단 hint로 표시한다.
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
- [x] 단일 non-stream 오류의 transport와 응답 shape 보존
- [x] Airflow 반복 실패 원인 집계 및 대표 오류 출력
- [x] 상세 오류 회귀 테스트와 DAG compile 검증
- [x] streaming parser와 모든 빈 content 재시도 제거
- [x] 운영 실패 응답 shape 회귀 테스트와 검증 실행
- [x] 핵심요약 단계의 빈 content가 시간순 요약 저장을 막지 않도록 부분 성공 처리
- [x] 모든 처리 row가 실패한 경우에만 API와 management command를 실패 처리
- [x] 시간 헤더가 없는 원문에 `create_date` 기본 이벤트 시간 적용

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.data_movement.ct_process_comment api.observer --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run agent:audit:api-boundary`

## 위험과 대응
- 위험: 외부 API 장애가 적재 lifecycle을 막을 수 있다.
- 대응: 파일 적재와 요약을 별도 command로 분리한다.
- 위험: LLM이 입력에 없는 내용을 생성할 수 있다.
- 대응: 고정 prompt와 명시적 "확인 불가" 규칙을 유지하고, 테스트로 요청 계약과 저장 형식을 검증한다.
- 위험: gpt-oss 또는 OpenWebUI 변환 계층이 reasoning token을 생성한 뒤 final content 없이 종료할 수 있다.
- 대응: 애플리케이션에서 reasoning을 요약으로 대체하거나 prompt를 변경하지 않는다. 시간순 요약이 비면 실패 처리하고,
  핵심요약 또는 검수만 비면 시간순 요약을 보존하면서 안전한 진단을 경고로 남긴다.
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
- 2026-08-06: 운영 로그에서 non-stream도 completion token을 소비한 뒤 final content 없이 종료하고,
  streaming 재시도 역시 빈 chunk로 끝나는 upstream final 채널 누락을 확인했다.
- 2026-08-06: upstream Harmony final 누락으로 원인이 확정되어 streaming parser, 응답 방식 fallback,
  `include_reasoning` 제어, final 강제 prompt 재시도를 제거하고 단일 non-stream 호출로 정리했다.
  Django 관련 테스트 101건, Airflow 오류 포맷 테스트 2건, migration check,
  backend boundary audit이 모두 통과했다.
- 2026-08-07: 핵심요약 또는 검수 응답만 비면 `llm_summary`를 저장하고 `llm_core_summary=NULL`로
  완료하도록 변경했으며, 첫 번째 시간순 요약의 빈 응답은 기존 실패 정책을 유지했다.
- 2026-08-07: 일부 row만 실패한 배치는 실패 상세를 유지하면서 성공 처리하고,
  처리된 모든 row가 실패한 경우에만 API 500과 command 오류를 반환하도록 변경했다.
  `api.data_movement` 테스트 144건, migration check, backend boundary audit이 모두 통과했다.
- 2026-08-07: 시간 헤더가 없는 `contents_text`는 원문 맨 앞에 `create_date` timestamp만 추가하도록 변경했다.
  `api.data_movement` 테스트 146건, migration check, backend boundary audit이 모두 통과했다.
