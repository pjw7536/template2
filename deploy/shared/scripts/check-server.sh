#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
APP="${1:-keycloak}"
PROFILE="${2:-prod}"
[[ "$PROFILE" == prod ]] || { echo "사내 서버는 Kubernetes 전용입니다. $PROFILE 환경의 Kubernetes 정의가 없습니다." >&2; exit 1; }
cd "$ROOT_DIR"

if [[ "$APP" == all || "$APP" == keycloak-airflow ]]; then
  selected_apps="$(python3 deploy/shared/scripts/app-paths.py "$APP" --names)"
  while IFS= read -r app; do
    bash "$ROOT_DIR/deploy/shared/scripts/check-server.sh" "$app" "$PROFILE"
  done <<< "$selected_apps"
  exit 0
fi

# Kubernetes 정의가 없는 앱을 Compose 검사로 대신 통과시키지 않습니다.
case "$APP" in
  ftp)
    bash -n deploy/ftp/k8s/start.sh
    kubectl kustomize deploy/ftp/k8s >/dev/null
    echo '서버 원본 검사 통과: ftp/prod (노드·Secret·포트·접속 검사는 별도)'
    exit 0 ;;
  airflow)
    python3 "$ROOT_DIR/deploy/airflow/scripts/manage.py" check
    exit 0 ;;
  headlamp)
    python3 "$ROOT_DIR/deploy/headlamp/scripts/manage.py" check
    exit 0 ;;
  monitoring)
    python3 "$ROOT_DIR/deploy/monitoring/scripts/manage.py" check
    exit 0 ;;
esac

# 예시·설정 형식과 Kubernetes 원본만 검사하며 클러스터에는 적용하지 않습니다.
bash deploy/shared/scripts/validate_env_profile_keys.sh "$APP" "$PROFILE"
case "$APP/$PROFILE" in
  keycloak/prod)
    kubectl kustomize deploy/keycloak/k8s >/dev/null ;;
  portal/prod)
    for directory in overlays/prod overlays/prod/migrate jobs/keycloak-client; do
      kubectl kustomize "deploy/portal/k8s/$directory" >/dev/null
    done ;;
  *) echo "지원하지 않는 서버 앱·환경: $APP/$PROFILE" >&2; exit 1 ;;
esac
echo "서버 원본 검사 통과: $APP/$PROFILE (실제 credential·서비스 연결 검사는 별도)"
