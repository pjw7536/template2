# ExecPlan: Observer 조회·pagination·Assistant 연결 단일화

## 목표
- 중복 로그 endpoint, pagination/query selector, Data Movement·Drone 조회와 Assistant 분석 연결을 정리한다.
- `/observer`와 evidence deep link의 KST 표시·결과를 유지한다.

## 현재 상태
- `selectors.py` 2,171줄, `tests.py` 2,408줄, `views.py` 823줄, `services/analysis.py` 1,032줄이다.
- frontend는 canonical `/logs/page`, `/logs/<logKey>/page|detail|evidence`를 사용한다.
- `/logs`, `/logs/eqp|tip|spc-interlock|fdc-interlock|ctttm|racb|esop` legacy endpoints와 line+eqp equipment-info alias가 남아 있다.
- Data Movement 7개 source와 Drone ESOP selector, Assistant observer-analysis가 연결돼 있다.

## 범위
- 수정: `api.observer`, frontend observer, Data Movement/Drone selector facade 소비, Assistant Observer tool contract, docs/tests.
- 유지: `/observer`, `/observer/:eqpId`, KST 날짜 해석, source별 payload, cursor/evidence deep link.

## 설계
- canonical endpoint는 metadata routes, `/equipment-info/<eqpId>`, `/logs/page`, `/logs/<logKey>/page|detail|evidence`, tkin-prevent routes뿐이다.
- `/equipment-info/<lineId>/<eqpId>`, `/logs`, 일곱 `/logs/<type>` legacy endpoint를 제거한다.
- source catalog는 logKey, Data Movement/Drone selector callable, page/detail/evidence serializer를 한 곳에서 정의한다. selector facade 밖 model/raw table import는 하지 않는다.
- query는 `lineId`, `sdwtId`, `prcGroup`, `eqpId`, `from`, `to`, `types`, `pageSize`, `cursor`, `logId`, `evidenceId` camelCase만 허용한다.
- server response/cursor는 current camelCase와 KST `+09:00` ISO contract를 유지한다.
- frontend server pages는 React Query infinite query만 소유하고 route/filter/slider/selected evidence는 URL+local UI state로 둔다.
- Assistant는 Observer public analysis service만 호출하고 browser raw log payload를 신뢰하지 않는다.
- DB/migration 변화는 없다.

## 실행 단계
- [x] canonical/legacy endpoint와 일곱 source payload characterization을 고정한다.
- [x] frontend unused `fetchLogs`와 line+eqp alias 소비를 제거한다.
- [x] view/selector/test/analysis를 metadata/logs/tkin/evidence/analysis package로 분리한다.
- [x] Data Movement·Drone facade 기반 source catalog를 적용한다.
- [x] legacy URL 참조 0건 후 routes/classes를 삭제한다.
- [x] Assistant analysis와 deep-link 회귀를 검증한다.

## 검증
- dev API container에서 `api.observer` 및 관련 7 Data Movement apps, `api.drone api.assistant` tests.
- frontend Observer tests/lint/build.
- legacy endpoint 404, canonical cursor/page/detail/evidence, KST browser-timezone matrix tests.
- migration drift와 boundary/hotspot/UI audit.

## 위험과 대응
- 위험: source catalog 통합이 source 고유 field를 평준화한다.
- 대응: 공통 envelope만 catalog화하고 source detail payload snapshot은 개별 serializer에 유지한다.
- 위험: legacy URL 북마크가 깨진다.
- 대응: 저장소 외 소비자가 없다는 사용자 가정에 따라 제거하며 canonical route를 문서화한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md), Data Movement 7개 selector 계획과 [Line Dashboard·Drone](line-dashboard-drone-refactor.md). Assistant 분석의 선행 단계다.
- 복구: DB schema가 없으므로 routes/view/selector/frontend를 함께 revert한다. source table과 cursor data는 변경하지 않는다.

## 진행 기록
- 2026-08-18: frontend 사용 경로를 근거로 canonical log/equipment endpoints와 제거 URL을 확정했다.
- 2026-08-18: canonical page/detail/evidence와 단일 equipment-info route만 남기고 legacy URL·view·frontend API/hooks를 제거했다. view·selector·test를 metadata/TKIN/log/source 책임으로 분리하고 분석을 context/payload/runtime 조율 모듈로 나눴다. Observer·Assistant·Drone·Data Movement 584개와 frontend Observer 30개 테스트, lint/build, migration drift 및 전체 agent audit를 통과했다.
