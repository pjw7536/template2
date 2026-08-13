# Observer 모듈

Observer는 설비 Observer 화면에 필요한 기준 정보와 로그를 조회합니다.

## 기능 요약

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

## 화면과 route

| Route | 설명 |
| --- | --- |
| `/observer` | 라인/SDWT/공정/설비를 선택해 observer 조회 |
| `/ESOP_Dashboard/tip-status/:lineId` | m_tkin_prevent 예방 상태 matrix 조회 |
| `/observer/:eqpId` | 특정 설비를 URL에서 바로 선택 |

프론트 feature는 `apps/web/src/features/observer`이며, 외부 공개는 `apps/web/src/features/observer/index.js`의 `observerRoutes`입니다.

## 데이터 소스

Observer 기준정보와 로그는 기본 DB의 data movement/업무 테이블을 조회합니다.

| 데이터 | Backend source | 설명 |
| --- | --- | --- |
| Line | 기본 DB `drone_target` | 선택 가능한 line 목록 |
| SDWT | 기본 DB `drone_target`, `station_master` | line별 target_user_sdwt_prod 목록 |
| Process group | 기본 DB `station_master` | target_user_sdwt_prod와 매칭되는 SDWT별 공정 그룹 |
| Equipment | 기본 DB `station_master`, `drone_target` | 설비 목록과 상세 |
| EQP log | 기본 DB `eqp_status_chg` | 상태 변경 기반 설비 로그 |
| TIP log | 기본 DB `mi_tip_update_hist` | TIP 유형별 설비 로그 |
| SPC Interlock log | 기본 DB `m_interlock` | `prod_eqp_id`와 `interlock_kind=SPC` 기준 이력 |
| FDC Interlock log | 기본 DB `m_interlock` | `prod_eqp_id`와 `interlock_kind=FDC` 기준 이력 |
| CTTTM log | 기본 DB `ctttm_workorder_list`, `ct_process_comment` | CTTTM 유형별 설비 로그와 요약 |
| RACB log | 기본 DB `racb_list` | RACB 유형별 설비 로그 |
| ESOP log | 기본 DB `drone_sop` | ESOP 관련 로그 |
| tkin Prevent | 기본 DB `m_tkin_prevent`, `station_master` | SDWT/PRC/process/step 기준 예방 상태 matrix |

## 조회 흐름

1. 요청 query를 정리합니다.
2. `lineId`, `sdwtId`, `prcGroup` 등 식별자를 대문자로 정규화합니다.
3. 필수 query가 없으면 400을 반환합니다.
4. `lineId`는 `drone_target.line_id`, `sdwtId`는 `drone_target.target_user_sdwt_prod`로 해석합니다.
5. `drone_target.target_user_sdwt_prod = station_master.sdwt_prod_lookup` 매칭으로 station 데이터를 제한합니다.
6. 신규 page 경로는 최대 90일과 page size/cursor scope를 검증합니다.
7. 최초 요청은 7개 source의 compact 첫 page를 batch 응답으로 반환합니다.
8. 추가 데이터는 유형별 keyset cursor로, 전체 상세는 선택 시 별도 endpoint로 조회합니다.
9. 프론트는 서버 응답을 React Query cache에 두고 resident log를 최대 5000개로 제한합니다.

## AI 종합 분석 흐름

1. Observer가 현재 설비, 기간, 활성 로그 유형, TIP 그룹을 전역 ChatWidget의 page context로 등록합니다.
2. 위젯에는 연결된 EQP·기간과 `종합 분석` 빠른 질문이 표시되며, 사용자가 입력한 질문을 row 전체가 아닌 조회 조건과 함께 backend에 전달합니다.
3. backend는 DB 조회 단계에서 EQP의 `DOWN`, `IDLE`, `LOCAL`과 TIP의 `L*_TIP`만 선별한 뒤 상태·comment별 통계로 압축합니다. TIP의 `DOING`, `CNT`는 제외됩니다.
4. SPC/FDC/CTTTM/RACB/ESOP는 관심 상태 전 30분부터 후 10분까지의 사건만 raw context로 선별합니다. CTTTM은 `llm_core_summary` 핵심요약과 `llm_summary` 시간순 이벤트 정리를 별도 context로 보존합니다.
5. 현재 방에서 Portal 앱·Observer·Email RAG가 공유한 장기 요약과 구조화한 입력을 기존 `OPENWEBUI_*` 연결 및 `gpt-oss-120b` 모델에 streaming으로 전달하고, 반복·집중 패턴과 시간적 연관성, 원인 일관성, 운영상 의미를 중요도순으로 분석합니다. 공유 대화는 질문 의도와 후속 문맥에만 사용하며 사실 판단은 현재 Observer 조회 데이터로 제한합니다.
6. 모델은 한 줄당 하나의 분석 블록인 NDJSON을 생성하고, backend는 완성된 블록부터 SSE `delta`로 전달합니다.
7. backend는 분석 입력에 존재하는 근거 ID만 최종 결과에 남기고 실제 모델명·프롬프트·스키마 버전을 SSE `done` payload로 응답합니다.
8. ChatWidget의 근거 ID를 누르면 분석 당시 설비·기간·로그 유형·TIP 그룹을 Observer에 복원하고, 해당 유형을 cursor로 찾은 뒤 Data Log 행을 선택·강조합니다.

ChatWidget 본문에는 핵심 결론, 종합 설명, 최대 5개의 주요 분석과 결론에 영향을 주는 분석 한계만 표시합니다. 기록된 원인, 주변 로그 기반 후보, 근거 ID, 범위·입력·버전은 본문에서 반복하지 않고 기존 `분석 범위와 근거` 패널과 Data Log 이동 흐름에서 확인합니다.

CTTTM `llm_summary`는 작업 내 사건 순서를 해석하는 배경지식으로만 사용합니다. 모델은 이 요약을 주변 raw event와 함께 분석하며, 요약 자체를 독립된 근거나 확정 원인으로 취급하지 않습니다.

이 방식은 화면 row 수와 무관하게 분석 입력 크기를 제한합니다. source 조회 또는 prompt가 제한된 경우 응답 coverage와 limitations에 반영되며, prompt 축소는 section별 전후 건수로 확인할 수 있습니다. 근거 패널은 분석 당시 범위와 현재 범위의 일치 여부를 구분하고 모델·프롬프트 버전을 함께 표시합니다. 같은 ChatWidget 대화방에서는 Portal 앱·Observer·Email RAG의 history·장기 요약을 이어서 사용하고, 모델 입력의 문맥 전환 메시지에 출처를 표시합니다. 다른 대화방의 기억은 포함하지 않습니다.

## 로그 조회 정책

| 항목 | 정책 |
| --- | --- |
| 기본 기간 | `from` 생략 시 `OBSERVER_QUERY_DAYS` 기준 최근 기간 |
| 현재 기본값 | 60일 |
| 최대 limit | 5000 |
| page size | 기본 250, 최대 1000 |
| page 기간 | 최대 90일 |
| resident log | 화면당 최대 5000 |
| 날짜 형식 | `YYYY-MM-DD` 또는 datetime 문자열, `Asia/Seoul` 기준 |
| 정렬/변환 | backend selector가 유형별 raw row를 공통 payload로 변환 |
| Interlock 시간 | `prod_progs_time`을 Asia/Seoul로 변환해 저장한 `prod_progs_at` 사용 |

SPC/FDC interlock은 독립 타입 필터와 timeline을 사용하며 기본 표시 순서는 `EQP → TIP → SPC Interlock → FDC Interlock → CTTTM → RACB → ESOP`입니다. Timeline marker는 `metroItem`을 우선 표시하고 `interlockType`, `interlockNo` 순서로 대체합니다. Data Log에서는 `Change Type`에 `metroItem`, `Operator`에 `interlockType`을 표시하며 두 유형 모두 Log Detail에도 포함됩니다.

Observer의 날짜 조회 경계, API `eventTime`, Timeline 축, Data Log와 Log Detail 표시는 모두 `Asia/Seoul` 기준입니다. 브라우저의 현지 시간대와 관계없이 같은 시각을 표시합니다.
EQP/TIP의 timezone 없는 원천값도 KST 벽시계로 해석해 저장합니다. 기존 데이터는 과거 Log Detail에 표시되던 벽시계를 기준으로 보정하므로 Data Log와 Log Detail의 시간이 일치합니다.

## 프론트 구조

| 경로 | 역할 |
| --- | --- |
| `apps/web/src/features/observer/pages/ObserverPage.jsx` | observer route page |
| `apps/web/src/features/observer/pages/TkinPreventDashboardPage.jsx` | tkin Prevent route page |
| `apps/web/src/features/observer/api/observerApi.js` | backend API 호출 |
| `apps/web/src/features/observer/hooks/useObserverLogs.js` | 로그 query orchestration |
| `apps/web/src/features/observer/hooks/useObserverLogDetailQuery.js` | 선택 로그 상세 지연 조회 |
| `apps/web/src/features/observer/hooks/useObserverAssistantContext.js` | 현재 조회 조건과 Observer 분석 sender를 ChatWidget에 등록 |
| `apps/web/src/features/observer/utils/observerAnalysisChat.js` | 분석 질문 history와 구조화 응답을 채팅 markdown으로 변환 |
| `apps/web/src/features/observer/utils/observerEvidence.js` | 분석 근거 URL 생성·해석과 로그 ID 매칭 |
| `apps/web/src/lib/assistant/pageContext.jsx` | feature와 전역 ChatWidget 사이의 공용 page context |
| `apps/web/src/features/observer/store/useObserverStore.js` | 선택/필터 UI 상태 |
| `apps/web/src/features/observer/utils/visObserverItems.js` | vis-timeline item 변환 |
| `apps/web/src/features/observer/components/*Detail.jsx` | 로그 유형별 상세 패널 |

## 운영 포인트

- Observer 조회 문제는 `/api/v1/observer/lines` 같은 기준 정보 API와 data movement 적재 상태부터 확인합니다.
- 기본 조회 기간은 `OBSERVER_QUERY_DAYS`로 조정합니다.
- Data Log는 row virtualizer를 사용하므로 resident log 수와 관계없이 화면에는 viewport 주변 행만 mount됩니다.
- Timeline DataSet은 전체 초기화 대신 ID 기준 diff를 반영해 선택과 zoom 초기화를 줄입니다.
- 화면이 느리면 로그 API의 `from`, `to`, `limit` 조합과 응답 건수를 먼저 확인합니다.
- AI 분석 호출 문제는 `OPENWEBUI_URL`, `OPENWEBUI_MODEL`, API token/header 설정과 `/api/v1/observer/analysis` 응답의 coverage부터 확인합니다.
- AI 분석은 source별 최대 5000건, raw 유형별 최대 400건과 prompt 문자 예산을 적용하므로 장기간·대량 조회에서는 coverage의 truncation 표시를 함께 해석합니다.
- 근거 링크 이동 시 해당 로그가 첫 page에 없으면 유형별 cursor를 resident 한도까지 추가 조회합니다. 찾지 못하면 Data Log 상단에 실패 상태를 표시합니다.
- Observer ChatWidget은 기존 정책대로 `assistant` 접근 권한이 있는 사용자에게 표시됩니다. EQP를 선택하지 않았거나 분석할 로그 유형이 없으면 일반 OpenWebUI mode를 사용합니다.
- CTTTM 요약이 비어 있으면 `summarize_ct_process_comment` command와 `ct_process_comment.update_flag` 상태를 확인합니다.
- ESOP 로그가 누락되면 `api.drone` 데이터와 observer 로그 결합 지점을 함께 확인합니다.
- SPC/FDC 로그가 누락되면 `m_interlock.prod_eqp_id_lookup`, `interlock_kind_lookup`, `prod_progs_at`과 적재 상태를 확인합니다.
- Interlock은 `prod_eqp_id_lookup`, `interlock_kind_lookup`, `prod_progs_at`과 `idx_m_intlk_obs_page`를 항상 사용합니다. typed 파생 필드가 비어 있는 기존 row는 조회에서 제외하며 문자열 조회 fallback을 제공하지 않습니다.
- tkin Prevent matrix가 비어 있으면 `station_master.ch_main`과 `m_tkin_prevent.eqp_id` 매핑부터 확인합니다.
- tkin Prevent에서 Line은 ESOP Dashboard 선택값을 사용하며, user_sdwt_prod 후보는 `account_affiliation.line/user_sdwt_prod` 기준입니다.
- tkin Prevent의 PRC/process/step/matrix 조회는 선택된 user_sdwt_prod와 PRC Group 기준입니다.

## 관련 API

- `docs/api/observer.md`
- `docs/inventory.md`
- `docs/configuration.md`
- `docs/data-model.md`

## 관련 코드

- `apps/api/api/observer/views.py`
- `apps/api/api/observer/selectors.py`
- `apps/web/src/features/observer`
