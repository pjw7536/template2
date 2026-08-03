# Activity / Health API

Activity는 활동 로그 조회, Health는 서버 상태 확인을 제공합니다.

## Endpoint

| Method | Path | Auth | 설명 |
| --- | --- | --- | --- |
| GET | `/api/v1/activity/logs?limit=50` | 권한 필요 | 최근 활동 로그 |
| POST | `/api/v1/activity/app-access-sync-external` | `access-stats` 접근 | 외부 앱 사용량 동기화 요청 |
| GET | `/api/v1/health/` | 공개 | 서버 상태 확인 |

## Activity 권한

다음 권한 중 하나가 필요합니다.

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

## Health 응답

```json
{
  "status": "ok",
  "application": "template2-api"
}
```

## 오류

| Status | 상황 |
| --- | --- |
| 401 | Activity 조회 시 로그인 필요 |
| 403 | Activity 조회 권한 없음 |

## 관련 모듈 문서

- `docs/modules/activity-health.md`
