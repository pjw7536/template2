# Activity / Health API

[API 공통 규칙·목록](README.md) · [문서 홈](../README.md) · [기능·데이터 설명](../modules/12-activity-health.md)

Activity는 활동 로그 조회, Health는 서버 상태 확인을 제공합니다.

## Endpoint

| Method | Path | Auth | 설명 |
| --- | --- | --- | --- |
| GET | `/api/v1/activity/logs?limit=50` | 권한 필요 | 최근 활동 로그 |
| POST | `/api/v1/activity/app-access` | 로그인 | 앱 화면 진입 이벤트 기록 |
| GET | `/api/v1/activity/app-access-stats` | `access-stats` 접근 | KST 기준 앱 접속 통계 조회 |
| POST | `/api/v1/activity/app-access-sync-external` | `access-stats` 접근 | 외부 앱 사용량 동기화 요청 |
| POST | `/api/v1/activity/app-access-manual-preview` | `access-stats` 관리자 | CSV/TSV 수동 입력 미리보기 |
| POST | `/api/v1/activity/app-access-manual-commit` | `access-stats` 관리자 | 검증된 수동 입력 반영 |
| GET | `/api/v1/health/` | 공개 | 서버 상태 확인 |

## Activity 권한

활동 로그는 세션 인증과 Portal·`access-stats` 앱 접근에 더해 다음 Django permission 중 하나가 필요합니다.

- `activity.view_activitylog`
- `api.view_activitylog`

## Activity query

| Query | 설명 |
| --- | --- |
| `limit` | 반환 개수, 기본 50, 1~200 |

잘못된 형식이나 범위의 `limit`은 기본값으로 보정하지 않고 400을 반환합니다.

## 앱 접속 통계

- 접속 이벤트 body: `appId`, `appName`, `path`
- 통계 query: `from`, `to`, `appId`, `period`
- 수동 입력 body: `pastedText`, `sourceName`

snake_case와 `granularity` 별칭은 허용하지 않습니다.
CSV/TSV의 사용자 입력 헤더에는 기존 snake_case와 한국어 별칭을 계속 허용합니다.

## Health 응답

```json
{
  "status": "ok",
  "application": "template2-api"
}
```

Health는 프로세스의 고정 상태와 `APPLICATION_NAME`(미설정 시 `template2-api`)을 반환합니다.
DB·MinIO·외부 서비스 연결을 검사하는 readiness endpoint가 아닙니다.

## 오류

Activity API 오류는 `code`, `message`, `details`, `fieldErrors` 공통 형식을 사용합니다.

| Status | 상황 |
| --- | --- |
| 401 | Activity 조회 시 로그인 필요 |
| 403 | Activity 조회 권한 없음 |

## 관련 모듈 문서

- [Activity / Health 모듈](../modules/12-activity-health.md)
