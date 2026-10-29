# 기능 안내

[문서 홈](../README.md) · [전체 구조](../concepts/01-architecture.md) · [API 명세](../api/README.md)

기능 설명에서 목적·화면·권한·처리 흐름을 읽고, 요청을 작성할 때 API 명세로 이동합니다.
표의 Web 경로는 `apps/portal/web/src/features/` 기준입니다.
실제 URL·모델·명령 이름은 [구현 색인](../reference/02-inventory.md)에 있습니다.

| 하려는 일 | 기능 설명 | Web feature | API app·명세 |
| --- | --- | --- | --- |
| 로그인·세션 확인 | [Auth](01-auth.md) | `auth` | `api.auth`, [Auth API](../api/01-auth.md) |
| 계정·앱 접근·데이터 범위 확인 | [Account](02-account.md) | `account` | `api.account`, [Account API](../api/02-account.md) |
| 메일 조회·분류·OCR·검색 자료 반영 | [Emails](03-emails.md) | `emails` | `api.emails`, [Emails API](../api/03-emails.md) |
| 일반 대화·메일 검색·업무 화면 AI 분석 | [Assistant](04-assistant.md) | `assistant` | `api.assistant`, `api.rag`, [Assistant API](../api/04-assistant.md) |
| 라인 현황·SOP 알림·수신자 관리 | [Line Dashboard / Drone](05-line-dashboard.md) | `line-dashboard` | `api.drone`, [Line Dashboard API](../api/05-line-dashboard.md) |
| 설비 로그·타임라인·종합 분석 | [Observer](06-observer.md) | `observer` | `api.observer`, [Observer API](../api/06-observer.md) |
| 분석 화면 선택·외부 분석 서비스 연결 | [Spider 화면 안내](07-spider.md) | `spider`, `l1-spider` | 외부 화면 연결, Portal 전용 API 없음 |
| L0 분석·추천 값 조회 | [Spider 화면 안내](07-spider.md) | `l0-spider` | `api.l0_spider`, [L0 Spider API](../api/07-l0-spider.md) |
| 이상감지·차트·예약 메일 | [L3 Spider](08-l3-spider.md) | `l3-spider` | `api.l3_spider`, [L3 Spider API](../api/08-l3-spider.md) |
| PM 비교·TRACE/OES 분석 | [Spider 화면 안내](07-spider.md), [파일 명세](09-pm-comparison-dashboard-spec.md) | `pm-spider` | `api.pm_comparison`, [PM SPIDER API](../api/09-pm-spider.md) |
| TTTM 대상·score·파형 조회 | [Spider 화면 안내](07-spider.md) | `tttm-spider` | `api.tttm_spider`, [TTTM Spider API](../api/10-tttm-spider.md) |
| 내부 앱 공유·댓글·좋아요 | [AppStore](10-appstore.md) | `appstore` | `api.appstore`, [AppStore API](../api/11-appstore.md) |
| 문의·개선 요청·답변 | [VOC](11-voc.md) | `voc` | `api.voc`, [VOC API](../api/12-voc.md) |
| 활동·앱 접속 통계·서버 상태 확인 | [Activity / Health](12-activity-health.md) | `access-stats` | `api.activity`, `api.health`, [Activity / Health API](../api/13-activity-health.md) |
| 원천 파일 적재·요약 자동화 | [Data Movement](13-data-movement.md) | 전용 화면 없음 | `api.data_movement`, [Data Movement API](../api/14-data-movement.md) |
| 홈·팀 안내·오류 화면 | [앱 공통 화면](07-spider.md#앱-공통-화면) | `home`, `teamstaff`, `errors` | 전용 업무 API 없음 |
| 요청·로그·파일·외부 전송 공통 처리 | [Common](14-common.md) | 공통 계층 | `api.common`, [외부 연동](../concepts/03-integrations.md) |

새 화면이나 API를 추가하면 이 표와 구현 색인을 함께 갱신합니다.
문서 작성 기준은 [작성·유지보수 안내](../development/04-documentation.md)를 따릅니다.
