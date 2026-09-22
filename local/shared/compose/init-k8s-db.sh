#!/usr/bin/env bash
set -euo pipefail
# 초기 volume에서만 앱별 소유자를 생성하고 비밀번호는 SQL 로그에 출력하지 않습니다.
psql -v ON_ERROR_STOP=1 --username postgres --dbname postgres \
  --set=portal_password="$PORTAL_DB_PASSWORD" \
  --set=airflow_password="$AIRFLOW_DB_PASSWORD" \
  --set=keycloak_password="$KEYCLOAK_DB_PASSWORD" <<'SQL'
CREATE ROLE portal LOGIN PASSWORD :'portal_password';
CREATE ROLE airflow LOGIN PASSWORD :'airflow_password';
CREATE ROLE keycloak LOGIN PASSWORD :'keycloak_password';
CREATE DATABASE dashboard OWNER portal;
CREATE DATABASE airflow OWNER airflow;
CREATE DATABASE keycloak OWNER keycloak;
\connect dashboard
CREATE EXTENSION IF NOT EXISTS pg_trgm;
\connect template1
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL
