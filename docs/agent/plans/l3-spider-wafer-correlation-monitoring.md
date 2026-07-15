# ExecPlan: L3 Spider Wafer 연계 이력 모니터링

## 문서 상태
- 상태: 설계 초안
- 작성일: 2026-07-15
- 구현 여부: 미구현
- 대상 기능: Chart 단일 trellis lasso 선택 결과와 SPC/Infab 후속 이력의 wafer 단위 연계 조회

## 목표
- 사용자가 Chart의 단일 trellis에서 선택한 wafer를 하나의 분석 cohort로 만든다.
- 선택된 L3 Spider 이상감지 행을 SPC interlock, 계측 Fail, Hold, Rework 등 후속 이력과 연결한다.
- 단순 존재 여부뿐 아니라 조인 정확성, 발생 시차, 정상 wafer 대비 발생률을 확인할 수 있게 한다.
- 이후 같은 조건을 반복 조회하거나 상시 모니터링하는 기능으로 확장할 수 있는 계약을 만든다.

## 현재 상태
- `apps/web/src/features/l3-spider/components/L3SpiderChart.jsx`가 wafer/lot lasso mode 상태를 관리한다.
- `apps/web/src/features/l3-spider/components/TrellisChart.jsx`가 Plotly `plotly_selected` 이벤트를 받아 선택 키를 하이라이트한다.
- wafer 선택 키는 현재 `root_lot_id + wafer_id`, lot 선택 키는 `lot_id`이다.
- 현재 선택 상태는 `{mode, keys}`뿐이라 선택한 trellis와 상세 point 정보가 상위 화면으로 전달되지 않는다.
- Plotly `customdata`에는 `root_lot_id`, `lot_id`, `wafer_id`, `tkin_time`, `comment`와 일부 모드의 `eqc`만 들어간다.
- `/api/v1/l3_spider/data` 응답 원본에는 다음 컬럼이 이미 포함된다.
  - `tkin_time`, `tkout_time`
  - `step_seq`, `ppid`
  - `root_lot_id`, `lot_id`, `wafer_id`
  - `eqp_id`, `chamber_id`, `eqc`
  - `bin_name`, `bin_value`, `risk_score`, `display_status`
- 저장소 안에는 실제 SPC/Infab wafer 이력 source 계약이 아직 없다.

## 범위
- 단일 trellis에서 선택된 point와 wafer 정보를 상위 Chart 화면으로 전달한다.
- 선택 cohort를 Postgres의 조회 전용 wafer event 데이터와 batch join한다.
- 선택 요약, wafer별 결과, 이벤트 타임라인, 대조군 비교 화면을 제공한다.
- 데이터 freshness와 조인 신뢰도를 사용자에게 표시한다.
- 향후 조건 저장형 모니터로 확장 가능한 데이터 계약을 정의한다.

## 범위 제외
- L3 Spider 판정 알고리즘 자체를 변경하지 않는다.
- 초기 단계에서 외부 SPC 시스템을 사용자 요청마다 실시간 조회하지 않는다.
- 연계 이력만으로 L3 Spider 이상이 후속 불량의 원인이라고 단정하지 않는다.
- 실제 source schema가 확정되기 전 migration이나 운영 테이블을 만들지 않는다.

## 설계

### 1. 단일 Trellis 선택 계약
- lasso를 시작한 trellis의 `chartKey`를 선택 상태에 포함한다.
- 같은 trellis에서 추가 lasso하면 기존 선택에 point를 추가하거나 제거한다.
- 다른 trellis에서 lasso하면 이전 cohort를 교체한다.
- 선택 cohort는 source trellis 한 곳에서만 생성한다.
- 같은 wafer가 다른 trellis에도 존재할 경우 교차 하이라이트는 가능하지만 cohort 구성에는 포함하지 않는다.

권장 프론트엔드 상태:

```js
{
  chartKey: "bin_01",
  trellisBy: "bin",
  mode: "wafer",
  pointKeys: new Set(),
  wafers: [
    {
      rootLotId,
      lotId,
      waferId,
      selectedPoints: [
        {
          tkinTime,
          tkoutTime,
          eqpId,
          chamberId,
          eqc,
          stepSeq,
          ppid,
          binName,
          binValue,
          displayStatus,
          riskScore,
        },
      ],
    },
  ],
}
```

- 한 wafer가 여러 Bin point로 선택될 수 있으므로 wafer 아래에 `selectedPoints`를 유지한다.
- Plotly `customdata`에 모든 행을 중복 저장하지 않고 안정적인 `pointKey`를 추가한다.
- `pointKey`로 이미 로딩된 Chart `rows`를 조회하여 상세 정보를 복원한다.
- lasso 결과의 기본 대상은 사용자가 실제로 드래그한 point 전체로 한다.
- `High Risk만` 필터를 기본 활성화할지는 운영 요구를 확인한 뒤 결정한다.

### 2. 조인 식별자와 시간 조건
- `lot_id + wafer_id`만으로는 재공정, lot split/merge, 반복 wafer 번호 때문에 오조인 가능성이 있다.
- 다음 우선순위로 join하고 응답에 사용한 방식을 표시한다.

1. `root_lot_id + wafer_id`
2. `lot_id + wafer_id`
3. Lot genealogy 변환 후 조인
4. 식별자와 시간 범위로 후보를 좁혔지만 하나로 확정할 수 없으면 `AMBIGUOUS`

후공정 이벤트의 기본 시간 조건:

```sql
history.event_time >= COALESCE(selected.tkout_time, selected.tkin_time)
AND history.event_time < COALESCE(selected.tkout_time, selected.tkin_time)
    + INTERVAL '72 hours'
```

- 후속 이력의 기준은 `tkout_time`을 우선한다.
- `tkout_time`이 없을 때만 `tkin_time`을 사용한다.
- 72시간은 설계 기본값일 뿐이며 실제 계측 대기시간에 맞춰 설정값으로 확정한다.
- 가능하면 다음 공정 또는 지정 계측 Step 도달 시각을 시간 범위의 상한으로 사용한다.

응답의 `matchType` 후보:

- `EXACT_ROOT_LOT`
- `EXACT_LOT`
- `GENEALOGY_MATCH`
- `AMBIGUOUS`
- `NO_HISTORY`
- `SOURCE_NOT_LOADED`

### 3. Postgres 조회 전용 데이터
- 외부 SPC/Infab 시스템을 화면 요청마다 직접 조회하지 않는다.
- ETL 또는 CDC로 대시보드 Postgres에 조회 전용 read model을 적재한다.
- 여러 source를 하나의 event 계약으로 정규화한다.

후보 테이블:

```text
public.l3_spider_wafer_event
- event_id
- source_system
- root_lot_id
- lot_id
- wafer_id
- event_time
- process_step
- eqp_id
- chamber_id
- event_type
- event_code
- result
- measured_value
- lsl
- usl
- source_updated_at
- loaded_at
```

후보 인덱스:

```sql
CREATE INDEX idx_l3_wafer_event_root_time
ON public.l3_spider_wafer_event
(root_lot_id, wafer_id, event_time);

CREATE INDEX idx_l3_wafer_event_lot_time
ON public.l3_spider_wafer_event
(lot_id, wafer_id, event_time);
```

- SPC interlock만 자주 조회하면 `event_type` 조건의 partial index를 실측 후 검토한다.
- source 원본이 동일 Postgres에 있어도 복잡한 여러 테이블을 UI 요청마다 직접 조인하기보다 안정된 view 또는 적재 테이블을 권장한다.
- ETL 주기와 마지막 적재 시각을 API 응답에 포함한다.

### 4. API 계약
- 후보 경로: `POST /api/v1/l3_spider/wafer-history/query`
- marker마다 개별 요청하지 않고 선택 wafer를 한 번에 batch 조회한다.
- 초기 최대 선택 수는 500 wafer를 권장한다.
- 클라이언트가 임의 테이블명, 컬럼명, SQL 조건을 전달할 수 없게 한다.

요청 예시:

```json
{
  "selectionContext": {
    "date": "2026-06-20",
    "chartKey": "bin_01",
    "trellisBy": "bin"
  },
  "wafers": [
    {
      "rootLotId": "ROOT_A",
      "lotId": "LOT_A",
      "waferId": "W01",
      "tkinTime": "2026-06-20 18:30:00",
      "tkoutTime": "2026-06-20 19:00:00",
      "eqpId": "EQP_301",
      "chamberId": "PM1",
      "stepSeq": "step_001",
      "ppid": "ppid_a",
      "binName": "bin_01",
      "displayStatus": "High Risk Chamber"
    }
  ],
  "eventTypes": ["SPC_INTERLOCK", "MEASUREMENT_FAIL", "HOLD", "REWORK"],
  "windowHours": 72
}
```

응답 예시:

```json
{
  "summary": {
    "selectedWaferCount": 25,
    "matchedWaferCount": 20,
    "spcInterlockCount": 7,
    "measurementFailCount": 4,
    "noHistoryCount": 3,
    "ambiguousCount": 2
  },
  "wafers": [],
  "sourceFreshness": {
    "sourceUpdatedAt": "2026-07-15 09:00:00",
    "loadedAt": "2026-07-15 09:10:00"
  }
}
```

- backend는 `jsonb_to_recordset`, `VALUES`, 임시 테이블 중 실제 선택 수에 맞는 batch join 방식을 사용한다.
- 선택 payload는 인증된 사용자가 이미 조회한 Chart 데이터 범위를 벗어나지 않는지 검증한다.
- 대조군 집계는 sampling된 Chart rows를 사용하지 않고 원본 또는 별도 fact table에서 계산한다.

### 5. 화면 구성
- Chart 아래에 접고 펼칠 수 있는 `선택 Wafer 분석` 패널을 둔다.
- 선택 직후에는 cohort 요약과 `연계 이력 조회` 명령만 표시한다.
- 조회 후 다음 정보를 제공한다.

KPI:

- 선택 Wafer
- High Risk / Warning
- 정확히 매칭된 Wafer
- SPC Interlock
- 계측 Fail
- 이력 없음
- 모호한 매칭

Wafer 결과 표:

- L3 판정과 Risk Score
- Root Lot / Lot / Wafer
- Step Seq / PPID / EQPCH / Bin
- EQP `TKOUT_TIME`
- 후속 계측 Step / EQP / Chamber
- Interlock 종류, 코드, 결과, 시각
- L3 이후 이벤트까지 걸린 시간
- Match Type

행 확장:

- EQP 공정 시작과 종료
- 후속 공정 이동
- 계측 결과
- SPC Interlock
- Hold / Rework / Scrap
- source별 시간순 이벤트

집계와 비교:

- EQPCH, Bin, Step Seq, PPID별 후속 이상률
- 선택 High Risk wafer의 Interlock 발생률
- 같은 lot의 비선택 또는 정상 wafer 발생률
- 두 cohort의 비율 차이와 risk ratio

- 화면 문구는 `원인`이 아니라 `연계 이력`, `후속 발생`, `상관 후보`로 표현한다.
- `SOURCE_NOT_LOADED`와 `NO_HISTORY`를 구분한다.

### 6. 상시 모니터 확장
- 과거 lasso selection은 정적인 wafer 목록이므로 그 자체는 상시 모니터 조건이 아니다.
- 상시 모니터는 선택 결과에서 source 조건을 추출해 별도 rule로 저장한다.

저장 후보 조건:

- Line / Process / EDS Step / Step Seq / PPID
- EQPCH / Bin
- L3 severity
- 후속 event type
- 시간 범위
- 조회 기간
- 알림 기준

- 스케줄러가 새 L3 detection cohort와 후속 event를 주기적으로 연결한다.
- 상태 변화와 알림 이력을 별도 저장한다.
- 초기 구현은 ad-hoc 조회로 제한하고 실제 사용 패턴을 확인한 후 rule 저장을 추가한다.

### 7. 성능과 캐시
- 선택 wafer 전체를 하나의 API 요청으로 조회한다.
- 요청 hash, event source version, window를 cache key로 사용할 수 있다.
- 5분 내 동일 selection 재조회는 짧은 TTL cache를 검토한다.
- 결과가 크면 wafer 요약과 상세 이벤트를 분리하고 상세 이벤트는 행 확장 시 조회한다.
- 대량 선택은 비동기 job으로 전환하거나 선택 상한을 적용한다.
- 실제 쿼리에 `EXPLAIN (ANALYZE, BUFFERS)`를 실행해 인덱스를 확정한다.

### 8. 권한과 감사
- SPC/Infab 이력이 별도 민감 데이터이면 `l3_spider.view_wafer_history` 권한을 추가한다.
- 권한이 없는 사용자는 lasso와 하이라이트는 사용할 수 있지만 연계 이력 패널은 표시하지 않는다.
- 저장형 모니터에는 생성자, 수정자, 조건 변경, 알림 실행 이력을 남긴다.
- API는 authenticated user가 조회 가능한 Line 범위가 있다면 동일 범위를 적용한다.

## 실행 단계
- [ ] 실제 SPC/Infab source 테이블과 컬럼 계약을 확인한다.
- [ ] Lot genealogy와 wafer 식별자 정규화 규칙을 확정한다.
- [ ] 후속 이벤트 종류와 시간 범위를 확정한다.
- [ ] 단일 trellis selection state와 `pointKey` 계약을 구현한다.
- [ ] 선택 wafer 요약 패널을 구현한다.
- [ ] Postgres wafer event read model과 적재 흐름을 구현한다.
- [ ] Batch join API와 권한을 구현한다.
- [ ] wafer 결과 표와 이벤트 타임라인을 구현한다.
- [ ] 정상 wafer 대조군과 발생률 비교를 구현한다.
- [ ] 실데이터 정확성, 성능, 매칭 품질을 검증한다.
- [ ] 운영 사용 후 저장형 모니터 필요성을 재평가한다.

## 검증
- 단일 trellis selection만 cohort에 포함되는지 확인한다.
- 동일 trellis에서 추가 lasso 시 선택 추가/제거가 정확한지 확인한다.
- 다른 trellis 선택 시 기존 cohort가 교체되는지 확인한다.
- 동일 wafer의 여러 selected point가 한 wafer 아래 보존되는지 확인한다.
- exact, genealogy, ambiguous, no-history 케이스를 각각 테스트한다.
- `tkout_time` 이후의 이벤트만 연결되는지 확인한다.
- source 미적재와 실제 이력 없음을 구분하는지 확인한다.
- 100, 500 wafer batch에서 응답 시간과 query plan을 측정한다.
- 권한 없는 사용자의 API와 UI 접근이 차단되는지 확인한다.
- 정상 대조군 계산에 Chart sampling 데이터가 사용되지 않는지 확인한다.

## 위험과 대응
- 위험: `lot_id + wafer_id` 오조인으로 잘못된 후속 이력이 표시될 수 있다.
- 대응: root lot, genealogy, 시간 범위를 함께 사용하고 match type을 노출한다.
- 위험: SPC/Infab 적재 지연을 이력 없음으로 오해할 수 있다.
- 대응: source freshness와 `SOURCE_NOT_LOADED` 상태를 표시한다.
- 위험: 선택 wafer별 개별 조회로 DB round trip이 증가할 수 있다.
- 대응: batch join과 선택 상한을 사용한다.
- 위험: Chart 정상 point sampling으로 대조군 통계가 왜곡될 수 있다.
- 대응: 대조군은 backend 원본 또는 전용 fact table에서 집계한다.
- 위험: 단순 시간적 선후관계를 인과관계로 오해할 수 있다.
- 대응: 정상 cohort 비교와 중립적인 화면 문구를 사용한다.

## 구현 전 확정 사항
1. 실제 SPC/Infab 데이터의 DB, schema, table 이름은 무엇인가.
2. `root_lot_id`, `lot_id`, `wafer_id` 중 source에서 보장되는 식별자는 무엇인가.
3. Lot split, merge, rework genealogy를 조회할 수 있는가.
4. SPC Interlock과 계측 Fail을 판별하는 event code와 result 값은 무엇인가.
5. EQP 종료 후 후속 이력을 찾는 기본 시간 범위는 몇 시간인가.
6. 사용자별 Line 또는 source data 접근 권한이 필요한가.
7. 초기 범위를 ad-hoc 조회로 할지 저장형 모니터까지 포함할지 결정한다.

## 진행 기록
- 2026-07-15: 현재 Chart lasso와 `/data` 컬럼 계약을 확인하고 설계 초안을 작성했다.
