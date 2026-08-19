# ExecPlan: Data Movement `mi_tip_update_hist`

## 목표
- TIP update history upsert, level mapping, timezone/retention과 Observer 소비 계약을 보존한다.

## 현재 상태
- 백틱 20-column 입력을 `tip_event_key` unique row로 upsert하고 180일 보존한다.
- 세 원천 datetime은 KST 벽시계로 해석하며 type/change/level 조합을 7개 eventType으로 매핑한다.

## 범위
- 수정: spec/loader/selectors/tests/command와 Observer TIP adapter.
- 유지: table/unique/indexes, event mapping, KST→UTC, retention과 stable IDs.

## 설계
- 지원 mapping 외 조합은 빈 eventType으로 저장하지 않고 파일 오류로 보고한다.
- 동일 key dedup, transaction upsert와 purge는 eqp_status_chg와 같은 공통 policy를 사용한다.
- `eqp_cb`와 uppercase lookup은 원천 eqp/chamber에서 결정적으로 생성한다.
- schema/migration 변화는 없고 기존 timezone migration은 수정하지 않는다.

## 실행 단계
- [x] 7개 mapping과 invalid combination characterization을 고정한다.
- [x] 공통 upsert lifecycle에 연결한다.
- [x] Observer list/page/detail와 cursor contract를 검증한다.
- [x] 공통 command와 canonical API/DAG 계약을 검증한다.

## 검증
- dev API container에서 `api.data_movement.mi_tip_update_hist api.observer` tests.
- mapping matrix, KST boundary, 180일 purge/rollback, unique conflict test.

## 위험과 대응
- 위험: 알려지지 않은 원천 조합 때문에 전체 load가 중단된다.
- 대응: error에 조합과 row 번호를 기록하고 silent fallback은 두지 않는다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md)와 [Data Movement 공통](data-movement-common-refactor.md). Observer TIP timeline의 선행 단계다.
- 복구: loader/selector를 revert하고 source file을 재적재한다. retention 삭제분은 사전 backup에서 복원한다.

## 진행 기록
- 2026-08-18: 7개 event mapping과 fail-closed unknown 처리로 확정했다.
- 2026-08-18: 13단계를 완료했다. event mapping·KST/UTC·180일 retention과 upsert rollback을 유지하며 공통 runner/command에 연결했고 Observer 포함 88개 테스트가 통과했다.
