# PM SPIDER API

PM 기준 주기의 Trace/OES score와 원시 파형을 조회합니다. Django session과 Portal·`pm-spider` 앱 접근이 필요합니다.
Prefix는 `/api/v1/pm_spider/`입니다.

| Method | 상대 경로 | 설명 |
| --- | --- | --- |
| GET | `meta` | partition 선택 옵션과 PM 시점 |
| POST | `compare` | 선택 조건의 score·주기·Trace/OES 상세 |

## 선택 옵션

`meta`의 query는 `lineId`, `eqpId`, `fdcBin`, `pmTimestamp`, `type`, `ppid`, `recipeId`,
`traceDataSource`를 사용합니다. 응답은 `lineIds`, `eqpIds`, `fdcBins`, `dtValues`, `pmDates`,
`types`, `ppids`, `recipeIds`, `dataSources`, `traceParamNames`, `warnings`입니다.

## 비교 요청

```json
{
  "lineId": "LINE_DEMO",
  "eqpId": "EQP_DEMO",
  "pmTimestamp": "2026-06-02",
  "chamberId": "PM2",
  "type": "ag",
  "includeDetails": false
}
```

필수 필드는 `lineId`, `eqpId`, `pmTimestamp`입니다. `pattern` 대신 `type`을 사용하며 데이터의
`ag`/`process` 구분과 파티션 구조는 [데이터 명세](../modules/pm-comparison-dashboard-spec.md)를 따릅니다.

| 선택 필드 | 기본값·범위 |
| --- | --- |
| `beforeHours`, `afterHours` | 각각 24, 0.1~720 |
| `chamberId`, `fdcBin`, `type`, `ppid`, `recipeId` | 빈 문자열 |
| `traceParamNames`, `dtValues` | 빈 배열 |
| `traceDataSource`, `oesDataSource` | `trace`, `oes` |
| `selectedStep`, `selectedWavelength` | 빈 문자열 |
| `refPmDates` | 미지정 가능. 참조 PM 주기 선택 |
| `includeDetails`, `includeTraceDetails`, `includeOesDetails` | `true` |
| `includeOesHeatmap`, `includeOesSpectrum` | `true` |
| `limit` | 1200, 50~5000 |
| `maxPoints` | 2400, 100~20000 |
| `xStart`, `xEnd` | 선택 구간 |
| `heatmapXBins`, `heatmapYBins` | 1200(20~1600), 100(10~240) |

## 응답·오류

응답은 `filters`, `window`, `trace`, `oes`, `warnings`입니다. `window`는 `pmTimestamp`, `pmDate`를 포함합니다.
`trace`와 `oes`의 요약·순위와 상세 필드는 선택 데이터 및 상세 조회 옵션에 따라 채워집니다.
조회는 `PM_COMPARISON_DATA_ROOT`의 Parquet를 읽으며 DB 변경이나 score 재계산을 수행하지 않습니다.

잘못된 입력·폴더 형식은 400, 인증·앱 접근은 401/403, 없는 데이터 경로는 404입니다.
서비스 오류는 기존 `error` 응답을 사용하며, 빈 데이터는 경고와 빈 결과로 반환할 수도 있습니다.

구현: `apps/portal/api/api/pm_comparison/views.py`, `serializers.py`, `services/comparison.py`.
