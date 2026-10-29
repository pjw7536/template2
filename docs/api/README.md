# API 공통 호출 규칙

[문서 홈](../README.md) · [기능 안내](../modules/README.md) · [API 개발](../development/02-backend.md)

API 호출을 작성하거나 기존 요청을 바꿀 때 사용하는 명세입니다.
공통 인증·입력·응답 규칙을 읽은 뒤 [모듈별 API 문서](#모듈별-api-문서)에서 method·path·입출력을 확인합니다.
업무의 목적과 화면 동작은 기능 안내에 있습니다.

## 호출 전에 확인할 순서

1. 호출할 환경의 주소와 해당 API의 method·path를 확인합니다.
2. 세션·Bearer·Internal token 중 해당 endpoint의 인증 방식을 확인합니다.
3. query·body의 필수값과 정확한 필드 표기를 따릅니다. API마다 입력·응답 형태가 다를 수 있습니다.
4. 성공 응답뿐 아니라 권한 오류·실패 조건과 DB 변경·외부 발송 여부를 확인합니다.

로그인 성공과 업무 권한 허용은 별도입니다. 브라우저 업무 API는 로그인 세션에 더해 앱 접근과
해당 기능의 데이터 범위를 검사합니다. 세부 규칙은 [Account](../modules/02-account.md)를 확인합니다.

## Base URL

`make dev`로 실행한 로컬 환경은 Portal과 같은 주소로 API를 호출합니다.

```text
http://localhost:8080
```

예를 들어 Health 조회 주소는 `http://localhost:8080/api/v1/health/`입니다.
포트를 변경했다면 [로컬 실행 안내](../../local/README.md)의 접속 주소를 사용하세요.

업무 API prefix:

```text
/api/v1
```

예외:

```text
/auth/keycloak/callback/
```

Keycloak이 authorization code와 state를 GET query로 전달하는 callback입니다.

## 인증 방식

| 방식 | 사용처 | 설명 |
| --- | --- | --- |
| Django session | 일반 웹 API | OIDC 로그인 후 브라우저 쿠키 기반 |
| Airflow Bearer token | 수집/동기화 trigger | `Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>` |
| Internal token | OCR worker | `X-Internal-Token: <EMAIL_OCR_INTERNAL_TOKEN>` |
| 공개 | Auth 설정·로그인, Health | 인증 없이 접근 가능 |

일반 업무 API는 세션 인증 외에 Portal·해당 앱의 `scopeAccess.allowed`를 검사합니다.
Observer·AppStore·VOC의 GET도 보호 대상입니다. Activity 통계·로그 조회는 `access-stats` scope를
검사하고, 활동 로그는 Django 조회 permission도 추가로 요구합니다. Bearer/Internal token 전용
endpoint는 별도 인증을 적용합니다.

## API 문서 작성 단위

각 endpoint에서 method·path·인증·입력·응답·오류·부작용을 확인할 수 있어야 합니다.
[작성·유지보수 기준](../development/04-documentation.md#설명의-기본-순서)을 따르며,
전체 endpoint 이름은 [API 경로 색인](../reference/02-inventory.md#백엔드-api-route)에서 찾습니다.

## 요청 형식

대부분의 write API는 JSON body를 사용합니다.

```http
Content-Type: application/json
```

일반 업무 API는 canonical camelCase를 사용하며 지원하지 않는 별칭은 허용하지 않습니다.
L3 Spider 설정 CRUD는 snake_case 등 별도 계약이 있으므로 모듈별 표기를 따릅니다.

## 응답 형식

기본 응답은 JSON입니다.

```json
{
  "results": []
}
```

파일/이미지 endpoint는 바이너리 또는 redirect를 반환할 수 있습니다.

목록 응답은 모듈별로 다음 중 하나를 사용합니다.

| 형태 | 예 |
| --- | --- |
| 단순 목록 | `{ "results": [] }` |
| 페이지 목록 | `{ "results": [], "page": 1, "pageSize": 20, "total": 100 }` |
| 요약 포함 | `{ "results": [], "summary": {} }` |
| 단건 객체 | `{ "id": 1, ... }` |
| 파일/HTML | binary, redirect, HTML response |

일반 업무 오류는 `code`, `message`, `details`, `fieldErrors`를 사용합니다.
Spider API는 기존 `error` 계약을 유지하며 DRF 입력 검증 응답도 endpoint에 따라 다릅니다.

## 공통 오류

| Status | 의미 |
| --- | --- |
| 400 | 잘못된 요청 body/query |
| 401 | 인증 필요 |
| 403 | 권한 없음 |
| 404 | 대상 없음 |
| 409 | 현재 상태와 맞지 않는 요청 |
| 410 | Keycloak 관리로 종료된 Account 변경 경로 |
| 500 | 서버 처리 실패 |
| 502 | 외부 연동 실패 |
| 503 | 필수 외부 연동 설정 누락 |

## Side effect 분류

| 분류 | 해당 모듈 |
| --- | --- |
| DB write | Auth 사용자 갱신, Activity, Assistant, Emails, Drone, AppStore, VOC, Data Movement, L3 설정 |
| 외부 read/search | Assistant/RAG, Activity 외부 사용량, Drone/Airflow |
| 외부 write/send | Emails RAG, Drone Jira/Mail/Messenger, Assistant OpenWebUI |
| 파일/asset | Emails, AppStore |
| ActivityLog | Account 일부 작업, Emails 이동/삭제, Drone table update, VOC |

## 모듈별 API 문서

| 문서 | 제공 기능 |
| --- | --- |
| [Auth](01-auth.md) | 로그인·로그아웃·현재 세션 |
| [Account](02-account.md) | 계정·권한 조회와 사용자 검색 |
| [Emails](03-emails.md) | 메일함, 메일 처리, 수집, OCR |
| [Assistant](04-assistant.md) | AI 대화, 스트리밍, 대화방 관리 |
| [Line Dashboard / Drone](05-line-dashboard.md) | 라인 현황, SOP, 알림 대상·수신자 |
| [Observer](06-observer.md) | 설비 기준정보·로그·분석 근거 조회 |
| [L0 Spider](07-l0-spider.md) | FDC Hard Limit 추천 조회 |
| [L3 Spider](08-l3-spider.md) | 이상감지 결과, 제외 조건, 메일 규칙 |
| [PM SPIDER](09-pm-spider.md) | PM 주기 비교와 Trace/OES 조회 |
| [TTTM Spider](10-tttm-spider.md) | 비교·참조 조건의 score와 파형 조회 |
| [AppStore](11-appstore.md) | 내부 앱, 댓글, 좋아요 |
| [VOC](12-voc.md) | 문의·개선 요청과 답변 |
| [Activity / Health](13-activity-health.md) | 활동 로그, 접속 통계, 프로세스 상태 |
| [Data Movement](14-data-movement.md) | 파일 적재와 공정 comment 요약 트리거 |
