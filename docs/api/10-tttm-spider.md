# TTTM Spider API

[API 공통 규칙·목록](README.md) · [문서 홈](../README.md)

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

## 대시보드 요청

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

## 데이터와 오류

`TTTM_SPIDER_ROOT` 아래 `data`, `result`, `reference`와 `lotwf_index.parquet`를 사용합니다.
마운트·참조 파일 계약은 [환경설정](../reference/01-configuration.md)을 봅니다.

필수 query·body 검증은 400, 인증·앱 접근 오류는 401/403입니다.
서비스 오류는 기존 `error` 응답과 서비스가 지정한 status를 사용합니다.
구현은 `apps/portal/api/api/tttm_spider/views.py`, 입력은 `serializers.py`가 기준입니다.
