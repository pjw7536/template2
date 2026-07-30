# ExecPlan: Observer SPC/FDC Interlock timeline

## 목표
- Observer 설비 상세에서 `m_interlock` 이력을 조회한다.
- `interlock_kind=SPC`는 `SPC Interlock`, `interlock_kind=FDC`는 `FDC Interlock`이라는 독립 timeline으로 표시한다.
- 기존 날짜 범위, 타입 필터, Data Log 선택, 상세 보기, 오류 재시도 흐름과 일관되게 동작시킨다.

## 현재 상태
- `m_interlock`은 append-only 원천 테이블이며 `prod_eqp_id`, `metro_eqp_id`, `prod_chamber_id`, `last_update_date`, `prod_progs_time`, `metro_progs_time`, `interlock_kind`를 가진다.
- `api.data_movement.m_interlock`에는 적재 loader가 있지만 Observer 조회 selector와 조회 인덱스는 없다.
- Observer backend는 EQP/TIP/CTTTM/RACB/ESOP를 타입별 selector와 `/api/v1/observer/logs/<type>` endpoint로 제공한다.
- Observer frontend는 타입별 React Query hook을 병렬 실행하고, 오른쪽 단일 세로 scroll 영역에 timeline을 순서대로 쌓는다.
- Data Log와 Log Detail도 동일 로그 배열을 공유하므로 새 로그 타입을 연결하면 필터·선택·상세 계약을 함께 맞춰야 한다.

## 범위
- `api.data_movement.m_interlock`에 Observer용 read-only selector와 조회 인덱스 migration을 추가한다.
- `api.observer`에 SPC/FDC 로그 fetcher, endpoint, response mapping, 테스트를 추가한다.
- Observer frontend에 SPC/FDC query hook, 필터, timeline, Data Log badge, 상세 표시를 추가한다.
- API/모듈/data model 문서를 갱신한다.
- `m_interlock` 적재 방식, retention, deduplication, 기존 Observer 로그 타입의 동작은 변경하지 않는다.

## 설계

### Backend 경계
- 설비/시간/종류 필터 SQL은 `api.data_movement.m_interlock.selectors`가 소유한다.
- `api.observer.selectors`는 해당 selector를 호출해 Observer camelCase log contract로 변환한다.
- Observer view는 기존 `_ObserverLogsByTypeView`를 재사용하고 ORM/SQL을 직접 실행하지 않는다.

### API
- 기존 패턴과 독립 오류 처리를 유지하기 위해 endpoint를 둘로 분리한다.
  - `GET /api/v1/observer/logs/spc-interlock?eqpId=...&from=...&to=...&limit=...`
  - `GET /api/v1/observer/logs/fdc-interlock?eqpId=...&from=...&to=...&limit=...`
- `interlock_kind`는 `trim + upper` 기준으로 정확히 `SPC`, `FDC`만 포함하고 null/기타 값은 제외한다.
- timeline과 날짜 필터의 event time은 `prod_progs_time`을 사용한다.
- `prod_progs_time`은 `YYYYMMDD HHMMSS` 형식만 허용하며, 형식이 잘못되거나 비어 있는 row는 timeline에서 제외한다.
- `prod_progs_time`은 Asia/Seoul 현지 시각으로 파싱하고 API `eventTime`은 `+09:00` offset이 포함된 ISO datetime으로 반환한다.
- 날짜만 전달된 `from/to`는 Asia/Seoul의 시작일 00:00:00과 종료일 23:59:59.999999로 해석한다.
- offset이 포함된 datetime 범위는 Asia/Seoul로 변환한 뒤 `YYYYMMDD HHMMSS` 조회 경계로 변환한다.
- Observer `eqpId`는 `prod_eqp_id`에만 매칭하며 `metro_eqp_id`와 `prod_chamber_id`는 조회 조건에 사용하지 않고 상세 필드로만 제공한다.
- UI 선택 ID 충돌을 막기 위해 `id`는 `SPC_INTERLOCK:<source_id>` 또는 `FDC_INTERLOCK:<source_id>`로 반환하고 원본 PK는 `sourceId`로 제공한다.
- 공통 응답 후보:
  - 식별: `id`, `sourceId`, `logType`, `interlockKind`
  - 시간/설비: `eventTime`, `eqpId`, `prodEqpId`, `prodChamberId`, `metroEqpId`
  - 표시: `eventType`, `interlockNo`, `itemValue`, `interlockType`, `interlockComment`
  - 공정: `processId`, `ppid`, `lotId`, `batchId`, `waferId`, `prodStepSeq`, `metroStepSeq`
  - spec: `usl`, `specTarget`, `lsl`, `ucl`, `cl`, `lcl`
  - 설명: `interlockDesc`, `eqpProcessPhase`, `eqpDetailComment`, `engrComment`

### 조회 성능
- `trim + upper(prod_eqp_id)`, `trim + upper(interlock_kind)`, `prod_progs_time` 순서의 expression 복합 인덱스를 추가한다.
- 고정폭 `YYYYMMDD HHMMSS` 문자열은 시간순 lexical order가 일치하므로 selector는 `from/to`를 같은 형식으로 변환해 range 비교하고 index를 활용한다.
- index 이름은 30자 이하 deterministic 이름 `idx_m_intlk_prd_kind_ptm`을 사용한다.
- SPC/FDC endpoint는 각각 같은 날짜 범위와 최대 `limit=5000` 계약을 적용한다.

### Frontend 데이터 흐름
- `useSpcInterlockLogs`, `useFdcInterlockLogs`를 기존 `useObserverLogQuery` 위에 얇게 구성한다.
- `useObserverLogs`가 두 query의 loading/error/refetch/data를 기존 로그들과 함께 조합한다.
- `DEFAULT_TYPE_FILTERS`에 `SPC_INTERLOCK`, `FDC_INTERLOCK`를 별도 항목으로 추가해 독립 on/off를 지원한다.
- `mergeLogsByTime`와 Data Log 변환에 두 배열을 포함하되 point event이므로 duration은 계산하지 않는다.
- SPC/FDC 모두 Data Log 타입 필터, 행 선택, Log Detail에 포함한다.

### Timeline/UI
- 기존 Observer 오른쪽 scroll owner는 유지하고 timeline section만 추가한다.
- 기본 순서는 `EQP → TIP → SPC Interlock → FDC Interlock → CTTTM → RACB → ESOP`로 둔다.
- 하나의 재사용 가능한 `InterlockObserver`를 SPC/FDC 설정으로 두 번 렌더링한다.
- 각 timeline은 single group과 point item을 사용하고 marker label은 `interlock_no`, 없으면 `interlock_type`을 사용한다.
- SPC/FDC는 제목과 badge text로 항상 구분하고 색상만으로 의미를 전달하지 않는다.
- 종류별 empty state, 공통 loading, 타입별 error/retry 상태를 기존 Observer 패턴으로 제공한다.
- `InterlockDetail`은 핵심 식별/시간/설비/공정/spec/comment를 섹션화하고 긴 comment는 줄바꿈 가능한 값 영역에 표시한다.

## 확정된 계약
- event time: `prod_progs_time`
- source time format: `YYYYMMDD HHMMSS` (`20260728 145502`)
- source timezone: Asia/Seoul
- equipment match: Observer `eqpId = prod_eqp_id`
- integration surface: SPC/FDC timeline, Data Log 필터/행, Log Detail 모두 포함

## Hard-Block Questions
- 없음

## Soft Assumptions
- SPC/FDC timeline은 기본 활성화하고 TIP 다음에 배치한다.
- `interlock_kind`는 대소문자와 주변 공백을 정규화한다.
- marker는 `interlock_no` 우선, `interlock_type` fallback으로 표시한다.
- 기존 Observer의 날짜 slider, legend toggle, 공통 scroll ownership을 유지한다.

## 실행 단계
- [x] `prod_progs_time` timezone을 확정하고 API `eventTime` offset 계약을 고정한다.
- [x] `m_interlock` selector, 조회 인덱스 migration, selector 테스트를 추가한다.
- [x] Observer SPC/FDC endpoint, fetcher registry, API 테스트를 추가한다.
- [x] frontend query hooks와 log aggregation/filter contract를 확장한다.
- [x] 재사용 timeline과 interlock 상세 컴포넌트를 추가한다.
- [x] Data Log badge/필터/선택 및 loading/empty/error 상태를 검증한다.
- [x] API/module/data model/inventory 문서를 갱신한다.
- [x] backend/frontend 회귀와 boundary/UI/docs audit를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.data_movement.m_interlock api.observer --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm --prefix apps/web test`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `npm run agent:audit:docs`
- `git diff --check`

## 위험과 대응
- 위험: 잘못된 시간 컬럼을 쓰면 timeline의 의미와 날짜 필터 결과가 달라진다.
- 대응: `prod_progs_time` 고정폭 형식, Asia/Seoul offset, 날짜 및 datetime range boundary 포함 여부를 테스트한다.
- 위험: production/metrology/chamber 설비 매칭이 실제 Observer ID와 다르면 로그가 누락되거나 섞인다.
- 대응: 실제 ID 규칙을 확정하고 base/chamber/metro 케이스를 selector 테스트 fixture로 고정한다.
- 위험: append-only 증가로 조회가 느려질 수 있다.
- 대응: 실제 where/order 조건과 같은 복합 인덱스를 migration으로 추가하고 query plan 후보를 점검한다.
- 위험: 숫자 PK가 다른 로그 타입 PK와 충돌해 잘못된 상세가 선택될 수 있다.
- 대응: frontend selection에 사용하는 응답 ID에 로그 타입 prefix를 포함한다.
- 위험: timeline 추가로 오른쪽 영역 높이가 길어진다.
- 대응: 기존 단일 y-scroll owner를 유지하고 각 timeline은 compact fixed-height point track으로 구성한다.

## 진행 기록
- 2026-07-30: 기존 Observer backend/frontend log pipeline과 `m_interlock` schema를 조사해 초안 계획을 작성했다.
- 2026-07-30: 구현 전 event time, equipment match, Data Log/Detail 포함 범위를 Hard-Block으로 분류했다.
- 2026-07-30: event time은 `prod_progs_time`, 설비는 `prod_eqp_id`, Data Log/상세 포함으로 확정했다.
- 2026-07-30: `prod_progs_time`이 timezone 없는 `YYYYMMDD HHMMSS` 원천이므로 timezone 계약을 추가 확인 항목으로 남겼다.
- 2026-07-30: `prod_progs_time`을 Asia/Seoul 현지 시각으로 확정하고 API `eventTime`을 `+09:00` ISO datetime으로 반환하기로 했다.
- 2026-07-30: 확정된 계약을 기준으로 backend selector/index/API와 frontend timeline/Data Log/상세 구현을 시작했다.
- 2026-07-30: SPC/FDC endpoint, Asia/Seoul selector, 표현식 인덱스, frontend timeline/Data Log/상세 연결과 문서 갱신을 완료했다.
- 2026-07-30: backend 64개 및 frontend 89개 테스트, migration check, production build, backend/frontend/UI boundary audit를 통과했다. docs audit은 기존 `docs/configuration.md`의 `DRONE_*` 색인 누락 1건으로 실패했으며 이번 변경 범위와 무관해 보존했다.
