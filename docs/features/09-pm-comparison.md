# PM Spider

[문서 홈](../README.md) · [기능·API](README.md)

- [기능과 흐름](#기능과-흐름)
- [API](#api)

## 기능과 흐름


현재 HTTP 계약은 [PM SPIDER API](#api), 이 문서는 파일 생산자와 조회 코드가 공유하는 데이터 명세입니다.
호스트 mount의 로컬 기본값은 저장소의 `data/pm_spider`이며 컨테이너 내부는 `PM_COMPARISON_DATA_ROOT`로 지정합니다.

### 1. 서버별 BASE 경로

| 환경 | BASE_DATA | BASE_RESULT |
|------|-----------|-------------|
| 로컬/컨테이너 | `/data/pm_spider/data/` | `/data/pm_spider/result/` |
| 호스트 | `${PM_COMPARISON_DATA_HOST_PATH}/data/` | `${PM_COMPARISON_DATA_HOST_PATH}/result/` |

BASE 아래의 하위 경로는 두 환경에서 같습니다. BASE만 실행 환경에 맞게 지정합니다.

---

### 2. 디렉터리 구조 전체

```text
BASE_RESULT/
├── score_data/                          ← 스코어/랭킹 (대시보드 주 입력)
│   └── line_id={LINE_ID}/
│       └── eqp_id={EQP_ID}/
│           └── chamber_id={CHAMBER_ID}/
│               └── type={TYPE}/
│                   ├── data_type=trace/
│                   │   └── scores.parquet
│                   └── data_type=oes/
│                       └── scores.parquet
│
└── decomp_data/                         ← Shape/Jitter 신호 시각화용
    └── line_id={LINE_ID}/
        └── eqp_id={EQP_ID}/
            └── chamber_id={CHAMBER_ID}/
                └── type={TYPE}/
                    └── comp_dt={YYYY-MM-DD}/
                        └── param={PARAM}/
                            └── ch_step={CH_STEP}/
                                ├── shape.parquet
                                └── jitter.parquet

BASE_DATA/
└── {LINE_ID}/{EQP_ID}/{CHAMBER_ID}/
    └── {PM_START}/                      ← 예: "2026-05-29 00:00:00"
        ├── trace/
        │   └── type={TYPE}/
        │       └── ppid={PPID}/
        │           └── recipe_id={RECIPE_ID}/
        │               └── priority={PRIORITY}/
        │                   └── trace_param_name={PARAM}/
        │                       └── *.parquet
        └── oes/
            └── {TYPE}/
                └── {STEP_SEQ}/
                    └── {PPID}/
                        └── {RECIPE_ID}/
                            └── {LOT_ID}/
                                └── {SLOT_NO}/
                                    └── {file_name}.parquet
```

---

### 3. 파티션 키 정의

| 키 | 예시 | 허용값 |
|----|------|--------|
| LINE_ID | `ABCD` | 영문·숫자·_·- |
| EQP_ID | `ABCD801` | 영문·숫자·_·- |
| CHAMBER_ID | `PM2` | 영문·숫자·_·- |
| TYPE | `ag` / `process` | ag=NPW seasoning, process=PW |
| PARAM | `RF_POWER` | `V_` 로 시작하는 항목 제외 |
| CH_STEP | `3` / `5` / `6` | 0, -1~-5 제외 |
| COMP_DT | `2026-05-29` | YYYY-MM-DD |
| PRIORITY | `1` | |

---

### 4. 파일별 스키마

#### 4-1. score_data/trace/scores.parquet

| 컬럼 | 타입 | 설명 |
|------|------|------|
| 날짜 | str | comp PM 날짜 (YYYY-MM-DD) |
| ref_dates | str | JSON 배열 `["2026-03-10","2026-04-21"]` |
| item_name | str | trace_param_name (예: RF_POWER) |
| score | float | 0~1, **낮을수록 나쁨** |
| step | str | ch_step |
| delta_shape | float | P3 ΔShape |
| delta_jitter | float | P3 ΔJitter |
| delta_level | float | P3 ΔLevel (참고용) |
| flag | str | `OK` / `SHAPE` / `JITTER` / `SHAPE+JITTER` |
| alarm_pct | float | P2 ALARM wafer 비율 (%) |
| line_id | str | |
| eqp_id | str | |
| chamber_id | str | |
| type | str | ag / process |
| data_type | str | trace |

#### 4-2. score_data/oes/scores.parquet

| 컬럼 | 타입 | 설명 |
|------|------|------|
| 날짜 | str | comp PM 날짜 |
| ref_dates | str | JSON 배열 |
| item_name | str | rcp_step (예: 1D) |
| score | float | 0~1, 낮을수록 나쁨 |
| step | str | rcp_step |
| wavelength | float | nm |
| delta_spectrum | float | P3 ΔSpectrum |
| direction | str | UP / DOWN |
| flagged_wl | int | 유의차 파장 수 |
| line_id, eqp_id, chamber_id, type, data_type | str | 파티션 식별 |

#### 4-3. decomp_data/.../shape.parquet

| 컬럼 | 타입 | 설명 |
|------|------|------|
| 날짜 | str | comp PM 날짜 |
| ref_dates | str | JSON 배열 |
| phase | int | 0~99 |
| value | float | shape 값 (Level 제거됨, 0 근처) |
| group | str | `ref_{lot}_{slot}` / `comp_{lot}_{slot}` / `tube_q50` / `tube_usl` / `tube_lsl` |
| lot_id | str | tube 계열은 `""` |
| slot_no | int | tube 계열은 `-1` |

#### 4-4. decomp_data/.../jitter.parquet

| 컬럼 | 타입 | 설명 |
|------|------|------|
| 날짜 | str | comp PM 날짜 |
| ref_dates | str | JSON 배열 |
| lot_id | str | |
| slot_no | int | |
| jitter_rms | float | RMS noise 수준 |
| level | float | baseline (참고용) |
| group | str | `ref` / `comp` |

#### 4-5. trace raw (참고용, 대시보드 직접 읽을 경우)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| Time | Float32 | 시간 (s) |
| value | Float32 | 센서값 |
| ch_step | str | |
| lot_id | str | |
| slot_no | int | |
| eqp_id | str | |
| fdc_bin | str | |

#### 4-6. OES raw 파일명 규칙

파일명을 `#` 으로 split:
```
{line_id}#{process_id}#{step_seq}#{rcp_step}#{ppid}#{recipe_id}
#{eqp_id}#{chamber_id}#{lot_id}#{slot_no}#{wafer_end_time}.parquet
```

OES raw 스키마:
```
Time: Float32
'200.0', '200.5', ..., '800.0': Float32   (파장 컬럼, 0.5nm 간격, 1201개)
```

---

### 5. score 값 규칙

```
score = 1 / (1 + delta)   →  0~1 범위, 낮을수록 나쁨 (rank 1 = worst)

delta=0   →  score=1.00  (변화 없음)
delta=1   →  score=0.50  (flag 경계)
delta=2   →  score=0.33
delta=5   →  score=0.17  (심각)
```

---

### 6. ref_dates 처리 방법

```python
import json

# 저장 형식
ref_dates = '["2026-03-10","2026-04-21"]'  # JSON string

# 읽을 때
dates = json.loads(ref_dates)  # → ["2026-03-10", "2026-04-21"]

# 빈 경우 (첫 번째 PM)
ref_dates = '[]'
```

---

### 7. shape.parquet group 컬럼 활용

```python
import polars as pl

df = pl.read_parquet("shape.parquet")

# ref wafer 개별 신호
ref_wafers = df.filter(pl.col("group").str.starts_with("ref_"))

# comp wafer 개별 신호
comp_wafers = df.filter(pl.col("group").str.starts_with("comp_"))

# ref tube 중심선
q50 = df.filter(pl.col("group") == "tube_q50")

# ref tube 상단/하단
usl = df.filter(pl.col("group") == "tube_usl")
lsl = df.filter(pl.col("group") == "tube_lsl")
```

---

### 8. 대시보드 selectors.py 구현 가이드

```python
BASE_RESULT = "/data/pm_spider/result"  # api 컨테이너 내부 경로

# score_data 읽기
def get_score_path(line_id, eqp_id, chamber_id, type_, data_type):
    return (f"{BASE_RESULT}/score_data"
            f"/line_id={line_id}/eqp_id={eqp_id}/chamber_id={chamber_id}"
            f"/type={type_}/data_type={data_type}/scores.parquet")

# decomp_data 읽기
def get_shape_path(line_id, eqp_id, chamber_id, type_, comp_dt, param, ch_step):
    return (f"{BASE_RESULT}/decomp_data"
            f"/line_id={line_id}/eqp_id={eqp_id}/chamber_id={chamber_id}"
            f"/type={type_}/comp_dt={comp_dt}/param={param}/ch_step={ch_step}"
            f"/shape.parquet")

def get_jitter_path(line_id, eqp_id, chamber_id, type_, comp_dt, param, ch_step):
    return (f"{BASE_RESULT}/decomp_data"
            f"/line_id={line_id}/eqp_id={eqp_id}/chamber_id={chamber_id}"
            f"/type={type_}/comp_dt={comp_dt}/param={param}/ch_step={ch_step}"
            f"/jitter.parquet")
```

## API


PM 기준 주기의 Trace/OES score와 원시 파형을 조회합니다. Django session과 Portal·`pm-spider` 앱 접근이 필요합니다.
Prefix는 `/api/v1/pm_spider/`입니다.

| Method | 상대 경로 | 설명 |
| --- | --- | --- |
| GET | `meta` | partition 선택 옵션과 PM 시점 |
| POST | `compare` | 선택 조건의 score·주기·Trace/OES 상세 |

### 선택 옵션

`meta`의 query는 `lineId`, `eqpId`, `fdcBin`, `pmTimestamp`, `type`, `ppid`, `recipeId`,
`traceDataSource`를 사용합니다. 응답은 `lineIds`, `eqpIds`, `fdcBins`, `dtValues`, `pmDates`,
`types`, `ppids`, `recipeIds`, `dataSources`, `traceParamNames`, `warnings`입니다.

### 비교 요청

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
`ag`/`process` 구분과 파티션 구조는 [데이터 명세](#기능과-흐름)를 따릅니다.

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

### 응답·오류

응답은 `filters`, `window`, `trace`, `oes`, `warnings`입니다. `window`는 `pmTimestamp`, `pmDate`를 포함합니다.
`trace`와 `oes`의 요약·순위와 상세 필드는 선택 데이터 및 상세 조회 옵션에 따라 채워집니다.
조회는 `PM_COMPARISON_DATA_ROOT`의 Parquet를 읽으며 DB 변경이나 score 재계산을 수행하지 않습니다.

잘못된 입력·폴더 형식은 400, 인증·앱 접근은 401/403, 없는 데이터 경로는 404입니다.
서비스 오류는 기존 `error` 응답을 사용하며, 빈 데이터는 경고와 빈 결과로 반환할 수도 있습니다.

구현: `apps/portal/api/api/pm_comparison/views.py`, `serializers.py`, `services/comparison.py`.
