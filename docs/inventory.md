# 앱 인벤토리

이 문서는 실제 코드 경로를 기준으로 앱의 route, model, command, env 계약을 한 곳에 모은 색인입니다. 상세 설명은 각 주제 문서와 모듈 문서를 봅니다.

## 백엔드 API route

모든 업무 API는 `apps/api/api/urls.py`에서 `/api/v1/` 아래로 include됩니다. Auth callback만 `apps/api/api/auth/callback_urls.py`를 통해 `/auth/keycloak/callback/`을 사용합니다.

| 모듈 | Prefix | 실제 라우팅 파일 | 주요 endpoint |
| --- | --- | --- | --- |
| Auth | `/api/v1/auth/` | `apps/api/api/auth/urls.py` | `login`, `logout`, `me`, `config`, empty redirect |
| Account | `/api/v1/account/` | `apps/api/api/account/urls.py` | 읽기 전용 `users`, `line-sdwt-options` |
| Emails | `/api/v1/emails/` | `apps/api/api/emails/urls.py` | `inbox/`, `sent/`, `mailboxes/`, `mailboxes/summary/`, `mailboxes/members/`, `unassigned/`, `unassigned/claim/`, `ingest/`, `outbox/process/`, `assets/ocr/claim/`, `assets/ocr/update/`, `bulk-delete/`, `move/`, `<email_id>/`, `<email_id>/assets/<sequence>/`, `<email_id>/html/` |
| Data Movement | `/api/v1/data-movement/` | `apps/api/api/data_movement/urls.py` | `<table_name>/load/` |
| Assistant | `/api/v1/assistant/` | `apps/api/api/assistant/urls.py` | `turns/stream`, `rag-indexes`, `conversations`, `conversations/<uuid>`, `conversations/<uuid>/messages`, `conversations/<uuid>/generate-title` |
| Line Dashboard / Drone | `/api/v1/line-dashboard/` | `apps/api/api/drone/urls.py` | `early-inform`, `tables`, `tables/update`, `jira-keys`, `notification-targets`, `notification-target-mappings`, `jira-user-sdwt-prods`, `notification-recipients`, `notification-recipient-permissions`, `my-notification-recipient-targets`, `admin/drone-targets`, `history`, `line-ids`, `line-sdwt-options`, `sop/<sop_id>/instant-inform`, `sop/<sop_id>/retry-channel`, `sop/ingest/pop3/trigger`, `sop/precheck`, `sop/trigger` |
| L3 Spider | `/api/v1/l3_spider/` | `apps/api/api/l3_spider/urls.py` | `meta`, `developer/unmapped-line-rules`, `structure`, `stats`, `summary`, `daily-summary`, `data`, `filter-candidates`, `exclusion-filters`, `exclusion-filters/<pk>`, `mail-rules`, `mail-rules/<pk>`, `mail-rules/<pk>/permissions`, `mail-rules/<pk>/test-send`, `mail-rules/trigger` |
| L0 Spider | `/api/v1/l0_spider/` (`/api/v1/fdc-trend/` 호환) | `apps/api/api/l0_spider/urls.py` | `hard-spec/meta`, `hard-spec/recommendations` |
| PM SPIDER | `/api/v1/pm_spider/` | `apps/api/api/pm_comparison/urls.py` | `meta`, `compare` |
| TTTM Spider | `/api/v1/tttm_spider/` | `apps/api/api/tttm_spider/urls.py` | `combo/options`, `combo/types`, `combo/data-types`, `targets/eqps`, `targets/chambers`, `targets/lotwf`, `targets/golden`, `targets/result-status`, `dashboard/data`, `sensor-trace` |
| Observer | `/api/v1/observer/` | `apps/api/api/observer/urls.py` | `lines`, `sdwts`, `prc-groups`, `equipments`, `equipment-info/<line_id>/<eqp_id>`, `equipment-info/<eqp_id>`, `logs`, `logs/page`, `logs/<log_type>/page`, `logs/<log_type>/detail`, `logs/eqp`, `logs/tip`, `logs/spc-interlock`, `logs/fdc-interlock`, `logs/ctttm`, `logs/racb`, `logs/esop`, `tkin-prevent/prc-groups`, `tkin-prevent/processes`, `tkin-prevent/step-seqs`, `tkin-prevent/matrix` |
| Work Hub | `/api/v1/work-hub/`, `/auth/grist/` | `apps/api/api/work_hub/urls.py`, `callback_urls.py` | `context`, `webhooks/grist`, `login`, `verify` |
| AppStore | `/api/v1/appstore/` | `apps/api/api/appstore/urls.py` | `apps`, `apps/order`, `apps/<app_id>`, `apps/<app_id>/cover`, `apps/<app_id>/like`, `apps/<app_id>/view`, `apps/<app_id>/comments`, `apps/<app_id>/comments/<comment_id>`, `apps/<app_id>/comments/<comment_id>/like` |
| VOC | `/api/v1/voc/` | `apps/api/api/voc/urls.py` | `posts`, `posts/<post_id>`, `posts/<post_id>/replies` |
| Activity | `/api/v1/activity/` | `apps/api/api/activity/urls.py` | `logs`, `app-access`, `app-access-stats`, `app-access-sync-external` |
| Health | `/api/v1/health/` | `apps/api/api/health/urls.py` | empty path |

## 프론트엔드 route

전역 route 조립은 `apps/web/src/routes/router.jsx`가 담당하고, 각 feature는 `apps/web/src/features/<feature>/routes.jsx`에서 route 배열을 공개합니다.

| Feature | Route | 실제 라우팅 파일 | 공개 facade |
| --- | --- | --- | --- |
| Home | `/` | `apps/web/src/features/home/routes.jsx` | `apps/web/src/features/home/index.js` |
| Auth | `/login` | `apps/web/src/features/auth/routes.jsx` | `apps/web/src/features/auth/index.js` |
| Account | `/settings`, `/settings/account` | `apps/web/src/features/account/routes.jsx` | `apps/web/src/features/account/index.js` |
| Emails | `/emails/inbox`, `/emails/sent`, `/emails/members` | `apps/web/src/features/emails/routes.jsx` | `apps/web/src/features/emails/index.js` |
| Assistant | `/assistant` | `apps/web/src/features/assistant/routes.jsx` | `apps/web/src/features/assistant/index.js` |
| Line Dashboard | `/ESOP_Dashboard`, `/ESOP_Dashboard/status/:lineId`, `/ESOP_Dashboard/tip-status`, `/ESOP_Dashboard/tip-status/:lineId`, `/ESOP_Dashboard/history/:lineId`, `/ESOP_Dashboard/settings/:lineId`, `/ESOP_Dashboard/settings/notification/:lineId`, `/ESOP_Dashboard/settings/recipients/:lineId`, `/ESOP_Dashboard/overview`, `/ESOP_Dashboard/admin/drone-targets` | `apps/web/src/features/line-dashboard/routes.jsx` | `apps/web/src/features/line-dashboard/index.js` |
| L3 Spider | `/l3_spider`, `/spider/l3` | `apps/web/src/features/l3-spider/routes.jsx` | `apps/web/src/features/l3-spider/index.js` |
| PM SPIDER | `/pm_spider` | `apps/web/src/features/pm-spider/routes.jsx` | `apps/web/src/features/pm-spider/index.js` |
| TTTM Spider | `/spider/tttm`, `/tttm_spider` | `apps/web/src/features/tttm-spider/routes.jsx` | `apps/web/src/features/tttm-spider/index.js` |
| Observer | `/observer`, `/observer/:eqpId` | `apps/web/src/features/observer/routes.jsx` | `apps/web/src/features/observer/index.js` |
| Work Hub | `/work-hub` | `apps/web/src/features/work-hub/routes.jsx` | `apps/web/src/features/work-hub/index.js` |
| AppStore | `/appstore` | `apps/web/src/features/appstore/routes.jsx` | `apps/web/src/features/appstore/index.js` |
| VOC | `/voc` | `apps/web/src/features/voc/routes.jsx` | `apps/web/src/features/voc/index.js` |
| Teamstaff | `/teamstaff` | `apps/web/src/features/teamstaff/routes.jsx` | `apps/web/src/features/teamstaff/index.js` |
| Errors | `*` | `apps/web/src/features/errors/routes.jsx` | `apps/web/src/features/errors/index.js` |

제거된 Account 관리 route `/settings/members`, `/settings/permissions`는 Keycloak 관리 콘솔로 대체되며 frontend router에 등록하지 않습니다.

## 주요 DB 모델

| Django app | 모델 |
| --- | --- |
| `api.account` | `User`, `Affiliation`, `UserCurrentAffiliation`, `UserSdwtProdAccess`, `UserScopeAffiliationGrant`, `AccessRole`, `AccessSource`, `AccessScope`, `AccessPolicyRule`, `UserAccess`, `AccessAuditLog`, `UserSdwtProdChange`, `ExternalAffiliationSnapshot` |
| `api.activity` | `ActivityLog`, `ExternalAppAccessDailyStat`, `ExternalAppUsageSyncState` |
| `api.appstore` | `AppStoreApp`, `AppStoreLike`, `AppStoreComment`, `AppStoreCommentLike` |
| `api.drone` | `DroneSOP`, `DroneSopTarget`, `DroneSopTargetChannelConfig`, `DroneSopNeedToSendRule`, `DroneSopTargetMapping`, `DroneSopTargetRecipient`, `DroneSopTargetDispatch`, `DroneSopDelivery`, `DroneEarlyInform` |
| `api.emails` | `Email`, `EmailOutbox`, `EmailAsset` |
| `api.assistant` | `AssistantConversation`, `AssistantConversationSummary`, `AssistantGeneration`, `AssistantContextSnapshot`, `AssistantMessage`, `AssistantMessageFeedback` |
| `api.data_movement.m_tkin_prevent` | `MTkinPrevent`, `MTkinPreventLoadJob` |
| `api.data_movement.ctttm_workorder_list` | `CtttmWorkorderList`, `CtttmWorkorderListLoadJob` |
| `api.data_movement.ct_process_comment` | `CtProcessComment`, `CtProcessCommentLoadJob` |
| `api.data_movement.eqp_status_chg` | `EqpStatusChg`, `EqpStatusChgLoadJob` |
| `api.data_movement.m_interlock` | `MInterlock`, `MInterlockLoadJob` |
| `api.data_movement.mi_tip_update_hist` | `MiTipUpdateHist`, `MiTipUpdateHistLoadJob` |
| `api.data_movement.racb_list` | `RacbList`, `RacbListLoadJob` |
| `api.data_movement.mes_line_mapping_info` | `MesLineMappingInfo`, `MesLineMappingInfoLoadJob` |
| `api.data_movement.station_master` | `StationMaster`, `StationMasterLoadJob` |
| `api.voc` | `VocPost`, `VocReply` |
| `api.work_hub` | `GristDocumentScope`, `GristAccessSyncOutbox`, `GristWebhookReceipt`, `GristTaskLink` |
| `api.l3_spider` | `L3SpiderFileIndex`, `L3SpiderDailyRunStats`, `L3SpiderRunStatus`, `L3SpiderLineNameRule`, `L3SpiderExclusionFilter`, `L3SpiderMailRule`, `L3SpiderMailDelivery`, `L3SpiderMailRulePermission` |
| `api.auth`, `api.rag`, `api.observer`, `api.l0_spider`, `api.pm_comparison`, `api.tttm_spider`, `api.health`, `api.common` | 자체 업무 model 없이 account/common/external DB 또는 외부 API/파일을 사용 |

## Management command

| Command | 위치 | 목적 |
| --- | --- | --- |
| `check_access_permission_integrity` | `apps/api/api/account/management/commands/check_access_permission_integrity.py` | 필수 `--phase` 기준 migration 전·후 접근 권한 정합성 점검 |
| `migrate_legacy_access_to_keycloak` | `apps/api/api/account/management/commands/migrate_legacy_access_to_keycloak.py` | 현재 유효한 기본 소속과 Portal·앱 역할의 dry-run/apply/비교 이관 |
| `audit_keycloak_cutover` | `apps/api/api/account/management/commands/audit_keycloak_cutover.py` | Account 테이블 row count/checksum과 DB backup·realm export·복원 시험 증적 검증 |
| `backfill_assistant_run_access` | `apps/api/api/assistant/management/commands/backfill_assistant_run_access.py` | legacy Assistant Run·메시지·요약·제목의 Profile과 권한 provenance를 batch 분류·보강 |
| `ensure_dev_database` | `apps/api/api/management/commands/ensure_dev_database.py` | dev 환경에서 Django 기본 DB와 필수 PostgreSQL extension 보장 |
| `process_email_outbox` | `apps/api/api/emails/management/commands/process_email_outbox.py` | pending `EmailOutbox`를 RAG insert/delete 호출로 처리 |
| `seed_dev_data` | `apps/api/api/management/commands/seed_dev_data.py` | 로컬 개발용 더미 사용자 보정 및 더미 데이터 통합 refresh |
| `seed_appstore_dummy_data` | `apps/api/api/appstore/management/commands/seed_appstore_dummy_data.py` | 로컬 개발용 Appstore 순서 관리 더미 앱 생성 |
| `seed_dummy_emails` | `apps/api/api/emails/management/commands/seed_dummy_emails.py` | 로컬 개발용 더미 Email 데이터를 생성 |
| `load_m_tkin_prevent` | `apps/api/api/data_movement/m_tkin_prevent/management/commands/load_m_tkin_prevent.py` | `m_tkin_prevent` deflate CSV 파일 적재 |
| `load_ctttm_workorder_list` | `apps/api/api/data_movement/ctttm_workorder_list/management/commands/load_ctttm_workorder_list.py` | `ctttm_workorder_list` deflate CSV 파일 적재 |
| `load_ct_process_comment` | `apps/api/api/data_movement/ct_process_comment/management/commands/load_ct_process_comment.py` | `ct_process_comment` deflate CSV 파일 적재 |
| `summarize_ct_process_comment` | `apps/api/api/data_movement/ct_process_comment/management/commands/summarize_ct_process_comment.py` | `ct_process_comment` OpenWebUI 요약 |
| `load_eqp_status_chg` | `apps/api/api/data_movement/eqp_status_chg/management/commands/load_eqp_status_chg.py` | `eqp_status_chg` deflate CSV 파일 적재 |
| `load_m_interlock` | `apps/api/api/data_movement/m_interlock/management/commands/load_m_interlock.py` | `m_interlock` deflate CSV 파일 interlock_no 기준 upsert |
| `load_mi_tip_update_hist` | `apps/api/api/data_movement/mi_tip_update_hist/management/commands/load_mi_tip_update_hist.py` | `mi_tip_update_hist` deflate CSV 파일 적재 |
| `load_racb_list` | `apps/api/api/data_movement/racb_list/management/commands/load_racb_list.py` | `racb_list` deflate CSV 파일 적재 |
| `load_mes_line_mapping_info` | `apps/api/api/data_movement/mes_line_mapping_info/management/commands/load_mes_line_mapping_info.py` | `mes_line_mapping_info` deflate CSV 파일 전체 교체 적재 |
| `load_station_master` | `apps/api/api/data_movement/station_master/management/commands/load_station_master.py` | `station_master` deflate CSV 파일 전체 교체 적재 |
| `import_l3_spider_line_name_rules` | `apps/api/api/l3_spider/management/commands/import_l3_spider_line_name_rules.py` | L3 Spider line name 규칙 CSV 검증·DB 교체 적재 |
| `seed_drone_dummy_data` | `apps/api/api/drone/management/commands/seed_drone_dummy_data.py` | 로컬 개발용 Drone SOP 더미 데이터를 생성 |
| `seed_drone_targets_from_file` | `apps/api/api/drone/management/commands/seed_drone_targets_from_file.py` | JSON/CSV 기준 Drone SOP/발송 이력/알림 설정 초기화 후 대상/채널/수신자 생성 |
| `prune_drone_sop` | `apps/api/api/drone/management/commands/prune_drone_sop.py` | 보관 기간을 초과한 Drone SOP 데이터 정리 |
| `purge_drone_sop` | `apps/api/api/drone/management/commands/purge_drone_sop.py` | Drone SOP 데이터를 수동 전체 삭제 또는 dry-run 확인 |
| `configure_grist_scope` | `apps/api/api/work_hub/management/commands/configure_grist_scope.py` | 소속과 Grist workspace/document/table ID mapping 등록 및 선택적 Webhook Authorization 출력 |
| `audit_grist_schema` | `apps/api/api/work_hub/management/commands/audit_grist_schema.py` | Equipment/WorkLog/Task column 계약 점검 |
| `sync_grist_equipment` | `apps/api/api/work_hub/management/commands/sync_grist_equipment.py` | Observer 설비를 Grist에 멱등 upsert/archive |
| `sync_grist_access` | `apps/api/api/work_hub/management/commands/sync_grist_access.py` | 비활성 소속을 포함한 Portal 사용자·역할을 Grist document ACL로 전체 동기화 |
| `process_grist_access_sync` | `apps/api/api/work_hub/management/commands/process_grist_access_sync.py` | 전용 worker의 만료 grant 회수, Grist 역할 Outbox 처리, 주기적 전체 ACL 복구와 완료 이력 정리 |
| `seed_grist_demo` | `apps/api/api/work_hub/management/commands/seed_grist_demo.py` | 로컬 Grist demo schema·record·Webhook·mapping 멱등 생성 |

## Env 파일과 설정 그룹

| 파일 | 역할 |
| --- | --- |
| `env/api.common.env` | API 공통 기본값, DB, auth, POP3, Drone, RAG, LLM, Mail API 기본 설정 |
| `env/api.dev.env` | 로컬 Keycloak과 dummy RAG/LLM/Mail/Jira, dev seed 설정 |
| `env/api.oidc.dev.env` | 실제 OIDC 개발 연결용 API 설정 |
| `env/api.prod.env` | 운영 배포용 API 설정 템플릿 |
| `env/airflow.common.env` | Airflow DAG API trigger와 실패 callback 설정 |
| `env/web.dev.env` | 로컬 web 개발 설정 |
| `env/web.oidc.dev.env` | 실제 OIDC 개발 연결용 web 설정 |
| `env/web.prod.env` | 운영 web 설정 템플릿 |
| `env/minio.env` | 로컬 MinIO 계정과 endpoint |
| `env/grist.common.env` | Grist 단일 조직, telemetry, update 정책 공통 설정 |
| `env/grist.remote.env` | 새 Grist 서버 `10.172.117.91`의 공개 주소, port, Portal 검증 URL과 비밀값 없는 runtime 기본값 |
| `env/work-hub.oidc.env` | OIDC(stage) Portal의 원격 Grist URL, 관리자와 기능 설정 |
| `env/work-hub.prod.env` | 운영 Portal의 원격 Grist URL, 관리자와 기능 설정 |

주요 env group은 `DJANGO_*`, `DJANGO_DB_*`, `KEYCLOAK_*`, `OIDC_*`, 전환기 호환용 `ADFS_*`, `DEV_AUTO_AFFILIATION_*`, `DEV_AUTO_SEED`, `DEV_SEED_PREFIX`, `L3_SPIDER_*`, `TTTM_SPIDER_*`, `FDC_HARD_SPEC_*`, `PM_COMPARISON_*`, `DATA_MOVEMENT_*`, `FTP_*`, `AIRFLOW_*`, `AIRFLOW_TRIGGER_TOKEN`, `EMAIL_POP3_*`, `DRONE_*`, `KNOX_MESSENGER_*`, `ASSISTANT_*`, `RAG_*`, `MAIL_API_*`, `MINIO_*`, `GRIST_*`, `WORK_HUB_ENABLED`, `VITE_*`입니다.
