# Emails

[문서 홈](../README.md) · [기능·API](README.md)

- [기능과 흐름](#기능과-흐름)
- [API](#api)

## 기능과 흐름


Emails는 수집한 메일을 권한에 맞는 메일함에서 조회·분류하고, 첨부와 검색 자료를 처리하는 기능입니다.
사용자가 메일을 이동·삭제하면 업무 DB를 갱신하고 검색 자료 반영 작업을 별도로 쌓습니다.
따라서 메일 화면의 변경과 RAG 검색 반영은 완료 시점이 다를 수 있습니다.

먼저 접근 권한을 확인한 뒤 메일 수집 → 검색 반영(Outbox) → 첨부 OCR의 처리 흐름을 읽으면 됩니다.
Outbox는 외부로 전달할 작업을 DB에 보관하는 구조이며, OCR은 이미지에서 텍스트를 추출하는 처리입니다.

### 기능 요약

- POP3 메일 수집
- 메일함 목록/요약/멤버 조회
- 받은 메일/보낸 메일 조회
- 메일 상세/HTML/asset 조회
- 미분류 메일 claim
- 메일 이동/삭제
- OCR 작업 처리
- RAG Outbox 처리

### 권한 기준

메일 접근은 Account가 계산한 `user_sdwt_prod` 접근 범위와 사용자의 `knox_id`를 사용합니다.
Portal 관리자를 포함한 모든 로그인 사용자는 사용자 식별을 위해 유효한
`knox_id`가 있어야 합니다.

- 일반 사용자: Keycloak SDWT 그룹으로 접근 가능한 소속 메일. 본인이 보냈다는 이유만으로 범위를 우회하지 않음
- Emails `admin`: 앱 관리자 역할이며 SDWT 데이터 범위는 별도 검사
- `portal-admin`: 전체 데이터 범위와 관리자 역할로 전체 메일함·`UNASSIGNED` 조회·관리
- Django `is_staff`/`is_superuser`만으로는 전체 메일함 권한을 얻지 않음

### 메일 수집 흐름

1. Airflow 또는 scheduler가 수집 endpoint를 호출합니다.
2. POP3에서 메일을 가져옵니다.
3. 제목 제외 규칙을 적용합니다.
4. 발신자 기준으로 소속을 판단합니다.
5. `Email`을 저장합니다.
6. RAG 작업이 필요하면 `EmailOutbox`에 쌓습니다.

### RAG Outbox 흐름

메일 저장/이동/삭제는 RAG 서버를 즉시 호출하지 않고 Outbox에 작업을 쌓습니다.

- `INDEX`: RAG 문서 등록/갱신
- `DELETE`: RAG 문서 삭제
- `RECLASSIFY`: 재분류
- `RECLASSIFY_ALL`: 전체 재분류

### OCR 흐름

1. OCR worker가 claim endpoint로 작업을 가져갑니다.
2. OCR 처리 후 update endpoint로 결과를 저장합니다.
3. asset별 OCR 상태와 텍스트가 갱신됩니다.

### 부작용

- Email/EmailOutbox DB write
- MinIO asset read/write
- RAG insert/delete
- ActivityLog 기록

### 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/emails/inbox`, `/emails/sent`, `/emails/members` |
| Frontend | `apps/portal/web/src/features/emails` |
| Backend API | `/api/v1/emails/**` |
| 데이터 | `Email`, `EmailAsset`, `EmailOutbox` |
| 외부 연동 | POP3, RAG, MinIO, OCR worker |

### 운영 포인트

- 메일 목록 누락은 Account 접근 권한과 mailbox 소속 분류를 먼저 확인합니다.
- RAG 반영 지연은 `EmailOutbox` 상태와 `process_email_outbox` 실행 결과를 확인합니다.
- 첨부 조회 실패는 MinIO 설정과 asset sequence를 확인합니다.
- OCR 지연은 internal token, claim/update endpoint, asset OCR 상태를 확인합니다.

### 관련 API

- [Emails API](#api)

### 관련 코드

- `apps/portal/api/api/emails/views/`
- `apps/portal/api/api/emails/models.py`
- `apps/portal/api/api/emails/permissions.py`
- `apps/portal/api/api/emails/selectors/`
- `apps/portal/api/api/emails/services/ingest.py`
- `apps/portal/api/api/emails/services/mutations.py`
- `apps/portal/api/api/emails/services/mailbox.py`
- `apps/portal/api/api/emails/services/ocr.py`
- `apps/portal/api/api/emails/services/rag.py`
- `apps/portal/api/api/emails/services/storage.py`
- `apps/portal/web/src/features/emails`

## API


Emails API는 메일함 조회, 메일 처리, POP3 수집, OCR, RAG Outbox 처리를 제공합니다.

### 호출자

- 브라우저 SPA
- Airflow 또는 scheduler
- OCR worker

### 인증

| API | 인증 |
| --- | --- |
| 일반 메일 조회/이동/삭제 | Django session, Portal·`emails` 앱 접근, SDWT 데이터 등급 |
| POP3 수집/Outbox 처리 | Airflow Bearer token |
| OCR claim/update | `X-Internal-Token` |

### Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/emails/inbox/` | 받은 메일 목록 |
| GET | `/api/v1/emails/sent/` | 보낸 메일 목록 |
| GET | `/api/v1/emails/mailboxes/` | 접근 가능한 메일함 |
| GET | `/api/v1/emails/mailboxes/summary/` | 메일함 접근 요약 |
| GET | `/api/v1/emails/mailboxes/members/` | 메일함 멤버 |
| GET | `/api/v1/emails/unassigned/` | 내 미분류 메일 수 |
| POST | `/api/v1/emails/unassigned/claim/` | 미분류 메일 가져오기 |
| POST | `/api/v1/emails/move/` | 메일 이동 |
| POST | `/api/v1/emails/bulk-delete/` | 메일 여러 건 삭제 |
| GET/DELETE | `/api/v1/emails/<email_id>/` | 메일 상세/삭제 |
| GET | `/api/v1/emails/<email_id>/html/` | HTML 본문 |
| GET | `/api/v1/emails/<email_id>/assets/<sequence>/` | 첨부/이미지 asset |
| POST | `/api/v1/emails/ingest/` | POP3 수집 |
| POST | `/api/v1/emails/outbox/process/` | RAG Outbox 처리 |
| POST | `/api/v1/emails/assets/ocr/claim/` | OCR 작업 claim |
| POST | `/api/v1/emails/assets/ocr/update/` | OCR 결과 update |

### 메일 목록 쿼리

```http
GET /api/v1/emails/inbox/?userSdwtProd=G-A&q=report&page=1&pageSize=20
```

| Query | 설명 |
| --- | --- |
| `userSdwtProd` | 메일함 필터 |
| `q` | 검색어 |
| `sender` | 발신자 필터 |
| `recipient` | 수신자 필터 |
| `dateFrom`, `dateTo` | 날짜/시간 필터 |
| `page`, `pageSize` | 페이지네이션 |

브라우저 메일 목록 query와 이동·삭제 JSON은 camelCase를 사용하며 제거된 snake_case alias는 400 `invalid_request`로 거부합니다.
내부 OCR claim·update 요청은 아래의 snake_case 계약을 사용합니다.

### 메일 이동

```json
{
  "emailIds": [1, 2, 3],
  "toUserSdwtProd": "G-B"
}
```

동작:

1. 원본 메일 접근 권한을 확인합니다.
2. 대상 소속 접근 권한을 확인합니다.
3. 메일 소속을 변경합니다.
4. RAG 재인덱싱 작업을 Outbox에 쌓습니다.

### POP3 수집

```http
POST /api/v1/emails/ingest/
Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>
```

동작:

1. POP3 mailbox에서 메일을 읽습니다.
2. 발신자 기준으로 소속을 분류합니다.
3. `Email`에 저장합니다.
4. 필요한 RAG 작업을 Outbox에 쌓습니다.

### OCR 작업

```http
POST /api/v1/emails/assets/ocr/claim/
X-Internal-Token: <EMAIL_OCR_INTERNAL_TOKEN>
```

claim body는 선택이며 `limit`, `lease_seconds`, `worker_id`를 받습니다.

```json
{
  "limit": 50,
  "lease_seconds": 1800,
  "worker_id": "ocr-worker-01"
}
```

응답의 `tasks`에는 `asset_id`, `email_id`, `lock_token`, `lock_expires_at` 등 작업 정보가 포함됩니다.
update 요청에는 claim에서 받은 `asset_id`와 `lock_token`을 그대로 전달합니다.

```http
POST /api/v1/emails/assets/ocr/update/
X-Internal-Token: <EMAIL_OCR_INTERNAL_TOKEN>
```

```json
{
  "results": [
    {
      "asset_id": 1,
      "lock_token": "<claim 응답의 토큰>",
      "status": "DONE",
      "text": "추출한 텍스트"
    }
  ]
}
```

각 항목의 필수 필드는 `asset_id`, `lock_token`, `status`이며 status는 `DONE` 또는 `FAILED`입니다.
선택 필드는 `text`, `error_code`, `error_message`, `ocr_model`, `ocr_duration_ms`, `processed_at`입니다.
응답은 `updated`, `rejected`, `ragQueued`, `ragFailed`, `ragSkipped`를 반환합니다.

### 오류

오류 body는 `code`, `message`, `details`, `fieldErrors`를 갖는 공통 형식을 사용합니다.

| Status | 상황 |
| --- | --- |
| 400 | 잘못된 query/body |
| 401 | 인증 필요 또는 token 오류 |
| 403 | 메일함/메일 접근 권한 없음 |
| 404 | 메일 또는 asset 없음 |
| 500 | 수집/저장 실패 |
| 502 | RAG/Mail 외부 호출 실패 |

### 관련 모듈 문서

- [Emails 모듈](#기능과-흐름)
