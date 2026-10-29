# Spider와 앱 공통 화면

[기능 안내](README.md) · [화면 색인](../reference/02-inventory.md#프론트엔드-route)

Spider는 여러 분석 화면의 진입점입니다. 앱 역할이 있는 항목으로 이동하며,
Portal 자체 분석 화면과 외부 서비스로 이동하는 화면을 구분합니다.

## 분석 화면 선택

| 기능 | 현재 동작 | 상세 |
| --- | --- | --- |
| Spider 홈 | `/spider`에서 분석 앱 카드 표시 | `apps/portal/web/src/features/spider` |
| L0 Spider | `/spider/l0`는 외부 화면으로 이동. `/l0_spider/**`, `/fdc_trend/**`는 Portal 분석 화면 | [L0 API](../api/07-l0-spider.md) |
| L1 Spider | `/spider/l1`에서 외부 L1 화면으로 이동 | `apps/portal/web/src/features/l1-spider` |
| Defect Spider | `/spider/defect`에서 `VITE_DEFECT_SPIDER_URL`로 이동. 값이 없으면 미설정 안내 표시 | [Web 설정](../reference/01-configuration.md) |
| L3 Spider | 이상감지 Summary·Chart·메일 규칙 제공 | [L3 기능](08-l3-spider.md), [L3 API](../api/08-l3-spider.md) |
| PM Spider | `/spider/pm`과 `/pm_spider`가 같은 비교 화면을 표시 | [PM API](../api/09-pm-spider.md), [파일 명세](09-pm-comparison-dashboard-spec.md) |
| TTTM Spider | 대상 선택 뒤 `score` 하위 화면에서 분석 결과 조회 | [TTTM API](../api/10-tttm-spider.md) |

TTTM은 `/spider/tttm`과 `/tttm_spider` 경로를 지원하며 각 경로 아래에 `score` 화면이 있습니다.
Portal의 분석 API는 로그인과 해당 앱 접근을 검사합니다. 외부 화면의 데이터·로그인·접속 가능 여부는 해당 서비스가 관리합니다.
L0·L1의 외부 주소는 현재 각 page 소스의 상수에 있으며, Defect는 공개 Web env에서 읽습니다.

## 앱 공통 화면

- `home`: 로그인 후 홈과 앱 진입 화면입니다.
- `teamstaff`: `/teamstaff`에서 팀 안내 이미지를 표시합니다. 전용 업무 API는 없습니다.
- `errors`: 일치하지 않는 URL과 route 오류를 표시합니다.

전체 화면의 접근 경계와 조립은 `apps/portal/web/src/routes/router.jsx`가 담당합니다.
ESOP의 TIP 상태 화면은 전역 router가 Observer 기능을 연결하므로 line-dashboard와 observer 접근을 함께 확인합니다.
