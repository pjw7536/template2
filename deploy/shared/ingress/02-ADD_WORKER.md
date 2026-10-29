# Traefik·APP VIP의 Worker 확장 상세

[공용 Ingress 안내](README.md) · [APP VIP와 앱 HTTPS 연결](01-VIP.md)

공통 진입점 설치는 [02. Traefik 셋업](../docs/kubernetes/02-traefik.md),
새 서버의 클러스터 가입은 [03. Worker 추가](../docs/kubernetes/03-worker.md)에서 시작합니다.
이 문서는 **등록된 Worker에 Traefik을 추가 배치하고 APP VIP Backend를 확장하는 상세 절차**입니다.
기존 배치 백업·개별 Worker HTTPS 검증·LB 활성화·복구가 필요한 경우 사용합니다.

## 어디에서 무엇을 하나요?

| 위치 | 작업 |
| --- | --- |
| 새 Worker | OS·containerd·kubelet 준비, 클러스터 조인, 포트·이미지 다운로드 확인 |
| CP1 | kubectl로 노드 확인, 기존 Traefik 백업·배치 변경·검증 |
| 인프라팀의 LB | 새 Worker IP:443을 APP VIP Backend에 추가·활성화 |
| 내 PC | 서비스 도메인으로 HTTPS 접속 확인 |

```text
PC → 업무 도메인 → APP VIP 10.172.26.150:443
                       ├─ 기존 Worker:443 → Traefik ─┐
                       └─ 새 Worker:443   → Traefik ─┤→ 앱 Service → 앱 Pod
```

CP1은 명령 실행 위치입니다. 사용자 접속은 CP1이나 port-forward를 거치지 않습니다.
Traefik Service는 ClusterIP를 유지합니다. LB는 Worker의 hostPort 443으로 연결합니다.
이 절차는 기존 Traefik Deployment만 변경하며 Keycloak·Airflow·Headlamp·DB를 재배포하지 않습니다.

## 1. 현재 값과 목표 확인 — CP1

[클러스터 구성 확인](../docs/infrastructure/cluster.md)에 따라 현재 노드·VIP·Backend를 조회합니다.
추가할 Worker의 실제 InternalIP를 확인하고 이미 등록된 노드에 join을 반복하지 않습니다.
기존 Backend와 현재 Traefik 배치를 보존한 상태에서 추가할 범위를 정합니다.

서버의 저장소 루트에서 시작합니다. `deploy/shared/ingress/routing.py`가 필요합니다.
이 문서의 변경을 서버로 전달한 뒤 실행하며, 실제 설정은 Git에 넣지 않습니다.

```bash
kubectl config get-contexts
read -r -p '대상 context 이름: ' VIP_CONTEXT
export VIP_CONTEXT
kubectl --context "$VIP_CONTEXT" get nodes -o wide
kubectl --context "$VIP_CONTEXT" -n etch-sso get pods \
  -l app.kubernetes.io/name=traefik -o wide
kubectl --context "$VIP_CONTEXT" -n etch-sso get deployment traefik \
  -o jsonpath='{.metadata.annotations.deploy\.tailwind\.local/vip-backends}{"\n"}'
```

마지막 출력이 비어 있으면 아직 이 저장소의 VIP 배치 목록이 기록되지 않은 상태입니다.
예시의 새 Worker가 이미 Ready라면 2단계의 조인은 건너뜁니다.

## 2. 새 Worker를 Kubernetes에 등록 — 인프라 담당자·새 Worker

미등록 서버는 [03. Worker 추가](../docs/kubernetes/03-worker.md)의 준비·가입·검증을 먼저 마칩니다.
이미 등록된 노드에는 join을 반복하지 않습니다.
`kubectl --context "$VIP_CONTEXT" get nodes -o wide`에서 새 Worker의 InternalIP·Ready를 확인한 뒤 3단계로 이동합니다.

## 3. 새 Worker의 진입 조건 확인

새 Worker에서 OS 프로세스의 포트 점유를 확인합니다.

```bash
sudo ss -lntp '( sport = :80 or sport = :443 )'
```

Nginx 등 다른 프로세스가 점유 중이면 담당자와 조정합니다. 자동으로 종료하지 않습니다.

hostPort는 네트워크 규칙으로 구현될 수 있습니다. 따라서 ss 결과가 비어 있어도 Traefik이 실행 중일 수 있습니다.
Kubernetes Pod의 포트 충돌은 다음 단계의 공통 로직이 검사합니다.

CP1에서 현재 Traefik 이미지를 확인하고 새 Worker의 containerd에서도 같은 이미지를 받을 수 있도록 준비합니다.
Docker에만 이미지를 넣어 두는 것으로는 containerd에서의 실행을 보장하지 않습니다.

```bash
kubectl --context "$VIP_CONTEXT" -n etch-sso get deployment traefik \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].image}{"\n"}'
```

인프라팀에는 `새 Worker IP:443`을 Backend에 준비하되, 직접 접속 검증이 끝날 때까지 트래픽을 보내지 않도록 요청합니다.
이미 Backend에 등록했다면 검증 전에는 새 대상만 비활성화합니다. 기존 정상 Backend는 유지합니다.
TCP 443 Health Check와 실패 Backend 제외를 설정하며 TLS는 기존 Traefik에서 종료합니다.

## 4. 기존 설정 백업과 변경 파일 생성 — CP1

`VIP_BACKENDS`에는 **새 Worker뿐 아니라 유지할 기존 Backend IP 전부**를 넣습니다.
현재 정상 Backend 전체와 추가할 Worker의 실제 IP를 쉼표로 구분합니다.

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

아래 블록은 파일만 생성합니다. 클러스터에는 아직 적용하지 않습니다.
현재 이미지·실행 인자·namespace 감시·ServiceAccount를 그대로 유지하고 배치 설정만 계산합니다.
공통 `routing.py`가 IP·Ready·cordon·taint·기존 Backend 누락·Pod의 80/443 충돌을 검사합니다.

현재 별도의 nodeSelector·affinity 정책이 있다면 생성 파일에서 대체되는 범위를 확인하고 운영 정책과 먼저 맞춥니다.

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

`diff`는 차이가 있으면 종료 코드 1을 반환하며 이는 정상입니다. 다음 변경만 있는지 확인합니다.

- replicas는 Backend 수, node affinity는 선택한 Worker 목록
- pod anti-affinity로 노드별 하나씩 배치
- RollingUpdate: `maxSurge=0`, `maxUnavailable=1`
- `deploy.tailwind.local/vip-backends` annotation에 전체 IP 목록 기록

## 5. Traefik만 적용 — CP1

처음 한 대에서 확장할 때는 기존 Pod 교체로 짧은 접속 중단이 생길 수 있으므로 작업 시간을 잡습니다.
무중단을 보장하는 절차는 아닙니다. 별도의 자동 배포가 같은 Deployment를 수정 중이면 먼저 작업을 조정합니다.

```bash
kubectl --context "$VIP_CONTEXT" -n etch-sso patch deployment traefik \
  --type=json --patch-file "$VIP_WORKDIR/patch.json" --dry-run=server -o name

kubectl --context "$VIP_CONTEXT" -n etch-sso patch deployment traefik \
  --type=json --patch-file "$VIP_WORKDIR/patch.json"

kubectl --context "$VIP_CONTEXT" -n etch-sso rollout status deployment/traefik --timeout=600s
kubectl --context "$VIP_CONTEXT" -n etch-sso get pods \
  -l app.kubernetes.io/name=traefik -o wide
```

dry-run이 실패하면 실제 적용하지 않습니다. resourceVersion 검사 실패는 조회 이후 리소스가 바뀌었다는 뜻입니다.
기존 백업을 보존한 채 4단계에서 새 작업 디렉터리를 만들어 다시 확인하며, 검사 항목을 삭제해 강행하지 않습니다.

예시에서는 `khplane01w09`와 `khplanew01`에 각각 하나씩 `1/1 Running`이어야 합니다.

| 상태 | 먼저 확인할 내용 |
| --- | --- |
| Pending | `kubectl describe pod`의 이벤트 |
| ImagePullBackOff | 해당 노드의 이미지 미러·인증 |
| Ready 실패 | Pod 로그와 CNI 연결 |

rollout이 실패한 상태에서는 새 LB Backend를 활성화하지 않습니다.

## 6. Worker 직접 접속 → VIP 순서로 검증

이미 동작하는 Ingress의 도메인·인증서·경로를 사용합니다. 아래는 기존 Keycloak realm이 `etch`인 환경의 예시입니다.
실제 realm이 다르면 경로를 바꾸고, 사내 CA가 PC/서버에 설치되지 않았다면 curl에 `--cacert /실제/사내-ca.pem`을 추가합니다.

```bash
export INGRESS_HOST='etch-sso.samsungds.net'
export CHECK_PATH='/realms/etch/.well-known/openid-configuration'

curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --resolve "$INGRESS_HOST:443:10.172.40.87" "https://$INGRESS_HOST$CHECK_PATH"
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --resolve "$INGRESS_HOST:443:10.172.40.117" "https://$INGRESS_HOST$CHECK_PATH"
```

두 요청 모두 정상 응답이면 인프라팀이 새 Backend를 활성화하고 Health Check가 UP인지 확인합니다.
그 뒤 같은 경로를 APP VIP로 검사합니다. `--resolve`는 실제 DNS를 바꾸지 않고 해당 도메인의 TLS·라우팅을 확인합니다.

```bash
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --resolve "$INGRESS_HOST:443:10.172.26.150" "https://$INGRESS_HOST$CHECK_PATH"
```

새 Worker IP는 실제 추가한 IP로 바꿉니다. 한 번의 VIP 요청 성공만으로 두 Backend가 모두 정상이라고 판단하지 않습니다.
각 Worker 직접 요청과 LB 상태를 함께 확인합니다. Ingress가 없는 `/`의 404는 VIP 장애의 근거가 아닙니다.

사용할 서비스 도메인의 DNS가 APP VIP를 가리키는지 확인한 뒤 PC 브라우저에서도 실제 로그인까지 검사합니다.
기존 Keycloak DNS 변경은 별도 전환 작업이며 이 가이드에서 자동 변경하지 않습니다.

## 7. 실패 시 복구

새 Backend를 이미 활성화했다면 인프라팀에서 **추가한 대상만 비활성화**하고 기존 정상 Backend를 유지합니다.
Traefik 배치를 이전 상태로 돌려야 한다면 4단계의 백업·복구 파일을 사용합니다.

```bash
kubectl --context "$VIP_CONTEXT" -n etch-sso patch deployment traefik \
  --type=json --patch-file "$VIP_WORKDIR/rollback.json" --dry-run=server -o name

kubectl --context "$VIP_CONTEXT" -n etch-sso patch deployment traefik \
  --type=json --patch-file "$VIP_WORKDIR/rollback.json"

kubectl --context "$VIP_CONTEXT" -n etch-sso rollout status deployment/traefik --timeout=600s
```

dry-run이 실패하면 적용하지 않습니다. 다른 작업이나 admission 정책이 spec을 변경했다면 복구의 test가 실패합니다.
현재 설정과 백업을 비교해 조정하며 test를 제거해 덮어쓰지 않습니다.

`rollout undo`만으로는 replicas와 VIP annotation까지 복구되지 않으므로 위 복구 파일을 사용합니다.
복구 뒤 기존 Worker 직접 HTTPS 접속과 VIP를 다시 확인합니다. 새 Worker의 drain·삭제·reset은 수행하지 않습니다.

## 8. 이후 재배포와 Headlamp 연결

VIP 배치 목록은 Deployment annotation에 남으며 기존 앱별 배포 도구가 이를 재사용합니다.
추가 Worker가 생기면 이 절차를 반복하면서 기존 IP 전체와 새 IP를 함께 지정합니다.
기존 Backend의 제거·교체는 LB 전환과 별도 계획이 필요하며 공통 로직도 묵시적인 제거를 차단합니다.

`kubectl apply -k deploy/shared/ingress` 또는 Keycloak 정적 YAML 직접 적용은 단일 Worker 기본값을 덮어쓸 수 있으므로 사용하지 않습니다.
이 절차에서는 Airflow까지 배포하는 `make server-up`도 실행할 필요가 없습니다.

Headlamp를 사용하려면 VIP 연결에 더해 공개 도메인 또는 경로, TLS Secret, Ingress,
Traefik의 `headlamp` namespace 감시·RBAC를 별도로 준비합니다.

현재 Headlamp 배포 도구는 운영 env로 `/headlamp` HTTPS 경로와 Keycloak 로그인을 구성합니다.
[Headlamp 운영 안내](../../headlamp/README.md)에 따라 TLS·OIDC Secret·CA와 제어면 인증을 준비하고 앱별 배포 명령을 사용합니다.

## 완료 기준

- 새 Worker가 Ready이고 선택한 각 Worker에 Traefik이 하나씩 Ready
- 각 Worker 직접 HTTPS 요청과 APP VIP 요청이 정상
- LB에서 모든 활성 Backend가 UP이며 실패 Backend 제외 동작 확인
- 사용 도메인의 DNS·인증서·앱 로그인 정상
- 백업·변경 파일과 실제 Backend 목록을 운영 기록에 보관

공식 참고: [kubectl patch](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_patch/),
[Deployment 업데이트 전략](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).
