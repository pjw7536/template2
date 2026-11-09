# 기능·API

[문서 홈](../README.md)

- [기능 찾기](#기능-찾기)
- [공통 API 호출 규칙](#공통-api-호출-규칙)

## 기능 찾기


각 기능 문서에서 화면·권한·처리 흐름과 API 계약을 함께 확인합니다.
표의 Web 경로는 `apps/portal/web/src/features/` 기준입니다.
실제 URL·모델·명령 이름은 [구현 색인](../reference/02-inventory.md)에 있습니다.

| 기능 | 설명·API | Web feature | API app |
| --- | --- | --- | --- |
| 로그인·세션 확인 | [Auth](01-auth.md#기능과-흐름) | `auth` | `api.auth` |
| 계정·앱 접근·데이터 범위 확인 | [Account](02-account.md#기능과-흐름) | `account` | `api.account` |
| 메일 조회·분류·OCR·검색 자료 반영 | [Emails](03-emails.md#기능과-흐름) | `emails` | `api.emails` |
| 일반 대화·메일 검색·업무 화면 AI 분석 | [Assistant](04-assistant.md#기능과-흐름) | `assistant` | `api.assistant`, `api.rag` |
| 라인 현황·SOP 알림·수신자 관리 | [Line Dashboard / Drone](05-line-dashboard.md#기능과-흐름) | `line-dashboard` | `api.drone` |
| 설비 로그·타임라인·종합 분석 | [Observer](06-observer.md#기능과-흐름) | `observer` | `api.observer` |
| 분석 화면 선택·외부 분석 서비스 연결 | [Spider 화면 안내](07-spider.md#화면과-공통-진입) | `spider`, `l1-spider` | 외부 화면 연결, Portal 전용 API 없음 |
| L0 분석·추천 값 조회 | [Spider 화면 안내](07-spider.md#화면과-공통-진입) | `l0-spider` | `api.l0_spider` |
| 이상감지·차트·예약 메일 | [L3 Spider](08-l3-spider.md#기능과-흐름) | `l3-spider` | `api.l3_spider` |
| PM 비교·TRACE/OES 분석 | [Spider 화면 안내](07-spider.md#화면과-공통-진입), [파일 명세](09-pm-comparison.md#기능과-흐름) | `pm-spider` | `api.pm_comparison` |
| TTTM 대상·score·파형 조회 | [Spider 화면 안내](07-spider.md#화면과-공통-진입) | `tttm-spider` | `api.tttm_spider` |
| 내부 앱 공유·댓글·좋아요 | [AppStore](10-appstore.md#기능과-흐름) | `appstore` | `api.appstore` |
| 문의·개선 요청·답변 | [VOC](11-voc.md#기능과-흐름) | `voc` | `api.voc` |
| 활동·앱 접속 통계·서버 상태 확인 | [Activity / Health](12-activity-health.md#기능과-흐름) | `access-stats` | `api.activity`, `api.health` |
| 원천 파일 적재·요약 자동화 | [Data Movement](13-data-movement.md#기능과-흐름) | 전용 화면 없음 | `api.data_movement` |
| 홈·팀 안내·오류 화면 | [앱 공통 화면](07-spider.md#앱-공통-화면) | `home`, `teamstaff`, `errors` | 전용 업무 API 없음 |
| 요청·로그·파일·외부 전송 공통 처리 | [Common](14-common.md) | 공통 계층 | `api.common`, [외부 연동](../concepts/03-integrations.md) |


## 공통 API 호출 규칙

### Base URL

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

### 인증 방식

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

### 요청 형식

대부분의 write API는 JSON body를 사용합니다.

```http
Content-Type: application/json
```

일반 업무 API는 canonical camelCase를 사용하며 지원하지 않는 별칭은 허용하지 않습니다.
L3 Spider 설정 CRUD는 snake_case 등 별도 계약이 있으므로 모듈별 표기를 따릅니다.
Emails 내부 OCR claim·update도 snake_case 입력을 사용하므로 [OCR 작업 계약](03-emails.md#ocr-작업)을 따릅니다.

### 응답 형식

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

### 공통 오류

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

### Side effect 분류

| 분류 | 해당 모듈 |
| --- | --- |
| DB write | Auth 사용자 갱신, Activity, Assistant, Emails, Drone, AppStore, VOC, Data Movement, L3 설정 |
| 외부 read/search | Assistant/RAG, Activity 외부 사용량, Drone/Airflow |
| 외부 write/send | Emails RAG, Drone Jira/Mail/Messenger, Assistant OpenWebUI |
| 파일/asset | Emails, AppStore |
| ActivityLog | Account 일부 작업, Emails 이동/삭제, Drone table update, VOC |
