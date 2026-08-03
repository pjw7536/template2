# L3 Spider 모듈

L3 Spider는 날짜·Line·Process·EDS Step 기준으로 Parquet 이상감지 결과를 탐색하고, 요약·차트·메일 규칙을 제공하는 기능입니다.

## 기능 요약

- 분석 완료 날짜와 line name 기반 선택 트리 조회
- High Risk·Warning 통계, 일별 summary matrix와 trellis chart 표시
- 사용자별 exclusion filter와 메일 발송 rule 관리
- L3 Spider `admin` 전용 미매핑 line name 분석
- Airflow token 기반 due mail rule 처리

## 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/l3_spider`, `/spider/l3` |
| Frontend | `apps/web/src/features/l3-spider` |
| Backend API | `/api/v1/l3_spider/**` |
| 업무 데이터 | `L3SpiderFileIndex`, `L3SpiderDailyRunStats`, `L3SpiderRunStatus`, `L3SpiderLineNameRule`, `L3SpiderExclusionFilter`, `L3SpiderMailRule`, `L3SpiderMailDelivery` |
| 파일 데이터 | `L3_SPIDER_DATA_ROOT` 아래 read-only daily anomaly Parquet |
| 외부 연동 | Airflow, Knox Mail API |

## 주요 흐름

1. `meta`가 완료 날짜와 line/process/EDS availability를 반환합니다.
2. 화면 선택값은 URL query와 동기화되어 메일 링크나 공유 링크를 복원합니다.
3. `structure`, `stats`, `summary`, `data`가 같은 선택 계약으로 필요한 집계와 chart row를 반환합니다.
4. 사용자 exclusion rule은 meta·stats·structure cache key와 분리되어 다른 사용자의 결과를 오염시키지 않습니다.
5. mail trigger는 due rule을 claim하고 발송 결과를 `L3SpiderMailDelivery`에 기록합니다.

## 권한과 운영 포인트

- 일반 조회와 개인 rule 관리는 Django session이 필요합니다.
- 개발자 옵션은 Portal 접근이 허용된 L3 Spider `admin`만 사용할 수 있습니다.
- mail trigger는 `AIRFLOW_TRIGGER_TOKEN`이 필요합니다.
- 날짜나 조합이 누락되면 PostgreSQL index table과 `L3_SPIDER_DATA_ROOT` mount를 함께 확인합니다.
- line name이 예상과 다르면 `L3SpiderLineNameRule` 우선순위와 import command 결과를 확인합니다.

## 관련 문서와 코드

- `docs/api/l3-spider.md`
- `docs/configuration.md`
- `apps/api/api/l3_spider/selectors.py`
- `apps/api/api/l3_spider/services/`
- `apps/web/src/features/l3-spider`
