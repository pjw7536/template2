#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

status=0

fail() {
  echo "FAIL: $*"
  status=1
}

ok() {
  echo "OK: $*"
}

require_file() {
  local path="$1"
  if [[ -f "$path" ]]; then
    ok "문서 존재: $path"
  else
    fail "문서 누락: $path"
  fi
}

require_text() {
  local file="$1"
  local text="$2"
  local label="$3"
  if grep -Fq "$text" "$file"; then
    ok "$label"
  else
    fail "$label 누락: $text in $file"
  fi
}

DOCS_INDEX="docs/reference/02-inventory.md"

echo "== 문서 원본 =="
for path in \
  docs/README.md \
  docs/getting-started/01-setup.md \
  docs/getting-started/02-usage.md \
  docs/concepts/01-architecture.md \
  docs/concepts/02-data-model.md \
  docs/concepts/03-integrations.md \
  docs/development/01-frontend.md \
  docs/development/02-backend.md \
  docs/development/03-migration-guide.md \
  docs/development/04-documentation.md \
  docs/reference/01-configuration.md \
  docs/reference/02-inventory.md \
  docs/reference/03-operations.md \
  docs/features/README.md \
  docs/features/01-auth.md \
  docs/features/02-account.md \
  docs/features/03-emails.md \
  docs/features/04-assistant.md \
  docs/features/05-line-dashboard.md \
  docs/features/06-observer.md \
  docs/features/07-spider.md \
  docs/features/08-l3-spider.md \
  docs/features/09-pm-comparison.md \
  docs/features/10-appstore.md \
  docs/features/11-voc.md \
  docs/features/12-activity-health.md \
  docs/features/13-data-movement.md \
  docs/features/14-common.md \
  docs/examples/README.md \
  deploy/README.md \
  deploy/shared/docs/README.md \
  deploy/shared/docs/infrastructure/README.md \
  README.md \
  apps/portal/api/README.md \
  apps/portal/web/README.md; do
  require_file "$path"
done
echo

echo "== 문서 진입점 =="
require_text "docs/README.md" "getting-started/01-setup.md" "문서 홈 getting-started/01-setup.md"
require_text "docs/README.md" "getting-started/02-usage.md" "문서 홈 getting-started/02-usage.md"
require_text "docs/README.md" "concepts/01-architecture.md" "문서 홈 concepts/01-architecture.md"
require_text "docs/README.md" "concepts/02-data-model.md" "문서 홈 concepts/02-data-model.md"
require_text "docs/README.md" "concepts/03-integrations.md" "문서 홈 concepts/03-integrations.md"
require_text "docs/README.md" "development/01-frontend.md" "문서 홈 development/01-frontend.md"
require_text "docs/README.md" "development/02-backend.md" "문서 홈 development/02-backend.md"
require_text "docs/README.md" "development/03-migration-guide.md" "문서 홈 development/03-migration-guide.md"
require_text "docs/README.md" "reference/01-configuration.md" "문서 홈 reference/01-configuration.md"
require_text "docs/README.md" "reference/02-inventory.md" "문서 홈 reference/02-inventory.md"
require_text "docs/README.md" "reference/03-operations.md" "문서 홈 reference/03-operations.md"
require_text "docs/README.md" "features/README.md" "문서 홈 features/README.md"
require_text "docs/README.md" "examples/README.md" "문서 홈 examples/README.md"
require_text "docs/features/README.md" "01-auth.md" "기능 01-auth"
require_text "docs/features/README.md" "02-account.md" "기능 02-account"
require_text "docs/features/README.md" "03-emails.md" "기능 03-emails"
require_text "docs/features/README.md" "04-assistant.md" "기능 04-assistant"
require_text "docs/features/README.md" "05-line-dashboard.md" "기능 05-line-dashboard"
require_text "docs/features/README.md" "06-observer.md" "기능 06-observer"
require_text "docs/features/README.md" "07-spider.md" "기능 07-spider"
require_text "docs/features/README.md" "08-l3-spider.md" "기능 08-l3-spider"
require_text "docs/features/README.md" "09-pm-comparison.md" "기능 09-pm-comparison"
require_text "docs/features/README.md" "10-appstore.md" "기능 10-appstore"
require_text "docs/features/README.md" "11-voc.md" "기능 11-voc"
require_text "docs/features/README.md" "12-activity-health.md" "기능 12-activity-health"
require_text "docs/features/README.md" "13-data-movement.md" "기능 13-data-movement"
require_text "docs/features/README.md" "14-common.md" "기능 14-common"
require_text "README.md" "docs/README.md" "root README docs link"
require_text "README.md" "deploy/README.md" "root README deploy link"
echo

echo "== 현재 코드와 문서 색인 =="
if ! python3 apps/tooling/agent/check_docs_routes.py; then
  status=1
fi
echo

echo "== Frontend route 색인 =="
for route in \
  "/" \
  "/login" \
  "/settings/account" \
  "/settings/members" \
  "/emails/inbox" \
  "/emails/sent" \
  "/emails/members" \
  "/assistant" \
  "/ESOP_Dashboard" \
  "/observer" \
  "/observer/:eqpId" \
  "/appstore" \
  "/voc" \
  "/teamstaff"; do
  require_text "$DOCS_INDEX" "$route" "frontend route $route"
done
echo

echo "== Env group 색인 =="
for env_group in \
  "DJANGO_*" \
  "DJANGO_DB_*" \
  "OIDC_*" \
  "AIRFLOW_TRIGGER_TOKEN" \
  "EMAIL_POP3_*" \
  "DRONE_*" \
  "KNOX_MESSENGER_*" \
  "ASSISTANT_*" \
  "RAG_*" \
  "MAIL_API_*" \
  "MINIO_*" \
  "VITE_*"; do
  require_text "$DOCS_INDEX" "$env_group" "env group $env_group"
  require_text "docs/reference/01-configuration.md" "$env_group" "configuration env group $env_group"
done
echo

exit "$status"
