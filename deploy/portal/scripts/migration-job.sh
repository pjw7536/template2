#!/usr/bin/env bash
# Job을 한 번 생성하고 결과만 보고한다. 기존 Job은 운영자가 상태를 확인한다.
set -euo pipefail
: "${KUBE_CONTEXT:?KUBE_CONTEXT를 명시하세요.}"

portal_wait_job() (
  local name="$1" status failures=0
  for _ in $(seq 180); do
    if status="$(kubectl --context "$KUBE_CONTEXT" -n tailwind-internal get job "$name" \
      -o jsonpath='{.status.succeeded}/{.status.failed}' 2>/dev/null)"; then
      failures=0
      case "$status" in
        1/*) echo "Job 완료: $name"; return 0 ;;
        */[1-9]*)
          # 검사 Job은 곧 자동 삭제되므로 실패 원인을 오류 출력에 함께 남긴다.
          echo "Job 실패: $name" >&2
          kubectl --context "$KUBE_CONTEXT" -n tailwind-internal logs "job/$name" --tail=30 >&2 2>/dev/null || true
          return 1 ;;
      esac
    else
      # API 일시 오류로 대기를 끝내지 않는다. 연속 실패만 조회 불가로 본다.
      failures=$((failures + 1))
      if (( failures >= 6 )); then
        echo "Job 상태 조회 실패: $name. Job은 계속 실행 중일 수 있습니다." >&2
        return 1
      fi
    fi
    sleep 5
  done
  echo "Job 대기 시간 초과: $name" >&2
  return 1
)

portal_permission_check() (
  local check_name="$1" check_phase="$2"
  python3 deploy/portal/scripts/up.py --context "$KUBE_CONTEXT" --render migrate |
    python3 -c '
import json
import sys

job = json.load(sys.stdin)
job["metadata"]["name"] = sys.argv[1]
job["spec"]["backoffLimit"] = 0
# 검사 Job은 결과 확인 뒤 스스로 정리되게 한다. 실패한 검사 Pod가 남아 이후 진단을 흐리지 않는다.
job["spec"]["ttlSecondsAfterFinished"] = 3600
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
    # overlay의 tag auto를 실제 tag로 바꾼 Job을 만든다.
    python3 deploy/portal/scripts/up.py --context "$KUBE_CONTEXT" --render migrate |
      kubectl --context "$KUBE_CONTEXT" create -f -
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
