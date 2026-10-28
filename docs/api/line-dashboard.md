# Line Dashboard / Drone API

Line Dashboard API는 Drone SOP, 라인 테이블, 히스토리, 알림 설정을 제공합니다.

## 호출자

- 브라우저 SPA
- Airflow 또는 scheduler

## 인증

- 화면 API: Django session과 Portal·`line-dashboard` 앱 접근
- SOP 수집/파이프라인 trigger: Airflow Bearer token

## Endpoint

| 영역 | Method/Path | 설명 |
| --- | --- | --- |
| 조기 알림 | `GET/POST/PATCH/DELETE /api/v1/line-dashboard/early-inform` | 조기 알림 설정 |
| 테이블 | `GET /api/v1/line-dashboard/tables` | 테이블 조회 |
| 테이블 | `PATCH /api/v1/line-dashboard/tables/update` | 테이블 row 수정 |
| 히스토리 | `GET /api/v1/line-dashboard/history` | 라인 히스토리 집계 |
| 라인 | `GET /api/v1/line-dashboard/line-ids` | 라인 목록 |
| 라인 | `GET /api/v1/line-dashboard/line-sdwt-options` | TIP status line/user_sdwt_prod 옵션 |
| Airflow | `GET /api/v1/line-dashboard/airflow/dag-overview` | Django가 Airflow credential로 조회한 DAG 현황 |
| Jira | `GET/POST /api/v1/line-dashboard/jira-keys` | Jira key |
| Jira | `GET /api/v1/line-dashboard/jira-user-sdwt-prods` | Jira 사용자 소속 후보 |
| 알림 대상 | `GET/POST /api/v1/line-dashboard/notification-targets` | 알림 대상 |
| 알림 매핑 | `POST/PATCH/DELETE /api/v1/line-dashboard/notification-target-mappings` | 대상 매핑 |
| 수신자 | `GET/PUT /api/v1/line-dashboard/notification-recipients` | 수신자 |
| 수신자 권한 | `GET /api/v1/line-dashboard/notification-recipient-permissions` | 수신자 권한 |
| 내 수신 대상 | `GET /api/v1/line-dashboard/my-notification-recipient-targets` | 로그인 사용자 수신 대상 |
| 템플릿 | `GET /api/v1/line-dashboard/notification-template-options` | 채널별 템플릿 옵션 |
| Target 관리 | `GET/POST/PATCH/DELETE /api/v1/line-dashboard/admin/drone-targets` | Line Dashboard `admin` 전용 Drone target 기준 정보 관리 |
| SOP | `POST /api/v1/line-dashboard/sop/<sop_id>/instant-inform` | 단건 즉시 인폼 |
| SOP | `POST /api/v1/line-dashboard/sop/<sop_id>/retry-channel` | 실패 채널 재시도 |
| SOP | `POST /api/v1/line-dashboard/sop/ingest/pop3/trigger` | SOP POP3 수집 |
| SOP | `POST /api/v1/line-dashboard/sop/precheck` | 파이프라인 사전 점검 |
| SOP | `POST /api/v1/line-dashboard/sop/trigger` | SOP 알림 파이프라인 |

## Airflow DAG 현황

브라우저는 Airflow REST API와 Basic Auth credential에 직접 접근하지 않습니다. Django API가
`AIRFLOW_BASE_URL`, `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD`를 사용해 DAG 목록과 최근 실행을
조회하고, 화면에는 정규화된 결과만 반환합니다.

```http
GET /api/v1/line-dashboard/airflow/dag-overview
```

응답의 `baseUrl`은 DAG 상세 화면 링크용 `AIRFLOW_PUBLIC_BASE_URL`이며 credential을 포함하지 않습니다.

## 알림 대상 조회

`admin/drone-targets`는 Portal 접근이 허용된 Line Dashboard `admin`만 사용할 수 있습니다. `is_staff`나 프로필 운영 역할은 이 관리자 판정에 사용하지 않습니다.

```http
GET /api/v1/line-dashboard/notification-targets?lineId=L1
```

`mappingOptions`와 `mappingOptionLines`는 `drone_sop_target`의 `line_id`,
`target_user_sdwt_prod` 기준으로 생성합니다. mapping/SOP 관측값이나 account 소속표 값은
Engr/설비 조합 드롭다운 후보에 섞지 않습니다.

## 테이블 조회

```http
GET /api/v1/line-dashboard/tables?table=drone_sop&lineId=L1&recentHoursStart=24&recentHoursEnd=0
```

주요 query:

- `table`
- `lineId`
- `from`, `to`
- `recentHoursStart`, `recentHoursEnd`: 각각 기본 8, 0. 범위는 0~168시간이며 24시간 초과 값은 일 단위로 보정

## 테이블 수정

```json
{
  "table": "drone_sop",
  "id": 123,
  "updates": {
    "comment": "확인 필요",
    "needtosend": 1
  }
}
```

수정 가능한 컬럼:

- `comment`
- `needtosend`

`instant_inform`, `status`는 이 API의 수정 허용 컬럼이 아닙니다. 즉시 인폼과 재시도는 전용 SOP endpoint를 사용합니다.

## 수신자 목록 교체

`PUT /api/v1/line-dashboard/notification-recipients`는
`lineId`, `targetUserSdwtProd`, `channel`, `userIds`, `externalKnoxIds`를 받아
해당 대상·채널의 최종 수신자 목록을 교체합니다. 개별 수신자용 POST/PATCH/DELETE는 제공하지 않습니다.

## SOP trigger

```http
POST /api/v1/line-dashboard/sop/trigger
Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>
```

동작:

1. 전송 후보 SOP를 조회합니다.
2. 대상 소속과 채널 설정을 확인합니다.
3. Jira, Messenger, Mail 채널을 실행합니다.
4. 채널별 결과를 저장합니다.

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 잘못된 테이블/파라미터/body |
| 401 | 인증 필요 또는 token 오류 |
| 403 | 권한 없음 |
| 404 | SOP 또는 설정 없음 |
| 500 | DB/파이프라인 처리 실패 |
| 502 | Airflow/Jira/Mail/Messenger 외부 호출 실패 |
| 503 | Airflow 서버 설정 누락 |

## 관련 모듈 문서

- [Line Dashboard / Drone 모듈](../modules/line-dashboard.md)
