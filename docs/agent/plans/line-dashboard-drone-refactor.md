# ExecPlan: Line Dashboard·Drone 상태 모델 단순화

## 목표
- 대형 views/selectors/tests, legacy model property/delivery seed와 SOP·target·recipient·channel 상태 흐름을 책임별로 단순화한다.
- ESOP Dashboard의 사용자 결과와 외부 Jira/Mail/Messenger/POP3 계약을 보존한다.

## 현재 상태
- `views.py` 2,464줄, `selectors.py` 1,973줄, `tests.py` 9,630줄이며 첫 단계 hotspot 복구 후에도 가장 큰 backend feature다.
- `DroneSOP`과 `DroneSopTarget`이 delivery/channel/rule row를 `send_jira`, `jira_key`, `jira_enabled` 등 legacy property로 다시 노출한다.
- dummy seed가 legacy flat delivery fields를 `legacy_delivery.py`로 변환한다.
- request 일부가 `targetUserSdwtProd`와 `userSdwtProd`를 같은 의미로 허용한다.

## 범위
- 수정: `api.drone`, frontend line-dashboard, Account/Common facade, Airflow/commands, Jira/Mail/Messenger/POP3 dummy/env/docs/tests.
- 유지: `/ESOP_Dashboard/**`, `/api/v1/line-dashboard/**`, current DB rows, delivery audit/history, recipient permission과 external behavior.
- 제외: Defect Spider URL/연결 자체. 기존 `defect_url` 값은 opaque data로 보존한다.

## 설계
- view package는 tables/history/early-inform/targets/recipients/triggers/delivery로, selector package는 dashboard/observer/pipeline/targets/recipients/history로 나눈다.
- canonical target field는 `targetUserSdwtProd` 하나이며 `userSdwtProd` alias는 target endpoint에서 제거한다. 실제 사용자 소속 field에서의 `userSdwtProd` 의미는 유지한다.
- delivery response는 channel delivery/dispatch serializer가 직접 생성하고 model의 `send_*`, `*_reason`, `jira_key`, `inform_step`, `informed_at` 호환 property를 제거한다.
- target response는 `DroneSopTargetChannelConfig`와 `DroneSopNeedToSendRule` serializer가 생성하고 target legacy property와 classmethod service bridge를 제거한다.
- dev seed/JSON/CSV importer는 normalized target/channel/delivery row를 직접 만들며 `legacy_delivery.py`를 삭제한다.
- fallback reason/status 값은 현재 enum 의미를 유지하고 채널별 retry/idempotency를 보존한다.
- frontend React Query가 tables/history/settings/recipient server state를 소유하고 quick filter/dialog/selection만 local state로 둔다.
- schema는 현재 normalized tables로 충분하므로 migration은 없다.

## 실행 단계
- [x] delivery/target/recipient/channel API와 외부 side effect characterization을 고정한다.
- [x] view/selector/test를 수직 responsibility package로 분리한다.
- [x] serializer/service 소비자를 normalized row로 전환한다.
- [x] dev seed와 모든 production/test 참조 0건 후 legacy property/service를 삭제한다.
- [x] frontend page/hooks를 흐름별 controller로 분리하고 query invalidation을 검증한다.
- [x] Observer/Assistant snapshot과 external dummy 전체를 회귀 검증한다.

## 검증
- dev API container에서 `api.drone api.account api.observer api.assistant` tests.
- frontend Line Dashboard tests/lint/build.
- POP3→SOP→dispatch→Jira/Mail/Messenger success/failure/retry end-to-end fake test.
- command dry-run, migration drift, boundary/hotspot/UI/docs audit.

## 위험과 대응
- 위험: model property 제거가 숨은 production 호출을 깨뜨린다.
- 대응: 각 property 이름의 repository reference를 0건으로 만든 뒤 삭제하고 normalized serializer snapshot을 비교한다.
- 위험: 외부 side effect 재시도로 중복 알림이 발생한다.
- 대응: dispatch/delivery idempotency key와 terminal status fencing test를 유지한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md), [감사 기준선](audit-baseline-recovery.md), [Account](account-refactor.md), station_master. Observer와 Assistant ESOP context의 선행 단계다.
- 복구: normalized DB schema는 바꾸지 않으므로 serializer/service/frontend를 revert한다. 외부 발송은 되돌릴 수 없으므로 delivery/dispatch audit row로 중복 재발송을 차단한다.

## 진행 기록
- 2026-08-18: normalized delivery/channel/rule row를 source of truth로 하고 legacy property/seed 제거를 확정했다.
- 2026-08-18: `targetUserSdwtProd`를 Jira target HTTP 계약으로 단일화하고 frontend facade도 target 명칭으로 바꿨다. 실제 사용자 소속/매핑의 `userSdwtProd`는 별도 의미로 유지했다.
- 2026-08-18: view 2,464줄·selector 1,973줄·test 9,630줄 단일 파일을 package/test 모듈로 분리했다. 분리 후 최대 파일은 view 564줄, selector 599줄, test 1,358줄이며 Drone hotspot 기준선 8건을 제거했다.
- 2026-08-18: `DroneSOP`/target/rule legacy property와 `legacy_delivery.py`를 삭제하고 normalized serializer·delivery snapshot·seed service로 모든 소비자를 전환했다. DB schema와 기존 row는 변경하지 않았다.
- 2026-08-18: Drone 외부 설정을 Django settings 단일 경로로 전환하고 POP3/Jira/pipeline 실행 함수의 `*_from_env` 이름을 `*_from_settings`로 교체했다. dummy seed에는 transaction rollback 방식 `--dry-run`을 추가했다.
- 2026-08-18: settings/recipient aggregate server state를 React Query key와 전용 hook으로 분리하고 mutation 후 cache invalidation을 연결했다. Drone·Account·Observer·Assistant 667개, frontend 195개 test와 lint/build, migration drift, 전체 agent audit를 통과했다.
