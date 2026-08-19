# ExecPlan: Data Movement `ctttm_workorder_list`

## 목표
- MST/MNU workorder 적재와 후행 CT comment/Observer 소비 계약을 단순화한다.

## 현재 상태
- 파일명에서 MST 55-column, MNU 49-column schema를 구분하고 ETCH·최근 180일 row만 7개 DB field로 축소한다.
- `source_type` 범위 교체이며 `ct_process_comment` DAG와 loader가 이 table을 선행 기준으로 사용한다.

## 범위
- 수정: spec/fast_csv/loader/selectors/tests/command, DAG dependency와 문서.
- 유지: 물리 table, source별 교체, 180일 filter, `load_ctttm_workorder_list >> load_ct_process_comment`.

## 설계
- filename regex와 MST/MNU column order를 canonical source contract로 둔다.
- fast parser는 백틱 delimiter, UTF-8 replacement, exact width, `area_name=ETCH`, create-date cutoff를 명시적으로 검증한다.
- 동일 source의 새 파일은 temp COPY 성공 후 해당 `source_type`만 교체하며 다른 source row를 보존한다.
- `workorder_id, -inprg_date, -id` selector ordering을 ct_process_comment와 Observer가 공유한다.
- schema/migration 변화는 없다.

## 실행 단계
- [x] source detection/filter/replace characterization을 고정한다.
- [x] 공통 lifecycle에 연결하고 fast parser 책임을 유지한다.
- [x] CT comment 선행 dependency와 Observer payload를 검증한다.
- [x] API/DAG camelCase 전환과 공통 command 적용을 완료한다.

## 검증
- dev API container에서 `api.data_movement.ctttm_workorder_list`, `ct_process_comment`, `observer` tests.
- MST/MNU 혼합, 오래된 row, 실패 시 기존 source 보존, DAG ordering test.

## 위험과 대응
- 위험: source 오인으로 다른 snapshot을 삭제한다.
- 대응: filename mismatch는 claim 전에 실패시키고 source별 row-count를 load-job에 기록한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md)와 [Data Movement 공통](data-movement-common-refactor.md). `ct_process_comment`와 Observer의 직접 선행 계획이다.
- 복구: source별 이전 row-count와 source file을 보존하고 해당 source만 재적재한다. 다른 source와 CT comment row는 삭제하지 않는다.

## 진행 기록
- 2026-08-18: source별 부분 교체와 CT comment 선행 관계를 확정했다.
- 2026-08-18: 10단계를 완료했다. MST/MNU fast parser와 source별 교체를 유지하며 공통 runner/command에 연결했고 CT comment·Observer를 포함한 148개 테스트가 통과했다.
