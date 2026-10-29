# Common 모듈

[모듈 목록](README.md) · [문서 홈](../README.md)

Common은 여러 API에서 반복해서 쓰는 요청 파싱·인증 보조·로그·DB·파일·외부 전송 기능을 제공합니다.
사용자가 직접 여는 화면은 없으며, 각 업무 app이 `api.common.services` 공개 진입점을 통해 사용합니다.
여러 기능에서 같은 오류가 발생할 때 공통 처리와 설정을 확인하는 출발점이 됩니다.

## 기능 요약

- JSON 요청 파싱
- Airflow Bearer token 검증
- ActivityLog metadata helper
- KnoxIdRequired middleware
- 안전한 raw SQL helper
- schema/table helper
- MinIO storage helper
- Knox Mail/Messenger client

## 사용 원칙

다른 모듈은 공통 기능을 직접 구현하지 않고 `api.common.services` facade를 통해 사용합니다.

## 대표 기능

| 기능 | 설명 |
| --- | --- |
| `parse_json_body` | JSON body 파싱 |
| `ensure_airflow_token` | Airflow trigger token 검증 |
| `set_activity_summary` | ActivityLog summary 주입 |
| `run_query`, `execute` | raw SQL 실행 |
| `sanitize_identifier` | 안전한 SQL 식별자 검증 |
| `upload_bytes`, `download_bytes` | MinIO 객체 처리 |
| `send_knox_mail_api` | Knox Mail API 호출 |
| `send_chat_message` | Knox Messenger 메시지 전송 |

## 의존 모듈

| Common 기능 | 주 사용 모듈 |
| --- | --- |
| request helper/token 검증 | Emails, Drone, Account |
| ActivityLog helper/middleware | Account, Emails, Drone, VOC, Activity |
| raw SQL/schema helper | Observer, Drone table API |
| storage helper | Emails |
| Mail API/Messenger client | Drone, Emails |

## 운영 포인트

- 여러 모듈에서 같은 증상이 발생하면 `api.common`의 helper 또는 env 설정을 먼저 확인합니다.
- 외부 client 변경은 `docs/concepts/03-integrations.md`와 `docs/reference/01-configuration.md`를 함께 갱신해야 합니다.
- middleware 변경은 ActivityLog와 인증/Knox ID 처리에 영향을 줄 수 있습니다.

## 관련 문서

- [외부 연동 계약](../concepts/03-integrations.md)
- [운영/개발 명령](../reference/03-operations.md)

## 관련 코드

- `apps/portal/api/api/common/services/__init__.py`
- `apps/portal/api/api/common/services/request_helpers.py`
- `apps/portal/api/api/common/services/activity_logging.py`
- `apps/portal/api/api/common/services/middleware.py`
- `apps/portal/api/api/common/services/db.py`
- `apps/portal/api/api/common/services/schema.py`
- `apps/portal/api/api/common/services/storage.py`
- `apps/portal/api/api/common/services/mail_api.py`
- `apps/portal/api/api/common/services/messenger.py`
