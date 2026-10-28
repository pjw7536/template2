# 실행 계획·검증 기록 목록

이 폴더에는 작업 당시의 목표, 설계, 실행 단계와 검증 결과를 보존합니다.
현재 작업에 적용할 계획 작성법은 [ExecPlan 규칙](../PLANS.md), 앱 사용법은 [전체 문서 안내](../../README.md)를 확인합니다.

## 기록을 찾는 방법

1. 아래 주제에서 관련 기록을 펼칩니다. 한 기록이 여러 주제에 걸치면 주된 변경 목적에 따라 한 곳에 연결했습니다.
2. 파일 제목과 `목표`를 보고 찾는 작업인지 확인합니다.
3. `진행 기록`의 날짜와 `검증`·결과를 읽고, 같은 주제의 후속 계획과 [결정 이력](../decisions.md)을 함께 확인합니다.

목록은 주제별·파일명순이며 최신순이 아닙니다. 체크박스나 파일 이름만으로 완료·진행 상태를 판단하지 않습니다.
과거 기록에는 폐기된 경로·명령·설계가 포함될 수 있으므로 그대로 실행하기 전에 현재 안내와 소스를 확인합니다.

| 주제 | 기록 수 |
| --- | --- |
| [계정·접근 권한·접속 통계](#계정접근-권한접속-통계) | 42 |
| [AI·대화·RAG](#ai대화rag) | 31 |
| [메일·앱 목록·공통 화면](#메일앱-목록공통-화면) | 13 |
| [Observer](#observer) | 17 |
| [Spider](#spider) | 36 |
| [ESOP·Drone 알림·TIP](#esopdrone-알림tip) | 23 |
| [데이터 적재·테이블](#데이터-적재테이블) | 30 |
| [Airflow](#airflow) | 11 |
| [Keycloak·Headlamp](#keycloakheadlamp) | 36 |
| [서버 배포·공통 인프라](#서버-배포공통-인프라) | 29 |
| [저장소·로컬 환경·환경 변수](#저장소로컬-환경환경-변수) | 30 |
| [에이전트·문서·검사·Git](#에이전트문서검사git) | 18 |

파일 이름이나 본문으로 찾고 싶다면 저장소 루트에서 다음 명령을 사용할 수 있습니다.

```bash
rg --files docs/agent/plans -g '*observer*.md'
rg -n '검색어' docs/agent/plans -g '*.md'
```

## 계정·접근 권한·접속 통계

로그인 이후의 사용자·소속·접근 권한과 접속 현황 변경 기록입니다. 현재 계약은 [Account 안내](../../modules/account.md)와 [Auth 안내](../../modules/auth.md)를 확인합니다.

<details>
<summary>기록 42개 펼치기</summary>

- [접근 권한 관리자 capability 분리](access-management-capability.md)
- [권한 migration 통합과 인증 상태 즉시 갱신](access-migration-and-auth-refresh.md)
- [Portal·앱 권한 매트릭스 통합](access-permission-matrix-unification.md)
- [권한 변경 통합 리뷰](access-permission-review.md)
- [권한 관리 UX 후속 개선](access-permission-ux-followup.md)
- [access-stats 수동 외부 API 동기화](access-stats-manual-external-sync.md)
- [access-stats 역할별 동기화 제한](access-stats-sync-throttle.md)
- [자동 접근 규칙 매트릭스](account-access-policy-matrix.md)
- [Account 권한 migration 통합](account-authorization-migration-squash.md)
- [Account 카드 높이 조정](account-card-viewport-height.md)
- [Account 현재 소속 실효 역할 통일](account-effective-affiliation-role.md)
- [권한 매트릭스 수동 부여 사용자 필터](account-manual-grant-filter.md)
- [대규모 권한 매트릭스 단일 변경 성능 개선](account-matrix-mutation-performance.md)
- [account migration 상태 복구](account-migration-state-recovery.md)
- [전체 권한 승인 대기 및 일괄 승인](account-pending-bulk-approval.md)
- [승인 대기 요청 무한 스크롤](account-pending-infinite-scroll.md)
- [Account 사용자·소속·접근 권한 단순화](account-refactor.md)
- [사용자 전체 권한 일괄 변경](account-user-apply-all-permissions.md)
- [Account 사용자 데이터테이블 통일](account-user-datatable.md)
- [Activity·Access Stats 통합](activity-access-stats-refactor.md)
- [등록 시 소속 입력과 접근 권한 분리](affiliation-initial-reference.md)
- [소속 역할 권한 강화](affiliation-role-authorization-hardening.md)
- [앱 권한 allowed/denied 단순화](app-access-boolean-permissions.md)
- [앱 접근 권한 강제](app-access-enforcement.md)
- [앱 단위 접근 scope 도입](app-access-scopes.md)
- [앱별 접속 통계 대시보드](app-access-stats-dashboard.md)
- [앱별 소속 데이터 범위 분리](app-affiliation-data-scope.md)
- [앱 권한 매트릭스 관리 UI](app-permission-matrix.md)
- [고정 역할 기반 접근 권한 단순화](app-rbac-unification.md)
- [Auth OIDC·session·dummy 계약 단일화](auth-refactor.md)
- [권한 코드리뷰 보완](authorization-review-remediation.md)
- [부서 전용 자동 접근 정책](department-only-access-policy.md)
- [개발 로그인 소속 처리](dev-login-affiliation.md)
- [외부 사용량 API 접속현황 연동](external-usage-api-access-stats.md)
- [초기 접근 권한 부여와 Line Dashboard 알림 권한 완화](initial-access-and-line-dashboard-permissions.md)
- [수동 외부 앱 접속현황 입력](manual-external-access-stats.md)
- [Scope 기반 접근 권한](portal-access-approval.md)
- [포털 권한 기능 보완](portal-access-hardening.md)
- [Portal 우선 권한 계층 강화](portal-access-hierarchy-hardening.md)
- [포털 권한 관리 운영 UI](portal-access-management.md)
- [Portal Keycloak 전환](portal-keycloak-transition.md)
- [Portal 역할 기반 앱 접근](portal-role-only-access.md)

</details>

## AI·대화·RAG

Assistant, ChatWidget, 앱 배경지식과 대화 저장·복구 기록입니다. 현재 기능은 [Assistant 안내](../../modules/assistant.md)를 확인합니다.

<details>
<summary>기록 31개 펼치기</summary>

- [Chat Widget 전면 개선](assistant-chat-widget-hardening.md)
- [ChatWidget 코드리뷰 결함 수정](assistant-chatwidget-code-review-fixes.md)
- [ChatWidget 대화방 지연 생성](assistant-chatwidget-lazy-room-creation.md)
- [ChatWidget 생명주기와 스크롤 개선](assistant-chatwidget-lifecycle-and-scroll-fixes.md)
- [ChatWidget 대화방 사이드바 너비 조절](assistant-chatwidget-resizable-sidebar.md)
- [ChatWidget 재리뷰 결함 수정](assistant-chatwidget-second-review-fixes.md)
- [Assistant 사용자별 대화방 영구 저장](assistant-conversation-persistence.md)
- [Assistant 현재 앱 지식 토글 복원](assistant-current-app-knowledge-toggle.md)
- [Assistant 영문 업무 용어 보존](assistant-domain-terminology-preservation.md)
- [Assistant frontend 유지보수성 개선](assistant-frontend-maintainability.md)
- [포털 홈 ChatWidget 안내 문구 반복 표시](assistant-home-attention-tooltip.md)
- [Assistant 최신 리뷰 수정](assistant-latest-review-fixes.md)
- [Assistant 이력 로딩과 답변 생성 상태 분리](assistant-loading-state-separation.md)
- [Assistant 초기 마이그레이션 통합](assistant-migration-consolidation.md)
- [Assistant·Observer 우선 결함 수정](assistant-observer-critical-fixes.md)
- [Assistant OpenWebUI 1차 기능 보강](assistant-openwebui-phase-one.md)
- [OpenWebUI 대화방 제목 자동 생성](assistant-openwebui-room-title.md)
- [화면별 Assistant OpenWebUI 전환](assistant-openwebui-routing.md)
- [Assistant 대화·runtime·UI 단일화](assistant-refactor.md)
- [Assistant 신뢰성 보강](assistant-reliability-hardening.md)
- [Assistant 추가 리뷰 후속 수정](assistant-review-followup-fixes.md)
- [Assistant 대화방 다중 삭제](assistant-room-bulk-delete.md)
- [Assistant 대화방 전환 스크롤 고정](assistant-room-scroll-position.md)
- [Assistant 실행 구조 v2](assistant-runtime-v2.md)
- [ChatWidget Appstore·ESOP 배경지식 연결](chatwidget-appstore-esop-context.md)
- [ChatWidget 동시성 및 복구 안정화](chatwidget-concurrency-recovery.md)
- [ChatWidget 앱 배경지식 선택 모드](chatwidget-context-mode.md)
- [ChatWidget 방 단위 공유 기억](chatwidget-shared-room-memory.md)
- [ESOP Dashboard Assistant 배경지식 전달 복구](esop-dashboard-assistant-context.md)
- [Portal Assistant 앱 컨텍스트 통합](portal-assistant-app-context.md)
- [RAG 공통 Adapter 단일화](rag-common-adapter-refactor.md)

</details>

## 메일·앱 목록·공통 화면

메일, AppStore, VOC, 홈 화면과 공통 처리의 변경 기록입니다. 현재 기능은 [기능별 안내](../../modules/README.md)에서 찾습니다.

<details>
<summary>기록 13개 펼치기</summary>

- [AppStore 커버 미리보기 안정화](appstore-cover-preview-stability.md)
- [Appstore 앱 노출 순서 관리](appstore-display-order.md)
- [Appstore 개발용 더미 데이터](appstore-dummy-data.md)
- [AppStore 책임·payload 단일화](appstore-refactor.md)
- [메일 제목 제외 wildcard 지원](email-excluded-subject-wildcard.md)
- [Email OpenWebUI 구조화 응답 호환성](email-openwebui-structured-reply.md)
- [Email RAG OpenWebUI 전환](email-rag-openwebui.md)
- [메일함 소속 옵션 기준 정리](emails-affiliation-options.md)
- [Emails 수집·mailbox·OCR·Outbox/RAG 단일화](emails-refactor.md)
- [홈 화면의 이전 코드 정리](home-legacy-cleanup.md)
- [Home·Portal Shell orchestration 정리](home-portal-shell-refactor.md)
- [Platform Common·Health·Errors 단일화](platform-common-health-errors-refactor.md)
- [VOC canonical 계약 축소](voc-refactor.md)

</details>

## Observer

로그 조회, 타임라인, 분석 근거와 성능 개선 기록입니다. 현재 동작은 [Observer 안내](../../modules/observer.md)를 확인합니다.

<details>
<summary>기록 17개 펼치기</summary>

- [Observer ChatWidget 분석 기간 정합화](observer-chatwidget-analysis-range.md)
- [Observer 기준정보를 기본 DB로 통합](observer-default-db-reference-data.md)
- [Observer의 Drone 대상 Line 기준 통일](observer-drone-target-line.md)
- [Observer ESOP EQP·챔버 lookup 복구](observer-esop-eqp-chamber-lookup.md)
- [Observer ESOP 명칭 통일](observer-esop-logtype.md)
- [Observer AI 근거 로그 이동](observer-evidence-navigation.md)
- [Observer 근거 query 수명주기](observer-evidence-query-lifecycle.md)
- [Observer SPC·FDC Interlock 타임라인](observer-interlock-timelines.md)
- [Observer 대용량 데이터 안정화](observer-large-data-stability.md)
- [Observer 로그 조회 기간 슬라이더](observer-log-range-slider.md)
- [Observer 조회 인덱스 최적화](observer-lookup-index-optimization.md)
- [Observer OpenWebUI 종합 분석](observer-openwebui-analysis.md)
- [Observer OpenWebUI 스트리밍](observer-openwebui-streaming.md)
- [Observer의 Radix 색상 적용](observer-radix-color-scale.md)
- [Observer 조회·pagination·Assistant 연결 단일화](observer-refactor.md)
- [Observer 도메인 명칭 통일](observer-rename.md)
- [Observer Asia/Seoul 시간 기준 통일](observer-seoul-timezone.md)

</details>

## Spider

L0·L3·PM·TTTM Spider와 허브 화면의 변경 기록입니다. 현재 기능과 API는 [기능별 안내](../../modules/README.md)와 [API 안내](../../api/README.md)에서 찾습니다.

<details>
<summary>기록 36개 펼치기</summary>

- [Defect Spider 링크 추가](defect-spider-link.md)
- [L0 Spider 화면 구성](fdc-trend-ui.md)
- [L0 Spider 명칭 변경](l0-spider-scope-rename.md)
- [L3 Spider 개발환경 Mock 인덱스](l3-spider-dev-mock-index.md)
- [L3 Spider 개발자 옵션 권한](l3-spider-developer-permission.md)
- [L3 Spider 제외 필터 Bin OR와 빈 선택 트리 제거](l3-spider-exclusion-bin-or-tree-pruning.md)
- [L3 Spider 설명서 이미지](l3-spider-guide-assets.md)
- [L3 Spider 페이지 설명서 갱신](l3-spider-guide-refresh.md)
- [L3 Spider Line Name 규칙 CSV 가져오기](l3-spider-line-name-rule-import-command.md)
- [L3 Spider Line Name 분석 Step 집계](l3-spider-line-name-run-stats.md)
- [L3 Spider 메일 Deep Link 상위 선택 복원](l3-spider-mail-deep-link-selection.md)
- [L3 Spider 메일링 설정](l3-spider-mailing-settings.md)
- [L3 Spider 인덱스 테이블 Django 관리 전환](l3-spider-managed-index-tables.md)
- [L3 Spider Meta 단일 집계 조회](l3-spider-meta-single-scan.md)
- [L3 Spider 정상 분석 조합 세부 요약](l3-spider-normal-detail-rows.md)
- [L3 Spider PostgreSQL 전용 전환](l3-spider-postgres-cutover.md)
- [L3 Spider 미사용 설비 랭킹 제거](l3-spider-remove-equipment-ranking.md)
- [L3 Spider 조회 책임 분리](l3-spider-selector-boundary.md)
- [L3 Spider SQLite/PostgreSQL 벤치마크](l3-spider-sqlite-postgres-benchmark.md)
- [L3 Spider 미매핑 line rule 진단](l3-spider-unmapped-line-rules.md)
- [L3 Spider 사용자 설명서](l3-spider-user-guide.md)
- [L3 Spider Wafer 연계 이력 모니터링](l3-spider-wafer-correlation-monitoring.md)
- [L3 Spider y5 브랜치 main 병합](l3-spider-y5-main-merge.md)
- [L3 Spider 이식](l3-spider.md)
- [PM SPIDER 대시보드](pm-comparison-dashboard.md)
- [PM Spider 차트 성능 개선](pm-spider-chart-performance.md)
- [PM SPIDER 데이터 마운트 경로 변경](pm-spider-data-mount.md)
- [PM Spider 기능 명칭 변경](pm-spider-feature-rename.md)
- [PM Spider OES 상세 조회 지연 개선](pm-spider-oes-detail-latency.md)
- [PM Spider OES 원본 메타데이터](pm-spider-oes-raw-metadata.md)
- [PM SPIDER 성능 개선](pm-spider-performance.md)
- [Spider 허브 feature boundary 정리](spider-hub-feature-boundary.md)
- [TTTM Spider 화면 임베드](tttm-spider-embed.md)
- [TTTM Spider 환경 변수 정리](tttm-spider-env-cleanup.md)
- [TTTM Spider HTTPS 프록시](tttm-spider-https-proxy.md)
- [TTTM Spider y5 브랜치 main 병합](tttm-spider-y5-main-merge.md)

</details>

## ESOP·Drone 알림·TIP

대시보드, 알림 대상·수신자·템플릿과 TIP 조회 기록입니다. 현재 동작은 [Line Dashboard 안내](../../modules/line-dashboard.md)를 확인합니다.

<details>
<summary>기록 23개 펼치기</summary>

- [알림 대상 매핑 삭제](delete-notification-target-mapping.md)
- [Drone Jira SSL 검증 비활성화](disable-drone-jira-ssl-verification.md)
- [Drone 대상 CSV 초기 데이터](drone-csv-target-seed.md)
- [Drone CTTTM URL 저장](drone-ctttm-url-persist.md)
- [Drone 대상 JSON 초기 데이터](drone-json-target-seed.md)
- [Drone 메일 템플릿 독립화](drone-mail-template-independence.md)
- [Drone 수신자 부서 선택](drone-recipient-department-picker.md)
- [Drone 수신자 저장 흐름](drone-recipient-joined-external-save.md)
- [Drone SOP 코멘트 없는 자동 예약](drone-sop-commentless-reservation.md)
- [Drone 대상 관리 화면](drone-target-admin-page.md)
- [Drone 대상 드롭다운 선택지](drone-target-dropdown-options.md)
- [Drone 대상의 데이터 원본 통일](drone-target-source-of-truth.md)
- [ESOP 변경 유형 범례](esop-change-type-legend.md)
- [ESOP 수신자 포커스 상태](esop-recipient-focus-state.md)
- [ESOP 테이블 새로고침 안정화](esop-table-refresh-stability.md)
- [Inform 완료 단계](inform-completion-step.md)
- [Line Dashboard·Drone 상태 모델 단순화](line-dashboard-drone-refactor.md)
- [Line Dashboard 새로고침 애니메이션](line-dashboard-refresh-animations.md)
- [알림 템플릿 선택](notification-template-selection.md)
- [TIP 상태의 Drone 선택지](tip-status-drone-options.md)
- [TIP 상태 드롭다운 조회 인덱스](tip-status-dropdown-query-index.md)
- [TIP 상태의 Line·SDWT 선택지](tip-status-line-sdwt-options.md)
- [TKIN Prevent 대시보드](tkin-prevent-dashboard.md)

</details>

## 데이터 적재·테이블

파일 적재, 테이블별 구조와 조회 기준 데이터의 변경 기록입니다. 현재 기능은 [Data Movement 안내](../../modules/data-movement.md)를 확인합니다.

<details>
<summary>기록 30개 펼치기</summary>

- [공정 코멘트 LLM 요약 컬럼](ct-process-comment-llm-summary.md)
- [공정 코멘트 OpenWebUI 일괄 요약](ct-process-comment-openwebui-summary.md)
- [공정 코멘트 요약 DAG 분리](ct-process-comment-summary-dag-split.md)
- [공정 코멘트 요약 형식](ct-process-comment-summary-format.md)
- [공정 코멘트 요약 재시도 제한](ct-process-comment-summary-retry-limit.md)
- [공정 코멘트 갱신 플래그](ct-process-comment-update-flag.md)
- [CTTTM 순차 요약 스트리밍](ctttm-sequential-summary-streaming.md)
- [Data Movement Airflow DAG 구성](data-movement-airflow-dag.md)
- [Data Movement 공통 적재 규약 표준화](data-movement-common-refactor.md)
- [Data Movement `ct_process_comment` 구조 정리](data-movement-ct-process-comment-refactor.md)
- [Data Movement `ctttm_workorder_list` 구조 정리](data-movement-ctttm-workorder-list-refactor.md)
- [Data Movement `eqp_status_chg` 구조 정리](data-movement-eqp-status-chg-refactor.md)
- [Data Movement 파일 readiness 가드](data-movement-file-readiness.md)
- [Data Movement FTP Compose 구성](data-movement-ftp-compose.md)
- [Data Movement `m_interlock` 구조 정리](data-movement-m-interlock-refactor.md)
- [Data Movement m_interlock 적재](data-movement-m-interlock.md)
- [Data Movement `m_tkin_prevent` 구조 정리](data-movement-m-tkin-prevent-refactor.md)
- [Data Movement m_tkin_prevent 적재](data-movement-m-tkin-prevent.md)
- [Data Movement `mes_line_mapping_info` 구조 정리](data-movement-mes-line-mapping-info-refactor.md)
- [Data Movement `mi_tip_update_hist` 구조 정리](data-movement-mi-tip-update-hist-refactor.md)
- [Data Movement·Observer 인덱스 최적화](data-movement-observer-index-optimization.md)
- [Data Movement `racb_list` 구조 정리](data-movement-racb-list-refactor.md)
- [Data Movement `station_master` 구조 정리](data-movement-station-master-refactor.md)
- [eqp_status_chg 디렉터리명 변경](eqp-status-chg-dir-rename.md)
- [eqp_status_chg timeline 전환](eqp-status-chg-timeline.md)
- [mes_line_mapping_info 파일 적재](mes-line-mapping-info-load.md)
- [MI TIP update history 내부 테이블 전환](mi-tip-update-hist.md)
- [racb_list timeline 전환](racb-list-timeline.md)
- [Station Master 추가 컬럼 반영](station-master-extra-columns.md)
- [station_master 파일 적재](station-master-load.md)

</details>

## Airflow

DAG, 이미지, 실행 제한과 SSO·배포 연동 기록입니다. 현재 사용법은 [Airflow 소스 안내](../../../apps/airflow/README.md)와 [배포 안내](../../../deploy/airflow/README.md)를 확인합니다.

<details>
<summary>기록 11개 펼치기</summary>

- [Airflow backend proxy 전환](airflow-backend-proxy.md)
- [Airflow BigDataQuery pip 호환성](airflow-bigdataquery-pip-compat.md)
- [Airflow Compose 공통화](airflow-compose-consolidation.md)
- [Airflow DAG 동시성 제한](airflow-dag-concurrency-limits.md)
- [Airflow 단계별 배포 문서](airflow-deployment-guides.md)
- [Airflow 사내 설정 Kubernetes 이관 정합성](airflow-internal-k8s-parity.md)
- [Airflow–Keycloak 로그인 연동](airflow-keycloak-sso.md)
- [Airflow 단순 실패 알림](airflow-simple-failure-alert.md)
- [Airflow 단일 서버 Helm 배포](airflow-single-server-helm.md)
- [Airflow code-server 제거](remove-airflow-code-server.md)
- [Airflow task 동시 실행 제한 제거](remove-airflow-pool-limits.md)

</details>

## Keycloak·Headlamp

인증 서버, claim·그룹·프로필과 Kubernetes 관리 화면의 변경 기록입니다. 현재 절차는 [Keycloak 안내](../../../deploy/keycloak/README.md)와 [Headlamp 안내](../../../deploy/headlamp/README.md)를 확인합니다.

<details>
<summary>기록 36개 펼치기</summary>

- [Keycloak mapper realm 옵션 교정](fix-keycloak-mapper-realm-option.md)
- [Keycloak 식별 속성 보호와 운영 라우팅 수정](fix-keycloak-production-routing.md)
- [Headlamp 관리자 그룹 전환](headlamp-admin-group.md)
- [Headlamp APP VIP HTTPS 연결](headlamp-app-vip.md)
- [Headlamp 최초 설치 가이드 보강](headlamp-first-install-guide.md)
- [현재 Keycloak과 Headlamp 로그인 연결](headlamp-keycloak-login.md)
- [Headlamp Keycloak 로그인](headlamp-keycloak.md)
- [서버 Headlamp 추가](headlamp-server.md)
- [Headlamp 최초 설치 안내 정리](headlamp-setup-guides.md)
- [사내 Keycloak·PostgreSQL 스택](internal-keycloak-stack.md)
- [account_user 기준 Keycloak 프로필](keycloak-account-user-profile.md)
- [Keycloak 실제 소속 속성 추가](keycloak-affiliation-claims.md)
- [기존 Keycloak과 Airflow 서버 기동](keycloak-airflow-server-start.md)
- [Keycloak 사내 claim 저장 이름 통일](keycloak-claim-storage.md)
- [Keycloak 사내 OIDC 공통 claim 계약](keycloak-corporate-claim-contract.md)
- [CP1 사용자 속성 관리 도구](keycloak-cp1-profile-tool.md)
- [Keycloak 배포 파일 전체 점검](keycloak-deployment-audit.md)
- [Keycloak discovery 실행 경로 재점검](keycloak-discovery-audit.md)
- [Keycloak discovery 초기 설정](keycloak-discovery-setup.md)
- [Keycloak 운영 문서 소유 위치 정리](keycloak-doc-ownership.md)
- [Keycloak 설명 문서 체계화](keycloak-docs-organization.md)
- [EPID를 Keycloak username으로 사용](keycloak-epid-username.md)
- [Keycloak 최초 설치 안내 통합](keycloak-first-install-guides.md)
- [Keycloak Kubernetes 역할별 파일 정리](keycloak-k8s-role-folders.md)
- [Keycloak 전달 YAML의 운영 Traefik 구성 유지](keycloak-operating-traefik.md)
- [Keycloak 조직·앱 권한 통합](keycloak-organization-authorization.md)
- [Keycloak 중복 avatarid 제거](keycloak-remove-avatarid.md)
- [삭제한 직급 매핑 복원](keycloak-restore-grade.md)
- [Keycloak 성·이름 중복 필드 정리](keycloak-retire-first-last-name.md)
- [SDWT 하위 그룹 기반 공통 권한](keycloak-sdwt-group-authorization.md)
- [Keycloak 본인 프로필 조회 허용](keycloak-self-profile-read.md)
- [Keycloak 단계별 실행 파일](keycloak-separate-steps.md)
- [Keycloak 서버 입력 폴더](keycloak-server-input-folders.md)
- [Keycloak 기본 성·이름 필드 사용](keycloak-standard-name-fields.md)
- [Keycloak 단독 배포 라우팅 복원](restore-keycloak-standalone-routing.md)
- [Keycloak 배포 파일 단순화](simplify-keycloak-deployment.md)

</details>

## 서버 배포·공통 인프라

Kubernetes, Ingress, 인증서, 저장소 선택과 설치형 제품 배포 기록입니다. 현재 절차는 [서버 배포 안내](../../../deploy/README.md)를 확인합니다.

<details>
<summary>기록 29개 펼치기</summary>

- [앱별 Kubernetes 배포 진입점](app-specific-k8s-entrypoints.md)
- [APP VIP의 두 Worker 443 연결](app-vip-worker-ingress.md)
- [도메인별 인증서 파일명 통일](certificate-common-filenames.md)
- [사이트별 인증서 폴더](certificate-site-folders.md)
- [deploy 잔재 정리와 운영 기본값 검증](deploy-cleanup-production-defaults.md)
- [deploy 전반 점검](deploy-comprehensive-review.md)
- [deploy 독립 운영과 Portal 후속 배포](deploy-independent-platform.md)
- [운영 일반 설정과 비밀값 분리](deploy-public-env-secrets.md)
- [배포 검토 후속 정정](deploy-review-corrections.md)
- [추가 deploy 리뷰 4건 수정](deploy-review-recovery-and-routing.md)
- [deploy 코드 리뷰 7건 수정](deploy-review-seven-fixes.md)
- [실제 배포 env 파일 저장](deploy-runtime-env-files.md)
- [배포 env 단일 파일 관리](deploy-unified-env.md)
- [배포 사전 검사와 초기화 오류 수정](deployment-preflight-fixes.md)
- [추가 배포 리뷰 후속 수정](deployment-review-followups.md)
- [FTP 배포 절차](ftp-deployment-workflow.md)
- [서버별 FTP Kubernetes 배포](ftp-node-daemonset.md)
- [운영 Ingress 명칭 통일](ingress-guide-names.md)
- [사내 Docker 이미지 저장소](internal-docker-registry.md)
- [사내 Kubernetes 입문·구축·배포 가이드](kubernetes-beginner-guide.md)
- [Kubernetes 가이드 간결화](kubernetes-guide-simplify.md)
- [MinIO 콘솔 하위 경로 공개](minio-console-path.md)
- [Kubernetes 전용 Monitoring](monitoring-kube-prometheus-stack.md)
- [모니터링 구성](monitoring-stack.md)
- [Portal 선택 checkout의 로그인 등록 명령 수정](portal-client-checkout-fix.md)
- [Portal 운영 환경을 Kubernetes prod로 통합](portal-k8s-prod.md)
- [서버 선택 전환 시 백업 파일 보존](server-checkout-backup-guard.md)
- [사내 Kubernetes 전용 정책](server-kubernetes-only.md)
- [서버 profile 환경변수 통합](server-profile-env-consolidation.md)

</details>

## 저장소·로컬 환경·환경 변수

소스·설정 소유 위치, 로컬 실행과 환경 변수 구성의 변경 기록입니다. 현재 구조는 [프로젝트 안내](../../../README.md), 실행은 [로컬 환경 안내](../../../local/README.md)를 확인합니다.

<details>
<summary>기록 30개 펼치기</summary>

- [앱별 배포·환경설정 통합](app-owned-deployment-layout.md)
- [앱 소유 환경설정과 Keycloak 설정 작업 분리](app-owned-environment.md)
- [앱별 소스·배포 구조 정리](app-source-deployment-layout.md)
- [Argo CD 준비형 profile 독립 env 계약](argo-ready-env-contract.md)
- [Compose 실행 진입점 단순화](compose-entrypoint-simplification.md)
- [profile env 단일 파일 통합](consolidate-profile-env-files.md)
- [핵심 Feature 호환성 유지 리팩토링](core-feature-refactor.md)
- [대시보드 DB 초기화](dashboard-db-reset.md)
- [개발 초기 데이터 자동 갱신](dev-auto-seed-refresh.md)
- [환경변수 카테고리 재분류](env-category-reclassification.md)
- [환경 변수·Compose 정리](env-compose-cleanup.md)
- [기능 간 독립성 정리](feature-independence-cleanup.md)
- [최상위 관리 폴더 다섯 개로 정리](five-root-folders.md)
- [Kubernetes 전환 후 인프라 정리](k8s-infrastructure-cleanup.md)
- [로컬 Kubernetes·Keycloak 전환](k8s-keycloak-local-migration.md)
- [Kubernetes 배포 파일을 서비스별로 정리](k8s-service-layout.md)
- [Kubernetes 기준 저장소 구조 정리](kubernetes-repository-cleanup.md)
- [폴더 구조 점검 후속 개선](layout-review-followup.md)
- [운영 legacy runtime 계약 정리](legacy-runtime-contract-cleanup.md)
- [로컬 전체 앱 Kubernetes 전환](local-all-apps-k8s.md)
- [로컬 개발과 사내 배포 분리](local-server-separation.md)
- [Portal 환경파일 가독성 정리](portal-env-readability.md)
- [로컬 Portal 실행 복구](portal-local-recovery.md)
- [profile env 카테고리 정리](profile-env-category-formatting.md)
- [env 기능 카테고리 재정렬](reorder-functional-env-categories.md)
- [저장소 Feature 아키텍처 유지보수성 강화 프로그램](repository-feature-refactor-program.md)
- [비-Spider Feature 선설계·순차 리팩토링 프로그램](repository-refactor-master-2026-08.md)
- [루트 실행·의존성 파일 정리](root-entrypoint-cleanup.md)
- [최종 Shared·Infra 정리](shared-infra-final-cleanup.md)
- [Web 공통 환경 변수](web-common-env.md)

</details>

## 에이전트·문서·검사·Git

에이전트 지침, 문서 정리, 저장소 감사와 병합 작업 기록입니다. 현재 작업 방식은 [에이전트 문서 안내](../README.md)를 확인합니다.

<details>
<summary>기록 18개 펼치기</summary>

- [에이전트 기능 경계 검사](agent-boundary-guardrails.md)
- [감사 기준선 복구](audit-baseline-recovery.md)
- [브랜치 병합 절차](branch-merge-routine.md)
- [현재 워크트리 main 반영](current-worktree-main-push.md)
- [배포 문서 목적별 정리](deploy-documentation-organization.md)
- [배포 문서 가독성 개선](deploy-markdown-readability.md)
- [환경 실행 문서 정리](env-command-docs.md)
- [앱 전체 문서 상세화](full-app-docs-overhaul.md)
- [현재 변경 전체 검증과 main 푸시](main-all-changes-push.md)
- [Markdown 가독성과 문서 탐색 체계 정리](markdown-readability-and-navigation.md)
- [저장소 Markdown 정합성 정리](markdown-repository-audit.md)
- [y5 브랜치 main 병합](merge-y5-into-main.md)
- [Portal 중심 에이전트 작업 범위](portal-agent-scope.md)
- [PR 16 main 병합 수정](pr-16-main-merge-fix.md)
- [Web 의존성 보안 감사 후속 수정](web-audit-remediation.md)
- [워크트리 리뷰 회귀 수정](worktree-review-regression-fixes.md)
- [y5 브랜치 main 병합](y5-main-merge.md)
- [y5 브랜치 병합](y5-merge.md)

</details>

## 목록 유지 방법

새 계획은 [작성 규칙](../PLANS.md)에 따라 같은 폴더에 만들고 해당 주제의 목록에 연결합니다.
기존 기록을 다른 주제로 옮길 때는 목록의 링크만 옮깁니다. 기록 본문과 파일 경로는 변경 근거가 있을 때만 수정합니다.
새 기록을 추가하거나 링크를 옮기면 위 표와 접기 목록의 기록 수도 함께 맞춥니다.
