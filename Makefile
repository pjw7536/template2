# 로컬 Kubernetes·Compose 검사·서버 배포 실행 진입점입니다.
COMPOSE_TEST=docker compose -f deploy/portal/compose/test.yml
COMPOSE_K8S_CHECK=docker compose --project-name tailwind-k8s-check --env-file local/shared/runtime/db.env -f local/shared/compose/k8s-check.yml
REFERENCE_USERS_CSV ?=
REGISTER_REFERENCE_USERS_APPLY ?= 0

# 값을 shell 코드에 삽입하지 않고 초기 설정 스크립트에 환경변수로 전달합니다.
export KEYCLOAK_SDWTS_CSV KEYCLOAK_USERS_CSV KEYCLOAK_SDWT_CLIENTS KEYCLOAK_SDWT_APPLY KEYCLOAK_SDWT_VALIDATE_ONLY

PROD_WEB_ENV_FILE ?= $(CURDIR)/deploy/portal/env/prod/web.env
PROD_API_ENV_FILE ?= $(CURDIR)/deploy/portal/env/prod/api.env
KIND_BIN ?= $(CURDIR)/.tools/bin/kind
# 앱을 고르는 타깃은 APP을 명시해야 합니다. 기본값을 두면 지정을 잊은 명령이 한 앱을 바꿉니다.
APP ?=
PROFILE ?= prod
MINIO_ENV ?= $(CURDIR)/deploy/minio/env/prod.env
REGISTRY_ENV ?= $(CURDIR)/deploy/registry/env/k8s.env
REGISTRY_PUSH_ENV ?= $(CURDIR)/deploy/registry/env/push-initial.env
COMPONENT ?= server
ENV_APP ?= all
ENV_PROFILE ?= all
KUBE_CONTEXT ?=
KEYCLOAK_ENV ?= $(CURDIR)/deploy/keycloak/env/prod.env
KEYCLOAK_CERTS ?=
AIRFLOW_ENV ?= $(CURDIR)/deploy/airflow/env/k8s.env
AIRFLOW_TLS_SOURCE ?=
VIP_BACKENDS ?=
# 관리 API 도구에 Keycloak env의 관리자 접속 정보를 환경변수로 넘깁니다. KEYCLOAK_ADMIN_URL·USERNAME·PASSWORD 중 하나라도 직접 지정하면 채우지 않습니다.
KEYCLOAK_ADMIN = python3 deploy/keycloak/scripts/admin_env.py --env "$(KEYCLOAK_ENV)" --

.PHONY: dev down env-check env-profile-key-check \
 k8s-tools k8s-render k8s-render-local k8s-render-server k8s-env k8s-up k8s-down k8s-ui server-check \
 test-api check-api makemigrations-check

# 기본 개발 환경은 한 PC의 전체 Kubernetes 앱입니다.
dev: k8s-up

# Portal 없이 deploy의 platform 그룹 전체를 실행하고 검사합니다.
.PHONY: dev-platform k8s-platform-check k8s-platform-smoke k8s-platform-status k8s-platform-rebuild
dev-platform: k8s-tools
	KIND_BIN="$(KIND_BIN)" python3 local/shared/scripts/k8s_platform.py up
k8s-platform-check:
	KIND_BIN="$(KIND_BIN)" python3 local/shared/scripts/k8s_platform.py check
k8s-platform-smoke:
	python3 local/shared/scripts/k8s_platform.py smoke
k8s-platform-status:
	python3 local/shared/scripts/k8s_platform.py status
k8s-platform-rebuild:
	KIND_BIN="$(KIND_BIN)" python3 local/shared/scripts/k8s_platform.py rebuild $(if $(APP),--app "$(APP)")

.PHONY: register-reference-users
register-reference-users:
	@test -f "$(REFERENCE_USERS_CSV)" || { echo 'REFERENCE_USERS_CSV에 참조 CSV 파일 경로를 지정하세요.'; exit 1; }
	$(COMPOSE_K8S_CHECK) run --rm -T -v "$(CURDIR)/apps/portal/api:/app" -v "$(abspath $(REFERENCE_USERS_CSV)):/data/account/reference-users.csv:ro" api register_reference_users /data/account/reference-users.csv $(if $(filter 1,$(REGISTER_REFERENCE_USERS_APPLY)),--apply,)

.PHONY: keycloak-org-sync keycloak-org-test
# 소속 그룹(/org) 트리에 맞춰 소속별 역할(client org)·라인/팀 묶음·토큰 scope를 반영합니다. 기본은 dry-run입니다.
keycloak-org-sync:
	$(KEYCLOAK_ADMIN) python3 deploy/keycloak/scripts/org_sync.py $(if $(filter 1,$(KEYCLOAK_ORG_APPLY)),--apply,)
keycloak-org-test:
	python3 -m unittest discover -s apps/tooling/tests -p 'test_keycloak_org.py'

.PHONY: keycloak-access-apply keycloak-access-test
# 앱 역할 카탈로그(deploy/keycloak/access/catalog.json)를 Keycloak에 반영합니다. 기본은 dry-run입니다.
keycloak-access-apply:
	$(KEYCLOAK_ADMIN) python3 deploy/keycloak/scripts/access_apply.py $(if $(filter 1,$(KEYCLOAK_ACCESS_APPLY)),--apply,)
keycloak-access-test:
	python3 -m unittest discover -s apps/tooling/tests -p 'test_keycloak_access.py'

.PHONY: local-keycloak-dummy
# DUMMY_LINES를 지정하면 전체 라인·인원 규모를 맞춥니다. DUMMY_REMOVE=1이면 더미 사용자만 지웁니다.
local-keycloak-dummy:
	python3 local/keycloak/scripts/seed_org_dummy.py $(if $(filter 1,$(DUMMY_REMOVE)),--remove,$(if $(DUMMY_LINES),--lines $(DUMMY_LINES) --total-users $(or $(DUMMY_TOTAL_USERS),2000),))

# IAM의 이미지와 Keycloak 설정을 개별 실행합니다.
IAM_ENV ?= $(CURDIR)/deploy/iam/env/prod.env
IAM_BUILD_ENV ?= $(CURDIR)/deploy/iam/env/build.env
IDENTITY_ENV ?=
.PHONY: identity-env-prepare iam-image iam-keycloak-setup iam-verify
identity-env-prepare:
	@test -n "$(IDENTITY_ENV)" || { echo 'IDENTITY_ENV에 운영 입력 파일 경로를 지정하세요.' >&2; exit 1; }
	@python3 deploy/iam/scripts/prepare_identity_env.py --identity-env "$(IDENTITY_ENV)" --keycloak-base "$(KEYCLOAK_ENV)" --iam-base "$(IAM_ENV)"
iam-image:
	python3 deploy/iam/scripts/manage.py publish --build-env "$(IAM_BUILD_ENV)" --registry-env "$(REGISTRY_ENV)" --push-env "$(REGISTRY_PUSH_ENV)"
iam-keycloak-setup:
	$(KEYCLOAK_ADMIN) python3 deploy/iam/scripts/setup_keycloak.py --env "$(IAM_ENV)" $(if $(filter 1,$(IAM_KEYCLOAK_APPLY)),--apply)
iam-verify:
	$(KEYCLOAK_ADMIN) python3 deploy/iam/scripts/setup_keycloak.py --env "$(IAM_ENV)" --verify

.PHONY: iam-workload-dev
iam-workload-dev:
	IAM_WORKLOAD_DB="$${IAM_WORKLOAD_DB:-$(CURDIR)/data/iam/workload.sqlite3}" \
	IAM_KEYCLOAK_ISSUER="$${IAM_KEYCLOAK_ISSUER:-http://localhost:8180/realms/portal}" \
	"$${IAM_WORKLOAD_PYTHON:-python3}" apps/iam/api/workload.py

.PHONY: keycloak-sdwt-init keycloak-sdwt-test
keycloak-sdwt-init:
	$(KEYCLOAK_ADMIN) bash ./deploy/keycloak/scripts/05-setup-sdwt.sh

keycloak-sdwt-test:
	python3 -m unittest discover -s apps/tooling/tests -p 'test_keycloak_sdwt.py'

KEYCLOAK_PORTAL_ENV ?=
.PHONY: keycloak-realm-setup keycloak-idp-setup keycloak-profile-setup keycloak-idp-mappers-setup keycloak-portal-client-setup
keycloak-realm-setup:
	bash deploy/keycloak/scripts/00-create-realm.sh --context "$(KUBE_CONTEXT)"
keycloak-idp-setup:
	bash deploy/keycloak/scripts/01-create-idp.sh --context "$(KUBE_CONTEXT)" --env "$(KEYCLOAK_ENV)"
keycloak-profile-setup:
	bash deploy/keycloak/scripts/02-register-user-profile.sh --context "$(KUBE_CONTEXT)"
keycloak-idp-mappers-setup:
	bash deploy/keycloak/scripts/03-sync-idp-mappers.sh --context "$(KUBE_CONTEXT)"
keycloak-portal-client-setup:
	bash deploy/keycloak/scripts/04-setup-portal-client.sh --context "$(KUBE_CONTEXT)" --portal-env "$(if $(KEYCLOAK_PORTAL_ENV),$(KEYCLOAK_PORTAL_ENV),$(PROD_API_ENV_FILE))"

# realm → 사내 IdP → 사용자 프로필 → IdP mapper를 순서대로 실행합니다. 각 단계는 다시 실행해도 같은 결과입니다.
.PHONY: keycloak-setup
keycloak-setup:
ifneq ($(strip $(KEYCLOAK_SDWTS_CSV)$(KEYCLOAK_USERS_CSV)),)
	$(MAKE) keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=1
endif
	python3 deploy/keycloak/scripts/setup_discovery.py check --step idp --context "$(KUBE_CONTEXT)" --env "$(KEYCLOAK_ENV)"
	bash deploy/keycloak/scripts/00-create-realm.sh --context "$(KUBE_CONTEXT)"
	bash deploy/keycloak/scripts/01-create-idp.sh --context "$(KUBE_CONTEXT)" --env "$(KEYCLOAK_ENV)"
	bash deploy/keycloak/scripts/02-register-user-profile.sh --context "$(KUBE_CONTEXT)"
	bash deploy/keycloak/scripts/03-sync-idp-mappers.sh --context "$(KUBE_CONTEXT)"
ifneq ($(strip $(KEYCLOAK_SDWTS_CSV)),)
	$(MAKE) keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0 KEYCLOAK_TARGET_REALM=etch
endif

.PHONY: keycloak-oidc-check keycloak-oidc-setup
keycloak-oidc-check:
	python3 deploy/keycloak/scripts/setup_discovery.py check --context "$(KUBE_CONTEXT)" --env "$(KEYCLOAK_ENV)" $(if $(KEYCLOAK_PORTAL_ENV),--portal-env "$(KEYCLOAK_PORTAL_ENV)")

keycloak-oidc-setup:
	python3 deploy/keycloak/scripts/setup_discovery.py apply --context "$(KUBE_CONTEXT)" --env "$(KEYCLOAK_ENV)" $(if $(KEYCLOAK_PORTAL_ENV),--portal-env "$(KEYCLOAK_PORTAL_ENV)")


# 저장소 전용 경로에 checksum 검증된 kind binary를 준비합니다.
k8s-tools:
	@test -x "$(KIND_BIN)" || ./local/shared/scripts/install-kind.sh
	@"$(KIND_BIN)" version

# 전체 개발 checkout에서 로컬·서버 Kustomize 결과를 확인합니다.
k8s-render: k8s-render-local k8s-render-server

k8s-render-local:
	kubectl kustomize local/shared/k8s >/dev/null
	kubectl kustomize local/shared/k8s/platform >/dev/null
	kubectl kustomize local/minio/k8s >/dev/null
	kubectl kustomize local/portal/k8s >/dev/null
	kubectl kustomize local/keycloak/k8s >/dev/null
	kubectl kustomize local/headlamp/k8s >/dev/null
	kubectl kustomize local/adfs_dummy/k8s >/dev/null
	kubectl kustomize local/portal/k8s/migrate >/dev/null
	kubectl kustomize local/ftp/k8s >/dev/null

k8s-render-server:
	kubectl kustomize deploy/shared/ingress >/dev/null
	kubectl kustomize deploy/minio/k8s >/dev/null
	kubectl kustomize deploy/keycloak/k8s >/dev/null
	kubectl kustomize deploy/portal/k8s/jobs/keycloak-client >/dev/null
	kubectl kustomize deploy/portal/k8s/overlays/prod >/dev/null
	kubectl kustomize deploy/portal/k8s/overlays/prod/migrate >/dev/null

# 앱·작업에 필요한 입력만 검사하고 Secret에 등록합니다.
k8s-env:
ifeq ($(APP)/$(PROFILE),portal/local)
	bash ./local/portal/scripts/apply-env.sh "$(COMPONENT)"
else
	bash ./deploy/shared/scripts/apply-env.sh "$(APP)" "$(PROFILE)" "$(COMPONENT)" "$(portal_component_env)"
endif

# 운영 Portal 검사와 Secret 등록은 같은 입력 파일을 사용합니다.
portal_component_env = $(if $(filter portal/prod,$(APP)/$(PROFILE)),$(if $(filter web,$(COMPONENT)),$(PROD_WEB_ENV_FILE),$(PROD_API_ENV_FILE)))

# 값은 출력하지 않고 선택한 앱의 필수 입력을 검사합니다.
env-check:
	bash ./deploy/shared/scripts/check-env.sh "$(APP)" "$(PROFILE)" "$(COMPONENT)" "$(portal_component_env)"

# 모든 앱은 고정 local context에 적용하고 기존 Docker DB는 건드리지 않습니다.
k8s-up: k8s-tools
	KIND_BIN="$(KIND_BIN)" python3 local/shared/scripts/k8s.py up

# kind cluster와 외부 PostgreSQL container를 중지합니다. DB volume은 유지합니다.
k8s-down:
	KIND_BIN="$(KIND_BIN)" python3 local/shared/scripts/k8s.py down

.PHONY: k8s-check k8s-rebuild k8s-status k8s-smoke k8s-health k8s-grafana k8s-prometheus
k8s-check:
	KIND_BIN="$(KIND_BIN)" python3 local/shared/scripts/k8s.py check
k8s-rebuild:
	KIND_BIN="$(KIND_BIN)" python3 local/shared/scripts/k8s.py rebuild $(if $(APP),--app "$(APP)")
k8s-status:
	python3 local/shared/scripts/k8s.py status
k8s-health:
	python3 local/shared/scripts/k8s.py health
k8s-smoke:
	python3 local/shared/scripts/k8s.py smoke
k8s-grafana:
	python3 local/shared/scripts/k8s.py grafana
k8s-prometheus:
	python3 local/shared/scripts/k8s.py prometheus

# Headlamp UI용 조회 token을 발급하고 localhost:4466 port-forward를 유지합니다.
k8s-ui:
	KUBECTL_BIN=kubectl ./local/headlamp/scripts/headlamp-ui.sh

# Kubernetes·로컬·CI 공개 입력의 존재와 중복 키를 확인합니다.
env-profile-key-check:
	bash ./deploy/shared/scripts/validate_env_profile_keys.sh "$(ENV_APP)" "$(ENV_PROFILE)"

# 선택한 서버 앱은 local 파일과 다른 앱의 env 없이 검사합니다.
server-check:
	bash ./deploy/shared/scripts/check-server.sh "$(APP)" "$(PROFILE)"

# 준비 검사는 앱 하나의 배포 준비 상태(접속·원본·선행 앱·입력·chart·CA·빌드 도구·공용 TLS·DNS)를 조회합니다.
# PREFLIGHT_PREPARE=1이면 저장소 도구로 끝낼 수 있는 준비(chart 받기·CA 묶음·공용 TLS 등록 등)를 실행합니다.
.PHONY: ops-preflight
ops-preflight:
	@python3 deploy/shared/scripts/ops_preflight.py "$(APP)" --context "$(KUBE_CONTEXT)" $(if $(filter 1,$(PREFLIGHT_PREPARE)),--prepare) $(if $(filter 1,$(PREFLIGHT_JSON)),--json)

# 앱 공통 타깃: 명령·입력 파일·기록 대상은 deploy/shared/apps.json이 원본이고 deploy/shared/scripts/app.py가 실행합니다.
#   make <app>-check   입력과 클러스터를 검사하고 변경하지 않음
#   make <app>-up      배포하고 성공하면 배포 기록을 남김
#   make <app>-smoke   워크로드 Ready와 공개 주소 응답을 조회. DNS에 없는 host는 APP VIP로 다시 확인
#   make <app>-render  현재 checkout의 적용 대상을 RENDER_OUTPUT 폴더에 생성
# 입력 파일은 환경변수(예: AIRFLOW_ENV=/경로)로 바꾸며 같은 값을 검사·배포·대조 명령에 붙입니다.
# 이름이 같은 명시적 타깃(k8s-up, env-check 등)이 먼저 적용됩니다.
app = @python3 deploy/shared/scripts/app.py $(1) "$*" --context "$(KUBE_CONTEXT)"
%-check: FORCE
	$(call app,check)
%-up: FORCE
	$(call app,up)
%-smoke: FORCE
	$(call app,smoke) $(if $(filter 1,$(SMOKE_JSON)),--json)
%-render: FORCE
	$(call app,render) --output "$(or $(RENDER_OUTPUT),$(CURDIR)/.tools/render/$*)"
.PHONY: FORCE
FORCE:

# 이미지 빌드 도구(nerdctl·BuildKit)를 확인·설치합니다. 설치는 비밀번호 없는 sudo가 필요하며 containerd를 재시작하지 않습니다.
.PHONY: build-tools-check build-tools-install
build-tools-check:
	@bash deploy/shared/scripts/build-tools.sh check
build-tools-install:
	@bash deploy/shared/scripts/build-tools.sh install

# 사내 이미지 저장소에 같은 tag가 없을 때만 빌드해 push합니다. tag는 소스 내용으로 자동으로 정해집니다.
AIRFLOW_BUILD_ENV ?= $(CURDIR)/deploy/airflow/env/build.env
export AIRFLOW_BUILD_ENV
PORTAL_BUILD_ENV ?= $(CURDIR)/deploy/portal/env/prod/build.env
PORTAL_IMAGE_TAG ?=
export PORTAL_BUILD_ENV PORTAL_IMAGE_TAG
.PHONY: airflow-image portal-image
airflow-image:
	python3 deploy/airflow/scripts/manage.py publish-image --env "$(AIRFLOW_ENV)" --build-env "$(AIRFLOW_BUILD_ENV)" --push-env "$(REGISTRY_PUSH_ENV)"
portal-image:
	python3 deploy/portal/scripts/image.py --context "$(KUBE_CONTEXT)" --push-env "$(REGISTRY_PUSH_ENV)"

# 사내 CA 폴더(deploy/shared/certs/ca)로 host의 OIDC·HTTPS 검증용 PEM 묶음을 만듭니다.
CA_HOST ?= sso.etch.samsungds.net
.PHONY: ca-bundle
ca-bundle:
	@python3 deploy/shared/scripts/ca_bundle.py "$(CA_HOST)"

# 앱 하나의 장애 상태(smoke·Pod·PVC·Warning 이벤트·로그 끝)를 한 번에 조회하고 가이드에서 볼 행을 알려 줍니다.
.PHONY: ops-diagnose
ops-diagnose:
	@python3 deploy/shared/scripts/ops_diagnose.py "$(APP)" --context "$(KUBE_CONTEXT)"

# 준비 검사(자동 준비 포함) → apps.json의 steps → 배포 상태 대조를 한 번에 수행합니다. 첫 실패에서 멈추고 JSON 요약을 출력합니다.
.PHONY: ops-deploy ops-report ops-redact
ops-deploy:
	@python3 deploy/shared/scripts/ops_deploy.py "$(APP)" --context "$(KUBE_CONTEXT)" $(if $(filter 1,$(OPS_SKIP_PREFLIGHT)),--skip-preflight)

# 서버 상태를 별칭(deploy/shared/docs/infrastructure/aliases.json)으로 바꾼 고정 양식 보고서를 출력합니다. 서버명·IP·도메인은 포함하지 않습니다.
ops-report:
	@python3 deploy/shared/scripts/ops_report.py "$(or $(APP),all)" --context "$(KUBE_CONTEXT)" \
	  $(if $(OPS_REPORT_OUT),--output "$(OPS_REPORT_OUT)") $(if $(filter 1,$(OPS_REPORT_SKIP_DRIFT)),--skip-drift)

# 표준 입력의 텍스트를 같은 별칭 규칙으로 바꿉니다. 추가 확인 결과를 외부로 전달하기 전에 통과시킵니다.
# KUBE_CONTEXT를 주면 별칭 표에 없는 노드 이름도 가립니다.
ops-redact:
	@python3 deploy/shared/scripts/ops_report.py redact --context "$(KUBE_CONTEXT)"

# 배포 직후 적용 commit·입력 파일 SHA-256·워크로드를 앱 namespace의 ConfigMap에 기록합니다.
# <app>-up은 성공 후 자동으로 기록합니다. 다른 명령으로 배포했을 때만 실행하며 배포에 쓴 env 변수를 같게 붙입니다.
.PHONY: deploy-record drift-check
deploy-record:
	@python3 deploy/shared/scripts/app.py record "$(APP)" --context "$(KUBE_CONTEXT)"

# 현재 checkout의 배포 정의와 클러스터 상태를 조회 전용으로 대조합니다. APP 생략 시 all, JSON resultCode 0 일치·1 불일치·2 판정 불가.
# 렌더에는 <app>-up과 같은 env 변수를 사용합니다. DRIFT_SKIP_MANIFEST=1이면 리소스 비교 없이 기록·상태만 봅니다.
drift-check:
	@python3 deploy/shared/scripts/deploy_state.py check "$(or $(APP),all)" --context "$(KUBE_CONTEXT)" \
	  $(if $(filter 1,$(DRIFT_SKIP_MANIFEST)),--skip-manifest) $(if $(filter 1,$(DRIFT_JSON)),--json)

# push 계정 Secret을 REGISTRY_PUSH_ENV의 계정으로 바꾸고 registry를 다시 시작합니다.
.PHONY: registry-account-rotate
registry-account-rotate:
	python3 deploy/registry/scripts/manage.py rotate-account --context "$(KUBE_CONTEXT)" --push-env "$(REGISTRY_PUSH_ENV)"
	@python3 deploy/shared/scripts/app.py record registry --context "$(KUBE_CONTEXT)"

# 공용 진입점(앱 ingress)은 앱 env·앱 소스 없이 준비하고 기존 라우팅·VIP 배치를 보존합니다. 검사·배포는 ingress-check·ingress-up입니다.
.PHONY: ingress-connect ingress-tls-up
ingress-tls-up:
	python3 deploy/shared/ingress/tls.py --context "$(KUBE_CONTEXT)" --host "$(TLS_HOST)" $(if $(TLS_SOURCE),--source "$(TLS_SOURCE)",--cert "$(TLS_CERT_FILE)" --key "$(TLS_KEY_FILE)")

# Portal overlay의 namespace·권한을 먼저 적용한 뒤 감시 목록만 연결합니다.
ingress-connect:
	python3 deploy/shared/ingress/manage.py connect --context "$(KUBE_CONTEXT)" --app "$(APP)"

# 로컬 Kubernetes와 새 DB만 종료하며 모든 영속 데이터를 보존합니다.
down: k8s-down

# Kubernetes 개발 이미지와 새 DB를 사용하는 일회성 Compose api 검사입니다.
test-api:
	K8S_API_ENV_FILE="$(CURDIR)/deploy/portal/env/test/api.env" $(COMPOSE_K8S_CHECK) run --rm -T api test

check-api:
	$(COMPOSE_K8S_CHECK) run --rm -T api check

makemigrations-check:
	$(COMPOSE_K8S_CHECK) run --rm -T api makemigrations --check --dry-run

# FTP 입력은 셸 코드로 삽입하지 않고 환경변수로 전달합니다. FTP_NODES를 비우면 이미 FTP 라벨이 있는 노드를 사용합니다.
FTP_ENV ?= $(CURDIR)/deploy/ftp/env/prod.env
FTP_CREDENTIAL_FILE ?= $(CURDIR)/deploy/ftp/env/initial-account.env
export KUBE_CONTEXT FTP_NODES FTP_CREDENTIAL_FILE FTP_ENV AIRFLOW_OIDC_CA_FILE
# 고정 chart를 사내 미러에서 받아 SHA-256을 검증합니다. 이미 있는 파일은 같은 내용으로 다시 씁니다.
.PHONY: airflow-fetch-chart monitoring-fetch-chart airflow-secret-restore
airflow-fetch-chart:
	python3 ./deploy/airflow/scripts/manage.py fetch-chart
monitoring-fetch-chart:
	python3 ./deploy/monitoring/scripts/manage.py fetch-chart

# DB나 설치 흔적은 남았는데 사라진 airflow-postgres·airflow-fernet Secret을 env 값으로 다시 만듭니다. 있는 Secret은 바꾸지 않습니다.
airflow-secret-restore:
	python3 ./deploy/airflow/scripts/manage.py restore-secrets --env "$(AIRFLOW_ENV)" --context "$(KUBE_CONTEXT)"

# checkout의 apps/airflow/dags를 Worker의 DAG 폴더에 맞춥니다. 같은 이름은 덮어쓰고 폴더에만 있는 파일은 남깁니다.
# check는 바뀔 목록만 보여 주며 폴더를 바꾸지 않습니다. 둘 다 임시 Pod를 만들고 끝나면 지웁니다.
.PHONY: airflow-dags-check airflow-dags-sync
airflow-dags-check:
	python3 ./deploy/airflow/scripts/dags.py --env "$(AIRFLOW_ENV)" --context "$(KUBE_CONTEXT)" --check
airflow-dags-sync:
	python3 ./deploy/airflow/scripts/dags.py --env "$(AIRFLOW_ENV)" --context "$(KUBE_CONTEXT)"

# Kubernetes 클러스터 모니터링을 독립적으로 검사·배포합니다.
MONITORING_ENV ?= $(CURDIR)/deploy/monitoring/env/k8s.env
MONITORING_GRAFANA_ENV ?= $(CURDIR)/deploy/monitoring/env/grafana-initial.env
# 배포 도구·문서 검사를 한 번에 실행합니다. 클러스터에 접속하지 않습니다.
.PHONY: deploy-test
deploy-test:
	@python3 deploy/shared/scripts/run_tests.py

# 로컬 보조 Compose와 CI 검사의 실행 진입점입니다.
.PHONY: compose-check build-ci-api test-ci-api check-ci-api makemigrations-ci-check

compose-check:
	bash apps/tooling/agent/check_compose_configs.sh

build-ci-api:
	$(COMPOSE_TEST) build api-test

test-ci-api:
	$(COMPOSE_TEST) run --rm api-test python manage.py test

check-ci-api:
	$(COMPOSE_TEST) run --rm api-test python manage.py check

makemigrations-ci-check:
	$(COMPOSE_TEST) run --rm api-test python manage.py makemigrations --check --dry-run

# 각 프로젝트가 자신의 Node 의존성을 설치합니다.
.PHONY: install web-install tooling-install web-dev web-test web-lint web-build web-preview tooling-test
install: web-install tooling-install
web-install:
	npm --prefix apps/portal/web ci --legacy-peer-deps
tooling-install:
	npm --prefix apps/tooling ci
web-dev:
	npm --prefix apps/portal/web run dev
web-test:
	npm --prefix apps/portal/web run test:run
web-lint:
	npm --prefix apps/portal/web run lint
web-build:
	npm --prefix apps/portal/web run build
web-preview:
	npm --prefix apps/portal/web run preview
tooling-test:
	npm --prefix apps/tooling test

# 감사 도구는 저장소 루트에서 실행해 Python namespace와 상대 경로를 유지합니다.
.PHONY: audit audit-tools-test audit-layout audit-web-boundary audit-api-boundary audit-hotspots audit-ui audit-docs
audit: audit-tools-test audit-layout audit-web-boundary audit-api-boundary audit-hotspots audit-ui audit-docs
audit-tools-test:
	python3 -m unittest discover -s apps/tooling/agent/tests -p 'test_*.py'
audit-layout:
	python3 apps/tooling/agent/check_app_layout.py
audit-web-boundary:
	bash apps/tooling/agent/check_frontend_boundaries.sh
audit-api-boundary:
	python3 apps/tooling/agent/check_backend_boundaries.py
audit-hotspots:
	python3 apps/tooling/agent/check_hotspot_growth.py
audit-ui:
	bash apps/tooling/agent/check_ui_consistency.sh
audit-docs:
	bash apps/tooling/agent/check_docs_inventory.sh

# Keycloak 로그인 방식의 서버 Headlamp를 독립적으로 운영합니다.
HEADLAMP_ENV ?= $(CURDIR)/deploy/headlamp/env/k8s.env
.PHONY: headlamp-ui headlamp-fetch-chart headlamp-oidc-client headlamp-oidc-check headlamp-oidc-setup headlamp-setup-env
# Keycloak client·관리자 그룹과 Headlamp namespace의 client secret·CA ConfigMap을 준비합니다.
headlamp-oidc-setup:
	$(KEYCLOAK_ADMIN) python3 ./deploy/headlamp/scripts/manage.py oidc-setup --context "$(KUBE_CONTEXT)" --env "$(HEADLAMP_ENV)" $(if $(HEADLAMP_OIDC_CA_FILE),--ca-file "$(HEADLAMP_OIDC_CA_FILE)")
headlamp-setup-env:
	@python3 ./deploy/headlamp/scripts/manage.py setup-env --env "$(HEADLAMP_ENV)"
headlamp-oidc-check:
	python3 ./deploy/headlamp/scripts/manage.py oidc-check --env "$(HEADLAMP_ENV)" $(if $(HEADLAMP_OIDC_CA_FILE),--ca-file "$(HEADLAMP_OIDC_CA_FILE)")
headlamp-oidc-client:
	@python3 ./deploy/headlamp/scripts/manage.py oidc-client --env "$(HEADLAMP_ENV)"
headlamp-fetch-chart:
	python3 ./deploy/headlamp/scripts/manage.py fetch-chart
headlamp-ui:
	python3 ./deploy/headlamp/scripts/manage.py ui --context "$(KUBE_CONTEXT)"

# 저장소에 포함한 사내 미러 구성으로 클러스터 공용 Metrics API를 설치합니다.
.PHONY: metrics-server-up
metrics-server-up:
	@test -n "$(KUBE_CONTEXT)" || { echo 'KUBE_CONTEXT를 지정하세요.' >&2; exit 1; }
	kubectl --context "$(KUBE_CONTEXT)" apply -f deploy/shared/metrics-server/components.yaml
	kubectl --context "$(KUBE_CONTEXT)" -n kube-system rollout status deployment/metrics-server --timeout=180s
	kubectl --context "$(KUBE_CONTEXT)" wait --for=condition=Available apiservice/v1beta1.metrics.k8s.io --timeout=180s


# 기존 realm을 유지하며 Airflow 전용 client만 등록합니다.
.PHONY: airflow-keycloak-client
airflow-keycloak-client:
	$(KEYCLOAK_ADMIN) python3 deploy/airflow/k8s/jobs/keycloak-client/setup_client.py --env "$(AIRFLOW_ENV)"

.PHONY: k8s-airflow-sso-check
k8s-airflow-sso-check:
	python3 local/airflow/smoke_sso.py
