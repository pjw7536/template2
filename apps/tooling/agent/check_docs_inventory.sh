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

echo "== 필수 문서 =="
for path in \
  docs/README.md \
  docs/getting-started/README.md \
  docs/getting-started/01-setup.md \
  docs/getting-started/02-usage.md \
  docs/concepts/README.md \
  docs/concepts/04-glossary.md \
  docs/development/README.md \
  docs/development/04-documentation.md \
  docs/development/03-migration-guide.md \
  docs/reference/README.md \
  docs/reference/kubernetes/README.md \
  docs/reference/integrations/proxy-mirrors.md \
  docs/concepts/01-architecture.md \
  docs/reference/02-inventory.md \
  docs/development/01-frontend.md \
  docs/development/02-backend.md \
  docs/concepts/02-data-model.md \
  docs/reference/01-configuration.md \
  docs/api/README.md \
  docs/api/07-l0-spider.md \
  docs/api/09-pm-spider.md \
  docs/api/10-tttm-spider.md \
  docs/api/14-data-movement.md \
  docs/modules/README.md \
  docs/modules/07-spider.md \
  docs/examples/README.md \
  docs/reference/03-operations.md \
  docs/concepts/03-integrations.md \
  README.md \
  apps/portal/api/README.md \
  apps/portal/web/README.md; do
  require_file "$path"
done
echo

echo "== 목적별 문서 진입점 링크 =="
require_text "README.md" "docs/README.md" "root README docs link"
require_text "README.md" "deploy/README.md" "root README deploy link"
for section in getting-started concepts development reference; do
  require_text "README.md" "docs/$section/README.md" "root README $section link"
  require_text "docs/README.md" "$section/README.md" "docs home $section link"
  require_text "docs/$section/README.md" "../README.md" "$section parent link"
done
for page in 01-setup 02-usage; do
  require_text "docs/getting-started/README.md" "$page.md" "getting-started $page link"
done
for page in 01-architecture 02-data-model 03-integrations 04-glossary; do
  require_text "docs/concepts/README.md" "$page.md" "concepts $page link"
done
for page in 01-frontend 02-backend 03-migration-guide 04-documentation; do
  require_text "docs/development/README.md" "$page.md" "development $page link"
done
for page in 01-configuration 02-inventory 03-operations; do
  require_text "docs/reference/README.md" "$page.md" "reference $page link"
done
require_text "docs/README.md" "modules/README.md" "docs home modules link"
require_text "docs/README.md" "api/README.md" "docs home API link"
require_text "apps/portal/api/README.md" "docs/development/02-backend.md" "api README backend link"
require_text "apps/portal/api/README.md" "docs/reference/02-inventory.md" "api README inventory link"
require_text "apps/portal/web/README.md" "docs/development/01-frontend.md" "web README frontend link"
require_text "apps/portal/web/README.md" "docs/reference/02-inventory.md" "web README inventory link"
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
