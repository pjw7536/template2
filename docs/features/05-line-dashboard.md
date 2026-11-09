# Line Dashboard·Drone

[문서 홈](../README.md) · [기능·API](README.md)

- [기능과 흐름](#기능과-흐름)
- [API](#api)

## 기능과 흐름


Line Dashboard는 라인의 SOP 현황·이력을 보여주고 조기 알림·수신자를 관리하는 화면입니다.
API의 Drone app은 SOP 메일 수집, 대상 계산, Jira·Messenger·Mail 채널 발송을 담당합니다.
화면 기능명과 백엔드 app 이름이 다르므로 관련 코드를 찾을 때 두 이름을 함께 확인합니다.

알림은 **SOP 수집 → 대상·수신자·채널 결정 → 채널별 전송 → 결과 기록** 순서로 처리합니다.
한 채널의 성공이 다른 채널의 성공을 뜻하지 않으므로, 실패 원인은 채널별 전달 결과에서 확인합니다.

### 기능 요약

- 라인 대시보드 테이블 조회/수정
- 라인 히스토리 집계
- 조기 알림 설정
- SOP POP3 수집
- SOP 대상 소속 계산
- Jira/Messenger/Mail 알림 전송
- 알림 대상/수신자 관리
- Line Dashboard `admin` 전용 Drone target 기준 정보 관리
- 실패 채널 재시도

### SOP 알림 흐름

1. POP3 또는 더미 API에서 SOP 메일을 수집합니다.
2. 메일 내용에서 SOP 데이터를 파싱합니다.
3. `drone_sop`에 저장하거나 갱신합니다.
4. `sdwt_prod`를 `target_user_sdwt_prod`로 해석합니다.
5. 채널별 전송 후보를 계산합니다.
6. Jira, Messenger, Mail을 독립적으로 전송합니다.
7. 채널별 성공/실패 사유를 저장합니다.

### 테이블 수정 흐름

1. 테이블명과 컬럼명을 검증합니다.
2. 허용된 컬럼만 업데이트합니다.
3. 변경 전/후 row를 조회합니다.
4. ActivityLog에 기록합니다.

### 주요 상태

| 상태 필드 | 의미 |
| --- | --- |
| `send_jira` | Jira 전송 상태 |
| `send_messenger` | Messenger 전송 상태 |
| `send_mail` | Mail 전송 상태 |
| `instant_inform` | 즉시 인폼 큐잉 여부 |
| `needtosend` | 전송 필요 여부 |

### 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/ESOP_Dashboard/**` |
| Frontend | `apps/portal/web/src/features/line-dashboard` |
| Backend API | `/api/v1/line-dashboard/**` |
| 데이터 | `DroneSOP`, `DroneSopTarget`, `DroneSopTargetChannelConfig`, `DroneSopTargetRecipient`, `DroneSopTargetDispatch`, `DroneSopDelivery`, `DroneEarlyInform` |
| 외부 연동 | POP3, Jira, Knox Messenger, Knox Mail API |

### 운영 포인트

- 수집 문제는 `sop/ingest/pop3/trigger`와 POP3 env를 확인합니다.
- 전송 문제는 channel별 delivery 상태와 Jira/Messenger/Mail env를 분리해 확인합니다.
- 알림 대상 문제는 Account 소속, target mapping, recipient 설정을 함께 확인합니다.
- `/admin/drone-targets` 403은 Line Dashboard `allowed/admin` 권한과 Portal 접근을 확인합니다.
- 테이블 수정 문제는 허용 컬럼과 ActivityLog 기록 여부를 확인합니다.

### Drone target seed

운영 초기 주입은 `seed_drone_targets_from_file` command를 사용합니다.
JSON에는 target, channel config, mapping, needtosend rule 설정을 작성하고,
수신인은 command가 account 사용자 pool에서 자동 생성합니다.

- `drone_sop_target`
- `drone_sop_target_mapping`
- `drone_sop_target_channel_config`
- `drone_sop_needtosend_rule`
- `drone_sop_target_recipient`

수신인은 JSON의 `department + recipient_user_sdwt_prod` 조합으로 account 활성 사용자와
external affiliation snapshot에서 자동 수집합니다.
`target_user_sdwt_prod`와 `recipient_user_sdwt_prod`는 각각 명시해야 하며 구형
`user_sdwt_prod` target 별칭은 허용하지 않습니다.

입력 파일 연결과 실행 예시는 [Drone 초기 데이터 명령](../reference/03-operations.md#drone-jsoncsv-target-seed)에 있습니다.
샘플 파일을 읽기 전용으로 연결하는 dry-run 예시부터 확인합니다.

이 command는 실행 시 기존 Drone SOP/발송 이력/알림 설정을 초기화합니다.
운영 반영 전 `--dry-run`으로 삭제/생성 카운트를 확인해야 합니다.

샘플 파일:

- `docs/examples/drone_targets.sample.json`
- `docs/examples/drone_targets.sample.csv`
- `docs/examples/drone_targets.multi_mapping.sample.csv`

### 관련 API

- [Line Dashboard / Drone API](#api)

### 관련 코드

- `apps/portal/api/api/drone/views/`
- `apps/portal/api/api/drone/models.py`
- `apps/portal/api/api/drone/selectors/`
- `apps/portal/api/api/drone/serializers.py`
- `apps/portal/api/api/drone/services/pop3/sop_pop3.py`
- `apps/portal/api/api/drone/services/inform/sop_inform.py`
- `apps/portal/api/api/drone/services/inform/retry_channel.py`
- `apps/portal/api/api/drone/services/jira/sop_jira.py`
- `apps/portal/api/api/drone/services/messenger/messenger_sender.py`
- `apps/portal/api/api/drone/services/mail/mail_sender.py`
- `apps/portal/api/api/drone/services/channels/recipients.py`
- `apps/portal/api/api/drone/services/table_ops.py`
- `apps/portal/web/src/features/line-dashboard`

## API


Line Dashboard API는 Drone SOP, 라인 테이블, 히스토리, 알림 설정을 제공합니다.

### 호출자

- 브라우저 SPA
- Airflow 또는 scheduler

### 인증

- 화면 API: Django session과 Portal·`line-dashboard` 앱 접근
- SOP 수집/파이프라인 trigger: Airflow Bearer token

### Endpoint

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

### Airflow DAG 현황

브라우저는 Airflow REST API와 인증값에 직접 접근하지 않습니다. Django API가
`AIRFLOW_BASE_URL`, `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD`를 사용해 `/auth/token`에서 JWT를 발급받고 API v2로 DAG 목록과 최근 실행을
조회하며, 화면에는 정규화된 결과만 반환합니다.

```http
GET /api/v1/line-dashboard/airflow/dag-overview
```

응답의 `baseUrl`은 DAG 상세 화면 링크용 `AIRFLOW_PUBLIC_BASE_URL`이며 credential을 포함하지 않습니다.

### 알림 대상 조회

`admin/drone-targets`는 Portal 접근이 허용된 Line Dashboard `admin`만 사용할 수 있습니다. `is_staff`나 프로필 운영 역할은 이 관리자 판정에 사용하지 않습니다.

```http
GET /api/v1/line-dashboard/notification-targets?lineId=L1
```

`mappingOptions`와 `mappingOptionLines`는 `drone_sop_target`의 `line_id`,
`target_user_sdwt_prod` 기준으로 생성합니다. mapping/SOP 관측값이나 account 소속표 값은
Engr/설비 조합 드롭다운 후보에 섞지 않습니다.

### 테이블 조회

```http
GET /api/v1/line-dashboard/tables?table=drone_sop&lineId=L1&recentHoursStart=24&recentHoursEnd=0
```

주요 query:

- `table`
- `lineId`
- `from`, `to`
- `recentHoursStart`, `recentHoursEnd`: 각각 기본 8, 0. 범위는 0~168시간이며 24시간 초과 값은 일 단위로 보정

### 테이블 수정

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

### 수신자 목록 교체

`PUT /api/v1/line-dashboard/notification-recipients`는
`lineId`, `targetUserSdwtProd`, `channel`, `userIds`, `externalKnoxIds`를 받아
해당 대상·채널의 최종 수신자 목록을 교체합니다. 개별 수신자용 POST/PATCH/DELETE는 제공하지 않습니다.

### SOP trigger

```http
POST /api/v1/line-dashboard/sop/trigger
Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>
```

동작:

1. 전송 후보 SOP를 조회합니다.
2. 대상 소속과 채널 설정을 확인합니다.
3. Jira, Messenger, Mail 채널을 실행합니다.
4. 채널별 결과를 저장합니다.

### 오류

| Status | 상황 |
| --- | --- |
| 400 | 잘못된 테이블/파라미터/body |
| 401 | 인증 필요 또는 token 오류 |
| 403 | 권한 없음 |
| 404 | SOP 또는 설정 없음 |
| 500 | DB/파이프라인 처리 실패 |
| 502 | Airflow/Jira/Mail/Messenger 외부 호출 실패 |
| 503 | Airflow 서버 설정 누락 |

### 관련 모듈 문서

- [Line Dashboard / Drone 모듈](#기능과-흐름)
