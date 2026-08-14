# Compose 실행 진입점입니다.
COMPOSE_DEV=docker compose -f docker-compose.dev.yml
WORK_HUB_DEV_ENV=WORK_HUB_ENABLED=1 VITE_WORK_HUB_ENABLED=1 GRIST_LOGOUT_ENABLED=1
WORK_HUB_DEPLOY_ENV=WORK_HUB_ENABLED=1 VITE_WORK_HUB_ENABLED=1 GRIST_LOGOUT_ENABLED=1
WORK_HUB_DISABLE_ENV=WORK_HUB_ENABLED=0 VITE_WORK_HUB_ENABLED=0 GRIST_LOGOUT_ENABLED=1
WORK_HUB_OFF_ENV=WORK_HUB_ENABLED=0 VITE_WORK_HUB_ENABLED=0 GRIST_LOGOUT_ENABLED=0
COMPOSE_DEV_WORK_HUB=$(WORK_HUB_DEV_ENV) $(COMPOSE_DEV) --profile work-hub
COMPOSE_OIDC=docker compose -f docker-compose.oidc.yml
COMPOSE_OIDC_WORK_HUB=$(WORK_HUB_DEPLOY_ENV) $(COMPOSE_OIDC) --profile work-hub
COMPOSE_OIDC_WORK_HUB_DISABLE=$(WORK_HUB_DISABLE_ENV) $(COMPOSE_OIDC) --profile work-hub
COMPOSE_OIDC_WORK_HUB_OFF=$(WORK_HUB_OFF_ENV) $(COMPOSE_OIDC) --profile work-hub
COMPOSE_PROD=docker compose -f docker-compose.yml
COMPOSE_PROD_WORK_HUB=$(WORK_HUB_DEPLOY_ENV) $(COMPOSE_PROD) --profile work-hub
COMPOSE_PROD_WORK_HUB_DISABLE=$(WORK_HUB_DISABLE_ENV) $(COMPOSE_PROD) --profile work-hub
COMPOSE_PROD_WORK_HUB_OFF=$(WORK_HUB_OFF_ENV) $(COMPOSE_PROD) --profile work-hub
GRIST_REMOTE_SECRET_HOST_PATH?=./data/work_hub_secrets/remote
GRIST_REMOTE_SECRET_UID?=$(shell id -u)
GRIST_REMOTE_SECRET_GID?=$(shell id -g)
COMPOSE_GRIST_REMOTE=WORK_HUB_SECRET_HOST_PATH="$(GRIST_REMOTE_SECRET_HOST_PATH)" GRIST_SECRET_UID=$(GRIST_REMOTE_SECRET_UID) GRIST_SECRET_GID=$(GRIST_REMOTE_SECRET_GID) docker compose --env-file env/grist.remote.env -f docker-compose.grist.yml

# infra는 재빌드 빈도가 낮은 기반 서비스만 포함합니다.
# - DB: airflow-postgres
# - Airflow: airflow-init, airflow-webserver, airflow-scheduler
# - FTP: ftp
# - Monitoring: OIDC/prod에서 prometheus, node-exporter, cadvisor, grafana
INFRA_SERVICES=airflow-postgres airflow-init airflow-webserver airflow-scheduler ftp
INFRA_BUILD_SERVICES=airflow-init airflow-webserver airflow-scheduler
MONITORING_SERVICES=prometheus node-exporter cadvisor grafana
OIDC_INFRA_SERVICES=$(INFRA_SERVICES) $(MONITORING_SERVICES)
PROD_INFRA_SERVICES=$(INFRA_SERVICES) $(MONITORING_SERVICES)

# app은 실제 애플리케이션 기능을 구성하는 서비스입니다.
# dev는 로컬 dummy 외부계(adfs)를 app으로 취급합니다.
DEV_APP_SERVICES=adfs minio minio-init api web nginx
DEV_APP_BUILD_SERVICES=adfs api web
DEV_WORK_HUB_SERVICES=grist grist-api-key-init work-hub-access-worker
DEPLOY_WORK_HUB_SERVICES=work-hub-access-worker
REMOTE_GRIST_SERVICES=grist grist-api-key-init grist-nginx

# OIDC/prod는 실제 연동 환경이므로 dummy adfs 없이 app 서비스만 다룹니다.
OIDC_APP_SERVICES=minio minio-init api web nginx
OIDC_APP_BUILD_SERVICES=api web
PROD_APP_SERVICES=minio minio-init api web nginx
PROD_APP_BUILD_SERVICES=api web
PROD_MIGRATION_STOP_SERVICES=api work-hub-access-worker

.PHONY: \
	network \
	dev dev-up dev-down dev-app-up dev-app-build dev-app-down dev-infra-up dev-infra-build dev-infra-down \
	dev-work-hub dev-work-hub-up dev-work-hub-down work-hub-up work-hub-down work-hub-logs work-hub-seed \
	oidc oidc-app-up oidc-app-build oidc-app-down oidc-work-hub-up oidc-work-hub-disable oidc-work-hub-down oidc-infra-up oidc-infra-build oidc-infra-down \
	prod prod-app-up prod-app-build prod-app-down prod-work-hub-build prod-work-hub-migrate prod-work-hub-up prod-work-hub-disable prod-work-hub-down prod-infra-up prod-infra-build prod-infra-down \
	grist-remote-config grist-remote-up grist-remote-disable grist-remote-down grist-remote-logs \
	work-hub-api-key-check \
	down test-api check-api makemigrations-check \
	y5push y5pull

# shared-net은 compose 파일에서 external network로 사용합니다.
network:
	docker network create shared-net 2>/dev/null || true

# dev 기본 실행: Portal과 Work Hub를 함께 올리고, Airflow/FTP는 제외합니다.
dev: dev-work-hub-up

# dev 기본 실행의 명시적 호환 진입점입니다.
dev-up: dev-work-hub-up

# dev 기본 실행 전체를 중지·제거하고 데이터 volume은 보존합니다.
dev-down: dev-work-hub-down

# 기존 Work Hub 명령은 명시적 up target의 호환 alias로 유지합니다.
dev-work-hub: dev-work-hub-up

# Work Hub 개발 실행: 기존 Portal과 Grist OSS를 같은 터미널에서 함께 올립니다.
dev-work-hub-up: network
	$(COMPOSE_DEV_WORK_HUB) up $(DEV_APP_SERVICES) $(DEV_WORK_HUB_SERVICES)

# Portal과 Grist 컨테이너를 함께 중지·제거하고 데이터 volume은 보존합니다.
dev-work-hub-down:
	$(COMPOSE_DEV_WORK_HUB) stop $(DEV_APP_SERVICES) $(DEV_WORK_HUB_SERVICES)
	$(COMPOSE_DEV_WORK_HUB) rm -f $(DEV_APP_SERVICES) $(DEV_WORK_HUB_SERVICES)

# Grist OSS와 접근 동기화 worker, 활성화된 Portal app stack을 백그라운드로 올립니다.
work-hub-up: network
	$(COMPOSE_DEV_WORK_HUB) up -d $(DEV_APP_SERVICES) $(DEV_WORK_HUB_SERVICES)

# Portal app을 기본 비활성 설정으로 되돌린 뒤 Work Hub service를 제거합니다.
work-hub-down:
	$(COMPOSE_DEV) up -d api web nginx
	$(COMPOSE_DEV_WORK_HUB) stop $(DEV_WORK_HUB_SERVICES)
	$(COMPOSE_DEV_WORK_HUB) rm -f $(DEV_WORK_HUB_SERVICES)

# Grist와 접근 동기화 worker 로그를 실시간으로 확인합니다.
work-hub-logs:
	$(COMPOSE_DEV_WORK_HUB) logs -f $(DEV_WORK_HUB_SERVICES)

# Portal 관리자 Grist API key가 주입된 API에서 DEV_ALPHA demo schema·record·mapping을 보장합니다.
work-hub-seed: work-hub-up
	@for attempt in $$(seq 1 30); do \
		curl -fsS http://localhost:8100/status >/dev/null 2>&1 && break; \
		sleep 2; \
	done
	@curl -fsS http://localhost:8100/status >/dev/null
	$(COMPOSE_DEV_WORK_HUB) up -d --force-recreate api
	@for attempt in $$(seq 1 30); do \
		curl -fsS http://localhost:8000/api/v1/health/ >/dev/null 2>&1 && break; \
		sleep 2; \
	done
	@curl -fsS http://localhost:8000/api/v1/health/ >/dev/null
	$(COMPOSE_DEV) exec -T api python manage.py seed_grist_demo

# dev app을 올립니다. api 의존성은 compose가 확인하므로 DB 준비 이후 API가 시작됩니다.
dev-app-up: network
	$(COMPOSE_DEV) up $(DEV_APP_SERVICES)

# dev app 이미지/빌드 산출물만 다시 빌드합니다.
dev-app-build: network
	$(COMPOSE_DEV) build $(DEV_APP_BUILD_SERVICES)

# dev app 컨테이너만 중지하고 제거합니다. volume과 network는 삭제하지 않습니다.
dev-app-down:
	$(COMPOSE_DEV) stop $(DEV_APP_SERVICES)
	$(COMPOSE_DEV) rm -f $(DEV_APP_SERVICES)

# dev infra만 올립니다.
dev-infra-up: network
	$(COMPOSE_DEV) up -d $(INFRA_SERVICES)

# dev infra 이미지 중 빌드가 필요한 Airflow 이미지만 다시 빌드합니다.
dev-infra-build: network
	$(COMPOSE_DEV) build $(INFRA_BUILD_SERVICES)

# dev infra 컨테이너만 중지하고 제거합니다. DB volume은 삭제하지 않습니다.
dev-infra-down:
	$(COMPOSE_DEV) stop $(INFRA_SERVICES)
	$(COMPOSE_DEV) rm -f $(INFRA_SERVICES)

# OIDC 전체 실행: infra를 먼저 올린 뒤 app을 올립니다.
oidc:
	$(MAKE) oidc-infra-up
	$(MAKE) oidc-app-up

# OIDC app만 올립니다.
oidc-app-up: network
	$(COMPOSE_OIDC) up -d --no-deps $(OIDC_APP_SERVICES)

# OIDC app과 원격 Grist 접근 동기화 worker를 함께 올립니다.
oidc-work-hub-up: network work-hub-api-key-check
	$(COMPOSE_OIDC_WORK_HUB) up -d $(OIDC_APP_SERVICES) $(DEPLOY_WORK_HUB_SERVICES)

# OIDC Work Hub 본문·worker는 끄고 기존 Grist session 정리만 유지합니다.
oidc-work-hub-disable: network
	$(COMPOSE_OIDC_WORK_HUB_DISABLE) up -d --no-deps --force-recreate api web nginx work-hub-access-worker

# 세션 정리 유예 후 OIDC Work Hub service를 제거하고 logout도 끅니다.
oidc-work-hub-down: network
	$(COMPOSE_OIDC_WORK_HUB_OFF) stop $(DEPLOY_WORK_HUB_SERVICES)
	$(COMPOSE_OIDC_WORK_HUB_OFF) rm -f $(DEPLOY_WORK_HUB_SERVICES)
	$(COMPOSE_OIDC_WORK_HUB_OFF) up -d --no-deps --force-recreate api web nginx

# OIDC app 이미지/빌드 산출물만 다시 빌드합니다.
oidc-app-build: network
	$(COMPOSE_OIDC) build $(OIDC_APP_BUILD_SERVICES)

# OIDC app 컨테이너만 중지하고 제거합니다.
oidc-app-down:
	$(COMPOSE_OIDC) stop $(OIDC_APP_SERVICES)
	$(COMPOSE_OIDC) rm -f $(OIDC_APP_SERVICES)

# OIDC infra만 올립니다.
oidc-infra-up: network
	$(COMPOSE_OIDC) up -d $(OIDC_INFRA_SERVICES)

# OIDC infra 이미지 중 빌드가 필요한 Airflow 이미지만 다시 빌드합니다.
oidc-infra-build: network
	$(COMPOSE_OIDC) build $(INFRA_BUILD_SERVICES)

# OIDC infra 컨테이너만 중지하고 제거합니다.
oidc-infra-down:
	$(COMPOSE_OIDC) stop $(OIDC_INFRA_SERVICES)
	$(COMPOSE_OIDC) rm -f $(OIDC_INFRA_SERVICES)

# prod 전체 실행: infra를 먼저 올린 뒤 app을 올립니다.
prod:
	$(MAKE) prod-infra-up
	$(MAKE) prod-app-up

# prod app만 올립니다.
prod-app-up: network
	$(COMPOSE_PROD) up -d --no-deps $(PROD_APP_SERVICES)

# Work Hub release용 API와 활성 Web bundle을 함께 빌드합니다.
prod-work-hub-build: network
	$(COMPOSE_PROD_WORK_HUB) build $(PROD_APP_BUILD_SERVICES)

# 구버전 API·worker를 중지한 뒤 새 API image로 운영 DB migration을 적용합니다.
prod-work-hub-migrate: prod-work-hub-build
	$(COMPOSE_PROD_WORK_HUB) stop $(PROD_MIGRATION_STOP_SERVICES)
	$(COMPOSE_PROD_WORK_HUB) run --rm --no-deps --entrypoint python api manage.py migrate --noinput

# build·migration이 성공한 prod app, Grist·접근 동기화 worker를 함께 올립니다.
prod-work-hub-up: work-hub-api-key-check prod-work-hub-migrate
	$(COMPOSE_PROD_WORK_HUB) up -d $(PROD_APP_SERVICES) $(DEPLOY_WORK_HUB_SERVICES)

# 운영 Work Hub 본문·worker는 끄고 기존 Grist session 정리만 유지합니다.
prod-work-hub-disable: network
	$(COMPOSE_PROD_WORK_HUB_DISABLE) up -d --no-deps --force-recreate api nginx work-hub-access-worker
	$(COMPOSE_PROD_WORK_HUB_DISABLE) build web
	$(COMPOSE_PROD_WORK_HUB_DISABLE) up -d --no-deps --force-recreate web

# 세션 정리 유예 후 운영 Work Hub service를 제거하고 logout도 끅니다.
prod-work-hub-down: network
	$(COMPOSE_PROD_WORK_HUB_OFF) build web
	$(COMPOSE_PROD_WORK_HUB_OFF) stop $(DEPLOY_WORK_HUB_SERVICES)
	$(COMPOSE_PROD_WORK_HUB_OFF) rm -f $(DEPLOY_WORK_HUB_SERVICES)
	$(COMPOSE_PROD_WORK_HUB_OFF) up -d --no-deps --force-recreate api web nginx

# prod app 이미지/빌드 산출물만 다시 빌드합니다.
prod-app-build: network
	$(COMPOSE_PROD) build $(PROD_APP_BUILD_SERVICES)

# prod app 컨테이너만 중지하고 제거합니다.
prod-app-down:
	$(COMPOSE_PROD) stop $(PROD_APP_SERVICES)
	$(COMPOSE_PROD) rm -f $(PROD_APP_SERVICES)

# prod infra만 올립니다.
prod-infra-up: network
	$(COMPOSE_PROD) up -d $(PROD_INFRA_SERVICES)

# prod infra 이미지 중 빌드가 필요한 Airflow 이미지만 다시 빌드합니다.
prod-infra-build: network
	$(COMPOSE_PROD) build $(INFRA_BUILD_SERVICES)

# prod infra 컨테이너만 중지하고 제거합니다.
prod-infra-down:
	$(COMPOSE_PROD) stop $(PROD_INFRA_SERVICES)
	$(COMPOSE_PROD) rm -f $(PROD_INFRA_SERVICES)

# Portal API와 worker에 같은 원격 Grist API key가 주입됐는지 확인합니다.
work-hub-api-key-check:
	@test -n "$${GRIST_API_KEY:-}" || { echo "GRIST_API_KEY 배포 secret이 필요합니다." >&2; exit 1; }

# 신규 서버의 원격 Grist Compose 렌더링을 검증합니다.
grist-remote-config:
	$(COMPOSE_GRIST_REMOTE) config --quiet

# 신규 서버에서 Grist, key initializer와 전용 Nginx를 함께 올립니다.
grist-remote-up:
	@test -n "$${GRIST_SESSION_SECRET:-}" || { echo "GRIST_SESSION_SECRET 배포 secret이 필요합니다." >&2; exit 1; }
	@install -d -m 700 "$(GRIST_REMOTE_SECRET_HOST_PATH)"
	@test -w "$(GRIST_REMOTE_SECRET_HOST_PATH)" || { echo "Grist key 디렉터리에 쓸 수 없습니다: $(GRIST_REMOTE_SECRET_HOST_PATH)" >&2; exit 1; }
	WORK_HUB_ENABLED=1 $(COMPOSE_GRIST_REMOTE) up -d $(REMOTE_GRIST_SERVICES)

# 신규 서버의 본문과 widget을 차단하되 기존 session logout은 유지합니다.
grist-remote-disable:
	WORK_HUB_ENABLED=0 $(COMPOSE_GRIST_REMOTE) up -d --no-deps --force-recreate grist-nginx

# 신규 서버의 Grist 서비스를 제거하고 volume과 발급 key 파일은 보존합니다.
grist-remote-down:
	WORK_HUB_ENABLED=0 $(COMPOSE_GRIST_REMOTE) down

# 신규 서버의 Grist, initializer와 Nginx 로그를 확인합니다.
grist-remote-logs:
	$(COMPOSE_GRIST_REMOTE) logs -f $(REMOTE_GRIST_SERVICES)

# 모든 실행 진입점의 compose project를 내립니다.
down:
	$(COMPOSE_DEV) down
	$(COMPOSE_OIDC) down
	$(COMPOSE_PROD) down

# 개발 API 컨테이너 기준 검증 명령입니다.
test-api:
	$(COMPOSE_DEV) exec -T api python manage.py test

check-api:
	$(COMPOSE_DEV) exec -T api python manage.py check

makemigrations-check:
	$(COMPOSE_DEV) exec -T api python manage.py makemigrations --check --dry-run

# 현재 변경사항 전체를 커밋한 뒤 y5 브랜치로 푸시합니다.
# 사용: make y5push msg="커밋 메시지"
y5push:
	@test -n "$(strip $(msg))" || (echo '사용: make y5push msg="커밋 메시지"'; exit 1)
	./y5push "$(msg)"

# 원격 main 브랜치 상태로 현재 작업트리를 강제 동기화합니다.
y5pull:
	./y5pull
