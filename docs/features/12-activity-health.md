# Activity·Health

[문서 홈](../README.md) · [기능·API](README.md)

- [기능과 흐름](#기능과-흐름)
- [API](#api)

## 기능과 흐름


Activity는 사용자 작업과 앱 접속 통계를 확인하는 기능이고, Health는 API 프로세스의 응답 여부를 확인하는 기능입니다.
활동 로그를 볼 권한과 서버 상태 조회의 공개 여부가 다르므로 두 API를 구분합니다.
Health 성공만으로 DB·외부 서비스 연결까지 정상이라고 판단하지 않습니다.

### 접속 통계 화면

`/access-stats`는 기간별 전체 접속 수·주요 앱·추이와 앱별 표를 표시합니다.
Web feature는 `apps/portal/web/src/features/access-stats`이며 `api.activity`를 호출합니다.
외부 사용량 동기화와 관리자용 CSV/TSV 붙여넣기·미리보기·반영 기능도 제공합니다.

통계 조회에는 `access-stats` 앱 접근이 필요하고 수동 반영은 해당 앱 관리자 역할을 검사합니다.
활동 로그 조회의 추가 Django permission과는 별개입니다. 요청 필드는 [Activity API](#api)를 따릅니다.

### Activity 기능

- 최근 ActivityLog 조회
- 조회 권한 검사
- 로그 직렬화
- 앱 접속 이벤트와 내부·외부 접속 통계 집계

ActivityLog 생성은 `api.common`의 middleware가 수행합니다.

### Activity 권한

활동 로그는 Portal·`access-stats` 앱 접근에 더해 다음 Django permission 중 하나가 필요합니다.

- `activity.view_activitylog`
- `api.view_activitylog`

### Health 기능

Health는 인증 없이 서버 상태를 반환합니다.

```json
{
  "status": "ok",
  "application": "template2-api"
}
```

### API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 통계 화면 | `/access-stats` |
| Activity API | `/api/v1/activity/logs` |
| Health API | `/api/v1/health/` |
| Backend | `apps/portal/api/api/activity`, `apps/portal/api/api/health` |
| 데이터 | `ActivityLog`, runtime health payload |
| 생성 경로 | `api.common` middleware와 service helper |

### 운영 포인트

- Activity 403은 `activity.view_activitylog` 또는 `api.view_activitylog` 권한을 확인합니다.
- Health 실패는 Django process와 reverse proxy routing을 확인합니다. Health 자체는 DB·외부 서비스 연결을 검사하지 않으므로 연결 정상 여부는 별도로 확인합니다.
- Activity가 비어 있으면 middleware 적용 여부와 작업별 metadata 주입 여부를 확인합니다.
- 외부 사용량 동기화는 `ExternalAppUsageSyncState.updated_at`을 마지막 실제 시도로 사용하며,
  일반 사용자는 성공·실패 후 6시간 제한을 적용하고 Keycloak `access-stats` 관리자 역할(Portal 관리자 포함)은 제한을 우회합니다. Django superuser만으로 우회하지 않습니다.

### 관련 API

- [Activity / Health API](#api)

### 관련 코드

- `apps/portal/api/api/activity/views.py`
- `apps/portal/api/api/activity/models.py`
- `apps/portal/api/api/activity/selectors.py`
- `apps/portal/api/api/activity/services/recording.py`
- `apps/portal/api/api/health/views.py`
- `apps/portal/api/api/health/services/health_status.py`
- `apps/portal/api/api/common/services/middleware.py`
- `apps/portal/api/api/common/services/activity_logging.py`

## API


Activity는 활동 로그 조회, Health는 서버 상태 확인을 제공합니다.

### Endpoint

| Method | Path | Auth | 설명 |
| --- | --- | --- | --- |
| GET | `/api/v1/activity/logs?limit=50` | 권한 필요 | 최근 활동 로그 |
| POST | `/api/v1/activity/app-access` | 로그인 | 앱 화면 진입 이벤트 기록 |
| GET | `/api/v1/activity/app-access-stats` | `access-stats` 접근 | KST 기준 앱 접속 통계 조회 |
| POST | `/api/v1/activity/app-access-sync-external` | `access-stats` 접근 | 외부 앱 사용량 동기화 요청 |
| POST | `/api/v1/activity/app-access-manual-preview` | `access-stats` 관리자 | CSV/TSV 수동 입력 미리보기 |
| POST | `/api/v1/activity/app-access-manual-commit` | `access-stats` 관리자 | 검증된 수동 입력 반영 |
| GET | `/api/v1/health/` | 공개 | 서버 상태 확인 |

### Activity 권한

활동 로그는 세션 인증과 Portal·`access-stats` 앱 접근에 더해 다음 Django permission 중 하나가 필요합니다.

- `activity.view_activitylog`
- `api.view_activitylog`

### Activity query

| Query | 설명 |
| --- | --- |
| `limit` | 반환 개수, 기본 50, 1~200 |

잘못된 형식이나 범위의 `limit`은 기본값으로 보정하지 않고 400을 반환합니다.

### 앱 접속 통계

- 접속 이벤트 body: `appId`, `appName`, `path`
- 통계 query: `from`, `to`, `appId`, `period`
- 수동 입력 body: `pastedText`, `sourceName`

snake_case와 `granularity` 별칭은 허용하지 않습니다.
CSV/TSV의 사용자 입력 헤더에는 기존 snake_case와 한국어 별칭을 계속 허용합니다.

### Health 응답

```json
{
  "status": "ok",
  "application": "template2-api"
}
```

Health는 프로세스의 고정 상태와 `APPLICATION_NAME`(미설정 시 `template2-api`)을 반환합니다.
DB·MinIO·외부 서비스 연결을 검사하는 readiness endpoint가 아닙니다.

### 오류

Activity API 오류는 `code`, `message`, `details`, `fieldErrors` 공통 형식을 사용합니다.

| Status | 상황 |
| --- | --- |
| 401 | Activity 조회 시 로그인 필요 |
| 403 | Activity 조회 권한 없음 |

### 관련 모듈 문서

- [Activity / Health 모듈](#기능과-흐름)
