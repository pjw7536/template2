# ExecPlan: Data Movement `m_tkin_prevent`

## 목표
- line별 snapshot 교체와 Observer prevention matrix 조회 계약을 분리·안정화한다.

## 현재 상태
- deflate CSV를 읽어 파일에 포함된 `line_id` 범위를 교체한다.
- Observer는 station_master와 결합해 prc-group/process/step/matrix를 제공한다.

## 범위
- 수정: spec/loader/selectors/tests/command와 Observer matrix adapter.
- 유지: 50-column schema, line별 교체, datetime/float coercion, 현재 indexes와 UI 결과.

## 설계
- delimiter는 현재 공통 parser 기본값과 동일한 control character `0x03`으로 spec에 명시하고 exact 50-column 검증을 활성화한다.
- 파일에 non-empty line_id가 없으면 실패하고 기존 snapshot을 보존한다.
- 포함된 line만 delete+COPY하며 다른 line row는 유지한다.
- Observer의 direct raw SQL은 후행 Observer 단계에서 m_tkin selector facade로 이동하고 반환 camelCase payload는 유지한다.
- schema/migration 변화는 없다.

## 실행 단계
- [x] 실제 delimiter/50-column/coercion/line replace test를 고정한다.
- [x] 공통 runner/COPY policy에 연결한다.
- [x] Observer dropdown/matrix와 station_master join을 검증한다.
- [x] 공통 command와 canonical API/DAG 계약을 검증한다.

## 검증
- dev API container에서 `api.data_movement.m_tkin_prevent api.observer` tests.
- multi-line partial replace, missing line, coercion failure, matrix empty/filter state tests.

## 위험과 대응
- 위험: 여러 line 파일에서 일부만 교체된다.
- 대응: replace value set과 temp row line set 일치 검사를 transaction 전에 수행한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md)와 [Data Movement 공통](data-movement-common-refactor.md). station_master와 함께 Observer prevention matrix의 선행 단계다.
- 복구: loader/selector를 revert하고 영향 line_id의 이전 snapshot file 또는 DB backup을 재적재한다.

## 진행 기록
- 2026-08-18: line_id 범위 교체를 불변 전략으로 확정했다.
- 2026-08-18: 15단계를 완료했다. `0x03` separator와 exact 50-column 검증을 spec/reader에 명시하고 line별 교체를 공통 runner/command에 연결했다. Observer matrix 포함 85개 테스트가 통과했다.
