# 로컬 Kubernetes·Compose 검사·서버 배포 실행 진입점입니다.
COMPOSE_TEST=docker compose -f deploy/portal/compose/test.yml
COMPOSE_K8S_CHECK=docker compose --project-name tailwind-k8s-check --env-file local/shared/runtime/db.env -f local/shared/compose/k8s-check.yml
REFERENCE_USERS_CSV ?=
REGISTER_REFERENCE_USERS_APPLY ?= 0

# 값을 shell 코드에 삽입하지 않고 초기 설정 스크립트에 환경변수로 전달합니다.
export KEYCLOAK_SDWTS_CSV KEYCLOAK_USERS_CSV KEYCLOAK_SDWT_CLIENTS KEYCLOAK_SDWT_APPLY KEYCLOAK_SDWT_VALIDATE_ONLY

PROD_API_ENV_FILE ?= $(CURDIR)/deploy/portal/env/prod/api.env
KIND_BIN ?= $(CURDIR)/.tools/bin/kind
APP ?= keycloak
PROFILE ?= prod
COMPONENT ?= server
ENV_APP ?= all
ENV_PROFILE ?= all
KUBE_CONTEXT ?=
KEYCLOAK_ENV ?= $(CURDIR)/deploy/keycloak/env/prod.env
KEYCLOAK_CERTS ?= $(CURDIR)/deploy/shared/certs/etch-sso.samsungds.net
AIRFLOW_ENV ?= $(CURDIR)/deploy/airflow/env/k8s.env
AIRFLOW_TLS_SOURCE ?=
VIP_BACKENDS ?=

.PHONY: dev down env-check env-profile-key-check prod-profile-env-check \
 k8s-tools k8s-render k8s-render-local k8s-render-server k8s-export k8s-env k8s-up k8s-down k8s-ui server-check server-up \
 test-api check-api makemigrations-check keycloak-check keycloak-up airflow-check airflow-up

# 기본 개발 환경은 한 PC의 전체 Kubernetes 앱입니다.
dev: k8s-up

.PHONY: register-reference-users
register-reference-users:
	@test -f "$(REFERENCE_USERS_CSV)" || { echo 'REFERENCE_USERS_CSV에 참조 CSV 파일 경로를 지정하세요.'; exit 1; }
	$(COMPOSE_K8S_CHECK) run --rm -T -v "$(CURDIR)/apps/portal/api:/app" -v "$(abspath $(REFERENCE_USERS_CSV)):/data/account/reference-users.csv:ro" api register_reference_users /data/account/reference-users.csv $(if $(filter 1,$(REGISTER_REFERENCE_USERS_APPLY)),--apply,)

.PHONY: keycloak-sdwt-init keycloak-sdwt-test
keycloak-sdwt-init:
	python3 ./deploy/keycloak/scripts/init_sdwt.py

keycloak-sdwt-test:
	python3 -m unittest discover -s apps/tooling/tests -p 'test_keycloak_sdwt.py'


# 저장소 전용 경로에 checksum 검증된 kind binary를 준비합니다.
k8s-tools:
	@test -x "$(KIND_BIN)" || ./local/shared/scripts/install-kind.sh
	@"$(KIND_BIN)" version

# 전체 개발 checkout에서 로컬·서버 Kustomize 결과를 확인합니다.
k8s-render: k8s-render-local k8s-render-server

k8s-render-local:
	kubectl kustomize local/shared/k8s >/dev/null
	kubectl kustomize local/portal/k8s >/dev/null
	kubectl kustomize local/keycloak/k8s >/dev/null
	kubectl kustomize local/headlamp/k8s >/dev/null
	kubectl kustomize local/adfs_dummy/k8s >/dev/null
	kubectl kustomize local/portal/k8s/migrate >/dev/null
	kubectl kustomize local/ftp/k8s >/dev/null

k8s-render-server:
	kubectl kustomize deploy/keycloak/k8s >/dev/null
	kubectl kustomize deploy/portal/k8s/jobs/keycloak-client >/dev/null
	kubectl kustomize deploy/portal/k8s/overlays/prod >/dev/null
	kubectl kustomize deploy/portal/k8s/overlays/prod/migrate >/dev/null

# CP1 전달용 Keycloak 스택과 별도 claim 등록 Job 파일을 생성합니다.
k8s-export:
	bash ./deploy/keycloak/scripts/render.sh

# 앱·작업에 필요한 입력만 검사하고 Secret에 등록합니다.
k8s-env:
ifeq ($(APP)/$(PROFILE),portal/local)
	bash ./local/portal/scripts/apply-env.sh "$(COMPONENT)"
else
	bash ./deploy/shared/scripts/apply-env.sh "$(APP)" "$(PROFILE)" "$(COMPONENT)"
endif

# 값은 출력하지 않고 선택한 앱의 필수 입력을 검사합니다.
env-check:
	bash ./deploy/shared/scripts/check-env.sh "$(APP)" "$(PROFILE)" "$(COMPONENT)"

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
	KIND_BIN="$(KIND_BIN)" python3 local/shared/scripts/k8s.py rebuild --app "$(APP)"
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

# Kubernetes 운영 API의 필수값을 확인합니다. 선택 업무 연동은 별도 확인합니다.
prod-profile-env-check:
	bash ./deploy/shared/scripts/validate_env_profile_keys.sh portal prod
	bash ./deploy/shared/scripts/check-env.sh portal prod api "$(PROD_API_ENV_FILE)"

# 로컬 Kubernetes와 새 DB만 종료하며 모든 영속 데이터를 보존합니다.
down: k8s-down

# Kubernetes 개발 이미지와 새 DB를 사용하는 일회성 Compose api 검사입니다.
test-api:
	K8S_API_ENV_FILE="$(CURDIR)/deploy/portal/env/test/api.env" $(COMPOSE_K8S_CHECK) run --rm -T api test

check-api:
	$(COMPOSE_K8S_CHECK) run --rm -T api check

makemigrations-check:
	$(COMPOSE_K8S_CHECK) run --rm -T api makemigrations --check --dry-run

# 기존 Keycloak과 Airflow UI를 같은 서버 진입점에 연결합니다.
server-up:
	python3 ./deploy/shared/scripts/server-up.py --context "$(KUBE_CONTEXT)" --airflow-env "$(AIRFLOW_ENV)" --tls-source "$(AIRFLOW_TLS_SOURCE)" --vip-backends "$(VIP_BACKENDS)"

# 앱별 검사는 실제 입력과 기존 클러스터를 확인하되 변경하지 않습니다.
keycloak-check:
	python3 ./deploy/keycloak/scripts/up.py --context "$(KUBE_CONTEXT)" --env "$(KEYCLOAK_ENV)" --certs "$(KEYCLOAK_CERTS)" --vip-backends "$(VIP_BACKENDS)" --check-only

keycloak-up:
	python3 ./deploy/keycloak/scripts/up.py --context "$(KUBE_CONTEXT)" --env "$(KEYCLOAK_ENV)" --certs "$(KEYCLOAK_CERTS)" --vip-backends "$(VIP_BACKENDS)"

airflow-check:
	python3 ./deploy/airflow/scripts/up.py --context "$(KUBE_CONTEXT)" --env "$(AIRFLOW_ENV)" --tls-source "$(AIRFLOW_TLS_SOURCE)" --check-only

airflow-up:
	python3 ./deploy/airflow/scripts/up.py --context "$(KUBE_CONTEXT)" --env "$(AIRFLOW_ENV)" --tls-source "$(AIRFLOW_TLS_SOURCE)"

# Kubernetes 클러스터 모니터링을 독립적으로 검사·배포합니다.
MONITORING_ENV ?= $(CURDIR)/deploy/monitoring/env/k8s.env
.PHONY: monitoring-check monitoring-up
monitoring-check:
	python3 ./deploy/monitoring/scripts/manage.py check --env "$(MONITORING_ENV)"

monitoring-up:
	python3 ./deploy/monitoring/scripts/manage.py deploy --context "$(KUBE_CONTEXT)" --env "$(MONITORING_ENV)"

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
.PHONY: headlamp-check headlamp-up headlamp-ui headlamp-fetch-chart headlamp-oidc-client
headlamp-oidc-client:
	@python3 ./deploy/headlamp/scripts/manage.py oidc-client --env "$(HEADLAMP_ENV)"
headlamp-fetch-chart:
	python3 ./deploy/headlamp/scripts/manage.py fetch-chart
headlamp-check:
	python3 ./deploy/headlamp/scripts/manage.py check --env "$(HEADLAMP_ENV)"
headlamp-up:
	python3 ./deploy/headlamp/scripts/manage.py deploy --context "$(KUBE_CONTEXT)" --env "$(HEADLAMP_ENV)"
headlamp-ui:
	python3 ./deploy/headlamp/scripts/manage.py ui --context "$(KUBE_CONTEXT)"
