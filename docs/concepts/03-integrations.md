# 외부 연동 계약

[문서 홈](../README.md) · [처음 시작하기](../getting-started/01-setup.md) · [개발 작업 흐름](../getting-started/02-usage.md)

Portal은 로그인, 검색·답변 생성, 메일·알림 전송 등에 별도 서비스를 사용합니다.
개발 PC에서는 실제 사내 연결 대신 Keycloak·MinIO·Airflow와 `local/adfs_dummy`를 사용합니다.
mock은 개발용 응답을 제공하며 실제 사내 서비스의 모든 동작을 검증하는 것은 아닙니다.

아래에서 서비스 역할과 사용하는 설정 이름을 찾을 수 있습니다.
각 연동의 설정 키 의미·형식은 [환경 설정](../reference/01-configuration.md#주요-설정-그룹),
각 요청의 상세 입출력은 [API 명세](../features/README.md#공통-api-호출-규칙)를 확인합니다.

## 연동 목록

| 연동 | 사용 모듈 | 로컬 대체 |
| --- | --- | --- |
| Keycloak/OIDC | Auth | `local/keycloak`와 upstream IdP mock `local/adfs_dummy` |
| RAG | Emails, Assistant | `local/adfs_dummy` |
| LLM | Assistant | `local/adfs_dummy` |
| Mail API | Emails, Drone | `local/adfs_dummy` |
| Jira | Drone | `local/adfs_dummy` |
| Knox Messenger | Drone/Common | 설정 기반 |
| MinIO | Emails/Common | `minio` service |
| Airflow | Emails/Drone/Data Movement/L3 예약 작업 | 로컬 Airflow와 공유 Bearer token |

## 로컬 dummy 외부계

`local/adfs_dummy`는 로컬 개발에서 다음 역할을 대체합니다.

| 파일 | 역할 |
| --- | --- |
| `local/adfs_dummy/adfs_oidc.py` | OIDC authorize/logout/callback 보조 |
| `local/adfs_dummy/adfs_rag.py` | RAG search/insert/delete/index-info |
| `local/adfs_dummy/adfs_llm.py` | LLM chat completions |
| `local/adfs_dummy/adfs_mail.py` | Mail send와 dummy mail messages |
| `local/adfs_dummy/adfs_jira.py` | Jira issue 대체 |
| `local/adfs_dummy/adfs_stores.py` | dummy 저장소 |

## Keycloak/OIDC

Portal은 Keycloak에 authorization code + PKCE로 로그인합니다. 로컬 Keycloak은
`http://localhost:8180`에 노출되며 API는 cluster 내부 token/JWKS URL을 호출합니다.
`local/adfs_dummy`는 Keycloak의 upstream IdP와 업무 외부계를 대체합니다. 앱 역할과 SDWT 그룹은
검증된 Keycloak 토큰에서 세션에 저장하며, DB 권한 행으로 대체하지 않습니다.

설정: `OIDC_*`, `ALLOWED_REDIRECT_HOSTS` ([설정 그룹](../reference/01-configuration.md#주요-설정-그룹))

## RAG

사용 위치:

- Emails: 메일 문서 insert/delete
- Assistant: 질문 검색

provider endpoint와 인증 header는 운영의 `deploy/portal/env/prod/api.env`에서 주입합니다. 로컬은 `local/portal/env/api.env`와 Kubernetes override를 합성합니다.

설정: `RAG_*`, `ASSISTANT_REQUEST_TIMEOUT` ([설정 그룹](../reference/01-configuration.md#주요-설정-그룹))

## Email RAG 답변 prompt

Assistant가 RAG 검색 결과를 OpenWebUI에 전달할 때 Email 구조화 답변 prompt를 적용합니다.

설정: `ASSISTANT_LLM_TEMPERATURE`, `ASSISTANT_LLM_SYSTEM_MESSAGE` ([설정 그룹](../reference/01-configuration.md#주요-설정-그룹))

## OpenWebUI

일반 Assistant와 Email RAG 답변, Observer 분석 및 `ct_process_comment` 요약 배치는 OpenWebUI의 OpenAI 호환 chat completions API를 사용합니다.

설정: `OPENWEBUI_*` ([설정 그룹](../reference/01-configuration.md#주요-설정-그룹))

사용처:

- 메일함 외 전역 ChatWidget과 `/assistant`의 일반 대화 SSE stream
- Email RAG 검색 결과의 구조화 `answer`/`segments` 답변 생성
- Assistant 첫 대화의 업무용 대화방 제목 생성
- Assistant 대화방의 Profile별 기억 partition에 저장하는 장기 요약
- Observer 현재 조회 데이터 구조화 분석
- `ct_process_comment` contents 요약 배치

Assistant Runtime은 외부 OpenAI 호환 요청에 `stream: true`를 보내고 `/api/v1/assistant/turns/stream`의 표준 SSE event로 정규화합니다. Nginx는 이 Turn 경로의 buffering/cache를 꺼야 합니다. 로컬 `adfs_dummy`도 `data: {...}`와 `[DONE]` chunk를 반환하며, system prompt에 따라 Email은 `answer`/`segments`, Observer는 분석 JSON 단일 계약을 생성합니다.

## Mail API

Emails와 Drone이 Knox Mail API를 호출할 수 있습니다.

설정: `MAIL_API_*`, `DRONE_MAIL_*` ([설정 그룹](../reference/01-configuration.md#주요-설정-그룹))

## Jira

Drone SOP 알림에서 Jira issue 생성 또는 업데이트에 사용합니다.

설정: `DRONE_JIRA_*` ([설정 그룹](../reference/01-configuration.md#주요-설정-그룹))

## MinIO

메일 asset 저장/조회에 사용합니다.

설정: `MINIO_ENDPOINT`, `MINIO_BUCKET`, `MINIO_REGION`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` ([설정 그룹](../reference/01-configuration.md#주요-설정-그룹))

위 값은 Portal API의 S3 client 입력입니다. MinIO 서버·초기화 Job은 별도의
`MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`를 사용하며 두 입력의 역할을 혼동하지 않습니다.

## Airflow trigger

외부 scheduler가 호출하는 endpoint는 Bearer token으로 보호합니다.

```http
Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>
```

사용 예:

- Data Movement 파일 적재·CTTTM 요약
- L3 Spider 예약 메일 발송
- Emails POP3 수집
- Emails Outbox 처리
- Drone SOP 수집/파이프라인

## 연동 변경 체크리스트

| 변경 | 함께 확인할 문서/파일 |
| --- | --- |
| OIDC provider 변경 | `deploy/portal/env/prod/api.env`, `local/portal/env/`, `local/keycloak/`, `local/adfs_dummy/adfs_oidc.py`, [Auth API](../features/01-auth.md#api) |
| RAG endpoint/schema 변경 | `deploy/portal/env/*/api.env`, `local/adfs_dummy/adfs_rag.py`, [Assistant API](../features/04-assistant.md#api), [Emails 모듈](../features/03-emails.md#기능과-흐름) |
| LLM request/response 변경 | `deploy/portal/env/*/api.env`, `local/adfs_dummy/adfs_llm.py`, [Assistant / OpenWebUI / RAG 모듈](../features/04-assistant.md#기능과-흐름) |
| OpenWebUI request/response 변경 | `deploy/portal/env/*/api.env`, `local/adfs_dummy/adfs_llm.py`, [Assistant / OpenWebUI / RAG 모듈](../features/04-assistant.md#기능과-흐름), [Assistant API](../features/04-assistant.md#api), [Observer 모듈](../features/06-observer.md#기능과-흐름), [Observer API](../features/06-observer.md#api) |
| Mail API 변경 | `deploy/portal/env/*/api.env`, `local/adfs_dummy/adfs_mail.py`, [Emails 모듈](../features/03-emails.md#기능과-흐름), [Line Dashboard / Drone 모듈](../features/05-line-dashboard.md#기능과-흐름) |
| Jira 변경 | `deploy/portal/env/*/api.env`, `local/adfs_dummy/adfs_jira.py`, [Line Dashboard / Drone 모듈](../features/05-line-dashboard.md#기능과-흐름) |
| MinIO 변경 | `deploy/minio/env/prod.env`, `local/minio/env/minio.env`, Portal의 `api.env`에 있는 client 설정, [데이터 모델과 저장소](02-data-model.md), [Emails 모듈](../features/03-emails.md#기능과-흐름) |
| Observer 기준정보·로그 계약 변경 | `deploy/portal/env/*/api.env`, `local/portal/env/api.env`, [Observer 모듈](../features/06-observer.md#기능과-흐름), [데이터 모델](02-data-model.md) |
| L3 Spider 데이터 경로 변경 | [파일 데이터 마운트 규칙](../reference/01-configuration.md#파일-데이터-마운트-규칙)의 동기화 파일, [L3 Spider](../features/08-l3-spider.md), [구현 색인](../reference/02-inventory.md) |
| Airflow token/trigger 변경 | `deploy/portal/env/*/api.env`, `deploy/airflow/env/*.env`, 관련 `docs/features/*.md`, [운영/개발 명령](../reference/03-operations.md) |
