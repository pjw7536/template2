# ExecPlan: Observer 대용량 데이터 안정화

## 목표
- `/observer`가 로그 원천 테이블과 조회 기간의 데이터가 크게 증가해도 API worker, DB, 브라우저 메모리, DOM을 무제한으로 사용하지 않게 한다.
- 최초 화면은 제한된 데이터 예산 안에서 빠르게 표시하고, 추가 데이터가 있다는 사실을 숨기지 않으며 사용자가 기간을 좁히거나 다음 페이지를 명시적으로 조회할 수 있게 한다.
- 로그 목록과 상세 payload를 분리해 Timeline/Data Log에 필요하지 않은 대형 필드의 DB 조회, Python 변환, JSON 직렬화, 네트워크 전송을 줄인다.
- 현재 7개 로그 유형의 독립 필터, 부분 실패, 선택 연동, 날짜 범위, 상세 화면 동작을 보존한다.
- 기존 `/api/v1/observer/logs` 및 `/api/v1/observer/logs/<type>` 배열 응답을 즉시 깨지 않고 신규 paged API로 단계적으로 전환한다.
- 성능 개선 여부를 운영과 유사한 데이터로 재현·계측하고, 배포·롤백 기준을 수치로 남긴다.

## 성공 기준

### 사용자 동작
- 최초 진입에서 최근 로그 일부가 먼저 표시되고, 나머지 로그를 조회 중이라는 이유로 전체 화면이 빈 상태로 남지 않는다.
- 일부 로그 유형이 실패해도 성공한 유형의 Timeline과 Data Log는 계속 사용할 수 있다.
- 조회 결과가 잘렸을 때 `hasMore` 또는 `truncated` 상태와 다음 행동을 화면에 명시한다.
- Data Log의 키보드 탐색, 선택, Timeline 선택 연동, 상세 열기 동작을 유지한다.
- 날짜 범위, 유형 필터, TIP 그룹 필터가 paged data에도 동일하게 적용된다.
- 로딩, 빈 결과, 부분 오류, 전체 오류, 추가 페이지 로딩, 상세 로딩 상태를 서로 다른 UI로 표시한다.

### 권장 초기 성능 목표
- 아래 수치는 구현 시작 시의 임시 수용 기준이며 Milestone 0 계측 결과로 확정한다.
- 성능 측정은 개발용 소량 fixture가 아니라 운영과 비슷한 데이터 분포를 가진 staging DB에서 수행한다.

| 구분 | 권장 목표 |
| --- | --- |
| 초기 batch API p95 | 2.5초 이하 |
| 단일 유형 다음 페이지 API p95 | 1.0초 이하 |
| 단일 유형 DB query p95 | 500ms 이하 |
| 초기 압축 전 JSON | 1.5MB 이하 |
| 초기 브라우저 상주 로그 | 전체 유형 합계 5,000건 이하 |
| Data Log 실제 DOM row | header 제외 100개 이하 |
| Timeline 주입 item | 전체 유형 합계 5,000개 이하 |
| main thread long task | 50ms 초과 작업이 연속 발생하지 않음 |
| Data Log 스크롤 | 일반 업무용 PC에서 55fps 이상 |
| EQP/기간 20회 변경 후 heap | 안정 구간 대비 지속 증가 50MB 이하 |
| 20 concurrent users | 오류율 1% 미만, API p95 3초 이하 |

### 데이터 프로파일
- `small`: 유형별 기간 내 100건 이하
- `normal`: 유형별 기간 내 1,000건
- `large`: 유형별 기간 내 10,000건
- `stress`: 유형별 기간 내 100,000건 이상
- 같은 시각에 여러 row가 존재하는 tie 데이터와 상세 Text/JSON이 큰 row를 별도 포함한다.
- EQP, TIP처럼 상태 구간을 계산하는 로그와 Interlock, CTTTM, RACB, ESOP처럼 point로 표시하는 로그를 분리해 측정한다.

## 현재 상태

### API와 요청
- 프론트 기본 날짜 범위는 7일이고 최대 90일까지 선택할 수 있다.
- 프론트는 날짜 `from/to`를 전달하지만 `limit`을 전달하지 않는다.
- backend는 `limit`이 전달된 경우에만 양의 정수 검증과 최대 5,000건 clamp를 수행한다.
- `limit`이 없으면 기간 안의 row를 모두 materialize해서 배열로 반환한다.
- 7개 유형이 기본 활성화되어 EQP, TIP, SPC Interlock, FDC Interlock, CTTTM, RACB, ESOP API가 동시에 실행된다.
- Observer API client는 한 호출 안에서 최대 3회 시도하고, 공통 React Query client도 query를 1회 재시도한다.
- 최악의 장애 상황에서는 한 사용자 동작이 유형별 최대 6회, 7개 유형 합계 최대 42회의 시도로 증폭될 수 있다.
- React Query의 abort `signal`이 Observer API client로 전달되지 않아 EQP나 날짜 범위가 바뀌어도 이전 HTTP 요청이 서버에서 계속 실행될 수 있다.
- API container 기본값은 Gunicorn worker 3개, thread 2개이므로 한 사용자의 7개 동시 요청만으로 기본 처리 slot을 순간적으로 모두 점유할 수 있다.

### Backend 조회와 응답
- `_fetch_all()`은 `cursor.fetchall()` 후 모든 row를 다시 dict list로 복제한다.
- 통합 `/logs` endpoint는 7개 유형을 모두 조회한 뒤 Python list를 합치고 다시 정렬한다.
- 통합 endpoint에 `limit`을 전달해도 각 유형에서 limit만큼 조회한 뒤 전체를 잘라내므로 최대 `7 × limit` row를 읽고 `limit` row만 반환할 수 있다.
- EQP, TIP, RACB selector는 Django model instance 전체를 생성한 뒤 list comprehension으로 응답 dict를 만든다.
- Interlock 목록 응답은 Timeline/Data Log에 필요하지 않은 30개 이상의 상세 필드를 포함한다.
- CTTTM 목록 응답은 description, core summary, summary를 모두 포함한다.
- ESOP 목록 응답은 모든 row의 `defect_url` JSON을 Python에서 파싱하고 defect map URL 배열을 생성한다.
- 응답은 단순 배열이어서 다음 페이지, 잘림 여부, 읽은 구간, 유형별 부분 오류를 표현할 수 없다.

### DB
- EQP는 `(eqp_cb_lookup, -chg_time)`, TIP은 `(eqp_cb_lookup, -gpm_update_date)`, RACB는 `(eqp_cb_lookup, -update_date)` 인덱스를 가진다.
- CTTTM은 `(eqp_id_lookup, -inprg_date)`, ESOP는 `(eqp_id_lookup, -created_at)` 인덱스를 가진다.
- CTTTM workorder join용 추가 인덱스도 이미 존재한다.
- 따라서 현재 단계에서 모든 원천 테이블에 인덱스를 추가하는 것은 우선 작업이 아니다.
- Interlock은 `prod_eqp_id`, `interlock_kind`, `prod_progs_time`을 문자열로 저장한다.
- Interlock 조회는 `Upper(Trim(...))`, regex, 문자열 range를 사용하고 조회 row마다 Python `strptime()`을 실행한다.
- Interlock에는 현재 조회식과 맞춘 expression index가 있지만 typed datetime과 명시적 lookup 컬럼은 없다.

### Frontend 변환과 렌더링
- 유형별 로그에 duration 계산을 수행하고, 7개 배열을 합쳐 다시 정렬한다.
- Data Log 변환에서 filter/map/sort를 다시 수행한다.
- 각 Timeline item 생성에서도 filter/sort/map을 수행한다.
- Data Log는 `data.map()`으로 모든 row component를 DOM에 렌더링한다.
- 선택된 Timeline item과 연결할 Data Log row를 찾을 때 이미 렌더링된 DOM 전체에서 `querySelector()`를 수행한다.
- vis Timeline data 변경 시 기존 `DataSet`을 `clear()`하고 모든 item을 다시 `add()`한다.
- Timeline은 현재 조회된 전체 로그 범위를 기준으로 min/max를 계산하고 모든 item을 data set에 넣는다.
- React Query key에 날짜 범위가 포함되므로 사용자가 여러 구간을 조회하면 큰 배열 cache가 gc 전까지 여러 벌 남을 수 있다.

### 이미 완료된 관련 개선
- Observer lookup 컬럼과 주요 lookup+시간 인덱스가 추가되었다.
- CTTTM join 조회용 보수적 인덱스가 추가되었다.
- 날짜 범위 slider가 기본 7일, 최대 90일로 추가되었다.
- SPC/FDC Interlock endpoint와 expression index가 추가되었다.
- 이 ExecPlan은 기존 개선을 되돌리거나 중복 구현하지 않고 다음 병목 단계만 다룬다.

## 범위

### 필수 범위
- Observer paged/compact/detail API contract
- 로그 query validation과 opaque cursor
- 유형별 compact selector와 detail selector
- batch 최초 조회와 유형별 다음 페이지 조회
- 부분 실패 응답
- frontend request cancellation, retry 단일화, cache 상한
- Data Log row virtualization
- Timeline item 상한과 증분 DataSet 갱신
- 결과 잘림/추가 로딩/부분 실패 UI
- Interlock typed lookup/time schema와 loader 파생 필드 동시 저장
- backend/frontend/API/module/configuration 문서
- query plan, response size, browser rendering, concurrency 검증

### 조건부 범위
- cursor query가 기존 index에서 정렬 비용을 유발한다고 `EXPLAIN (ANALYZE, BUFFERS)`로 확인된 원천만 `-id` tie-breaker를 포함한 신규 복합 인덱스를 추가한다.
- bounded data 적용 후에도 timestamp 변환이나 정렬이 50ms를 넘을 때만 Web Worker를 도입한다.
- 기준정보 API의 반복 조회가 실제 p95 병목으로 확인될 때만 짧은 cache를 추가한다.
- JSON payload가 충분히 작아진 뒤에도 네트워크 전송 비중이 크면 Nginx gzip을 활성화한다.
- 전체 테이블 크기와 retention 요구가 확인된 뒤에만 월 단위 partition/archive를 별도 ExecPlan으로 분리한다.

### 수정하지 않을 영역
- Observer의 로그 의미, 타입 이름, 표시 순서, 권한 정책
- data movement 적재 주기와 원천 파일 계약
- TIP/RACB/CTTTM/ESOP의 업무 규칙
- 다른 feature의 공통 API client 또는 React Query 정책
- 적용된 기존 migration 수정
- 사용자 요청과 무관한 frontend 디자인 개편
- 기존 `/logs` 배열 endpoint의 즉시 삭제
- 별도 `/ESOP_Dashboard/tip-status/:lineId` 제품 화면인 Tkin Prevent의 API·UI
- `apps/web/src/lib/config/portalNavigation.js`의 현재 사용자 변경

## 구현 전 결정 게이트

아래 항목은 계획의 권장안을 제시하지만 API/DB 계약에 영향을 주므로 구현 시작 전에 사용자 확인이 필요하다.

1. 신규 paged endpoint를 추가하고 기존 배열 endpoint를 유지할지 확정한다.
   - 권장: 신규 `/logs/page`, `/logs/<type>/page`, `/logs/<type>/detail`을 추가하고 기존 endpoint는 최소 한 release 이상 유지한다.
2. 초기 결과가 일부만 표시되는 것을 허용할지 확정한다.
   - 권장: 허용하되 `hasMore`, 유형별 조회 건수, 기간 좁히기 안내를 반드시 표시하고 silent truncation은 금지한다.
3. API가 허용할 최대 날짜 범위를 확정한다.
   - 권장: frontend와 동일하게 90일로 제한하고 그보다 긴 조회는 400과 구체적인 오류 코드를 반환한다.
4. 목록 tooltip에서 전체 comment 대신 preview를 사용하는 것을 확정한다.
   - 권장: 200자 preview를 사용하고 전체 comment/summary/defect map은 선택 후 detail API로 조회한다.
5. 초기 page budget을 확정한다.
   - 권장: 유형별 기본 250건, 유형별 최대 1,000건, 최초 batch 최대 1,750건, 브라우저 상주 합계 최대 5,000건으로 시작하고 계측 후 조정한다.
6. Interlock 기존 row의 문자열 조회 호환 여부를 확정한다.
   - 확정: 호환 경로와 backfill은 제공하지 않으며 typed 파생 필드가 비어 있는 기존 row는 조회에서 제외한다.
7. 성능 수용 기준을 어떤 staging 데이터와 동시 사용자 수로 승인할지 확정한다.
   - 권장: 위 `large/stress` 데이터 프로파일과 20 concurrent users를 최소 기준으로 사용한다.

답변은 번호 기준으로 기록한다. 권장안을 모두 수용하는 경우 `1~7 권장안`으로 확정할 수 있다.

구현 전 Hard-Block 확인이 필요하다.

## 설계

### 전체 데이터 흐름

```text
ObserverPage
  ├─ 최초 batch query
  │    └─ GET /api/v1/observer/logs/page
  │          ├─ type별 compact selector
  │          ├─ pageSize + 1 조회
  │          └─ type별 items / cursor / hasMore / error
  ├─ 다음 페이지 query
  │    └─ GET /api/v1/observer/logs/<type>/page
  ├─ 선택 상세 query
  │    └─ GET /api/v1/observer/logs/<type>/detail
  ├─ virtualized Data Log
  └─ bounded + incremental vis Timeline
```

### API 하위 호환 전략
- 기존 endpoint는 그대로 유지한다.
  - `GET /api/v1/observer/logs`
  - `GET /api/v1/observer/logs/eqp`
  - `GET /api/v1/observer/logs/tip`
  - `GET /api/v1/observer/logs/spc-interlock`
  - `GET /api/v1/observer/logs/fdc-interlock`
  - `GET /api/v1/observer/logs/ctttm`
  - `GET /api/v1/observer/logs/racb`
  - `GET /api/v1/observer/logs/esop`
- 신규 frontend만 paged endpoint를 사용한다.
- frontend rollback 시 이전 bundle이 기존 endpoint를 계속 호출할 수 있어야 한다.
- 신규 endpoint가 안정화되기 전 기존 endpoint의 response shape, 날짜 의미, ID를 변경하지 않는다.
- 기존 endpoint 삭제는 사용처 검색, access log 확인, 별도 deprecation 공지 후 별도 작업으로 분리한다.

### 최초 batch endpoint

#### 요청

```http
GET /api/v1/observer/logs/page
  ?eqpId=EQP-001
  &from=2026-07-01
  &to=2026-07-07
  &types=eqp,tip,spc-interlock,fdc-interlock,ctttm,racb,esop
  &pageSize=250
```

#### 응답

```json
{
  "data": {
    "eqp": {
      "items": [],
      "nextCursor": "opaque-token-or-null",
      "hasMore": false,
      "error": null
    },
    "tip": {
      "items": [],
      "nextCursor": "opaque-token-or-null",
      "hasMore": true,
      "error": null
    },
    "esop": {
      "items": [],
      "nextCursor": null,
      "hasMore": false,
      "error": {
        "code": "SOURCE_QUERY_TIMEOUT",
        "message": "ESOP 로그 조회 시간이 초과되었습니다."
      }
    }
  },
  "meta": {
    "from": "2026-07-01T00:00:00",
    "to": "2026-07-07T23:59:59.999999",
    "pageSize": 250,
    "partial": true
  }
}
```

#### 상태 코드
- query contract가 잘못되면 전체 요청을 실행하지 않고 400을 반환한다.
- 인증/권한 오류는 기존 정책을 따른다.
- 일부 source만 실패하면 200과 `meta.partial=true`, 유형별 `error`를 반환한다.
- 모든 source가 timeout 또는 DB 오류로 실패하면 503을 반환한다.
- 예외 원문, SQL, 내부 host 정보는 응답에 포함하지 않는다.

#### backend 실행 정책
- 최초 batch는 한 HTTP request에서 유형을 bounded하게 순차 실행한다.
- 한 source가 정해진 query budget을 초과하면 해당 source만 실패 처리하고 다음 source를 계속한다.
- 초기 구현에서 thread pool로 7개 DB query를 다시 병렬화하지 않는다.
- 운영 계측에서 순차 latency가 목표를 넘을 때만 최대 2개 수준의 bounded concurrency를 별도 검토한다.

### 유형별 페이지 endpoint

```http
GET /api/v1/observer/logs/tip/page
  ?eqpId=EQP-001
  &from=2026-07-01
  &to=2026-07-07
  &pageSize=250
  &cursor=opaque-token
```

```json
{
  "items": [],
  "page": {
    "nextCursor": "opaque-token-or-null",
    "hasMore": true,
    "pageSize": 250
  },
  "meta": {
    "logType": "TIP",
    "from": "2026-07-01T00:00:00",
    "to": "2026-07-07T23:59:59.999999"
  }
}
```

### cursor 규칙
- cursor는 frontend가 내부 구조에 의존하지 않는 opaque URL-safe token이다.
- token payload는 version, source type, event time, source tie-breaker를 포함한다.
- cursor의 source type, 날짜 범위, EQP가 현재 요청과 다르면 400을 반환한다.
- token은 malformed input으로 selector 예외가 발생하지 않게 serializer에서 검증한다.
- 기본 정렬은 `event_time DESC, source_tie_breaker DESC`이다.
- 다음 페이지 조건은 다음과 같은 keyset 비교를 사용한다.

```text
event_time < cursor.event_time
OR (event_time = cursor.event_time AND source_tie_breaker < cursor.tie_breaker)
```

- selector는 `pageSize + 1`건만 조회해 `hasMore`를 판정하고 응답에는 `pageSize`건만 넣는다.
- cursor에는 개인정보, comment, 내부 SQL 정보가 들어가지 않는다.
- token 서명 필요성은 위변조가 권한 상승이나 데이터 범위 확장으로 이어지는지 검토한다. 최소한 요청 filter와 cursor filter의 일치 여부를 서버에서 재검증한다.

### 유형별 cursor와 projection

| 유형 | 정렬/cursor 후보 | compact 필드 | detail 전용 필드 |
| --- | --- | --- | --- |
| EQP | `chg_time`, `id` | id, logType, eventType, eventTime, operator, commentPreview | 전체 comment 및 추가 원천 필드가 필요할 때만 확장 |
| TIP | `gpm_update_date`, `id` | id, logType, eventType, eventTime, operator, process, step, ppid, commentPreview | 전체 comment 및 추가 TIP 속성 |
| SPC/FDC | `prod_progs_at`, `id` | id, sourceId, logType, eventTime, eventType, metroItem, interlockType, commentPreview | spec, lot, process, equipment, 상세 comment 전체 |
| CTTTM | `inprg_date`, model id | id, logType, eventType, eventTime, url, commentPreview | description, coreSummary, summary |
| RACB | `update_date`, model id | id, logType, eventType, eventTime, operator, url, lineId | 추가 RACB 상세가 필요할 때 별도 projection |
| ESOP | `created_at`, id | id, logType, eventType, eventTime, operator, status, lineId, eqpId, lotId, commentPreview | 전체 comment, defectMaps |

- compact payload의 기존 `id` 값은 Data Log/Timeline selection 호환을 위해 유지한다.
- cursor tie-breaker는 API 응답에 노출할 필요가 없으며 opaque cursor 내부에서만 사용한다.
- `commentPreview`는 Unicode 문자열 기준 권장 200자로 제한하고 잘림 여부를 별도 boolean으로 표시한다.
- ESOP defect map URL 파싱은 detail selector에서만 수행한다.
- CTTTM summary는 detail selector에서만 join/projection한다.
- Interlock 상세 필드도 선택된 한 row에 대해서만 매핑한다.

### 상세 endpoint

```http
GET /api/v1/observer/logs/esop/detail
  ?eqpId=EQP-001
  &logId=12345
```

- `eqpId`와 `logId`가 함께 일치하는 row만 반환해 다른 설비 row를 ID만으로 읽지 못하게 한다.
- `logType`별 ID 형식을 serializer에서 검증한다.
- 존재하지 않으면 404를 반환한다.
- detail query는 selected row가 바뀔 때만 실행한다.
- frontend detail cache key는 `["observer", "logDetail", type, eqpId, logId]`로 구성한다.
- detail에는 pagination을 적용하지 않지만 ESOP defect map처럼 내부 배열이 커질 수 있는 필드는 별도 최대값과 `hasMoreDefectMaps`를 둔다.

### request validation
- `apps/api/api/observer/serializers.py`에 paged log query serializer와 detail query serializer를 둔다.
- view는 serializer validation, selector 호출, HTTP status 결정만 담당한다.
- 허용 type은 기존 fetcher registry와 동일한 목록으로 제한한다.
- `pageSize`는 기본 250, 최소 1, 최대 1,000으로 clamp하지 않고 범위를 벗어나면 400을 반환한다. 조용한 clamp로 호출자 오류를 숨기지 않는다.
- `from/to`는 기존 날짜/datetime 의미를 유지한다.
- 최대 90일 정책이 확정되면 backend에서도 span을 검사한다.
- `from > to`, cursor/request mismatch, 알 수 없는 type은 각각 안정적인 error code를 반환한다.

### Backend 책임 분리
- `views.py`: HTTP query validation, selector 호출, status/response
- `serializers.py`: request schema, cursor field validation, 날짜 범위 검증
- `observer/selectors.py`: 유형 오케스트레이션, compact/detail response mapping, 부분 실패 경계
- 각 data movement `selectors.py`: 소유 테이블의 read-only keyset query와 최소 projection
- 각 data movement `models.py`: schema와 index 선언
- 각 data movement `services/loader.py`: lookup/time dual-write
- view에서 ORM이나 raw SQL을 직접 실행하지 않는다.
- selector에서 write/backfill을 수행하지 않는다.

### Frontend query 흐름
- 최초 조회는 하나의 batch query를 사용한다.
- 유형별 `hasMore`와 cursor를 query data에 보존한다.
- “더 불러오기”는 해당 유형의 page endpoint만 호출한다.
- page 결과는 기존 item ID 기준으로 중복 제거하고 시간 역순을 유지한다.
- disabled type은 다음 batch 요청의 `types`에서 제외한다.
- filter를 다시 활성화했을 때 같은 EQP/기간 cache가 유효하면 재사용하고, 없으면 해당 type 첫 page만 조회한다.
- page query는 React Query의 `queryFn({ signal })`을 API client로 전달한다.
- API client는 caller signal과 30초 timeout signal을 함께 처리한다.
- EQP, 날짜, type이 바뀌면 이전 request가 즉시 abort되는지 검증한다.
- Observer API client 내부 retry를 제거하고 React Query layer 한 곳에서만 retry를 결정한다.
- retry 권장값은 429/502/503/network error에 1회, 400/401/403/404/500에는 0회이다.
- exponential delay에는 jitter를 추가해 여러 browser가 동시에 재시도하지 않게 한다.
- 큰 query cache가 여러 날짜 범위에 남지 않게 Observer log query의 `gcTime`을 권장 2분으로 명시하고 실제 heap 계측으로 조정한다.
- `select` 단계에서 `eventTimeMs`를 한 번 계산해 이후 정렬마다 `new Date()`를 반복하지 않는다.

### Data Log virtualization
- `@tanstack/react-virtual`을 `apps/web` dependency로 추가하는 방안을 사용한다.
- scroll owner는 현재 Data Log body 한 곳으로 유지한다.
- virtualizer의 권장 초기값은 예상 row 높이 40px, overscan 8행이다.
- 실제 row 높이가 달라질 수 있으므로 `measureElement`로 측정한다.
- 전체 row를 DOM에 넣지 않고 viewport와 overscan row만 `ObserverTableRow`로 렌더링한다.
- 선택 row 이동은 DOM `querySelector()` 대신 `id -> rowIndex` Map과 `virtualizer.scrollToIndex()`를 사용한다.
- 선택 row가 아직 로드되지 않았으면 Timeline selection을 지우지 않고 “선택한 로그가 현재 로드 범위 밖입니다” 상태를 표시한다.
- keyboard focus가 virtualized row unmount로 사라지지 않도록 roving focus 또는 container 중심 keyboard handler를 적용한다.
- `aria-setsize`, `aria-posinset`, `aria-selected` 등 virtual list 접근성 정보를 유지한다.
- table header는 고정 영역, body만 세로 scroll owner가 되게 한다.
- 같은 region에 추가 y-scroll container를 만들지 않고 `min-h-0`, `min-w-0`를 유지한다.

### Timeline 제한과 증분 갱신
- Timeline은 frontend에 상주한 bounded item만 표시한다.
- 유형별 `hasMore`가 있으면 Timeline 제목 옆에 “일부 데이터 표시 중” 상태와 조회 건수를 표시한다.
- 전체 기간의 모든 marker가 표시된 것처럼 오해하게 만드는 silent truncation은 금지한다.
- `replaceObserverItems()`의 `clear()+add()`를 ID diff 기반 `add/update/remove`로 바꾼다.
- 이전 item Map과 다음 item Map을 비교해 변경된 item만 DataSet에 적용한다.
- 데이터 추가 시 기존 zoom window를 유지한다.
- selection ID가 유지되는 item update에서는 selection을 재설정하지 않는다.
- 전체 Timeline item budget은 권장 5,000개로 시작한다.
- budget을 넘으면 자동으로 더 읽지 않고 사용자가 기간을 좁히도록 안내한다.
- vis-timeline 자체 clustering은 browser가 모든 raw item을 가진 뒤의 rendering 최적화이므로 서버 pagination 대체로 사용하지 않는다.
- 서버 downsampling은 EQP/TIP 연속 구간 의미를 바꿀 수 있으므로 초기 범위에서 제외하고 별도 도메인 결정 후 진행한다.

### 반복 변환 정리
- page 응답 수신 시 공통 normalized log model을 한 번 생성한다.
- `eventTimeMs`, 표시 timestamp, stable type key를 이 단계에서 계산한다.
- 유형별 page가 이미 최신순이면 병합은 전체 재정렬 대신 k-way merge 또는 신규 page 구간 삽입을 사용한다.
- Data Log는 이미 정렬된 merged array를 다시 sort하지 않는다.
- Timeline item 생성은 해당 유형 array 순서를 신뢰하되 development assertion으로 ordering을 점검한다.
- bounded data 적용 후에도 변환이 50ms를 넘는 경우에만 Worker로 이전한다.
- `useMemo`, `React.memo`는 profiler로 재렌더 원인이 확인된 component에만 적용한다.

### Interlock typed schema

#### 신규 필드
- `prod_eqp_id_lookup`: 정규화된 설비 ID
- `interlock_kind_lookup`: 정규화된 SPC/FDC 종류
- `prod_progs_at`: Asia/Seoul 원천 시각을 timezone-aware datetime으로 변환한 값

#### 적용 순서
1. nullable 신규 필드만 추가하는 `0005` migration을 생성한다.
2. loader가 기존 필드와 신규 필드를 동시에 저장하도록 dual-write한다.
3. 신규 적재 row의 세 필드가 채워지는 테스트를 통과시킨다.
4. 잘못된 `prod_progs_time`은 신규 적재 시 `prod_progs_at=null`로 저장한다.
5. 신규 `(prod_eqp_id_lookup, interlock_kind_lookup, -prod_progs_at, -id)` index를 concurrent 방식으로 추가한다.
6. `ANALYZE m_interlock` 후 신규 selector의 query plan을 확인한다.
7. Observer selector는 feature flag 없이 typed field만 조회한다.
8. 기존 expression index는 `0005` concurrent migration에서 함께 제거한다.

#### migration 안전
- 기존 적용 migration은 수정하지 않는다.
- concurrent index migration은 PostgreSQL 요구에 맞게 `atomic=False`를 사용한다.
- index 이름은 30자 이하 deterministic 이름을 사용한다.
- nullable 상태를 유지할지 non-null constraint를 추가할지는 invalid 원천 데이터 정책 확정 후 결정한다.
- typed 파생 필드가 비어 있는 기존 row는 Observer 조회에서 제외되는 계약을 테스트한다.

### 다른 로그 source index 정책
- 기존 lookup+시간 index를 우선 사용한다.
- cursor tie-breaker `-id`가 index에 없더라도 같은 timestamp tie 수가 작으면 기존 index가 충분할 수 있다.
- 각 source에서 `EXPLAIN (ANALYZE, BUFFERS)`로 sort node, scanned rows, heap fetch, execution time을 기록한다.
- 다음 조건 중 하나를 만족할 때만 `(lookup, -time, -id)` index를 추가한다.
  - pageSize 250 조회가 성능 목표를 반복적으로 초과한다.
  - 같은 timestamp tie가 커서 explicit sort가 지배적이다.
  - planner가 기존 index 대신 sequential scan을 선택하고 통계 갱신 후에도 개선되지 않는다.
- 신규 index를 추가할 때 기존 prefix index를 즉시 제거하지 않는다.
- write amplification과 index storage를 함께 측정한 뒤 중복 index 제거를 별도 판단한다.

### UI 상태
- 최초 loading: 각 panel skeleton과 “로그를 조회하고 있습니다” 문구
- 유형별 loading: 해당 Timeline에만 compact loading 표시
- 다음 페이지 loading: 기존 row를 유지하고 하단 progress 표시
- partial error: 성공 data 유지, 실패 유형 이름과 개별 재시도 action 표시
- all error: 원인 요약과 전체 재시도 action
- empty: 실제 결과 없음과 filter로 숨겨진 상태를 구분
- truncated/hasMore: 표시 건수와 기간 좁히기/더 불러오기 action
- detail loading: 선택 상태는 유지하고 detail skeleton 표시
- detail error: 목록과 Timeline은 유지하고 detail만 재시도
- selected: 색상 외 border/focus/aria-selected로 표시
- dark mode와 keyboard focus를 기존 semantic token으로 유지한다.

### 관측성과 진단
- source별 structured log에 `request_id`, `log_type`, `elapsed_ms`, `row_count`, `has_more`, `timed_out`을 기록한다.
- Prometheus label에는 `eqpId`, cursor, 사용자 ID처럼 high-cardinality 값을 넣지 않는다.
- EQP 식별이 문제 분석에 필요하면 structured log field에서 마스킹 또는 hash 정책을 적용한다.
- 응답 payload byte는 Nginx access log의 body bytes 또는 frontend Resource Timing으로 측정한다.
- browser는 React Profiler, Chrome Performance, Memory heap snapshot을 사용한다.
- DB는 source별 실제 SQL에 `EXPLAIN (ANALYZE, BUFFERS)`를 실행한다.
- cold cache와 warm cache를 분리해 최소 20회 측정하고 p50/p95를 기록한다.
- baseline과 각 milestone 결과를 이 문서 `진행 기록`에 링크 또는 수치로 추가한다.

### 타임아웃과 자원 보호
- frontend 30초 timeout을 성능 해결책으로 사용하지 않는다.
- source query별 DB statement timeout 권장값은 baseline 후 5~10초 범위에서 정한다.
- timeout이 발생하면 해당 source의 부분 오류로 처리하고 다른 source 결과를 보존한다.
- pageSize, 날짜 span, type 개수를 server에서 검증해 비정상적으로 큰 query를 차단한다.
- disconnected client query가 DB에서 계속 실행되는지 staging에서 확인한다.
- Gunicorn worker/thread 증설은 bounded query 적용 후 부하 시험 결과로 결정한다.
- worker 수만 늘려 DB 동시 query 수를 무제한으로 키우지 않는다.
- `DJANGO_DB_CONN_MAX_AGE` 변경은 이번 필수 범위에서 제외하고 connection setup이 실제 병목일 때만 별도 검토한다.

### 압축
- compact/pagination 적용 전 gzip으로 대형 응답 문제를 숨기지 않는다.
- 적용 후에도 JSON 전송 시간이 유의미하면 Observer API JSON에 Nginx gzip을 적용한다.
- `gzip_vary on`, 적절한 `gzip_min_length`, `application/json` type을 설정한다.
- 압축 전/후 payload, CPU, latency를 함께 비교한다.
- Nginx 설정 변경 시 dev/prod 대상 설정 파일을 명확히 구분하고 `nginx -t`를 통과해야 한다.

### retention과 partition
- pagination과 index는 조회를 bounded하게 하지만 원천 테이블의 무한 증가 자체를 해결하지 않는다.
- table/index 크기, 월 증가량, 보존 기간, 감사 요구를 운영 owner와 확인한다.
- retention은 업무 규칙이므로 임의 삭제하지 않는다.
- partition 전환은 unique constraint, loader upsert, 기존 FK/쿼리에 영향을 줄 수 있어 이 ExecPlan의 즉시 구현 범위에서 제외한다.
- 필요성이 확인되면 source별 archive/partition 전용 ExecPlan을 별도로 작성한다.

## 예상 파일 변경

### 계획·문서
- `docs/agent/plans/observer-large-data-stability.md`
  - 이 실행 계획과 진행 기록
- `docs/api/observer.md`
  - 신규 paged/batch/detail 계약, error code, compatibility
- `docs/modules/observer.md`
  - bounded 조회 흐름, 운영 진단, UI 데이터 예산
- `docs/configuration.md`
  - 신규 env가 생기는 경우에만 query timeout 또는 Nginx 관련 설정 문서화

### Backend Observer
- `apps/api/api/observer/serializers.py`
  - page/detail query validation과 cursor field
- `apps/api/api/observer/views.py`
  - 신규 endpoint, 부분 실패 HTTP 응답
- `apps/api/api/observer/selectors.py`
  - batch 오케스트레이션과 compact/detail mapping
- `apps/api/api/observer/urls.py`
  - 신규 상대 route
- `apps/api/api/observer/tests.py`
  - API contract, cursor, partial failure, projection 테스트

### Backend source selectors
- `apps/api/api/data_movement/eqp_status_chg/selectors.py`
- `apps/api/api/data_movement/mi_tip_update_hist/selectors.py`
- `apps/api/api/data_movement/m_interlock/selectors.py`
- `apps/api/api/data_movement/racb_list/selectors.py`
- `apps/api/api/data_movement/ctttm_workorder_list/selectors.py`
- `apps/api/api/drone/selectors.py`
  - source 소유 keyset page/detail query와 최소 projection

### Interlock schema/loader
- `apps/api/api/data_movement/m_interlock/models.py`
- `apps/api/api/data_movement/m_interlock/services/loader.py`
- `apps/api/api/data_movement/m_interlock/migrations/0005_*.py`
- 필요 시 index 전용 후속 migration
- `apps/api/api/data_movement/m_interlock/tests.py`

### Frontend
- `apps/web/package.json`
- `apps/web/package-lock.json`
  - virtualizer dependency
- `apps/web/src/features/observer/api/client.js`
  - caller signal, timeout signal, retry 단일화
- `apps/web/src/features/observer/api/observerApi.js`
- `apps/web/src/features/observer/api/queryKeys.js`
  - batch/page/detail API와 query key
- `apps/web/src/features/observer/hooks/useObserverLogQuery.js`
- `apps/web/src/features/observer/hooks/useObserverLogs.js`
- 신규 `hooks/useObserverLogPages.js`
- 신규 `hooks/useObserverLogDetailQuery.js`
- `apps/web/src/features/observer/hooks/useVisObserver.js`
- `apps/web/src/features/observer/utils/logs.js`
- `apps/web/src/features/observer/utils/dataTransformers.js`
- `apps/web/src/features/observer/utils/visObserverAdapter.js`
- 신규 `utils/logPagination.js`
- `apps/web/src/features/observer/components/ObserverDataTable.jsx`
- `apps/web/src/features/observer/components/table/ObserverTableRow.jsx`
- 필요 시 신규 `components/table/ObserverVirtualTableBody.jsx`
- `apps/web/src/features/observer/components/ObserverBoard.jsx`
- `apps/web/src/features/observer/components/LogDetailSection.jsx`

### 성능 검증
- 필요 시 `scripts/performance/observer_load.js`
  - URL, EQP, 날짜, 동시 사용자 수를 env로 받는 k6 시나리오
- 운영 환경 의존 도구를 추가할 때는 offsite에서 실행 가능한 대체 절차를 함께 문서화한다.

## 실행 단계

### Milestone 0: baseline과 계약 확정
- [x] 구현 전 결정 게이트 1~7을 확정한다.
- [ ] 대표 EQP와 기간별 유형 row count를 기록한다.
- [ ] 기존 7개 endpoint의 p50/p95, query time, payload bytes를 측정한다.
- [ ] 7개 동시 요청이 Gunicorn/DB에 주는 영향을 측정한다.
- [ ] frontend initial render, DOM node, long task, heap baseline을 기록한다.
- [ ] source별 `EXPLAIN (ANALYZE, BUFFERS)`를 저장한다.
- [ ] 권장 page budget과 SLO를 계측 결과로 갱신한다.

완료 조건:
- 병목 비율과 수치가 문서에 기록되어 있고 API 계약의 Hard-Block이 해소되어 있다.

### Milestone 1: 하위 호환 paged backend
- [x] paged query/detail serializer를 추가한다.
- [x] opaque cursor encode/decode와 mismatch validation을 추가한다.
- [x] EQP/TIP/RACB source selector에 keyset page query를 추가한다.
- [x] CTTTM/ESOP compact projection과 detail query를 추가한다.
- [x] 현재 Interlock schema 기준 임시 keyset page query를 추가한다.
- [x] 유형별 `/page`, `/detail` endpoint를 추가한다.
- [x] 최초 batch `/logs/page`와 부분 실패 response를 추가한다.
- [x] `pageSize+1`, hasMore, stable tie ordering을 테스트한다.
- [x] 기존 배열 endpoint 회귀 테스트를 유지한다.
- [x] API/module 문서를 갱신한다.

완료 조건:
- 신규 endpoint는 모든 response를 bounded하게 반환한다.
- 기존 endpoint 테스트가 그대로 통과한다.
- same-timestamp page 경계에서 누락·중복이 없다.
- ESOP list query에서 defect map parsing이 실행되지 않는다.
- CTTTM list query에서 summary 대형 projection을 읽지 않는다.

### Milestone 2: frontend paged 전환과 요청 안정화
- [x] Observer API client가 React Query signal을 수용하게 한다.
- [x] retry 책임을 React Query 한 곳으로 단일화한다.
- [x] 최초 7개 query를 batch query로 전환한다.
- [x] 유형별 다음 page 로딩과 중복 제거를 구현한다.
- [x] 선택된 로그만 detail query를 호출한다.
- [x] partial/error/loading/truncated UI를 구현한다.
- [x] Observer log query의 gcTime과 resident item cap을 설정한다.
- [ ] EQP/기간/type 변경 시 이전 request abort를 검증한다.
- [ ] 기존 필터, 선택, 공유 URL, 날짜 slider 회귀를 검증한다.

완료 조건:
- 한 화면 진입이 기본적으로 HTTP request 1개로 시작한다.
- 장애 시 retry 폭증이 발생하지 않는다.
- 이전 EQP/기간 응답이 새 화면 상태를 덮어쓰지 않는다.
- detail 대형 payload는 row 선택 전 전송되지 않는다.

### Milestone 3: Data Log와 Timeline 렌더링 제한
- [x] virtualizer dependency를 추가한다.
- [x] Data Log body를 row virtualizer로 전환한다.
- [x] selection scroll을 index 기반으로 전환한다.
- [ ] virtual list keyboard/accessibility 동작을 검증한다.
- [x] vis DataSet 갱신을 diff 기반으로 전환한다.
- [x] Timeline item budget과 “일부 표시 중” 상태를 추가한다.
- [ ] 중복 Date parsing과 전체 재정렬을 줄인다.
- [ ] React Profiler와 Memory로 before/after를 기록한다.

완료 조건:
- 10,000개 Data Log model에서도 DOM row는 100개 이하이다.
- 추가 페이지 로딩 시 Timeline zoom/selection이 불필요하게 초기화되지 않는다.
- 스크롤과 선택이 성능 목표를 만족한다.
- 같은 축 nested scroll이 새로 생기지 않는다.

### Milestone 4: Interlock typed schema 직접 전환
- [x] nullable lookup/time 필드 migration을 추가한다.
- [x] loader dual-write와 테스트를 추가한다.
- [x] concurrent typed index를 추가한다.
- [x] feature flag와 문자열 fallback 없이 typed selector로 전환한다.
- [x] legacy 문자열 조회 표현식 인덱스를 concurrent migration으로 제거한다.
- [ ] staging에서 typed selector query plan을 확인한다.

완료 조건:
- 신규 적재 row의 typed 파생 필드 정합성이 검증된다.
- invalid time row의 `prod_progs_at`이 `NULL`로 저장되고 조회에서 제외된다.
- typed selector p95가 목표를 만족한다.
- typed 파생 필드가 비어 있는 row가 조회에서 제외된다.

### Milestone 5: 범위 통제
- [x] Tkin Prevent는 Observer 화면이 아닌 별도 제품 화면임을 확인했다.
- [x] Tkin Prevent에 추가했던 matrix window API와 축 이동 UI를 원복했다.
- [x] Observer 로그·타임라인 변경만 유지했다.

완료 조건:
- Tkin Prevent의 기존 matrix API와 사용자 동작이 변경 전과 동일하다.
- 대용량 최적화 변경이 Observer 화면 경로에만 적용된다.

### Milestone 6: 인프라·부하 검증·문서화
- [ ] compact response 기준 gzip 효과를 측정한다.
- [ ] 필요하면 Nginx JSON gzip을 추가하고 `nginx -t`를 실행한다.
- [ ] 20 concurrent users 부하 시험을 수행한다.
- [ ] DB connection, worker busy, error rate, latency를 확인한다.
- [ ] SLO 미달 source만 query/index를 추가 조정한다.
- [x] `docs/api/observer.md`, `docs/modules/observer.md`, 필요 시 `docs/configuration.md`를 최종 갱신한다.
- [ ] 구 endpoint deprecation 여부를 access log 기준으로 결정한다.

완료 조건:
- 수용 기준을 모두 통과하거나 미달 항목과 후속 계획이 명시되어 있다.
- backend/frontend/문서 audit이 통과한다.
- rollback 절차가 staging에서 확인되어 있다.

## 테스트 계획

### Backend view/API
- 필수 query 누락 400
- 잘못된 pageSize, cursor, type, 날짜 span 400
- pageSize 기본값과 최대값
- source 일부 실패 시 200/partial
- source 전체 실패 시 503
- 기존 배열 endpoint response shape 회귀
- detail EQP/log ID mismatch 404
- detail 대형 필드가 list에 포함되지 않는 projection 검증

### Selector/cursor
- 첫 page와 다음 page 사이 중복 없음
- 같은 event time row가 page boundary에 걸려도 누락 없음
- cursor가 다른 EQP/type/range에 재사용되면 거부
- pageSize+1만 평가해 hasMore 판정
- empty 마지막 page
- invalid source time 제외 정책
- compact ordering과 기존 timeline ordering 동일
- ESOP detail에서만 defect map parsing
- CTTTM detail에서만 summary projection

### Interlock
- loader가 세 신규 필드를 dual-write
- Asia/Seoul naive source를 올바른 aware datetime으로 변환
- invalid/null source time 처리
- typed selector from/to 포함 경계
- SPC/FDC 분리
- typed index model/migration state 일치

### Frontend 동작
- batch 성공, 부분 실패, 전체 실패
- type disable/enable
- 기간/EQP 변경 request cancellation
- load more 중복 제거
- hasMore 종료
- 선택 detail loading/error/success
- selected row virtual scroll 이동
- Timeline 선택에서 Data Log index 이동
- cache GC 후 재조회
- 5,000 row virtual list keyboard 동작
- Timeline incremental add/update/remove

## 검증

### 정적·회귀 검증

```bash
docker compose -f docker-compose.dev.yml exec -T api \
  python manage.py makemigrations --check --dry-run

docker compose -f docker-compose.dev.yml exec -T api \
  python manage.py test \
  api.observer \
  api.data_movement.eqp_status_chg \
  api.data_movement.mi_tip_update_hist \
  api.data_movement.m_interlock \
  api.data_movement.racb_list \
  api.data_movement.ctttm_workorder_list \
  api.drone \
  --keepdb

npm run web:lint
npm run web:build
npm run agent:audit:api-boundary
npm run agent:audit:web-boundary
npm run agent:audit:ui
npm run agent:audit:docs
git diff --check
```

### DB query plan
- backend runtime SQL은 Docker Compose `api` container 기준으로 실행한다.
- 실제 EQP와 날짜는 env 또는 안전한 운영 절차로 전달하고 문서에 고정 식별자를 하드코딩하지 않는다.
- 각 source에 다음 항목을 기록한다.
  - planning time
  - execution time
  - rows scanned/returned
  - shared hit/read blocks
  - sort method/memory
  - index scan 이름

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT ...
ORDER BY event_time DESC, id DESC
LIMIT 251;
```

### HTTP 단일 요청

```bash
curl --fail --silent --show-error \
  --output /tmp/observer-page.json \
  --write-out 'status=%{http_code} time=%{time_total} size=%{size_download}\n' \
  "${OBSERVER_BASE_URL}/api/v1/observer/logs/page?eqpId=${OBSERVER_EQP_ID}&from=${OBSERVER_FROM}&to=${OBSERVER_TO}&pageSize=250"
```

- 실제 실행 시 task 전용 env 이름만 사용한다.
- 응답 파일은 민감 데이터 보존 정책에 따라 즉시 안전하게 폐기한다.

### 브라우저
- Chrome Performance에서 초기 fetch부터 첫 Data Log paint까지 기록
- React Profiler에서 `ObserverDataTable`, `ObserverBoard`, 각 Timeline commit 기록
- Elements에서 실제 rendered row/item 수 확인
- Memory에서 EQP/기간 20회 변경 전후 heap snapshot 비교
- Network에서 abort된 이전 request와 list/detail payload 분리 확인
- keyboard로 filter, row, detail, load-more 접근 확인

### 부하
- 대표 large profile EQP를 사용한다.
- 1, 5, 20 concurrent users 단계로 증가시킨다.
- 각 사용자는 최초 batch, 다음 page 2회, detail 3회를 수행한다.
- 실패 source와 retry 횟수를 함께 집계한다.
- 테스트 중 DB CPU/IO, active connection, Gunicorn worker busy, response p95를 기록한다.
- 운영 DB에 직접 stress test하지 않고 승인된 staging에서만 수행한다.

## 배포 계획

### 배포 A: 신규 backend API
- paged/batch/detail endpoint만 추가한다.
- 기존 frontend와 endpoint는 변경하지 않는다.
- 신규 endpoint smoke test와 access log를 확인한다.
- 문제 시 application rollback만 수행하면 된다.

### 배포 B: frontend 전환
- frontend를 신규 endpoint로 전환한다.
- 기존 endpoint가 남아 있으므로 frontend bundle rollback으로 즉시 복귀할 수 있다.
- 부분 실패, load more, detail lazy load를 집중 모니터링한다.

### 배포 C: virtualization
- API 안정화 후 Data Log/Timeline virtualization을 배포한다.
- selection/scroll 회귀가 있으면 frontend만 rollback한다.

### 배포 D1: Interlock typed schema와 selector
- nullable field migration, loader dual-write, typed selector, legacy index 제거 migration을 함께 배포한다.
- typed 파생 필드가 비어 있는 기존 row는 즉시 Observer 조회에서 제외된다.

### 배포 D2: index 검증
- concurrent index 적용 상태와 ANALYZE 결과를 확인하고 typed query plan을 검증한다.
- migration 이전의 기존 row는 typed 파생 필드가 비어 있으면 조회되지 않는다.

### 배포 E: 압축과 구 endpoint 정리
- 압축은 독립 infra 변경으로 배포한다.
- 구 endpoint 삭제는 최소 한 release 사용처 0을 확인한 뒤 별도 승인한다.

## 롤백 기준
- 기존 대비 API p95가 20% 이상 악화
- page 경계 누락/중복 발생
- detail이 다른 EQP row를 반환
- 부분 실패가 전체 화면 실패로 전파
- heap이 반복 동작마다 지속 증가
- Data Log selection 또는 Timeline 연동 회귀
- Interlock typed selector의 결과 누락이 허용 범위를 초과

## 롤백 방법
- backend 신규 endpoint는 기존 endpoint를 삭제하지 않으므로 frontend를 이전 bundle로 되돌린다.
- paged selector 오류는 신규 route만 비활성화하거나 이전 backend image로 되돌린다.
- Interlock nullable field와 index는 긴급 rollback 중 즉시 삭제하지 않는다.
- 문자열 selector 호환 경로는 제공하지 않으므로 문제 시 이전 application image로 rollback한다.
- migration rollback이 대형 table lock을 유발할 수 있으므로 긴급 상황에서 field/index 제거를 자동 수행하지 않는다.

## 위험과 대응
- 위험: pagination으로 사용자가 전체 로그가 표시되었다고 오해할 수 있다.
  - 대응: hasMore/truncated를 항상 시각적으로 표시하고 기간 좁히기와 추가 조회 action을 제공한다.
- 위험: cursor tie ordering 오류로 row가 누락되거나 중복될 수 있다.
  - 대응: event time과 stable tie-breaker를 함께 사용하고 동일 timestamp fixture를 테스트한다.
- 위험: batch endpoint 한 source 지연이 전체 최초 응답을 늦출 수 있다.
  - 대응: source별 statement timeout과 부분 실패를 적용하고 bounded concurrency는 계측 후에만 도입한다.
- 위험: 목록/상세 분리로 선택 직후 상세가 늦게 보일 수 있다.
  - 대응: 즉시 skeleton을 표시하고 최근 detail cache를 재사용한다.
- 위험: virtual row가 unmount되어 focus나 선택 scroll이 깨질 수 있다.
  - 대응: index 기반 이동, roving focus, keyboard 회귀 테스트를 적용한다.
- 위험: Timeline item cap이 분석 완전성을 낮출 수 있다.
  - 대응: cap을 숨기지 않고 날짜 범위를 좁히는 workflow를 제공한다.
- 위험: 신규 index가 write amplification과 storage를 늘린다.
  - 대응: EXPLAIN으로 확인된 index만 추가하고 기존 중복 index 제거는 안정화 후 판단한다.
- 위험: retry 축소로 일시 오류가 더 자주 노출될 수 있다.
  - 대응: 안전한 오류만 1회 재시도하고 명시적 사용자 재시도 action을 제공한다.
- 위험: gzip이 API CPU를 증가시킬 수 있다.
  - 대응: compact response 적용 후 CPU/latency를 함께 측정하고 독립 배포한다.
- 위험: 성능 수치가 개발 fixture에서는 재현되지 않는다.
  - 대응: staging large/stress profile을 수용 기준으로 사용한다.

## 완료 정의
- 구현 전 결정 게이트가 모두 확정되었다.
- 모든 필수 milestone이 완료되거나 조건부 제외 이유가 기록되었다.
- 기존 endpoint와 신규 endpoint 회귀 테스트가 통과했다.
- backend container test, migration check, frontend lint/build, boundary/UI/docs audit가 통과했다.
- same-time cursor, partial failure, abort, virtualization, typed-only Interlock 조회가 검증되었다.
- staging large/stress 성능 결과가 성공 기준을 만족한다.
- 배포와 rollback runbook이 실제 순서대로 검토되었다.
- API/module/configuration 문서가 실제 contract와 일치한다.
- 진행 기록에 최종 수치, 미실행 검증, 잔여 위험이 남아 있다.

## 진행 기록
- 2026-07-31: Observer main log의 backend, DB, frontend 대용량 병목을 정적 분석했다.
- 2026-07-31: 기존 lookup+시간 인덱스가 주요 source에 이미 존재함을 확인해 무조건적인 인덱스 추가를 계획에서 제외했다.
- 2026-07-31: 하위 호환 paged API, compact/detail 분리, request 안정화, virtualization, Interlock typed migration 순서로 초기 ExecPlan을 작성했다.
- 2026-07-31: 구현 전 확정이 필요한 API/DB/UX/SLO 결정 7개를 Hard-Block gate로 기록했다.
- 2026-07-31: 결정 게이트 1~7의 권장 기본값으로 구현을 시작했다. compact batch/page/detail API, source별 keyset selector, 부분 실패 응답을 추가했다.
- 2026-07-31: 프론트를 단일 batch 시작, React Query abort/retry, 선택 상세 지연 조회, 5000건 resident cap 구조로 전환했다.
- 2026-07-31: Data Log row virtualizer와 vis DataSet diff 갱신을 적용했다. 가상화의 동적 높이/좌표 inline style은 UI audit의 measured-layout 예외로 유지했다.
- 2026-07-31: Interlock nullable typed 필드, dual-write, concurrent index를 구현했다.
- 2026-07-31: 기존 문자열 조회 호환이 필요 없다는 결정에 따라 typed 전환 플래그와 legacy selector를 제거하고 typed selector를 상시 사용하도록 전환했다.
- 2026-07-31: legacy 문자열 조회 전용 표현식 인덱스 제거를 미적용 `0005` concurrent migration에 합쳐 적재 비용과 저장 공간을 줄였다.
- 2026-07-31: Tkin Prevent가 별도 제품 화면임을 확인해 신규 matrix window API와 축 이동 UI를 원복하고 Observer 로그·타임라인 최적화만 유지했다.
- 2026-07-31: Observer 재리뷰에서 확인한 resident cap의 타입 순서 편향을 제거하고, 유형 필터를 로컬 표시 상태로 분리했으며 compact/detail 병합 시 목록 전용 필드가 유지되도록 보완했다.
- 2026-07-31: typed-only Interlock 정리 후 backend Observer/Interlock 74개 테스트, frontend lint/build, backend/frontend/docs boundary audit를 통과했다. UI audit는 기존 L3 raw color와 virtualizer measured inline style 후보로 비영(非零) 종료했다.
- 2026-07-31: 연관 앱 확장 회귀 402개 중 398개가 통과했고, 변경 범위 밖의 `DroneSopTargetAdminTests` 4개는 깨끗한 test DB에서도 account access grant 준비 단계가 400을 반환해 실패했다.
- 2026-07-31: staging/운영 데이터가 필요한 baseline, EXPLAIN, 브라우저 profiler, 20-user 부하 시험은 미실행 상태로 남겼다.
