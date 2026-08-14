# Work Hub

## 목적

Work Hub는 `sdwt_prod` 그룹별 설비 Shift 업무일지와 후속 조치 Task를 Grist OSS grid에서 공동편집하는 기능입니다. Portal은 사용자·소속·앱 접근 권한과 Grist 연결 정보만 소유하고, 업무일지와 Task record의 원본은 Grist document에 둡니다.

Grist 소스를 현재 저장소에 vendor하거나 fork하지 않습니다. `gristlabs/grist-oss:1.7.13`을 독립 서비스로 실행해 upstream 교체 범위를 Compose image와 REST adapter로 제한합니다.

운영에서는 기존 Portal 서버와 Grist 서버를 분리합니다. 기존 서버에는 Django API, Account DB, Web, `work-hub-access-worker`를 두고 새 서버 `10.172.117.91`에는 Grist OSS, Grist 전용 Nginx, Grouped View widget, API key initializer만 실행합니다. 두 서버는 Portal forward-auth 검증 API와 Grist REST API로만 통신합니다.

## 시스템 경계

| 영역 | 원본/책임 |
| --- | --- |
| `api.account` | Portal 사용자, 현재 소속, viewer/member/manager, `work-hub` app scope |
| `api.observer` | `station_master` 기반 설비 기준정보 |
| `api.work_hub` | 소속↔Grist document mapping, 접근 권한 Outbox, Webhook 멱등 이력, 설비 투영과 Task 생성 |
| Grist OSS | Equipment projection, WorkLog, Task, 실시간 공동편집과 document history |
| `work-hub` frontend | 허용 그룹을 보여주고 Grist document URL로 이동 |

Portal account가 Grist 인증 identity의 단일 원본입니다. Portal은 안정적인 사용자 PK를 짧은 수명의 ticket으로 서명하고, Nginx 내부 검증이 성공한 account email만 Grist forward-auth header로 전달합니다. Portal 메뉴 권한과 Grist document 권한은 별도 보안 경계입니다. Portal account의 현재 소속, 명시 소속 역할, `work-hub` 앱별 소속 데이터 범위, 사용자·소속 활성 상태를 Grist ACL의 단일 원본으로 사용합니다. `viewer/member/manager`는 각각 Grist `viewers/editors/owners`로 투영되며, 이메일이 등록된 활성 superuser는 모든 활성 document의 `owner`로 투영됩니다. account 변경 signal과 신규 document mapping은 같은 DB transaction에 `GristAccessSyncOutbox`만 적재합니다. 등록된 mapping의 `doc_id`는 이전 document ACL이 관리 범위 밖에 남지 않도록 변경할 수 없습니다. 외부 Grist 호출은 `work-hub-access-worker`가 전담하고 재시도 가능한 ACL·Webhook 오류를 지수 backoff로 재시도합니다. worker는 만료된 앱별 소속 grant를 비활성화해 해당 document ACL을 회수하고, 완료 Outbox와 완료 Webhook receipt는 기본 30일, 실패·terminal Webhook receipt는 기본 90일 보존 후 정리합니다.

## 사용자 흐름

1. `/work-hub`가 `GET /api/v1/work-hub/context`를 호출합니다.
2. 일반 사용자는 현재 소속 document 하나로 이동하고 manager와 superuser는 여러 소속 중 선택합니다.
3. 사용자는 Grist WorkLog grid를 공동편집합니다.
4. `follow_up_required=true`인 WorkLog Webhook을 Django가 받으면 같은 document의 Task를 한 번만 생성하고 양쪽 record를 연결합니다.

iframe을 사용하지 않습니다. Grist public URL, OIDC callback, cookie와 WebSocket origin이 일치하도록 전용 host root에서 엽니다.

## Grist document template

`Affiliation.user_sdwt_prod` 하나당 document 하나를 사용합니다. table과 column ID는 다음 계약을 유지합니다.

| Table | 주요 column |
| --- | --- |
| `Equipment` | `equipment_id`, `line_id`, `sdwt_prod`, `prc_group`, `equipment_name`, `is_active`, `source_updated_at`, `archived` |
| `WorkLog` | `worklog_key`, `work_date`, `shift_code`, `occurred_at`, `equipment`, `sdwt_prod`, `writer`, `symptom`, `cause`, `action`, `result`, `status`, `handover_required`, `follow_up_required`, `task`, `archived` |
| `Task` | `task_key`, `title`, `description`, `source_worklog`, `equipment`, `sdwt_prod`, `assignee`, `status`, `priority`, `due_at`, `resolution`, `reviewer`, `completed_at`, `archived` |

`equipment`, `source_worklog`, `task`는 Grist Ref column입니다. 자동화 키와 `archived`는 삭제 대신 멱등 처리와 논리 보관에 사용합니다.

## 로컬 실행과 더미 데이터

Portal과 Grist를 함께 실행합니다.

```bash
make dev
```

이 명령은 선택 profile뿐 아니라 API·Web·Nginx를 `WORK_HUB_ENABLED=1`, `VITE_WORK_HUB_ENABLED=1`, `GRIST_LOGOUT_ENABLED=1`로 함께 실행합니다. `make dev-up`과 `make dev-work-hub-up`도 같은 통합 실행의 호환 명령입니다. Portal만 실행하려면 세 값을 모두 끄는 `make dev-app-up`을 사용합니다.

기존 Portal이 실행 중이면 Grist만 올릴 수 있습니다.

```bash
make work-hub-up
```

더미 schema, Equipment 3건, WorkLog 3건, Task 2건, Webhook, `DEV_ALPHA` mapping과 document email 권한을 멱등 생성합니다.

```bash
make work-hub-seed
```

Grist는 `http://localhost:8100`의 전용 Nginx proxy에서 열립니다. Grist container의 8484 포트는 host에 직접 공개하지 않고 외부 `X-Forwarded-User`와 `/boot` 요청은 각각 제거·차단합니다. `/auth/login`은 Portal `/auth/grist/login`으로 이동하며 미로그인 상태이면 로컬 dummy ADFS 로그인을 거친 뒤 Grist로 돌아옵니다.

### Grouped View widget

컬럼 값별 레코드를 아코디언으로 접고 펼치는 `Grouped View`를 Grist user plugin으로 함께 제공합니다. `Add New` → `Add Widget to Page` → `Custom`에서 `Grouped View (Work Hub Grouped View)`를 선택하고 대상 table을 연결한 뒤 `Read table` 접근을 승인합니다. 위젯 상단의 `그룹 기준`에서 컬럼을 선택하면 그룹별 접기/펼치기, 그룹 개수 정렬, 색상과 최대 높이를 설정할 수 있습니다.

위젯 소스는 `deploy/grist/plugins/work-hub-grouped-view`에 revision을 고정해 두며 Grist container에는 read-only로 mount합니다. 로컬 widget origin은 `http://localhost:8101`입니다. 새 서버의 초기 운영 origin은 `http://10.172.117.91:8101`이며, DNS와 TLS를 적용할 때 `GRIST_WIDGET_PUBLIC_URL`만 새 origin으로 바꿉니다. Nginx는 등록된 plugin 정적 경로만 공개하고 cookie를 제거하며 CSP로 외부 네트워크 요청을 막습니다. 저장된 그룹 색상은 `#RRGGBB` 형식만 허용하고 DOM style property로 적용합니다.

`seed_grist_demo`, 설비·ACL 동기화 같은 server-to-server 명령은 Portal 관리자 Grist API key를 사용합니다. 로컬 개발에서는 API와 worker가 initializer의 key 파일을 함께 읽습니다. 분리 운영에서는 `grist-api-key-init`이 새 서버의 `${WORK_HUB_SECRET_HOST_PATH}/grist_api_key`에 key를 생성하고, 운영자가 그 값을 기존 Portal 서버의 `GRIST_API_KEY` 배포 비밀값으로 한 번 전달합니다. 두 서버 사이에 key 파일을 공유 mount하지 않으며 실제 key는 저장소 env 파일에 기록하지 않습니다.

로그와 중지는 다음 명령을 사용합니다.

```bash
make work-hub-logs
make work-hub-down
make dev-work-hub-down
```

중지해도 `grist_data` volume은 보존됩니다. `down -v`는 사용하지 않습니다.

## 운영 mapping과 점검

새 Grist 서버에서 session secret을 배포 환경으로 주입하고 먼저 기동합니다. tracked `env/grist.remote.env`에는 비밀값이 없으며, 기본 공개 주소는 `10.172.117.91`입니다.

```bash
GRIST_SESSION_SECRET='<배포 비밀값>' make grist-remote-config
GRIST_SESSION_SECRET='<배포 비밀값>' make grist-remote-up
curl -fsS http://10.172.117.91/status
```

첫 기동 후 새 서버의 `data/work_hub_secrets/remote/grist_api_key` 값을 보안 채널로 기존 Portal 서버의 배포 secret에 `GRIST_API_KEY`로 등록합니다. `make grist-remote-up`은 key 디렉터리를 배포 사용자 권한으로 만들고 initializer에 현재 `id -u`/`id -g`를 전달하므로 key는 해당 사용자 소유 `0600`으로 생성됩니다. 경로나 UID/GID를 바꿀 때만 `GRIST_REMOTE_SECRET_HOST_PATH`, `GRIST_REMOTE_SECRET_UID`, `GRIST_REMOTE_SECRET_GID`를 Make 변수로 재정의합니다. 그 다음 Portal 서버에서 운영은 `make prod-work-hub-up`, OIDC(stage)는 `make oidc-work-hub-up`을 실행합니다. 이 target은 원격 Grist를 새로 띄우지 않고 Portal API, Web, Nginx와 접근 동기화 worker만 활성화합니다. 운영 target은 API와 `VITE_WORK_HUB_ENABLED=1`이 포함된 Web image를 함께 빌드하고, 같은 API image로 DB migration을 적용한 뒤만 서비스를 올립니다.

새 Grist 서버에서 기존 Portal의 `PORTAL_VERIFY_URL`에 접근할 수 있어야 하고, 기존 Portal 서버에서 `http://10.172.117.91`에 접근할 수 있어야 합니다. 방화벽은 사용자망과 Portal 서버에서 Grist의 80/8101 포트로, Grist 서버에서 Portal HTTPS로 필요한 방향만 허용합니다.

이후 Portal 서버에서 다음 점검 명령을 사용합니다.

```bash
COMPOSE_FILE=docker-compose.yml
GRIST_PUBLIC_URL=http://10.172.117.91

docker compose -f "$COMPOSE_FILE" exec -T api python manage.py configure_grist_scope \
  --user-sdwt-prod SDWT-A \
  --workspace-id 1 \
  --doc-id abc123 \
  --equipment-table-id Equipment \
  --worklog-table-id WorkLog \
  --task-table-id Task \
  --launch-url "$GRIST_PUBLIC_URL/o/work-hub/doc/abc123" \
  --show-webhook-authorization

docker compose -f "$COMPOSE_FILE" exec -T api python manage.py audit_grist_schema
docker compose -f "$COMPOSE_FILE" exec -T api python manage.py sync_grist_equipment --all --dry-run
docker compose -f "$COMPOSE_FILE" exec -T api python manage.py sync_grist_access --all --dry-run
docker compose -f "$COMPOSE_FILE" exec -T api python manage.py process_grist_access_sync
```

실제 동기화 시 `--dry-run`을 제거합니다. `audit_grist_schema`는 필수 column의 이름과 type을 함께 검사합니다. 설비 원본에서 사라진 record는 삭제하지 않고 `is_active=false`, `archived=true`로 바꿉니다. Work Hub Django Admin은 mapping과 처리 이력을 조회만 하며, 변경은 검증과 Outbox 적재를 보장하는 management command·service 경로로 수행합니다.

## Portal account SSO

Grist 자체 OIDC client나 외부 boot key 화면은 사용하지 않습니다. Grist OSS의 forward-auth login path만 새 서버 Nginx의 인증 middleware에 연결합니다. Portal `/auth/grist/login`은 Grist public origin을 검증하고 로그인된 사용자 PK를 최대 30초의 Django 서명 ticket으로 반환합니다. 새 서버 Nginx의 내부 `/auth/grist/verify` subrequest가 기존 Portal의 검증 API에서 기능 플래그, ticket 서명·만료, 활성 account, Portal 접근, `work-hub` app 접근을 다시 검사한 뒤 email을 `X-Forwarded-User`로 설정합니다. `WORK_HUB_ENABLED=0`이면 Portal은 새 login과 이미 발급된 ticket을 거부하며, 새 서버도 `make grist-remote-disable`로 본문·widget proxy를 503으로 차단해야 합니다. 일반 proxy 경로에서는 외부가 보낸 같은 header를 항상 제거합니다. Portal logout은 Work Hub가 활성 상태이거나 `GRIST_LOGOUT_ENABLED=1`인 정리 기간에 Grist `/logout`을 먼저 거쳐 Grist session을 제거하고 `grist_cleared=1` marker로 돌아온 뒤 기존 IdP logout을 수행합니다.

Portal 로그인만으로 document 권한을 우회할 수 없습니다. callback은 Portal과 `work-hub` app 승인을 모두 검사하고, Grist는 별도로 동기화된 document ACL을 적용합니다. 전용 worker는 기존 정리 주기(기본 1시간)마다 비활성 소속 mapping까지 포함한 전체 ACL을 Portal desired state로 복구하며, Portal에 없는 Grist 공개 계정도 회수합니다. `WORK_HUB_ENABLED=0`이면 worker는 보존 이력 정리만 유지하고 전체 reconciliation과 Outbox의 Grist 쓰기는 건너뜁니다. 즉시 수동 점검할 때는 `sync_grist_access --all`을 사용합니다. break-glass email은 실제 Portal account와 같은 `GRIST_ADMIN_EMAIL`에 두며, ACL에 없으면 추가되고 Portal 일반 역할과 겹쳐도 항상 명시적 `owner`로 유지됩니다. 해당 계정 외에도 최소 한 명의 운영 owner를 더 유지합니다.

## Webhook

- callback은 `/api/v1/work-hub/webhooks/grist?doc_id=<id>&table_id=WorkLog`입니다.
- `GRIST_WEBHOOK_SECRET`은 서버의 마스터 키이며 Grist document에 직접 입력하지 않습니다.
- `configure_grist_scope --show-webhook-authorization`이 출력한 document·table 전용 Authorization 값을 해당 Webhook에 입력합니다. 이 값은 보안 터미널에서만 출력하고 로그에 남기지 않습니다.
- 동일 payload가 다시 오면 `duplicate=true`를 반환하되 Task를 새로 만들지 않고 기존 Task 참조를 WorkLog에 다시 연결합니다.
- callback은 검증된 payload를 receipt queue에 저장하고 `202 Accepted`로 즉시 끝나며, Task 생성·연결은 worker가 처리합니다.
- 처리 중인 동일 payload나 WorkLog row를 기다리며 DB를 반복 조회하지 않고 기존 작업 유지 또는 지수 backoff 재시도로 전환합니다.
- 로컬 link가 가리키는 Task가 삭제되었으면 원격 `task_key`를 다시 확인하고 없을 때 새 Task로 복구합니다.
- `WORK_HUB_ENABLED=0`이면 Webhook과 worker의 Grist 쓰기를 모두 중단합니다.
- `task_key` 확인은 Grist record filter를 사용해 일치 Task만 조회합니다.
- 개발의 Docker 내부 HTTP callback은 `ALLOWED_WEBHOOK_DOMAINS=*`로 한정 허용합니다.
- OIDC/prod는 공개 HTTPS Portal host 하나만 `GRIST_ALLOWED_WEBHOOK_DOMAINS`에 둡니다.

새 서버의 `GRIST_SESSION_SECRET`과 첫 기동에 발급되는 `GRIST_API_KEY`는 배포 환경으로 주입합니다. Portal의 `GRIST_WEBHOOK_SECRET`과 `GRIST_FORWARD_AUTH_TICKET_SECRET`은 환경별 Work Hub env 값을 사용하며, 운영 환경에서 별도 secret manager가 있으면 같은 이름으로 재정의할 수 있습니다. Grist API key 자체는 tracked env에 기록하지 않습니다.

## 백업과 원복

- Grist 영속 데이터는 새 서버의 `tailwind_grist_remote_data` volume `/persist`에 있습니다.
- 업그레이드 전 volume snapshot을 만들고 별도 환경에서 document, attachment, ACL, Webhook 복원을 확인합니다.
- 분리 운영에서는 Portal 서버의 `*-work-hub-disable`과 새 서버의 `make grist-remote-disable`을 함께 실행해 worker 쓰기와 Grist 본문·widget 접근을 모두 차단합니다. session 정리 기간 뒤 Portal 서버의 `*-work-hub-down`과 새 서버의 `make grist-remote-down`으로 container를 제거합니다.
- `grist-remote-down`은 named volume과 bootstrap key 파일을 삭제하지 않습니다. 서버를 완전히 폐기할 때도 snapshot과 복원 점검 후 명시적으로 해당 데이터만 삭제합니다.
- 실제 서버에는 Work Hub migration이 적용되지 않았으므로, 테스트 전환 과정의 Baserow/APITable table은 생성하지 않고 Grist 초기 schema와 Webhook queue 후속 migration만 적용합니다.
- 이전 Baserow volume `tailwind_baserow_data`는 자동 삭제하지 않으므로 교체 검증 중에도 복구할 수 있습니다.
- Grist image downgrade는 저장 형식 역호환을 가정하지 않고 업그레이드 전 snapshot을 복원합니다.

## 관련 코드

- `apps/api/api/work_hub`
- `apps/api/api/observer/selectors.py`
- `apps/web/src/features/work-hub`
- `compose/dev.work-hub.yml`
- `compose/oidc.work-hub.yml`
- `compose/prod.work-hub.yml`
- `docker-compose.grist.yml`
- `env/grist.remote.env`
- `deploy/grist/bootstrap_api_key.sh`
- `deploy/grist/plugins/work-hub-grouped-view`
- `deploy/grist/nginx.remote.conf`
