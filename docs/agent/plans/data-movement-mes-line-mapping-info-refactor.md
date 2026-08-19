# ExecPlan: Data Movement `mes_line_mapping_info`

## 목표
- MES line mapping snapshot 적재의 schema/전체 교체/load-job 계약을 표준화한다.

## 현재 상태
- 백틱 28-column 파일을 읽어 `gpm_line_name_lookup`을 추가하고 table 전체를 교체한다.
- 현재 제품 selector 소비자는 없고 Airflow/command만 이 dataset을 유지한다.
- spec pattern은 `*_MES_LINE_MAPPING_INFO_*`, 일부 문서는 `*_MES_MAPPING_INFO_*`로 drift했다.

## 범위
- 수정: spec/loader/selectors/tests/command, Airflow와 문서.
- 유지: physical table, full snapshot, read-only source mount와 indexes.

## 설계
- 실제 loader test와 producer naming에 맞춰 filename을 `*_MES_LINE_MAPPING_INFO_*.csv.deflate`로 canonicalize하고 문서를 수정한다.
- exact width, datetime/float coercion, uppercase lookup을 검증한 뒤 non-empty snapshot만 atomic replace한다.
- 미사용 dataset이지만 외부 운영 적재 contract가 있으므로 제거하지 않는다.
- schema/migration 변화는 없다.

## 실행 단계
- [x] filename/column/lookup/full replace characterization을 고정한다.
- [x] 공통 lifecycle에 연결한다.
- [x] 저장소 selector 소비자 0건과 Airflow/command 소비를 문서화한다.
- [x] API/DAG/docs drift를 수정한다.

## 검증
- dev API container에서 `api.data_movement.mes_line_mapping_info` tests.
- empty/invalid snapshot 보존, atomic replace, filename match, load-job test.

## 위험과 대응
- 위험: producer가 문서의 짧은 파일명을 사용 중이다.
- 대응: 배포 전 incoming filename inventory를 실행하고 canonical pattern 불일치 파일이 있으면 구현을 중단한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md)와 [Data Movement 공통](data-movement-common-refactor.md). 제품 selector 후행 소비자는 없고 Airflow/운영 적재만 유지한다.
- 복구: loader를 revert하고 직전 전체 snapshot source 또는 DB backup을 재적재한다.

## 진행 기록
- 2026-08-18: dataset 유지와 긴 canonical filename pattern을 확정했다.
- 2026-08-18: 16단계를 완료했다. mounted incoming inventory가 비어 있음을 확인한 뒤 실제 spec/test의 긴 filename과 exact 28-column 계약을 유지해 공통 runner/command에 연결했다. 세 운영 문서의 짧은 pattern을 교정했고 앱 8개 테스트가 통과했다.
