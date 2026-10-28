# Activity / Health 모듈

Activity는 변경 작업 로그 조회, Health는 서버 상태 확인을 담당합니다.

## Activity 기능

- 최근 ActivityLog 조회
- 조회 권한 검사
- 로그 직렬화
- 앱 접속 이벤트와 내부·외부 접속 통계 집계

ActivityLog 생성은 `api.common`의 middleware가 수행합니다.

## Activity 권한

활동 로그는 Portal·`access-stats` 앱 접근에 더해 다음 Django permission 중 하나가 필요합니다.

- `activity.view_activitylog`
- `api.view_activitylog`

## Health 기능

Health는 인증 없이 서버 상태를 반환합니다.

```json
{
  "status": "ok",
  "application": "template2-api"
}
```

## API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| Activity API | `/api/v1/activity/logs` |
| Health API | `/api/v1/health/` |
| Backend | `apps/portal/api/api/activity`, `apps/portal/api/api/health` |
| 데이터 | `ActivityLog`, runtime health payload |
| 생성 경로 | `api.common` middleware와 service helper |

## 운영 포인트

- Activity 403은 `activity.view_activitylog` 또는 `api.view_activitylog` 권한을 확인합니다.
- Health 실패는 Django process와 reverse proxy routing을 확인합니다. Health 자체는 DB·외부 서비스 연결을 검사하지 않으므로 연결 정상 여부는 별도로 확인합니다.
- Activity가 비어 있으면 middleware 적용 여부와 작업별 metadata 주입 여부를 확인합니다.
- 외부 사용량 동기화는 `ExternalAppUsageSyncState.updated_at`을 마지막 실제 시도로 사용하며,
  일반 사용자는 성공·실패 후 6시간 제한을 적용하고 Keycloak `access-stats` 관리자 역할(Portal 관리자 포함)은 제한을 우회합니다. Django superuser만으로 우회하지 않습니다.

## 관련 API

- [Activity / Health API](../api/activity-health.md)

## 관련 코드

- `apps/portal/api/api/activity/views.py`
- `apps/portal/api/api/activity/models.py`
- `apps/portal/api/api/activity/selectors.py`
- `apps/portal/api/api/activity/services/recording.py`
- `apps/portal/api/api/health/views.py`
- `apps/portal/api/api/health/services/health_status.py`
- `apps/portal/api/api/common/services/middleware.py`
- `apps/portal/api/api/common/services/activity_logging.py`
