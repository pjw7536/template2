# Spider 화면과 분석 API

[문서 홈](../README.md) · [기능·API](README.md)

- [화면과 공통 진입](#화면과-공통-진입)
- [L0 API](#l0-api)
- [TTTM API](#tttm-api)

## 화면과 공통 진입


Spider는 여러 분석 화면의 진입점입니다. 앱 역할이 있는 항목으로 이동하며,
Portal 자체 분석 화면과 외부 서비스로 이동하는 화면을 구분합니다.

### 분석 화면 선택

| 기능 | 현재 동작 | 상세 |
| --- | --- | --- |
| Spider 홈 | `/spider`에서 분석 앱 카드 표시 | `apps/portal/web/src/features/spider` |
| L0 Spider | `/spider/l0`는 외부 화면으로 이동. `/l0_spider/**`, `/fdc_trend/**`는 Portal 분석 화면 | [L0 API](#l0-api) |
| L1 Spider | `/spider/l1`에서 외부 L1 화면으로 이동 | `apps/portal/web/src/features/l1-spider` |
| Defect Spider | `/spider/defect`에서 `VITE_DEFECT_SPIDER_URL`로 이동. 값이 없으면 미설정 안내 표시 | [Web 설정](../reference/01-configuration.md) |
| L3 Spider | 이상감지 Summary·Chart·메일 규칙 제공 | [L3 기능](08-l3-spider.md#기능과-흐름), [L3 API](08-l3-spider.md#api) |
| PM Spider | `/spider/pm`과 `/pm_spider`가 같은 비교 화면을 표시 | [PM API](09-pm-comparison.md#api), [파일 명세](09-pm-comparison.md#기능과-흐름) |
| TTTM Spider | 대상 선택 뒤 `score` 하위 화면에서 분석 결과 조회 | [TTTM API](#tttm-api) |

TTTM은 `/spider/tttm`과 `/tttm_spider` 경로를 지원하며 각 경로 아래에 `score` 화면이 있습니다.
Portal의 분석 API는 로그인과 해당 앱 접근을 검사합니다. 외부 화면의 데이터·로그인·접속 가능 여부는 해당 서비스가 관리합니다.
L0·L1의 외부 주소는 현재 각 page 소스의 상수에 있으며, Defect는 공개 Web env에서 읽습니다.

### 앱 공통 화면

- `home`: 로그인 후 홈과 앱 진입 화면입니다.
- `teamstaff`: `/teamstaff`에서 팀 안내 이미지를 표시합니다. 전용 업무 API는 없습니다.
- `errors`: 일치하지 않는 URL과 route 오류를 표시합니다.

전체 화면의 접근 경계와 조립은 `apps/portal/web/src/routes/router.jsx`가 담당합니다.
ESOP의 TIP 상태 화면은 전역 router가 Observer 기능을 연결하므로 line-dashboard와 observer 접근을 함께 확인합니다.

## L0 API


FDC Hard Limit 추천용 Parquet 데이터를 조회합니다. Django session과 Portal·`l0-spider` 앱 접근이 필요합니다.
기본 prefix는 `/api/v1/l0_spider/`이며 `/api/v1/fdc-trend/`도 같은 view를 사용하는 호환 경로입니다.

| Method | 상대 경로 | 입력 |
| --- | --- | --- |
| GET | `hard-spec/meta` | 선택 `lineId`, `stepSeq`, `recipeId` |
| GET | `hard-spec/recommendations` | 필수 `lineId`, `stepSeq`, `recipeId`, `fdcModel` |

### 응답과 데이터

`meta`는 `lineIds`, `lineId`, `stepSeq`, `recipeId`, `stepSeqs`, `recipeIds`, `fdcModels`,
`sourcePaths`, `warnings`를 반환합니다. 비어 있는 선택값은 사용 가능한 첫 값으로 보완합니다.

`recommendations`는 `rows`, `chartRows`, `sourcePaths`, `warnings`를 반환합니다.
선택 조건에 통계·Hard Limit 데이터나 A/B priority 센서가 없으면 빈 목록과 경고를 반환할 수 있습니다.
DB 쓰기나 추천 파이프라인 실행은 수행하지 않습니다.

설정은 `FDC_HARD_SPEC_DATA_ROOT`, `FDC_HARD_SPEC_PRIORITY_PATH`,
`FDC_HARD_SPEC_UNIT_MODEL_PATH`, `FDC_HARD_SPEC_HARD_LIMIT_PATH`를 사용합니다.
파일 조회 조건과 응답 계산은 `apps/portal/api/api/l0_spider/services/dashboard.py`가 담당합니다.

### 오류

세션·앱 접근 오류는 401/403입니다. 필수 query·형식 오류는 400이며,
서비스 오류는 기존 `error` 응답을 사용합니다. 파일·데이터 문제는 응답의 `warnings`도 함께 확인합니다.

입력 정의: `apps/portal/api/api/l0_spider/serializers.py`.
화면 경로는 [인벤토리](../reference/02-inventory.md#프론트엔드-route), 마운트는 [환경설정](../reference/01-configuration.md)을 봅니다.

## TTTM API


미리 계산된 Parquet score와 원시 파형을 읽습니다. Django session과 Portal·`tttm-spider` 앱 접근이 필요합니다.
Prefix는 `/api/v1/tttm_spider/`이며 조회 요청으로 계산 파이프라인을 실행하지 않습니다.

| Method | 상대 경로 | 입력 |
| --- | --- | --- |
| GET | `combo/options` | 필수 `level`: `line/eqp/chamber/date`, 선택 `line`, `eqp`, `chamber` |
| GET | `combo/types` | type 선택 옵션 |
| GET | `combo/data-types` | data type 선택 옵션 |
| GET | `targets/eqps` | 전체 설비 후보 |
| GET | `targets/chambers` | 필수 `eqp` |
| GET | `targets/lotwf` | 필수 `eqp`, `chamber` |
| GET | `targets/golden` | 선택 `recipe` |
| POST | `targets/result-status` | `items` 배열의 조합별 결과 존재 여부 |
| POST | `dashboard/data` | 비교·참조 조건의 대시보드 묶음 |
| POST | `sensor-trace` | 선택 센서·OES step의 파형과 분해 데이터 |

`combo/options`는 `source=comp/ref`를 검증하지만 현재 view는 이를 서비스에 전달하지 않고 공통 옵션을 조회합니다.
서로 다른 source별 옵션을 보장하는 계약으로 사용하지 않습니다.

### 대시보드 요청

```json
{
  "comp": {"line": "LINE_DEMO", "eqp": "EQP_DEMO", "chamber": "PM2", "date": "2026-06-02", "type": "ag"},
  "ref": {"line": "LINE_DEMO", "eqp": "EQP_REF", "chamber": "PM2", "date": "2026-05-20"},
  "dataType": "trace"
}
```

`comp`의 `line`, `eqp`, `chamber`, `date`, `type`과 `ref`의 `line`, `eqp`, `chamber`, `date`,
최상위 `dataType`이 필수입니다. 선택 필드는 `stage`, `oesMethod`(기본 `oob`), `traceRecipeId`입니다.
응답은 `bundle`과 비교 설비·챔버를 조합한 `name`입니다.

`sensor-trace`는 같은 `comp`, `ref`, `dataType`에 필수 `sensorKey`를 추가합니다.
Serializer는 `wlCenter`, `wlHalfWidth`도 허용하지만 현재 view는 해당 값을 서비스에 전달하지 않습니다.
파장 구간 제어가 적용된다고 가정하지 않습니다.

### 데이터와 오류

`TTTM_SPIDER_ROOT` 아래 `data`, `result`, `reference`와 `lotwf_index.parquet`를 사용합니다.
마운트·참조 파일 계약은 [환경설정](../reference/01-configuration.md)을 봅니다.

필수 query·body 검증은 400, 인증·앱 접근 오류는 401/403입니다.
서비스 오류는 기존 `error` 응답과 서비스가 지정한 status를 사용합니다.
구현은 `apps/portal/api/api/tttm_spider/views.py`, 입력은 `serializers.py`가 기준입니다.
