# ExecPlan: 비-Spider Feature 선설계·순차 리팩토링 프로그램

## 목표
- 제품 코드를 수정하기 전에 이번 범위의 모든 feature 계약과 상세 ExecPlan을 동결한다.
- 사용자 흐름과 업무 데이터를 보존하면서 내부 호환 alias, 중복 책임, 대형 hotspot을 제거한다.
- API·DB·권한·Airflow·dummy·env 의존성을 하나의 계약표로 관리하고 아래 실행 순서대로 한 feature씩 검증한다.

## 현재 상태
- 2026-08-18 기준 backend/frontend 경계 감사는 통과한다.
- hotspot 감사는 `apps/api/api/drone/selectors.py` 1,973줄(기준 1,893)과 `apps/api/api/drone/tests.py` 9,630줄(기준 9,571) 때문에 실패한다.
- 저장소의 API route, frontend route, model, command, env 색인은 `docs/inventory.md`에 있으나 일부 실제 코드와 drift가 있다. 대표적으로 `racb_list`의 실제 separator는 백틱인데 문서에는 comma로 적혀 있다.
- 브라우저 요청은 대체로 camelCase지만 AppStore·Emails 등 일부 입력에서 snake_case alias를 함께 허용한다.
- Data Movement의 Airflow 요청/응답은 snake_case이며, browser API와 내부 trigger가 서로 다른 표기 규칙을 사용한다.
- 개발 DB의 `ActivityLog`는 0건이어서 운영 접속 여부를 판단할 근거로 사용하지 않는다.

## 범위
- 포함: 감사 기준선, Platform Common·Health·Errors, Account, Auth, Activity·Access Stats, AppStore, VOC, Data Movement 공통과 9개 표 앱, RAG 공통 adapter, Emails, Line Dashboard·Drone, Observer, Assistant, Home·Portal Shell, 최종 Shared·Infra 정리.
- 제외: L0/L1/L3/PM/TTTM Spider, Spider Hub, Defect 외부 연결과 그 route/API/권한/env/branding/Assistant context, Teamstaff 전체.
- 제외 영역은 이번 프로그램에서 발견한 위반도 수정하지 않고 별도 debt로만 남긴다.
- 시각 디자인 전면 개편, 적용 migration 수정, 운영 데이터 물리 삭제, commit/push는 포함하지 않는다.

## 설계
- 아래 공통 계약을 모든 상세 계획의 상위 규칙으로 적용한다.
- 상세 계획이 같은 endpoint/model/helper를 변경할 때는 먼저 실행되는 소유 계획이 public contract를 확정하고 후행 계획은 그 facade만 소비한다.
- 구현 중 계약 사실이 달라지면 영향받는 상세 계획과 이 문서를 함께 갱신하고 전체 교차 검토를 다시 통과하기 전까지 제품 코드 변경을 중단한다.

## 공통 계약

### 대표 화면 URL
| 소유 feature | 대표 URL | 결정 |
| --- | --- | --- |
| Home | `/` | 유지 |
| Auth | `/login` | 유지 |
| Account | `/settings/account`, `/settings/members`, `/settings/permissions` | `/settings` index redirect는 유지 |
| Access Stats | `/access-stats` | 유지 |
| AppStore | `/appstore` | 유지 |
| VOC | `/voc` | 유지 |
| Emails | `/emails/inbox`, `/emails/sent`, `/emails/members` | 유지 |
| Assistant | `/assistant`와 전역 ChatWidget | 둘 다 유지하되 공통 controller를 공유 |
| Line Dashboard | `/ESOP_Dashboard/**` | 대소문자를 포함한 현재 공개 URL 유지 |
| Observer | `/observer`, `/observer/:eqpId` | 유지 |
| Home preview | `/react-logo-preview` | 내부 참조 0건이므로 제거 |
| Spider·Teamstaff | 현재 URL 전체 | 사용자 지시에 따라 변경 금지 |

### API 표기와 오류
- 브라우저와 Airflow가 보내고 받는 JSON/query key는 camelCase 하나만 허용한다.
- DB column, Django model field, Python 내부 keyword는 snake_case를 유지하고 serializer/view 경계에서만 변환한다.
- 기존 snake_case HTTP alias는 characterization test로 현재 소비자를 먼저 고정한 뒤 저장소 참조를 0건으로 만들고 같은 feature 단계에서 400 `invalid_request`로 전환한다.
- 공통 오류 body는 `{ "code": string, "message": string, "details": object|null, "fieldErrors": object }`이다.
- 순차 구현 중간 상태에서는 Platform Common이 builder와 공용 계층 소유 오류를 먼저 전환하고, 각 업무 API는 해당 소유 단계에서 저장소 소비자와 함께 전환한다. 제외된 Spider API 오류는 이번 프로그램에서 재작성하지 않는다.
- 인증 실패는 401 `authentication_required`, 접근 실패는 403 `scope_access_required`, 입력 실패는 400 `invalid_request`, 외부 의존 실패는 502 `external_dependency_error`, timeout은 504 `external_dependency_timeout`, 취소는 client disconnect로 응답 생성을 중단한다.
- 성공 응답의 업무 필드는 camelCase를 사용한다. 파일/DB 원천 column을 그대로 제공해야 하는 표 데이터는 명시된 row object 안에서만 원천 snake_case를 유지하며 새 API 공용 계약으로 확산하지 않는다.

### API 소비자 표
| API/adapter | 저장소 내부 소비자 | 소유 계획 |
| --- | --- | --- |
| `/api/v1/health/` | Compose/배포 health check | Platform Common·Health·Errors |
| `/api/v1/auth/**`, `/auth/google/callback/` | AuthProvider, login page, dummy ADFS | Auth |
| `/api/v1/account/**` | Account UI, Auth gate/onboarding, Emails mailbox UI, Line Dashboard line/recipient UI, Assistant 권한 provenance | Account |
| `/api/v1/activity/**` | AppAccessTracker, Access Stats page, 외부 usage API | Activity·Access Stats |
| `/api/v1/appstore/**` | AppStore page와 Assistant AppStore snapshot | AppStore |
| `/api/v1/voc/**` | VOC page | VOC |
| `/api/v1/data-movement/**` | Airflow DAG, management command와 운영 호출 | Data Movement 공통·표 앱 |
| `api.rag.services` | Assistant, Emails, offsite dummy RAG | RAG 공통 Adapter |
| `/api/v1/emails/**` | Emails UI, OCR worker, Airflow/운영 trigger, Assistant Email context | Emails |
| `/api/v1/line-dashboard/**` | Line Dashboard UI, Airflow, POP3/Jira/Mail/Messenger, Observer와 Assistant ESOP snapshot | Line Dashboard·Drone |
| `/api/v1/observer/**` | Observer UI와 Assistant Observer 분석 | Observer |
| `/api/v1/assistant/**` | Assistant page, ChatWidget, Emails/Observer/AppStore/Line Dashboard context | Assistant |

### DB 소유권과 참조
| 소유 app | 테이블/모델 | 허용 참조 |
| --- | --- | --- |
| Account | `account_*`, `User`와 접근/소속 모델 | Auth·Activity·AppStore·VOC·Emails·Drone·Assistant는 service/selector facade만 사용 |
| Activity | `activity_log`, `activity_external_*` | middleware write와 Access Stats selector/service |
| AppStore | `appstore_*` | Assistant snapshot은 AppStore selector facade만 사용 |
| VOC | `voc_post`, `voc_reply` | Account 작성자 FK, Activity middleware |
| Data Movement 표 앱 | 물리 table명과 `<table>_load_job` | Observer와 ct_process_comment는 각 표 selector facade만 사용 |
| Emails | `emails_*` | Account 권한 facade, RAG adapter, Assistant Email context |
| Drone | `drone_*` | Account selector, Observer read facade, Assistant snapshot |
| Assistant | `assistant_*` | Account 권한과 domain snapshot selector, RAG adapter |
- cross-feature FK는 기존 schema를 보존한다. 내부 import는 다른 app의 `services/__init__.py` 또는 `selectors.py`/`selectors/__init__.py`만 사용한다.
- 적용 migration은 변경하지 않는다. column 제거는 expand/backfill/verify/contract 순서의 새 migration으로 수행하고 역 migration이 데이터 복원을 보장하지 못하면 배포 전 backup/row-count 검증을 rollback 조건으로 둔다.

### 권한 흐름
- `UserAccess.role`의 `user`/`admin`과 canonical `portal` 선행 조건을 유지한다.
- Account가 scope 판정의 source of truth이며 frontend gate는 표시 최적화일 뿐 backend 권한 검사를 대체하지 않는다.
- Data Movement와 운영 trigger는 `AIRFLOW_TRIGGER_TOKEN`, OCR은 `EMAIL_OCR_INTERNAL_TOKEN`을 사용한다.
- Emails data scope, Drone recipient/target 권한, Assistant provenance는 현재 더 엄격한 domain 규칙을 유지한다.
- scope key 삭제는 VOC field나 preview route 제거와 무관하다. Spider·Teamstaff scope는 이번 범위에서 변경하지 않는다.

### 외부 연동·offsite 계약
- 외부 URL은 Django/Vite env로만 주입하고 settings의 기능별 다중 fallback을 제거해 한 canonical env key만 읽는다.
- Auth/RAG/Assistant/Mail 계약 변경은 `docker-compose.dev.yml`, `env/api.dev.env`, `apps/adfs_dummy`, Django 설정/호출부를 같은 단계에서 갱신한다.
- Data Movement는 `data_movement_file_load`, `ct_process_comment_summary` DAG와 management command를 실제 소비자로 취급한다.
- API business file mount는 `/data/<domain>`과 `${<DOMAIN>_DATA_HOST_PATH:-../data/<domain>}` 규칙을 유지한다.

### 제거와 유지
| 대상 | 결정 | 제거 gate |
| --- | --- | --- |
| AppStore/Emails HTTP snake_case alias | 제거 | frontend, tests, command 소비자 0건 및 camelCase 오류 test |
| Data Movement snake_case JSON key | `dry_run`, `processed_count` 등 제거 | Airflow DAG를 camelCase로 동시 전환 |
| VOC `app="기타"` UI/API/DB column | 제거 | 전체 row가 `기타`인지 migration 사전 검사 |
| `/react-logo-preview` | 제거 | 저장소 route/link 참조 0건 확인 |
| Auth `target`/`next` redirect alias | `target`만 유지하고 `next` 제거 | dummy와 frontend가 `target`만 사용 |
| 장애 대응 fallback | 유지 | 네트워크 timeout/cancel, Email unassigned, load-job 실패 기록, Assistant `legacy-unresolved` |
| Spider·Teamstaff compatibility | 유지 | 이번 범위 제외 |

## 상세 ExecPlan 색인과 실행 순서
1. [감사 기준선 복구](audit-baseline-recovery.md)
2. [Platform Common·Health·Errors](platform-common-health-errors-refactor.md)
3. [Account](account-refactor.md)
4. [Auth](auth-refactor.md)
5. [Activity·Access Stats](activity-access-stats-refactor.md)
6. [AppStore](appstore-refactor.md)
7. [VOC](voc-refactor.md)
8. [Data Movement 공통](data-movement-common-refactor.md)
9. [`station_master`](data-movement-station-master-refactor.md)
10. [`ctttm_workorder_list`](data-movement-ctttm-workorder-list-refactor.md)
11. [`eqp_status_chg`](data-movement-eqp-status-chg-refactor.md)
12. [`m_interlock`](data-movement-m-interlock-refactor.md)
13. [`mi_tip_update_hist`](data-movement-mi-tip-update-hist-refactor.md)
14. [`racb_list`](data-movement-racb-list-refactor.md)
15. [`m_tkin_prevent`](data-movement-m-tkin-prevent-refactor.md)
16. [`mes_line_mapping_info`](data-movement-mes-line-mapping-info-refactor.md)
17. [`ct_process_comment`](data-movement-ct-process-comment-refactor.md)
18. [RAG 공통 Adapter](rag-common-adapter-refactor.md)
19. [Emails](emails-refactor.md)
20. [Line Dashboard·Drone](line-dashboard-drone-refactor.md)
21. [Observer](observer-refactor.md)
22. [Assistant](assistant-refactor.md)
23. [Home·Portal Shell](home-portal-shell-refactor.md)
24. [Shared·Infra](shared-infra-final-cleanup.md)

## 실행 단계
- [x] 사용자 범위 결정: Spider 전체와 Teamstaff 제외, VOC 단일 app field와 react preview 제거.
- [x] 현재 경계·hotspot·route·model·env·내부 소비자 기준선 조사.
- [x] 위 24개 상세 ExecPlan 작성.
- [x] endpoint/model/helper의 단일 소유자와 downstream 순서를 교차 검토.
- [x] 모든 계획의 계약·삭제 대상·rollback 조건이 확정문으로 작성됐는지 검사하고 설계를 동결.
- [x] 1번부터 24번까지 한 번에 하나씩 구현·검증.
- [x] 최종 전체 회귀와 문서/fixture/env cleanup 검증.

## 검증
- 설계: placeholder 검사는 고정 단어 목록을 인자로 받는 일회성 검사로 실행하고 결과가 0건이어야 한다.
- 정적 감사: `npm run agent:audit`
- Backend: `docker compose -f docker-compose.test.yml run --rm api-test python manage.py test`, `check`, `makemigrations --check --dry-run`.
- Frontend: `npm run web:test -- --run`, `npm run web:lint`, `npm run web:build`.
- 무결성: `docker compose -f docker-compose.dev.yml exec -T api python manage.py check_access_permission_integrity --phase post-migration`, feature별 row-count/constraint query, `git diff --check`.
- 제외 범위: 최종 diff에 Spider·Teamstaff product path가 없는지 `git diff --name-only`로 확인한다.

## 위험과 대응
- 위험: 한 feature의 alias 제거가 후행 feature 소비자를 먼저 깨뜨릴 수 있다.
- 대응: producer 단계에서 저장소 소비자를 함께 canonical 계약으로 전환하고 전체 회귀가 통과한 뒤 다음 단계로 간다.
- 위험: 적용 migration과 운영 row를 단순화 과정에서 손상할 수 있다.
- 대응: 새 migration만 추가하고 사전 row-count/값 분포 검사와 사후 무결성 command를 배포 gate로 사용한다.
- 위험: offsite dummy가 운영 호출부와 drift할 수 있다.
- 대응: Auth/RAG/Assistant/Mail 단계마다 dummy contract test와 dev Compose smoke test를 실행한다.
- 위험: 범위 제외 Spider·Teamstaff 파일이 공용 catalog 정리 과정에서 함께 바뀔 수 있다.
- 대응: 공용 catalog에서 해당 entry를 그대로 보존하고 최종 changed-path 검사를 수행한다.

## 진행 기록
- 2026-08-18: 기존 계획·문서·코드와 정적 감사를 조사했다. 경계 감사 통과, Drone hotspot 2건 실패를 확인했다.
- 2026-08-18: 사용자 결정으로 Spider 전체와 Teamstaff를 제외하고 VOC 단일 app 계약과 react preview 제거를 확정했다.
- 2026-08-18: 공통 URL/API/DB/권한/offsite/compatibility 계약과 24단계 실행 순서를 확정했다.
- 2026-08-18: 상세 계획 24개가 필수 섹션, 상호 링크, 선행·후행 의존성과 복구 기준을 모두 갖는지 검사했다. placeholder 0건, master link 24건, 계획 외 변경 0건, docs audit 통과를 확인하고 설계를 동결했다.
- 2026-08-18: 1단계 감사 기준선 복구를 완료했다. Drone selector/test 책임을 분리해 기준선 상향 없이 hotspot 감사를 복구했고 Drone 297개 테스트, migration drift, 전체 agent audit를 통과했다.
- 2026-08-18: 2단계 조사에서 전역 오류 재작성과 전역 strict parser가 제외된 Spider 동작까지 바꾼다는 사실을 확인했다. 공용 계층 소유 오류와 비-Spider env만 먼저 전환하고 업무 오류는 각 feature 단계에서 전환하도록 공통 계약을 재동결했다.
- 2026-08-18: 2단계 Platform Common·Health·Errors를 완료했다. strict env, canonical error/HTTP adapter와 안전한 route 오류 UI를 적용하고 backend 1,109개·frontend 185개 테스트 및 전체 감사를 통과했다. Spider 오류 계약과 설정 parser는 기존 동작을 보존했다.
- 2026-08-18: Account 사전 검사에서 integrity command의 실제 phase가 `pre-migration/post-migration`임을 확인해 계획의 잘못된 `pre/post` 표기를 교정하고 재동결했다.
- 2026-08-18: 3단계 Account를 완료했다. camelCase HTTP/Airflow 계약과 canonical 오류를 적용하고 view·selector·감사 service·frontend query key를 분리했으며 Account 230개와 downstream 524개 회귀, frontend test/lint/build, 무결성·migration·경계·hotspot 검사를 통과했다. 기존 hotspot 기준선 숫자는 유지했다.
- 2026-08-18: 4단계 Auth를 완료했다. redirect를 `target` 하나로, `/me`를 camelCase와 `scopeAccess`로 단일화하고 User 쓰기를 Account facade로 이동했다. Dummy discovery/token/userinfo를 실제 endpoint와 일치시켰으며 Auth+Account 266개·frontend 188개 test, build/lint, Compose/offsite smoke와 전체 감사를 통과했다.
- 2026-08-18: 5단계 Activity·Access Stats를 완료했다. 기록·집계·수동 입력·외부 sync service와 차트·요약·입력 panel을 분리하고 Activity 오류를 canonical 계약으로 전환했다. frozen tracking catalog를 tracker·branding·통계가 함께 사용하며 Spider·Teamstaff snapshot을 보존했다. 전체 backend 1,119개·frontend 191개 test, build/lint, migration·권한 무결성과 전체 감사를 통과했다.
- 2026-08-18: 6단계 AppStore를 완료했다. 실제 DB 커버 저장 모델에 맞춰 계획을 재동결하고 apps/order/cover/detail/reactions/comments view를 분리했다. snake_case HTTP·frontend fallback을 제거하고 DB rollback을 고정했으며 전체 backend 1,121개·frontend 195개 test, build/lint, migration·권한 무결성과 전체 감사를 통과했다.
- 2026-08-18: 7단계 VOC를 완료했다. 값 분포를 사전 확인하고 fail-closed migration으로 단일 `app=기타` DB column을 제거했으며 API/UI/category 상태를 함께 축소했다. 개발 DB schema·row count를 사후 확인하고 전체 backend 1,122개·frontend 195개 test, build/lint, migration·권한 무결성과 전체 감사를 통과했다.
- 2026-08-18: 8단계 Data Movement 공통을 완료했다. 9개 직접 import를 지연 registry로 교체하고 공통 파일 선점 runner를 추가했으며 trigger API와 Airflow DAG를 camelCase로 동시 전환했다. legacy payload 거절, outcome metadata 변환과 mocked DAG 요청을 고정하고 Data Movement 159개·Airflow 3개 테스트 및 migration drift를 통과했다.
- 2026-08-18: 9단계 `station_master`를 완료했다. full-replace/lookup 정책을 유지한 채 공통 runner와 command facade에 연결했고 station·Drone·Observer 382개 회귀를 통과했다.
- 2026-08-18: 10단계 `ctttm_workorder_list`를 완료했다. MST/MNU source별 filter/replace와 DAG 선행 관계를 유지하며 공통 runner/command에 연결했고 CT comment·Observer 포함 148개 회귀를 통과했다.
- 2026-08-18: 11단계 `eqp_status_chg`를 완료했다. timezone/retention/upsert 정책을 유지하며 공통 runner/command에 연결했고 Observer 포함 87개 회귀를 통과했다.
- 2026-08-18: 12단계 `m_interlock`을 완료했다. 35-column/dedup/lookup upsert 정책을 유지하며 공통 runner에 연결했고 Observer 포함 98개 회귀를 통과했다.
- 2026-08-18: 13단계 `mi_tip_update_hist`를 완료했다. event mapping/timezone/retention upsert 정책을 유지하며 공통 runner/command에 연결했고 Observer 포함 88개 회귀를 통과했다.
- 2026-08-18: 14단계 `racb_list`를 완료했다. 백틱 원천과 comma eqp explode 계약을 바로잡고 latest 범위 교체를 공통 runner/command에 연결했다. RACB 기본 URL을 env-only/null fallback으로 정리하고 Observer 포함 85개 회귀를 통과했다.
- 2026-08-18: 15단계 `m_tkin_prevent`를 완료했다. `0x03`/50-column 계약과 line 범위 교체를 명시해 공통 runner/command에 연결했고 Observer matrix 포함 85개 회귀를 통과했다.
- 2026-08-18: 16단계 `mes_line_mapping_info`를 완료했다. canonical filename/28-column/full-replace 계약을 공통 runner/command에 연결하고 문서 drift를 교정했으며 앱 8개 테스트가 통과했다.
- 2026-08-18: 17단계 `ct_process_comment`를 완료했다. loader lifecycle을 공통화하고 summary prompt/constants/test 책임을 분리했으며, 직접 DB/OpenWebUI를 소유하던 540줄 연속 DAG를 107줄 canonical API consumer로 교체했다. ct_process_comment 56개·Observer 포함 133개·Airflow 3개 테스트와 hotspot 감사를 통과하고 기준선 3건을 제거했다.
- 2026-08-18: 18단계 RAG 공통 Adapter를 완료했다. `ASSISTANT_RAG_*`/runtime env fallback을 제거하고 strict immutable config, index allowlist와 search/insert/delete/index-info adapter를 도입했다. dev Compose/dummy를 canonical `RAG_*`로 재생성해 네 endpoint smoke를 통과했고 RAG·Emails·Assistant 132개 회귀 및 경계·migration 검사를 통과했다.
- 2026-08-18: 19단계 Emails를 완료했다. HTTP JSON/query를 camelCase로 단일화하고 view·selector·test를 책임별로 분리했으며 POP3 설정과 RAG adapter/Outbox·MinIO compensation 경계를 고정했다. dev Mail/RAG/OCR smoke, downstream backend 365개와 frontend 195개 test, lint/build, migration·경계·UI·hotspot 검사를 통과했다.
- 2026-08-18: 20단계 Line Dashboard·Drone을 완료했다. target HTTP 계약을 `targetUserSdwtProd`로 단일화하고 normalized delivery/channel/rule row로 legacy model property와 seed bridge를 제거했다. view·selector·test hotspot을 책임별 모듈로 분리하고 settings 단일 외부 설정, seed `--dry-run`, frontend React Query settings snapshot을 적용했다. downstream backend 667개·frontend 195개 test, lint/build, migration drift와 전체 감사를 통과했다.
- 2026-08-18: 21단계 Observer를 완료했다. canonical page/detail/evidence와 단일 equipment-info route만 보존하고 legacy URL·selector·frontend hooks를 제거했다. view·selector·test와 분석 context/payload/runtime 조율 책임을 분리했으며 Observer·Assistant·Drone·Data Movement 584개와 frontend Observer 30개 테스트, lint/build, migration drift 및 전체 감사를 통과했다.
- 2026-08-18: 22단계 Assistant를 완료했다. view·test hotspot과 Turn 입력/권한·실행/저장 책임을 분리하고 page/widget의 session·composer controller를 통합했다. `legacy-unresolved`, SSE cancel/fence, 포함 domain context를 보존해 backend 765개·frontend 195개 회귀, OpenWebUI/RAG dummy smoke, backfill dry-run, migration drift와 전체 감사를 통과했다.
- 2026-08-18: 23단계 Home·Portal Shell을 완료했다. route gate, access tracking, navigation, branding metadata를 `portalAppCatalog`로 단일화하고 Assistant widget 숨김 판정을 shell helper로 이동했다. `/react-logo-preview`와 빈 component/CSS를 제거했으며 frontend 199개 테스트, lint/build, 전체 감사를 통과하고 Spider·Teamstaff product path 불변을 확인했다.
- 2026-08-18: 24단계 Shared·Infra를 완료했다. 무참조 legacy env migration script와 외부 adapter runtime env fallback, Jira `templateKey` alias, snake_case browser fixture를 제거하고 canonical settings/query 계약과 configuration 문서를 맞췄다. 전체 backend 1,123개·frontend 199개·Airflow 5개 테스트, lint/build, Django·Compose·dummy smoke·DB unique/FK 무결성·전체 agent audit가 통과했으며 Spider·Teamstaff product path 변경은 0건이었다.
