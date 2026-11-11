# Traefik·VIP 확장

[가이드 홈](../README.md#https인증서) · [Traefik 셋업](setup.md) · [Worker 추가](../kubernetes/worker.md) · [운영 기준](operations.md)

**목적:** 운영 중인 공용 Traefik Deployment의 이미지·실행 인자·namespace 감시·ServiceAccount를 그대로 두고,
등록된 Worker에 Traefik을 추가 배치해 APP VIP backend를 확장합니다. 적용 전 백업과 복구 파일을 만듭니다.
저장소 원본으로 함께 갱신해도 되면 [Traefik 셋업](setup.md)의 `make ingress-up VIP_BACKENDS=...`를 사용합니다.

**준비물:** Ready 상태로 등록된 새 Worker([Worker 추가](../kubernetes/worker.md)), 현재 backend 목록([네트워크 원본](../infrastructure/network.md#vipdns접속-경로)과 클러스터 조회),
LB 변경을 수행할 인프라 담당자, 검사할 기존 Ingress의 도메인·정상 경로.

| 위치 | 작업 |
| --- | --- |
| CP1 (저장소 루트) | 현재 배치 조회, 백업·변경 파일 생성, 적용·검증·복구 |
| 새 Worker | 80/443 점유 확인, Traefik 이미지 접근 준비 |
| 인프라팀의 LB | 새 Worker IP:443 backend 추가·활성화 |
| 내 PC | 서비스 도메인 HTTPS·로그인 확인 |

Traefik Service는 ClusterIP를 유지하고 LB는 Worker의 hostPort 443으로 연결합니다. 사용자 접속은 CP1이나 port-forward를 거치지 않습니다.
이 절차는 Traefik Deployment만 변경하며 Keycloak·Airflow·Headlamp·DB를 재배포하지 않습니다.

## 1. 현재 배치 조회 — CP1

```bash
kubectl config get-contexts
read -r -p '대상 context 이름: ' VIP_CONTEXT
export VIP_CONTEXT
kubectl --context "$VIP_CONTEXT" get nodes -o wide
kubectl --context "$VIP_CONTEXT" -n etch-sso get pods \
  -l app.kubernetes.io/name=traefik -o wide
kubectl --context "$VIP_CONTEXT" -n etch-sso get deployment traefik \
  -o jsonpath='{.metadata.annotations.deploy\.tailwind\.local/vip-backends}{"\n"}'
kubectl --context "$VIP_CONTEXT" -n etch-sso get deployment traefik \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].image}{"\n"}'
```

**기대 결과:** 새 Worker의 InternalIP가 Ready이고, 마지막 두 줄에 현재 backend 목록과 Traefik 이미지가 표시됩니다.
backend 목록이 비어 있으면 아직 이 저장소의 VIP 배치 목록이 기록되지 않은 상태입니다.
새 Worker가 미등록이면 [Worker 추가](../kubernetes/worker.md)를 먼저 마칩니다. 이미 등록된 노드에 join을 반복하지 않습니다.

## 2. 새 Worker 진입 조건 확인 — 새 Worker·인프라 담당자

```bash
sudo ss -lntp '( sport = :80 or sport = :443 )'
```

- 다른 프로세스가 점유 중이면 담당자와 조정하며 자동으로 종료하지 않습니다. Pod의 hostPort 충돌은 3단계의 공통 로직이 검사합니다.
- 1단계의 Traefik 이미지를 새 Worker의 containerd에서 받을 수 있도록 준비합니다. Docker에만 넣은 이미지는 containerd 실행을 보장하지 않습니다.
- 인프라팀에는 `새 Worker IP:443`을 backend로 준비하되 직접 접속 검증이 끝날 때까지 트래픽을 보내지 않도록 요청합니다.
  이미 등록했다면 새 대상만 비활성화하고 기존 정상 backend는 유지합니다. TCP 443 Health Check와 실패 backend 제외를 설정하며 TLS는 Traefik에서 종료합니다.

## 3. 백업과 변경 파일 생성 — CP1

`VIP_BACKENDS`에는 **유지할 기존 backend IP 전부와 새 Worker IP**를 쉼표로 구분해 넣습니다.

```bash
read -r -p '유지할 전체 Backend IP 목록(쉼표 구분): ' VIP_BACKENDS
export VIP_BACKENDS
umask 077
export VIP_WORKDIR="$(mktemp -d /tmp/traefik-vip.XXXXXX)"
printf '백업·변경 파일 위치: %s\n' "$VIP_WORKDIR"

kubectl --context "$VIP_CONTEXT" -n etch-sso get deployment traefik -o json > "$VIP_WORKDIR/before.json"
kubectl --context "$VIP_CONTEXT" get nodes -o json > "$VIP_WORKDIR/nodes.json"
kubectl --context "$VIP_CONTEXT" get pods -A -o json > "$VIP_WORKDIR/pods.json"
```

아래 블록은 파일만 생성하며 클러스터에 적용하지 않습니다. 현재 Deployment를 기준으로 배치 설정만 계산하고,
공통 `routing.py`가 IP·Ready·cordon·taint·기존 backend 누락·Pod의 80/443 충돌을 검사합니다.
별도의 nodeSelector·affinity 정책이 있다면 생성 파일에서 대체되는 범위를 운영 정책과 먼저 맞춥니다.

```bash
python3 - <<'PY'
import importlib.util
import json
import os
from pathlib import Path

work = Path(os.environ['VIP_WORKDIR'])
spec = importlib.util.spec_from_file_location('routing', 'deploy/shared/ingress/routing.py')
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)
read = lambda name: json.loads((work / name).read_text())
before = read('before.json')
ips = routing.vip_backend_ips(os.environ['VIP_BACKENDS'], before)
after = routing.place_vip_backends(before, before, ips, read('nodes.json')['items'], read('pods.json')['items'])
patch = [
    {'op': 'test', 'path': '/metadata/resourceVersion', 'value': before['metadata']['resourceVersion']},
    {'op': 'replace', 'path': '/spec', 'value': after['spec']},
    {'op': 'add', 'path': '/metadata/annotations', 'value': after['metadata']['annotations']},
]
# 복구 시 다른 운영자의 spec 변경을 덮어쓰지 않으며 VIP annotation만 복원합니다.
key = '/metadata/annotations/deploy.tailwind.local~1vip-backends'
rollback = [
    {'op': 'test', 'path': '/spec', 'value': after['spec']},
    {'op': 'test', 'path': key, 'value': ','.join(ips)},
    {'op': 'replace', 'path': '/spec', 'value': before['spec']},
]
old = before['metadata'].get('annotations', {}).get(routing.VIP_BACKENDS)
rollback.append({'op': 'add', 'path': key, 'value': old} if old is not None else {'op': 'remove', 'path': key})
for name, value in [('desired.json', after), ('patch.json', patch), ('rollback.json', rollback)]:
    (work / name).write_text(json.dumps(value, indent=2) + '\n')
print('검사 완료. 배치할 Traefik 수:', after['spec']['replicas'])
print('변경 파일:', work / 'patch.json')
PY

diff -u "$VIP_WORKDIR/before.json" "$VIP_WORKDIR/desired.json"
```

**기대 결과:** `검사 완료`가 표시됩니다. `diff`는 차이가 있으면 종료 코드 1을 반환하며 정상입니다. 다음 변경만 있는지 확인합니다.

- replicas는 backend 수, node affinity는 선택한 Worker 목록
- pod anti-affinity로 노드별 하나씩 배치
- RollingUpdate: `maxSurge=0`, `maxUnavailable=1`
- `deploy.tailwind.local/vip-backends` annotation에 전체 IP 목록 기록

**실패 확인:** 검사 오류가 나면 표시된 노드·IP·포트 문제를 해결하고 3단계를 새 작업 디렉터리로 다시 실행합니다.

## 4. Traefik만 적용 — CP1

한 대에서 확장할 때는 기존 Pod 교체로 짧은 접속 중단이 생길 수 있으므로 작업 시간을 잡습니다. 무중단을 보장하지 않습니다.
별도의 자동 배포가 같은 Deployment를 수정 중이면 먼저 작업을 조정합니다.

```bash
kubectl --context "$VIP_CONTEXT" -n etch-sso patch deployment traefik \
  --type=json --patch-file "$VIP_WORKDIR/patch.json" --dry-run=server -o name

kubectl --context "$VIP_CONTEXT" -n etch-sso patch deployment traefik \
  --type=json --patch-file "$VIP_WORKDIR/patch.json"

kubectl --context "$VIP_CONTEXT" -n etch-sso rollout status deployment/traefik --timeout=600s
kubectl --context "$VIP_CONTEXT" -n etch-sso get pods \
  -l app.kubernetes.io/name=traefik -o wide
```

**기대 결과:** `VIP_BACKENDS`의 각 Worker에 Traefik이 하나씩 `1/1 Running`입니다.

**실패 확인:**

- dry-run이 실패하면 실제 적용하지 않습니다. resourceVersion 검사 실패는 조회 이후 리소스가 바뀌었다는 뜻이며, 기존 백업을 보존한 채 3단계를 새 작업 디렉터리로 다시 실행합니다. 검사 항목을 삭제해 강행하지 않습니다.
- Pod 상태별 확인은 [Traefik 셋업](setup.md#3-traefik-설치갱신--cp1)의 표를 따릅니다.
- rollout이 실패한 상태에서는 새 LB backend를 활성화하지 않습니다.

## 5. Worker 직접 접속 → VIP 순서로 검증

이미 동작하는 Ingress의 도메인·인증서·경로를 사용합니다. 사내 CA가 신뢰 저장소에 없으면 curl에 `--cacert /실제/사내-ca.pem`을 추가합니다.
`--resolve`는 실제 DNS를 바꾸지 않고 해당 도메인의 TLS·라우팅을 확인합니다.

```bash
read -r -p '검사할 공개 도메인: ' INGRESS_HOST
read -r -p '정상 응답을 확인할 경로(/로 시작): ' CHECK_PATH
for worker_ip in ${VIP_BACKENDS//,/ }; do
  curl --fail --show-error --connect-timeout 5 --max-time 20 \
    --resolve "$INGRESS_HOST:443:$worker_ip" "https://$INGRESS_HOST$CHECK_PATH"
done
```

예: Keycloak realm `etch`의 경로는 `/realms/etch/.well-known/openid-configuration`입니다.

모든 요청이 정상이면 인프라팀이 새 backend를 활성화하고 Health Check가 UP인지 확인합니다. 그다음 APP VIP로 검사합니다.

```bash
read -r -p 'APP VIP: ' APP_VIP
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --resolve "$INGRESS_HOST:443:$APP_VIP" "https://$INGRESS_HOST$CHECK_PATH"
```

**실패 확인:** 한 번의 VIP 성공만으로 모든 backend가 정상이라고 판단하지 않고 각 Worker 직접 요청과 LB 상태를 함께 확인합니다.
Ingress가 없는 `/`의 404는 VIP 장애의 근거가 아닙니다.

서비스 도메인의 DNS가 APP VIP를 가리키는지 확인한 뒤 PC 브라우저에서 실제 로그인까지 검사합니다.
Keycloak DNS 변경은 별도 전환 작업이며 이 절차에서 변경하지 않습니다.

## 6. 실패 시 복구 — 인프라 담당자·CP1

새 backend를 이미 활성화했다면 인프라팀에서 **추가한 대상만 비활성화**하고 기존 정상 backend를 유지합니다.
Traefik 배치를 되돌려야 하면 3단계의 복구 파일을 사용합니다. 복구 파일은 다른 운영자의 spec 변경을 덮어쓰지 않으며 VIP annotation을 이전 값으로 되돌립니다.

```bash
kubectl --context "$VIP_CONTEXT" -n etch-sso patch deployment traefik \
  --type=json --patch-file "$VIP_WORKDIR/rollback.json" --dry-run=server -o name

kubectl --context "$VIP_CONTEXT" -n etch-sso patch deployment traefik \
  --type=json --patch-file "$VIP_WORKDIR/rollback.json"

kubectl --context "$VIP_CONTEXT" -n etch-sso rollout status deployment/traefik --timeout=600s
```

- dry-run이 실패하면 적용하지 않습니다. 다른 작업이나 admission 정책이 spec을 변경했다면 복구의 test가 실패하며, 현재 설정과 백업을 비교해 조정합니다. test를 제거해 덮어쓰지 않습니다.
- `rollout undo`만으로는 replicas와 VIP annotation까지 복구되지 않으므로 위 복구 파일을 사용합니다.
- 복구 뒤 기존 Worker 직접 HTTPS 접속과 VIP를 다시 확인합니다. 새 Worker의 drain·삭제·reset은 수행하지 않습니다.

## 7. 완료 기준과 이후 운영

- 새 Worker가 Ready이고 선택한 각 Worker에 Traefik이 하나씩 Ready
- 각 Worker 직접 HTTPS 요청과 APP VIP 요청이 정상
- LB에서 모든 활성 backend가 UP이며 실패 backend 제외 동작 확인
- 사용 도메인의 DNS·인증서·앱 로그인 정상
- 백업·변경 파일과 실제 backend 목록을 운영 기록에 보관하고 [네트워크 원본](../infrastructure/network.md#vipdns접속-경로)의 backend 확인 상태를 갱신

VIP 배치 목록은 Deployment annotation에 남으며 `ingress-up`과 앱별 배포 도구가 이를 재사용합니다.
추가 Worker가 생기면 기존 IP 전체와 새 IP를 함께 지정해 이 절차를 반복합니다.
기존 backend의 제거·교체는 LB 전환과 별도 계획이 필요하며 공통 로직도 묵시적인 제거를 차단합니다.
공용 원본 직접 적용 금지는 [운영 기준](operations.md#적용-명령과-주의)을 따릅니다. 새 namespace의 앱(예: Headlamp) 연결은 해당 앱 문서의 배포 명령을 사용합니다.

공식 참고: [kubectl patch](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_patch/),
[Deployment 업데이트 전략](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).
