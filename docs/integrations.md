# 외부 연동 계약

이 문서는 앱이 외부 시스템과 통신하는 방식을 정리합니다. 로컬 개발에서는 대부분 `apps/adfs_dummy`가 외부 시스템을 대체합니다.

## 연동 목록

| 연동 | 사용 모듈 | 로컬 대체 |
| --- | --- | --- |
| ADFS/OIDC | Auth | `apps/adfs_dummy` |
| RAG | Emails, Assistant | `apps/adfs_dummy` |
| LLM | Assistant | `apps/adfs_dummy` |
| Mail API | Emails, Drone | `apps/adfs_dummy` |
| Jira | Drone | `apps/adfs_dummy` |
| Knox Messenger | Drone/Common | 설정 기반 |
| MinIO | Emails/Common | `minio` service |
| Airflow | Account/Emails/Drone trigger | Bearer token |

## 참고 문서

| 문서 | 용도 |
| --- | --- |
| `docs/integrations/proxy-mirrors.md` | 외부 package repository public URL과 내부 proxy mirror 이름 매핑 |

## 로컬 dummy 외부계

`apps/adfs_dummy`는 로컬 개발에서 다음 역할을 대체합니다.

| 파일 | 역할 |
| --- | --- |
| `apps/adfs_dummy/adfs_oidc.py` | OIDC authorize/logout/callback 보조 |
| `apps/adfs_dummy/adfs_rag.py` | RAG search/insert/delete/index-info |
| `apps/adfs_dummy/adfs_llm.py` | LLM chat completions |
| `apps/adfs_dummy/adfs_mail.py` | Mail send와 dummy mail messages |
| `apps/adfs_dummy/adfs_jira.py` | Jira issue 대체 |
| `apps/adfs_dummy/adfs_stores.py` | dummy 저장소 |

## ADFS/OIDC

주요 설정:

- `OIDC_CLIENT_ID`
- `OIDC_ISSUER`
- `ADFS_AUTH_URL`
- `ADFS_LOGOUT_URL`
- `OIDC_REDIRECT_URI`
- `ADFS_CER_PATH`
- `ALLOWED_REDIRECT_HOSTS`

로컬 인증은 `http://localhost:8180`의 Keycloak 26.7.1을 사용합니다. `http://localhost:9102` 서비스는 RAG/LLM/Mail/Jira dummy만 제공합니다.

## RAG

사용 위치:

- Emails: 메일 문서 insert/delete
- Assistant: 질문 검색

주요 설정:

- `ASSISTANT_RAG_URL`, `RAG_SEARCH_URL`
- `ASSISTANT_RAG_INSERT_URL`, `RAG_INSERT_URL`
- `ASSISTANT_RAG_DELETE_URL`, `RAG_DELETE_URL`
- `RAG_INDEX_DEFAULT`, `RAG_INDEX_EMAILS`, `RAG_INDEX_LIST`
- `ASSISTANT_RAG_PERMISSION_GROUPS`, `RAG_PERMISSION_GROUPS`
- `ASSISTANT_REQUEST_TIMEOUT`

## Email RAG 답변 prompt

Assistant가 RAG 검색 결과를 OpenWebUI에 전달할 때 Email 구조화 답변 prompt를 적용합니다.

주요 설정:

- `ASSISTANT_LLM_TEMPERATURE`
- `ASSISTANT_LLM_SYSTEM_MESSAGE`

## OpenWebUI

일반 Assistant와 Email RAG 답변, Observer 분석 및 `ct_process_comment` 요약 배치는 OpenWebUI의 OpenAI 호환 chat completions API를 사용합니다.

주요 설정:

- `OPENWEBUI_URL`
- `OPENWEBUI_API_TOKEN`
- `OPENWEBUI_MODEL`
- `OPENWEBUI_COMMON_HEADERS`
- `OPENWEBUI_TIMEOUT_SECONDS`
- `OPENWEBUI_SUMMARY_BATCH_SIZE`

사용처:

- 메일함 외 전역 ChatWidget과 `/assistant`의 일반 대화 SSE stream
- Email RAG 검색 결과의 구조화 `answer`/`segments` 답변 생성
- Assistant 첫 대화의 업무용 대화방 제목 생성
- Assistant 대화방의 Portal 앱·Observer·Email RAG 공유 rolling summary
- Observer 현재 조회 데이터 구조화 분석
- `ct_process_comment` contents 요약 배치

Assistant Runtime은 외부 OpenAI 호환 요청에 `stream: true`를 보내고 `/api/v1/assistant/turns/stream`의 표준 SSE event로 정규화합니다. Nginx는 이 Turn 경로의 buffering/cache를 꺼야 합니다. 로컬 `adfs_dummy`도 `data: {...}`와 `[DONE]` chunk를 반환하며, system prompt에 따라 Email은 `answer`/`segments`, Observer는 분석 JSON 단일 계약을 생성합니다.

## Mail API

Emails와 Drone이 Knox Mail API를 호출할 수 있습니다.

주요 설정:

- `MAIL_API_URL`
- `MAIL_API_KEY`
- `MAIL_API_SYSTEM_ID`
- `MAIL_API_KNOX_ID`
- `DRONE_MAIL_*`

## Jira

Drone SOP 알림에서 Jira issue 생성 또는 업데이트에 사용합니다.

주요 설정:

- `DRONE_JIRA_BASE_URL`
- `DRONE_JIRA_TOKEN`
- `DRONE_JIRA_ISSUE_TYPE`
- `DRONE_JIRA_USE_BULK_API`
- `DRONE_JIRA_BULK_SIZE`

## MinIO

메일 asset 저장/조회에 사용합니다.

주요 설정:

- `MINIO_ENDPOINT`
- `MINIO_BUCKET`
- `MINIO_REGION`
- `MINIO_ROOT_USER`
- `MINIO_ROOT_PASSWORD`

## Airflow trigger

외부 scheduler가 호출하는 endpoint는 Bearer token으로 보호합니다.

```http
Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>
```

사용 예:

- 외부 소속 동기화
- Emails POP3 수집
- Emails Outbox 처리
- Drone SOP 수집/파이프라인

## Grist OSS Work Hub

Self-hosted Grist OSS 1.7.13의 공식 REST API, Webhook, forward-auth를 사용합니다. 브라우저 인증은 Grist 전용 boot key/OIDC가 아니라 Portal session의 `account.User` PK를 짧게 서명하고 Nginx 내부 검증이 반환한 account email을 신뢰 header로 전달합니다. Grist container 포트는 host에 직접 노출하지 않고 일반 proxy 경로에서 외부 `X-Forwarded-User`를 제거합니다. API key는 server-to-server 작업에만 주입하며 브라우저는 group별 document launch URL만 받습니다. document access API로 Portal `viewer/member/manager`를 `viewers/editors/owners`에 동기화하고, account 변경은 Outbox에 적재해 Grist 장애와 Portal transaction을 분리합니다.

주요 설정:

- `GRIST_API_URL`
- `GRIST_API_KEY`
- `GRIST_PUBLIC_URL`
- `GRIST_WEBHOOK_CALLBACK_URL`
- `GRIST_WEBHOOK_SECRET`
- `GRIST_ALLOWED_LAUNCH_HOSTS`
- `WORK_HUB_ENABLED`

## 연동 변경 체크리스트

| 변경 | 함께 확인할 문서/파일 |
| --- | --- |
| OIDC provider 변경 | `env/api*.env`, `env/web*.env`, `apps/adfs_dummy/adfs_oidc.py`, `docs/api/auth.md` |
| RAG endpoint/schema 변경 | `env/api*.env`, `apps/adfs_dummy/adfs_rag.py`, `docs/api/assistant.md`, `docs/modules/emails.md` |
| LLM request/response 변경 | `env/api*.env`, `apps/adfs_dummy/adfs_llm.py`, `docs/modules/assistant.md` |
| OpenWebUI request/response 변경 | `env/api*.env`, `apps/adfs_dummy/adfs_llm.py`, `docs/modules/assistant.md`, `docs/api/assistant.md`, `docs/modules/observer.md`, `docs/api/observer.md` |
| Mail API 변경 | `env/api*.env`, `apps/adfs_dummy/adfs_mail.py`, `docs/modules/emails.md`, `docs/modules/line-dashboard.md` |
| Jira 변경 | `env/api*.env`, `apps/adfs_dummy/adfs_jira.py`, `docs/modules/line-dashboard.md` |
| MinIO 변경 | `env/minio.env`, `docs/data-model.md`, `docs/modules/emails.md` |
| Airflow token/trigger 변경 | `env/api*.env`, 관련 `docs/api/*.md`, `docs/operations.md` |
| Grist image/API/schema/forward-auth/widget 변경 | `compose/*.work-hub.yml`, `compose/*.app.yml`, `deploy/grist/plugins/*`, `deploy/nginx/default*.conf`, `env/api*.env`, `env/grist.common.env`, `docs/modules/work-hub.md`, `docs/api/work-hub.md` |
