# ExecPlan: Data Movement `station_master`

## 목표
- `station_master` snapshot 적재와 Observer/Drone 조회용 lookup 계약을 명확히 분리한다.

## 현재 상태
- 백틱 구분 55-column 파일을 읽어 전체 table을 교체한다.
- `station_lookup`, `sdwt_prod_lookup`, `prc_group_lookup` 파생 column과 Observer raw SQL, Drone selector facade가 소비한다.

## 범위
- 수정: station_master spec/loader/selectors/tests/command와 관련 Observer·Drone characterization, 문서.
- 유지: 물리 table, 전체 교체, source/reference read-only mount, 현재 indexes와 원천 column.

## 설계
- 파일 계약은 `*_STATION_MASTER_*.csv.deflate`, delimiter 백틱, 정확히 55개 원천 column으로 고정한다.
- normalization은 lookup 세 column의 trim+uppercase만 수행하고 원천값은 보존한다.
- 새 snapshot은 temp COPY와 row-count 검증 후 단일 transaction에서 교체하며 0-row 파일은 실패해 기존 snapshot을 보존한다.
- consumer는 `station_master.selectors` facade를 사용한다. Observer의 복합 join raw SQL은 Observer 단계에서 selector facade로 이동한다.
- schema/migration 변화는 없다.

## 실행 단계
- [x] column width/lookup/full-replace characterization을 고정한다.
- [x] 공통 runner/COPY policy에 연결한다.
- [x] Observer·Drone 소비 계약과 query indexes를 검증한다.
- [x] command를 공통 facade로 전환하고 API camelCase summary를 검증한다.

## 검증
- `python manage.py test api.data_movement.station_master api.drone api.observer`를 dev API container에서 실행.
- empty snapshot 보존, atomic replace, lookup case-insensitive 조회, load-job terminal status test.

## 위험과 대응
- 위험: 잘못된 snapshot이 전체 기준정보를 비운다.
- 대응: 0-row/column-width 실패를 transaction 이전에 판정한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md)와 [Data Movement 공통](data-movement-common-refactor.md). 후행 Drone·Observer가 selector facade를 소비한다.
- 복구: loader 코드를 이전 버전으로 되돌린다. 전체 교체 transaction이 성공한 뒤의 데이터 복구는 적재 직전 snapshot backup 또는 동일 source 파일 재적재로 수행한다.

## 진행 기록
- 2026-08-18: 전체 교체와 세 lookup column을 불변 계약으로 확정했다.
- 2026-08-18: 9단계를 완료했다. 파일 탐색·선점을 공통 runner에 연결하고 command 중복을 공통 기반으로 제거했다. 전체 교체·빈 snapshot 보존·lookup 및 Drone/Observer 소비 계약을 포함한 382개 테스트가 통과했다.
