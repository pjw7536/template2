# ExecPlan: 최종 Shared·Infra 정리

## 목표
- 앞선 23단계 이후 참조되지 않는 included-scope env, Compose wiring, compatibility helper, export, docs와 fixture를 제거한다.
- 저장소 전체 회귀와 DB 무결성을 최종 확인한다.

## 현재 상태
- canonical/legacy env, payload alias, route, facade가 여러 문서와 fixture에 중복돼 있다.
- Spider·Teamstaff는 사용자 지시로 현 상태를 유지해야 한다.

## 범위
- 수정: included feature에서 무참조가 입증된 env/Compose/docs/test fixture/export/compatibility 코드, agent baseline.
- 유지: 운영 장애 fallback, applied migrations, business rows, 모든 Spider·Teamstaff 파일과 공용 entry.

## 설계
- 삭제 대상은 `rg` 저장소 참조 0건, rendered Compose env 0건, runtime registry 0건을 모두 만족해야 한다.
- env 삭제는 `env/api.common.env`, dev/oidc/prod env, 세 app Compose, Django settings, `apps/adfs_dummy`, `docs/configuration.md`를 한 묶음으로 처리한다.
- obsolete migration helper script는 migration graph나 운영 runbook에서 참조가 없을 때만 제거하며 migration 파일은 삭제하지 않는다.
- hotspot baseline은 파일이 임계값 아래로 내려간 obsolete row만 삭제하고 상향하지 않는다.
- docs inventory/API/module/configuration/operations와 fixture를 실제 route/model/command/env에 맞춘다.
- final compatibility search는 snake_case HTTP alias, legacy Observer routes, Drone legacy property/seed, VOC app, react preview가 0건임을 확인한다.

## 실행 단계
- [x] included-scope reference graph와 deletion manifest를 만든다.
- [x] env/Compose/dummy/settings/docs를 manifest 단위로 제거한다.
- [x] public facade/export와 fixture의 무참조 항목을 제거한다.
- [x] docs inventory와 decisions를 최종 상태로 갱신한다.
- [x] 전체 test/build/audit/DB integrity를 실행한다.
- [x] 최종 diff가 Spider·Teamstaff product path를 포함하지 않는지 확인한다.

## 최종 삭제 manifest와 유지 결정

| 대상 | 참조 근거 | 결정 |
| --- | --- | --- |
| `scripts/migrate_legacy_env.py` | 저장소 코드·문서·운영 command 참조 0건 | 삭제 |
| Airflow token, Mail API, Knox Messenger runtime `os.environ` fallback | canonical Django settings 소비자가 존재하고 runtime fallback 참조 0건 | settings 단일 경로로 제거 |
| Drone Jira `templateKey` payload/response alias | frontend 소비자 0건, canonical `jiraTemplateKey` 회귀 존재 | alias 제거, 오래된 요청의 명시적 400 guard만 유지 |
| Email navigation/Assistant fixture의 `user_sdwt_prod` query | browser 소비자 0건, canonical `userSdwtProd` 계약 존재 | canonical query로 교체 |
| 추가 env/Compose key | canonical settings 또는 배포 injection 소비가 모두 존재 | 삭제 없음 |
| 추가 public facade/export | frontend/backend boundary와 docs inventory 감사에서 orphan 0건 | 삭제 없음 |

- 네트워크 timeout/cancel, Email unassigned, load-job 실패 기록, Assistant `legacy-unresolved`는 장애·데이터 복구 fallback이므로 유지했다.
- 현재 작업 diff 기준 tracked 3,167줄 추가·39,286줄 삭제, 새 분리 파일 40,260줄이며 전체 파일 수는 1,560개에서 1,694개로 증가했다. 대형 파일을 책임별 module/test로 나눈 결과이고 source hotspot growth와 boundary 감사가 모두 통과했다.

## 검증
- `docker compose -f docker-compose.test.yml run --rm api-test python manage.py test`
- Django `check`, `makemigrations --check --dry-run`, Account integrity post phase.
- `npm run web:test -- --run`, `npm run web:lint`, `npm run web:build`, `npm run agent:audit`.
- `docker compose -f docker-compose.dev.yml config`, Airflow DAG import/tests, dummy endpoint smoke.
- DB table별 row count/unique/orphan query, compatibility `rg`, `git diff --check`.

## 위험과 대응
- 위험: env가 배포 시스템에서만 주입돼 저장소 검색에 나오지 않는다.
- 대응: canonical env migration 표를 configuration 문서에 남기고 rendered deployment config 확인을 release gate로 둔다.
- 위험: cleanup이 제외 범위를 건드린다.
- 대응: changed-path denylist와 catalog snapshot 실패 시 cleanup을 중단한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md)와 앞선 23개 완료 계획. 이 계획 뒤에는 제품 변경 단계가 없다.
- 복구: 삭제 manifest를 역순 적용하고 이전 env/Compose/dummy/docs를 함께 복원한다. migration과 업무 row는 이 단계에서 변경하지 않는다.

## 진행 기록
- 2026-08-18: 참조 0건과 제외-path 불변을 최종 삭제 gate로 확정했다.
- 2026-08-18: 무참조 legacy env migration script를 삭제하고 Airflow token·Mail·Knox Messenger를 Django settings 단일 경로로 전환했다. Jira `templateKey` alias와 남은 snake_case browser fixture를 제거했으며 환경 key는 배포 소비가 남아 있어 추가 삭제하지 않았다.
- 2026-08-18: 전체 backend 1,123개, frontend 199개, Airflow 5개 테스트와 lint/build, Django check·migration drift·권한 무결성, dev/OIDC/prod Compose render, dummy OIDC/RAG/Mail/Jira/API health smoke, 전체 agent audit가 통과했다.
- 2026-08-18: 포함 범위 61개 관리 테이블의 정확한 row count를 수집했고 unique 중복과 FK orphan은 모두 0건이었다. 최종 status denylist에서 Spider·Teamstaff product path 변경도 0건이었다.
