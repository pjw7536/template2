# L0 Spider API

FDC Hard Limit 추천용 Parquet 데이터를 조회합니다. Django session과 Portal·`l0-spider` 앱 접근이 필요합니다.
기본 prefix는 `/api/v1/l0_spider/`이며 `/api/v1/fdc-trend/`도 같은 view를 사용하는 호환 경로입니다.

| Method | 상대 경로 | 입력 |
| --- | --- | --- |
| GET | `hard-spec/meta` | 선택 `lineId`, `stepSeq`, `recipeId` |
| GET | `hard-spec/recommendations` | 필수 `lineId`, `stepSeq`, `recipeId`, `fdcModel` |

## 응답과 데이터

`meta`는 `lineIds`, `lineId`, `stepSeq`, `recipeId`, `stepSeqs`, `recipeIds`, `fdcModels`,
`sourcePaths`, `warnings`를 반환합니다. 비어 있는 선택값은 사용 가능한 첫 값으로 보완합니다.

`recommendations`는 `rows`, `chartRows`, `sourcePaths`, `warnings`를 반환합니다.
선택 조건에 통계·Hard Limit 데이터나 A/B priority 센서가 없으면 빈 목록과 경고를 반환할 수 있습니다.
DB 쓰기나 추천 파이프라인 실행은 수행하지 않습니다.

설정은 `FDC_HARD_SPEC_DATA_ROOT`, `FDC_HARD_SPEC_PRIORITY_PATH`,
`FDC_HARD_SPEC_UNIT_MODEL_PATH`, `FDC_HARD_SPEC_HARD_LIMIT_PATH`를 사용합니다.
파일 조회 조건과 응답 계산은 `apps/portal/api/api/l0_spider/services/dashboard.py`가 담당합니다.

## 오류

세션·앱 접근 오류는 401/403입니다. 필수 query·형식 오류는 400이며,
서비스 오류는 기존 `error` 응답을 사용합니다. 파일·데이터 문제는 응답의 `warnings`도 함께 확인합니다.

입력 정의: `apps/portal/api/api/l0_spider/serializers.py`.
화면 경로는 [인벤토리](../inventory.md#프론트엔드-route), 마운트는 [환경설정](../configuration.md)을 봅니다.
