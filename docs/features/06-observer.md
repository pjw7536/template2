# Observer

[문서 홈](../README.md) · [기능·API](README.md)

- [기능과 흐름](#기능과-흐름)
- [API](#api)

## 기능과 흐름


Observer는 라인·SDWT·공정·설비를 고른 뒤 여러 종류의 설비 로그를 한 타임라인에서 확인하는 화면입니다.
설비별 상세 로그를 열고 현재 조회 조건을 바탕으로 AI 종합 분석을 요청할 수 있습니다.

조회할 기준정보와 로그는 기본 DB에 있어야 합니다. 원천 파일을 DB에 넣는 과정은
[Data Movement](13-data-movement.md#기능과-흐름)가 담당합니다. 아래에서 화면 선택 → 데이터 조회 → 분석 순서로 확인합니다.

### 기능 요약

- 라인 목록 조회
- 라인별 SDWT 조회
- 공정 그룹 조회
- 설비 목록/상세 조회
- 설비별 통합 로그 조회
- 최초 batch 및 유형별 keyset page 조회
- 선택 로그의 상세 지연 조회
- EQP, TIP, SPC Interlock, FDC Interlock, CTTTM, RACB, ESOP 유형별 로그 조회
- 현재 조회 조건의 관심 상태 통계와 주변 로그를 이용한 OpenWebUI 종합 분석
- URL의 `eqpId`를 기준으로 설비 상세와 observer item 동기화
- tkin Prevent process/step matrix 조회

### 화면과 route

| Route | 설명 |
| --- | --- |
| `/observer` | 라인/SDWT/공정/설비를 선택해 observer 조회 |
| `/ESOP_Dashboard/tip-status/:lineId` | m_tkin_prevent 예방 상태 matrix 조회 |
| `/observer/:eqpId` | 특정 설비를 URL에서 바로 선택 |

프론트 feature는 `apps/portal/web/src/features/observer`이며, 외부 공개는 `apps/portal/web/src/features/observer/index.js`의 `observerRoutes`입니다.

조회 API는 로그인과 Portal·`observer` 앱 접근을 검사합니다. AI 분석은 `assistant` 접근도 필요합니다.

### 데이터 소스

Observer 기준정보와 로그는 기본 DB의 data movement/업무 테이블을 조회합니다.

| 데이터 | Backend source | 설명 |
| --- | --- | --- |
| Line | 기본 DB `drone_sop_target` | 선택 가능한 line 목록 |
| SDWT | 기본 DB `drone_sop_target`, `station_master` | line별 target_user_sdwt_prod 목록 |
| Process group | 기본 DB `station_master` | target_user_sdwt_prod와 매칭되는 SDWT별 공정 그룹 |
| Equipment | 기본 DB `station_master`, `drone_sop_target` | 설비 목록과 상세 |
| EQP log | 기본 DB `eqp_status_chg` | 상태 변경 기반 설비 로그 |
| TIP log | 기본 DB `mi_tip_update_hist` | TIP 유형별 설비 로그 |
| SPC Interlock log | 기본 DB `m_interlock` | `prod_eqp_id`와 `interlock_kind=SPC` 기준 이력 |
| FDC Interlock log | 기본 DB `m_interlock` | `prod_eqp_id`와 `interlock_kind=FDC` 기준 이력 |
| CTTTM log | 기본 DB `ctttm_workorder_list`, `ct_process_comment` | CTTTM 유형별 설비 로그와 요약 |
| RACB log | 기본 DB `racb_list` | RACB 유형별 설비 로그 |
| ESOP log | 기본 DB `drone_sop` | ESOP 관련 로그 |
| tkin Prevent | 기본 DB `m_tkin_prevent`, `station_master` | SDWT/PRC/process/step 기준 예방 상태 matrix |

### 조회 흐름

1. 요청 query를 정리합니다.
2. `lineId`, `sdwtId`, `prcGroup` 등 식별자를 대문자로 정규화합니다.
3. 필수 query가 없으면 400을 반환합니다.
4. `lineId`는 `drone_sop_target.line_id`, `sdwtId`는 `drone_sop_target.target_user_sdwt_prod`로 해석합니다.
5. `drone_sop_target.target_user_sdwt_prod = station_master.sdwt_prod_lookup` 매칭으로 station 데이터를 제한합니다.
6. 신규 page 경로는 최대 90일과 page size/cursor scope를 검증합니다.
7. 최초 요청은 7개 source의 compact 첫 page를 batch 응답으로 반환합니다.
8. 추가 데이터는 유형별 keyset cursor로, 전체 상세는 선택 시 별도 endpoint로 조회합니다.
9. 프론트는 서버 응답을 React Query cache에 두고 resident log를 최대 5000개로 제한합니다.

### AI 종합 분석 흐름

1. Observer가 현재 설비, 기간, 활성 로그 유형, TIP 그룹을 전역 ChatWidget의 page context로 등록합니다.
2. 위젯에는 연결된 EQP·기간과 `종합 분석` 빠른 질문이 표시되며, `observer-analysis` Profile의 표준 Turn API로 질문과 조회 조건만 전달합니다.
3. backend는 DB 조회 단계에서 EQP의 `DOWN`, `IDLE`, `LOCAL`과 TIP의 `L*_TIP`만 선별한 뒤 상태·comment별 통계로 압축합니다. TIP의 `DOING`, `CNT`는 제외됩니다.
4. SPC/FDC/CTTTM/RACB/ESOP는 관심 상태 전 30분부터 후 10분까지의 사건만 raw context로 선별합니다. CTTTM은 `llm_core_summary` 핵심요약과 `llm_summary` 시간순 이벤트 정리를 별도 context로 보존합니다.
5. 현재 방의 `shared`와 `scope:observer` partition에서 현재 권한을 통과한 기억만 구조화 입력과 함께 기존 `OPENWEBUI_*` 연결 및 `gpt-oss-120b` 모델에 `stream: true`로 전달합니다. 대화 기억은 질문 의도와 후속 문맥에만 사용하며 사실 판단은 현재 Observer 조회 데이터로 제한합니다.
6. backend는 stream을 취소 가능하게 소비한 뒤 단일 분석 JSON 객체를 엄격히 검증합니다. 코드펜스나 일반 텍스트를 분석 결과로 대신 사용하지 않습니다.
7. backend는 분석 입력에 존재하는 근거 ID만 남기고 모델명·프롬프트·스키마 버전을 포함한 구조화 결과를 표준 Turn SSE의 `message.completed`로 전달합니다. 실행 완료는 `run.completed`로 알립니다.
8. ChatWidget의 근거 ID를 누르면 분석 당시 설비·기간·로그 유형·TIP 그룹을 Observer에 복원하고, 해당 유형을 cursor로 찾은 뒤 Data Log 행을 선택·강조합니다.

ChatWidget 본문에는 핵심 결론, 종합 설명, 최대 5개의 주요 분석과 결론에 영향을 주는 분석 한계만 표시합니다. 기록된 원인, 주변 로그 기반 후보, 근거 ID, 범위·입력·버전은 본문에서 반복하지 않고 기존 `분석 범위와 근거` 패널과 Data Log 이동 흐름에서 확인합니다.

CTTTM `llm_summary`는 작업 내 사건 순서를 해석하는 배경지식으로만 사용합니다. 모델은 이 요약을 주변 raw event와 함께 분석하며, 요약 자체를 독립된 근거나 확정 원인으로 취급하지 않습니다.

이 방식은 화면 row 수와 무관하게 분석 입력 크기를 제한합니다. source 조회 또는 prompt가 제한된 경우 응답 coverage와 limitations에 반영되며, prompt 축소는 section별 전후 건수로 확인할 수 있습니다. 근거 패널은 분석 당시 범위와 현재 범위의 일치 여부를 구분하고 모델·프롬프트 버전을 함께 표시합니다. 같은 ChatWidget 대화방이라도 Email partition은 Observer Profile이 읽지 않으며, 다른 대화방의 기억도 포함하지 않습니다.

### 로그 조회 정책

| 항목 | 정책 |
| --- | --- |
| page 기간 입력 | `from`, `to` 필수. 날짜·시간은 Asia/Seoul 기준 |
| 내부 selector 기본 기간 | 명시적 기간이 없는 내부 호출은 `OBSERVER_QUERY_DAYS` 기본 60일 |
| 최대 limit | 5000 |
| page size | 기본 250, 최대 1000 |
| page 기간 | 최대 90일 |
| resident log | 화면당 최대 5000 |
| 날짜 형식 | `YYYY-MM-DD` 또는 datetime 문자열, `Asia/Seoul` 기준 |
| 정렬/변환 | backend selector가 유형별 raw row를 공통 payload로 변환 |
| Interlock 시간 | `prod_progs_time`을 Asia/Seoul로 변환해 저장한 `prod_progs_at` 사용 |

SPC/FDC interlock은 독립 타입 필터와 timeline을 사용하며 기본 표시 순서는 `EQP → TIP → SPC Interlock → FDC Interlock → CTTTM → RACB → ESOP`입니다. Timeline marker는 `metroItem`을 우선 표시하고 `interlockType`, `interlockNo` 순서로 대체합니다. Data Log에서는 `Change Type`에 `metroItem`, `Operator`에 `interlockType`을 표시하며 두 유형 모두 Log Detail에도 포함됩니다.

Observer의 날짜 조회 경계, API `eventTime`, Timeline 축, Data Log와 Log Detail 표시는 모두 `Asia/Seoul` 기준입니다. 브라우저의 현지 시간대와 관계없이 같은 시각을 표시합니다.
EQP/TIP의 시간대 없는 원천값은 KST 벽시계로 해석해 저장하며 Data Log와 Log Detail은 같은 시각을 표시합니다.

### 프론트 구조

| 경로 | 역할 |
| --- | --- |
| `apps/portal/web/src/features/observer/pages/ObserverPage.jsx` | observer route page |
| `apps/portal/web/src/features/observer/pages/TkinPreventDashboardPage.jsx` | tkin Prevent route page |
| `apps/portal/web/src/features/observer/api/observerApi.js` | backend API 호출 |
| `apps/portal/web/src/features/observer/hooks/useObserverLogs.js` | 로그 query orchestration |
| `apps/portal/web/src/features/observer/hooks/useObserverLogDetailQuery.js` | 선택 로그 상세 지연 조회 |
| `apps/portal/web/src/features/observer/hooks/useObserverAssistantContext.js` | 현재 조회 조건을 ChatWidget page context에 등록 |
| `apps/portal/web/src/features/observer/utils/observerEvidence.js` | 분석 근거 URL 생성·해석과 로그 ID 매칭 |
| `apps/portal/web/src/lib/assistant/pageContext.jsx` | feature와 전역 ChatWidget 사이의 공용 page context |
| `apps/portal/web/src/features/observer/store/useObserverStore.js` | 선택/필터 UI 상태 |
| `apps/portal/web/src/features/observer/utils/visObserverItems.js` | vis-timeline item 변환 |
| `apps/portal/web/src/features/observer/components/*Detail.jsx` | 로그 유형별 상세 패널 |

### 운영 포인트

- Observer 조회 문제는 `/api/v1/observer/lines` 같은 기준 정보 API와 data movement 적재 상태부터 확인합니다.
- 기본 조회 기간은 `OBSERVER_QUERY_DAYS`로 조정합니다.
- Data Log는 row virtualizer를 사용하므로 resident log 수와 관계없이 화면에는 viewport 주변 행만 mount됩니다.
- Timeline DataSet은 전체 초기화 대신 ID 기준 diff를 반영해 선택과 zoom 초기화를 줄입니다.
- 화면이 느리면 로그 API의 `from`, `to`, `limit` 조합과 응답 건수를 먼저 확인합니다.
- AI 분석 호출 문제는 `OPENWEBUI_URL`, `OPENWEBUI_MODEL`, API token/header 설정과 `/api/v1/assistant/turns/stream`의 Tool event부터 확인합니다.
- AI 분석은 source별 최대 5000건, raw 유형별 최대 400건과 prompt 문자 예산을 적용하므로 장기간·대량 조회에서는 coverage의 truncation 표시를 함께 해석합니다.
- 근거 링크 이동 시 해당 로그가 첫 page에 없으면 유형별 cursor를 resident 한도까지 추가 조회합니다. 찾지 못하면 Data Log 상단에 실패 상태를 표시합니다.
- Observer ChatWidget은 `assistant` 접근 권한이 있고 현재 조회 조건의 page context 등록이 끝난 사용자에게 표시됩니다. Observer context가 없을 때 Portal mode로 대신 실행하지 않습니다.
- CTTTM 요약이 비어 있으면 `summarize_ct_process_comment` command와 `ct_process_comment.update_flag` 상태를 확인합니다.
- ESOP 로그가 누락되면 `api.drone` 데이터와 observer 로그 결합 지점을 함께 확인합니다.
- SPC/FDC 로그가 누락되면 `m_interlock.prod_eqp_id_lookup`, `interlock_kind_lookup`, `prod_progs_at`과 적재 상태를 확인합니다.
- Interlock은 `prod_eqp_id_lookup`, `interlock_kind_lookup`, `prod_progs_at`과 `idx_m_intlk_obs_page`를 항상 사용합니다. typed 파생 필드가 비어 있는 기존 row는 조회에서 제외하며 문자열 조회 fallback을 제공하지 않습니다.
- tkin Prevent matrix가 비어 있으면 `station_master.ch_main`과 `m_tkin_prevent.eqp_id` 매핑부터 확인합니다.
- tkin Prevent에서 Line은 ESOP Dashboard 선택값을 사용합니다. `user_sdwt_prod` 후보는 `drone_sop_target.line_id/target_user_sdwt_prod`와 `station_master.sdwt_prod_lookup` 매칭을 기준으로 조회합니다.
- tkin Prevent의 PRC/process/step/matrix 조회는 선택된 user_sdwt_prod와 PRC Group 기준입니다.

### 관련 API

- [Observer API](#api)
- [앱 인벤토리](../reference/02-inventory.md)
- [환경 설정](../reference/01-configuration.md)
- [데이터 모델과 저장소](../concepts/02-data-model.md)

### 관련 코드

- `apps/portal/api/api/observer/views/`
- `apps/portal/api/api/observer/selectors/`
- `apps/portal/web/src/features/observer`

## API


Observer API는 설비 Observer 화면에 필요한 라인, SDWT, 공정, 설비, 로그 데이터를 제공합니다.

### 호출자

- 브라우저 SPA

### 인증

- 모든 조회는 Django session과 Portal·`observer` 앱 접근이 필요합니다.
- AI 종합 분석은 Assistant Turn 경로를 사용하므로 `assistant`와 `observer` 접근을 함께 검사합니다.

### Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/observer/lines` | 라인 목록 |
| GET | `/api/v1/observer/sdwts?lineId=...` | 라인별 SDWT |
| GET | `/api/v1/observer/prc-groups?lineId=...&sdwtId=...` | 공정 그룹 |
| GET | `/api/v1/observer/equipments?lineId=...&sdwtId=...&prcGroup=...` | 설비 목록 |
| GET | `/api/v1/observer/equipment-info/<eqp_id>` | 설비 상세 |
| GET | `/api/v1/observer/logs/page?eqpId=...&from=...&to=...` | 모든 유형의 첫 compact page를 한 번에 조회 |
| GET | `/api/v1/observer/logs/<log_type>/page?eqpId=...&from=...&to=...` | 유형별 다음 compact page 조회 |
| GET | `/api/v1/observer/logs/<log_type>/detail?eqpId=...&logId=...` | 선택한 로그의 전체 상세 조회 |
| GET | `/api/v1/observer/logs/<log_type>/evidence?eqpId=...&evidenceId=...&from=...&to=...` | AI 분석에 사용된 근거 로그 단건 복원 |
| GET | `/api/v1/observer/tkin-prevent/prc-groups?userSdwtProd=...` | tkin Prevent PRC 그룹 목록 |
| GET | `/api/v1/observer/tkin-prevent/processes?userSdwtProd=...&prcGroup=...` | tkin Prevent process_id 목록 |
| GET | `/api/v1/observer/tkin-prevent/step-seqs?userSdwtProd=...&prcGroup=...&processId=...` | tkin Prevent step_seq 목록 |
| GET | `/api/v1/observer/tkin-prevent/matrix?userSdwtProd=...&prcGroup=...&processId=...&stepSeq=...` | tkin Prevent matrix |

### Query 규칙

#### 기준정보와 설비 선택

- `lineId`, `sdwtId`, `prcGroup`는 대문자로 정규화됩니다.
- 필수 query가 없으면 400을 반환합니다.
- Observer drill-down의 `lineId`는 `drone_sop_target.line_id`, `sdwtId`는 `drone_sop_target.target_user_sdwt_prod` 기준입니다.
- PRC/설비 조회는 `drone_sop_target.target_user_sdwt_prod = station_master.sdwt_prod_lookup` 매칭으로 station 데이터를 제한합니다.
- 기준정보와 로그는 기본 DB의 data movement/업무 테이블을 조회합니다.

#### 로그 목록·상세·근거 조회

- 로그 page API는 `from`, `to`를 필수로 받고 최대 90일 범위만 허용합니다.
- page API의 `pageSize` 기본값은 250, 최대값은 1000입니다. 다음 page는 응답의 opaque `nextCursor`를 같은 EQP·기간·로그 유형 요청에 그대로 전달합니다.
- `/logs/page`는 유형별 `items`, `page`, `error`를 반환합니다. 일부 source만 실패하면 성공 유형을 유지한 200 응답을 반환하고, 전부 실패하면 503을 반환합니다.
- page 목록은 comment preview와 `detailId`만 포함하며, 전체 comment·defect map·CTTTM summary 같은 대형 필드는 `/detail`에서 선택 시 조회합니다.
- `/evidence`는 분석 당시와 같은 유형별 source filter와 5,000건 상한을 적용해 `evidenceId`와 일치하는 한 건만 반환합니다. frontend은 현재 resident page에 근거가 없을 때 이 endpoint로 복원해 목록과 상세에 표시합니다.
- CTTTM 로그의 `summary`는 `ct_process_comment.llm_summary` 값을 사용합니다.

#### 날짜와 시간

- `from`, `to`는 `YYYY-MM-DD` 또는 datetime 문자열을 받습니다. 날짜와 offset 없는 datetime은 `Asia/Seoul`로 해석하며, offset이 있는 datetime은 같은 instant의 `Asia/Seoul` 시각으로 변환합니다.
- 모든 Observer 로그의 `eventTime`은 `Asia/Seoul` 기준 `+09:00` offset을 포함한 ISO datetime으로 반환합니다.
- EQP와 TIP의 timezone 없는 원천 시간은 KST 벽시계로 적재하며, page 목록과 detail은 같은 저장 instant를 사용하므로 동일한 KST 시간을 반환합니다.

#### SPC/FDC interlock

- SPC/FDC interlock은 정규화된 `eqpId = m_interlock.prod_eqp_id_lookup`과 `interlock_kind_lookup`으로 매칭합니다.
- SPC/FDC interlock의 event time은 `prod_progs_time`에서 변환해 저장한 `prod_progs_at`을 사용합니다. 원천 `YYYYMMDD HHMMSS` 또는 18자리 timestamp는 Asia/Seoul 현지 시각으로 해석합니다.
- typed 파생 필드가 비어 있거나 원천 시간 형식이 잘못된 row는 응답에서 제외합니다.
- SPC/FDC 응답 `logType`은 각각 `SPC_ITL`, `FDC_ITL`입니다.
- SPC/FDC 응답 ID는 `<logType>:<sourceId>` 형식이며 원본 `m_interlock.id`는 `sourceId`로 제공합니다.

#### AI 분석 요청과 입력 범위

- AI 분석은 `/api/v1/assistant/turns/stream`의 `observer-analysis` Profile을 사용합니다. `toolInputs["observer.analysis"]`에 `eqpId`, `from`, `to`, `logTypes`, 선택 `tipGroups`를 전달합니다. 대화방은 Turn의 `conversationId`로 지정하며, 기존 `roomId` 분석 요청 형식은 사용하지 않습니다. 조회 기간은 최대 90일입니다.
- 분석 API는 브라우저의 현재 row를 받지 않고 같은 조회 조건으로 backend source를 다시 조회합니다.
- EQP는 DB에서 `DOWN`, `IDLE`, `LOCAL`만 먼저 선별해 발생 빈도와 comment 원인을 요약합니다. TIP도 DB에서 `L*_TIP`만 선별하므로 `DOING`, `CNT`는 조회 상한을 소비하지 않습니다.
- SPC/FDC/CTTTM/RACB/ESOP는 EQP/TIP 관심 이벤트 전 30분부터 후 10분까지의 raw context만 전달합니다. 관심 이벤트가 없으면 선택된 비 EQP/TIP 로그를 제한된 raw context로 전달합니다.
- CTTTM context row는 `summary`에 `llm_core_summary` 핵심요약을, `chronologicalSummary`에 `llm_summary` 시간순 이벤트 정리를 담습니다. 시간순 정리는 사건 흐름 해석의 배경지식이며 독립된 raw 근거나 확정 원인으로 사용하지 않습니다.
- source별 최대 5000건, raw 유형별 최대 400건, 전체 prompt 180,000자 예산을 적용합니다. 예산을 넘으면 주변 로그, 개별 대상 이벤트, 기록 원인, TIP/EQP 통계 순으로 축소하고 `meta.promptTruncation`에 section별 전후 건수를 표시합니다.
- 분석 모델 호출은 기존 `OPENWEBUI_*` 설정을 재사용하고 `reasoning_effort=medium`으로 실행합니다.
- 분석 응답 `meta`에는 실제 호출 모델 `analysisModel`, 프롬프트 계약 `promptVersion`, 입력 스키마 `schemaVersion`을 포함합니다.
- finding의 `evidenceIds`는 분석 입력에 실제로 포함된 event ID만 남겨 모델이 생성한 알 수 없는 ID를 제거합니다.

#### tkin Prevent

- tkin Prevent 화면은 ESOP Dashboard line 선택과 `drone_sop_target.line_id/target_user_sdwt_prod` 및 `station_master.sdwt_prod_lookup` 매칭으로 `userSdwtProd` 후보를 정합니다.
- tkin Prevent PRC 후보는 `station_master.sdwt_prod_lookup = userSdwtProd`인 row의 `station_master.prc_group_lookup`에서 가져옵니다.
- tkin Prevent process/step/matrix 조회는 `userSdwtProd`와 `prcGroup`으로 대상 `station_master.ch_main`을 찾습니다.
- tkin Prevent 조회는 `station_master.ch_main`과 `m_tkin_prevent.eqp_id`를 정규화 비교해 대상 설비를 제한합니다.
- tkin Prevent matrix 응답의 `columns[]`는 `lineId`, `eqpId`, `chamberId`, `label`을 포함합니다.

### 예시

```http
GET /api/v1/observer/equipments?lineId=L1&sdwtId=S1&prcGroup=P1
```

```http
GET /api/v1/observer/logs/page?eqpId=EQP-001&from=2026-07-28&to=2026-07-30&pageSize=250
```

```http
GET /api/v1/observer/logs/eqp/page?eqpId=EQP-001&from=2026-07-28&to=2026-07-30&pageSize=250&cursor=<opaque-cursor>
```

Observer 화면의 AI 분석은 별도 Observer HTTP endpoint를 제공하지 않습니다. 전역 ChatWidget이 현재 조회 조건을 page context로 등록하고 `/api/v1/assistant/turns/stream`에 `observer-analysis` Profile로 요청합니다. Assistant Runtime이 `api.observer.services` facade를 통해 현재 데이터를 다시 조회하며, 완료된 메시지에는 구조화 분석과 제한된 근거 snapshot을 저장합니다.

```http
GET /api/v1/observer/tkin-prevent/matrix?userSdwtProd=S1&prcGroup=P1&processId=PROC1&stepSeq=10
```

### 오류

| Status | 상황 |
| --- | --- |
| 400 | 필수 query 누락 |
| 401 | 세션 인증 필요 |
| 403 | Portal·Observer 앱 접근 또는 필수 신원 정보 없음 |
| 404 | 설비 정보 또는 선택한 상세 로그 없음 |
| 503 | page batch의 모든 source 조회 실패 |
| 500 | 기본 DB 조회 실패 |

### 관련 모듈 문서

- [Observer 모듈](#기능과-흐름)
