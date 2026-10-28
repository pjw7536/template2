# 모듈 문서 색인

모듈 문서는 기능의 목적, 화면 흐름, 권한과 운영 시 확인할 사항을 설명합니다.
표의 모듈 이름을 누르면 기능 설명으로, API 링크를 누르면 호출 계약으로 이동합니다.
실제 경로와 모델 이름은 [앱 인벤토리](../inventory.md)에서 찾으세요.

## 모듈별 추적표

| 모듈 | Frontend feature | Backend app | API 문서 | 주요 데이터/외부 연동 |
| --- | --- | --- | --- | --- |
| [Auth](auth.md) | `apps/portal/web/src/features/auth` | `api.auth`, `api.account` | [Auth API](../api/auth.md) | Keycloak/OIDC, Django session |
| [Account](account.md) | `apps/portal/web/src/features/account` | `api.account` | [Account API](../api/account.md) | `User`, Keycloak 세션 앱 역할·SDWT 그룹 |
| [Emails](emails.md) | `apps/portal/web/src/features/emails` | `api.emails` | [Emails API](../api/emails.md) | `Email`, `EmailAsset`, `EmailOutbox`, POP3, RAG, MinIO |
| [Assistant/RAG](assistant.md) | `apps/portal/web/src/features/assistant` | `api.assistant`, `api.rag` | [Assistant API](../api/assistant.md) | PostgreSQL 대화 이력, OpenWebUI, RAG, LLM, Account permission group |
| [Line Dashboard/Drone](line-dashboard.md) | `apps/portal/web/src/features/line-dashboard` | `api.drone` | [Line Dashboard API](../api/line-dashboard.md) | `DroneSOP`, target/channel/recipient/delivery, Jira/Mail/Messenger |
| [L3 Spider](l3-spider.md) | `apps/portal/web/src/features/l3-spider` | `api.l3_spider` | [L3 Spider API](../api/l3-spider.md) | Parquet anomaly, index table, line name rule, Mail API |
| [Observer](observer.md) | `apps/portal/web/src/features/observer` | `api.observer` | [Observer API](../api/observer.md) | 기본 DB 기준정보와 로그 |
| L0 Spider | `apps/portal/web/src/features/l0-spider` | `api.l0_spider` | [L0 Spider API](../api/l0-spider.md) | FDC Hard Limit 추천 Parquet |
| TTTM Spider | `apps/portal/web/src/features/tttm-spider` | `api.tttm_spider` | [TTTM Spider API](../api/tttm-spider.md) | 원시 파형·사전 계산 Parquet |
| PM SPIDER | `apps/portal/web/src/features/pm-spider` | `api.pm_comparison` | [PM SPIDER API](../api/pm-spider.md) | [PM SPIDER raw/result Parquet 명세](pm-comparison-dashboard-spec.md) |
| [AppStore](appstore.md) | `apps/portal/web/src/features/appstore` | `api.appstore` | [AppStore API](../api/appstore.md) | `AppStoreApp`, 댓글, 좋아요, cover image |
| [VOC](voc.md) | `apps/portal/web/src/features/voc` | `api.voc` | [VOC API](../api/voc.md) | `VocPost`, `VocReply`, ActivityLog |
| [Activity/Health](activity-health.md) | API only | `api.activity`, `api.health` | [Activity / Health API](../api/activity-health.md) | `ActivityLog`, runtime health |
| [Common](common.md) | shared | `api.common` | [외부 연동](../integrations.md) | request helper, storage, mail, messenger, middleware |

Data Movement는 화면 없이 동작하는 파일 적재 기능입니다. [처리 흐름](data-movement.md)과
[트리거 API](../api/data-movement.md)를 함께 확인하세요.
L0·TTTM Spider의 조회 설명은 해당 API 문서에, PM SPIDER의 파일 구조는 데이터 명세에 모았습니다.

## 각 모듈 문서의 필수 항목

- 기능 목적과 사용자가 보는 화면
- 주요 route와 endpoint
- 인증/권한 기준
- 핵심 데이터 모델 또는 외부 데이터 소스
- 주요 흐름과 side effect
- 운영/장애 확인 포인트
- 관련 코드 경로
