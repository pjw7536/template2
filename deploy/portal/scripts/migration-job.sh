#!/usr/bin/env bash
# Job을 한 번 생성하고 결과만 보고한다. 기존 Job은 운영자가 상태를 확인한다.
set -euo pipefail
: "${KUBE_CONTEXT:?KUBE_CONTEXT를 명시하세요.}"

portal_wait_job() (
  local name="$1" status
  for _ in $(seq 180); do
    status="$(kubectl --context "$KUBE_CONTEXT" -n tailwind-internal get job "$name" \
      -o jsonpath='{.status.succeeded}/{.status.failed}')"
    case "$status" in
      1/*) echo "Job 완료: $name"; return 0 ;;
      */[1-9]*)
        echo "Job 실패: $name" >&2; return 1 ;;
    esac
    sleep 5
  done
  echo "Job 대기 시간 초과: $name" >&2
  return 1
)

portal_permission_check() (
  local check_name="$1" check_phase="$2"
  kubectl --context "$KUBE_CONTEXT" create --dry-run=client \
    -k deploy/portal/k8s/overlays/prod/migrate -o json |
    python3 -c '
import json
import sys

job = json.load(sys.stdin)
job["metadata"]["name"] = sys.argv[1]
job["spec"]["backoffLimit"] = 0
container = next(item for item in job["spec"]["template"]["spec"]["containers"] if item["name"] == "migrate")
container["command"] = ["python"]
container["args"] = ["manage.py", "check_access_permission_integrity", "--phase", sys.argv[2]]
json.dump(job, sys.stdout)
' "$check_name" "$check_phase" |
    kubectl --context "$KUBE_CONTEXT" create -f -
  portal_wait_job "$check_name"
)

case "${1:-}" in
  migrate)
    kubectl --context "$KUBE_CONTEXT" create -k deploy/portal/k8s/overlays/prod/migrate
    portal_wait_job portal-migrate ;;
  pre-migration|post-migration)
    : "${PORTAL_CHECK_JOB:?사용하지 않은 검사 Job 이름을 지정하세요.}"
    if [[ "$PORTAL_CHECK_JOB" == portal-migrate ]]; then
      echo '검사 Job은 portal-migrate와 다른 이름을 사용하세요.' >&2
      exit 1
    fi
    portal_permission_check "$PORTAL_CHECK_JOB" "$1" ;;
  *) echo '지원하지 않는 Portal Job 단계입니다.' >&2; exit 1 ;;
esac
