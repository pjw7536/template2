# Traefik·VIP 확장

[가이드 홈](../README.md#https인증서) · [ingress 가이드](../../ingress/README.md) · [Traefik 셋업](setup.md) · [Worker 추가](../kubernetes/worker.md) · [운영 기준](operations.md)

**목적:** 운영 중인 공용 Traefik에 등록된 Worker를 backend로 추가해 APP VIP backend를 확장합니다. 적용 전에 현재 Deployment를 백업하고 되돌릴 복구 파일을 만듭니다.
namespace 감시·ServiceAccount와 기존 backend는 그대로 둡니다. Traefik이 아직 없는 클러스터의 설치는 [Traefik 셋업](setup.md)입니다.

backend 변경은 서비스 진입 경로를 바꾸므로 4단계의 적용과 6단계의 복구는 [승인] 단계입니다.

**준비물:** Ready 상태로 등록된 새 Worker([Worker 추가](../kubernetes/worker.md)), 현재 backend 목록([네트워크 원본](../infrastructure/network.md#vipdns접속-경로)과 1단계 조회), 검사할 기존 Ingress의 공개 host·정상 경로.

| 위치 | 작업 |
| --- | --- |
| 관리 호스트 (저장소 루트) | 현재 배치 조회, 백업, 검사·적용·검증·복구 |
| 새 Worker ([노드 명령 실행](../infrastructure/access.md#노드-명령-실행)) | 80/443 점유 확인, Traefik 이미지 접근 확인 |
| LB ([APP VIP와 LB](../infrastructure/access.md#app-vip와-lb)) | 새 Worker IP:443 backend 추가·활성화 |
| 브라우저 ([화면 기능 확인](../infrastructure/access.md#화면-기능-확인)) | 서비스 도메인 HTTPS·로그인 확인 |

Traefik Service는 ClusterIP를 유지하고 LB는 Worker의 hostPort 443으로 연결합니다. 사용자 접속은 관리 호스트나 port-forward를 거치지 않습니다.
이 절차는 Traefik Deployment만 변경하며 Keycloak·Airflow·Headlamp·DB를 재배포하지 않습니다.

**자리표시:** 블록마다 새 셸이므로 값은 각 블록에 직접 씁니다.

| 자리표시 | 값 |
| --- | --- |
| `<IP 목록>` | **유지할 기존 backend IP 전부와 새 Worker IP**를 쉼표로 이은 값. 서로 다른 주소 두 개 이상 |
| `<작업 폴더>` | 백업·복구 파일을 둘 관리 호스트의 새 폴더 절대 경로(저장소 밖). 3·4·6단계에 같은 경로를 씁니다 |
| `<공개 host>`, `<경로>` | 이미 동작하는 Ingress의 host와 정상 응답 경로. 예: Keycloak realm `etch`는 `/realms/etch/.well-known/openid-configuration` |
| `<CA PEM 파일>` | [사내 CA 묶음](../../../README.md#사내-ca-묶음)의 `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem` |
| `<APP VIP 주소>` | [별칭 표](../infrastructure/aliases.json)의 `VIP-APP` |

## 1. 현재 배치 조회 — 관리 호스트

[조회]

```bash
kubectl config get-contexts
kubectl --context "<context>" get nodes -o wide
kubectl --context "<context>" -n etch-sso get pods \
  -l app.kubernetes.io/name=traefik -o wide
kubectl --context "<context>" -n etch-sso get deployment traefik \
  -o jsonpath='{.metadata.annotations.deploy\.tailwind\.local/vip-backends}{"\n"}'
kubectl --context "<context>" -n etch-sso get deployment traefik \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].image}{"\n"}'
make drift-check APP=ingress KUBE_CONTEXT="<context>"
```

**기대 결과:** 새 Worker의 InternalIP가 Ready이고, `kubectl`의 마지막 두 줄에 현재 backend 목록과 Traefik 이미지가 표시됩니다.
backend 목록이 비어 있으면 아직 이 저장소의 VIP 배치 목록이 기록되지 않은 상태입니다. 이때 `<IP 목록>`에는 현재 Traefik Pod가 있는 Worker의 InternalIP와 새 Worker IP를 넣습니다.
새 Worker가 미등록이면 [Worker 추가](../kubernetes/worker.md)를 먼저 마칩니다. 이미 등록된 노드에 join을 반복하지 않습니다.

`drift-check`가 `OK manifest`로 일치를 표시하면 4단계는 배치만 바꿉니다. `DRIFT manifest` 줄이 있으면 4단계가 저장소 원본의 그 차이(이미지·인자 등)도 함께 적용하므로, 그 줄을 4단계의 승인 요청에 포함합니다.

## 2. 새 Worker 진입 조건 확인 — 새 Worker

[변경] 새 Worker에서 포트 점유를 조회하고 Traefik 이미지를 미리 받습니다(이미지만 내려받으며 실행 중인 것은 바꾸지 않습니다). 블록은 관리 호스트의 저장소 밖 파일에 저장해 [노드 명령 실행](../infrastructure/access.md#노드-명령-실행)의 `--script`로 전달하고, `<Traefik 이미지>`는 1단계에서 조회한 이미지입니다.

```bash
sudo ss -lntp '( sport = :80 or sport = :443 )'
sudo crictl --runtime-endpoint unix:///run/containerd/containerd.sock pull <Traefik 이미지>
```

- 다른 프로세스가 80·443을 점유 중이면 그 Worker를 backend에 넣지 않습니다. 프로세스를 종료하지 않고 출력과 함께 보고합니다. Pod의 hostPort 충돌은 4단계의 `ingress-check`가 검사합니다.
- `pull`이 성공해야 새 Worker의 containerd가 Traefik 이미지를 받을 수 있습니다. Docker에만 넣은 이미지는 containerd 실행을 보장하지 않습니다. 실패하면 [파일 반입](../infrastructure/access.md#파일-반입) 절과 노드의 미러 설정을 확인합니다.
- [변경] LB에는 `새 Worker IP:443`을 backend로 준비하되 5단계의 직접 접속 검증이 끝날 때까지 트래픽을 보내지 않도록 비활성 상태로 둡니다. 방법은 [APP VIP와 LB](../infrastructure/access.md#app-vip와-lb) 절입니다.
  이미 등록했다면 새 대상만 비활성화하고 기존 정상 backend는 유지합니다. TCP 443 Health Check와 실패 backend 제외를 설정하며 TLS는 Traefik에서 종료합니다.

## 3. 백업 — 관리 호스트

[변경] 현재 Deployment를 관리 호스트의 작업 폴더에 저장합니다. 클러스터는 바꾸지 않습니다. `before.json`이 이미 있는 폴더에서는 멈추므로 새 폴더 경로를 씁니다.

```bash
set -eu
umask 077
mkdir -p "<작업 폴더>"
test ! -e "<작업 폴더>/before.json"
kubectl --context "<context>" -n etch-sso get deployment traefik -o json > "<작업 폴더>/before.json"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('백업 완료: replicas', d['spec']['replicas'], '/ backend', d['metadata'].get('annotations', {}).get('deploy.tailwind.local/vip-backends', '(기록 없음)'))" "<작업 폴더>/before.json"
```

성공: `백업 완료: replicas <수> / backend <현재 목록>`.

## 4. Traefik만 적용 — 관리 호스트

한 대에서 확장할 때는 기존 Pod 교체로 짧은 접속 중단이 생길 수 있습니다. 무중단을 보장하지 않습니다.

[검사] 새 배치를 검사합니다. IP·Ready·cordon·taint·기존 backend 누락·Pod의 80/443 충돌을 확인하며 클러스터를 바꾸지 않습니다.

```bash
make ingress-check KUBE_CONTEXT="<context>" VIP_BACKENDS=<IP 목록>
```

성공: `공용 Ingress 원본·배치 검사 통과. 클러스터를 변경하지 않았습니다.` 오류가 나면 표시된 노드·IP·포트 문제를 해결하고 다시 검사합니다. 검사가 실패한 상태로 적용하지 않습니다.

[승인] `<IP 목록>`, 아래 변경 내용, 접속 중단 가능성을 보여 주고 승인받은 뒤 적용합니다.

```bash
make ops-deploy APP=ingress KUBE_CONTEXT="<context>" VIP_BACKENDS=<IP 목록>
```

성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. 적용되는 변경은 다음과 같습니다.

- replicas는 backend 수, node affinity는 선택한 Worker 목록
- pod anti-affinity로 노드별 하나씩 배치
- RollingUpdate: `maxSurge=0`, `maxUnavailable=1`
- `deploy.tailwind.local/vip-backends` annotation에 전체 IP 목록 기록

[변경] 적용 직후의 상태로 복구 파일을 만듭니다. 관리 호스트의 작업 폴더에 `after.json`과 `rollback.json`만 쓰며 클러스터는 바꾸지 않습니다. `failedStep`이 `ingress-smoke`여도 실행합니다.

```bash
python3 - "<context>" "<작업 폴더>" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

context, work = sys.argv[1], Path(sys.argv[2])
key = 'deploy.tailwind.local/vip-backends'
path = '/metadata/annotations/' + key.replace('~', '~0').replace('/', '~1')
before = json.loads((work / 'before.json').read_text())
after = json.loads(subprocess.run(
    ['kubectl', '--context', context, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json'],
    check=True, capture_output=True, text=True).stdout)
old = before['metadata'].get('annotations', {}).get(key)
new = after['metadata'].get('annotations', {}).get(key)
if new is None or after['spec'] == before['spec']:
    sys.exit('적용된 변경이 없습니다. 복구 파일을 만들지 않았습니다.')
# 적용 직후의 spec과 VIP 기록이 그대로일 때만 되돌려, 그 뒤의 다른 변경을 덮어쓰지 않는다.
rollback = [
    {'op': 'test', 'path': '/spec', 'value': after['spec']},
    {'op': 'test', 'path': path, 'value': new},
    {'op': 'replace', 'path': '/spec', 'value': before['spec']},
    {'op': 'add', 'path': path, 'value': old} if old is not None else {'op': 'remove', 'path': path},
]
(work / 'after.json').write_text(json.dumps(after, indent=2) + '\n')
(work / 'rollback.json').write_text(json.dumps(rollback, indent=2) + '\n')
print('복구 파일 생성:', work / 'rollback.json')
print('적용 전 backend:', old or '(기록 없음)', '/ 적용 후 backend:', new)
PY
```

성공: `복구 파일 생성: <작업 폴더>/rollback.json`과 적용 전·후 backend 목록. `적용된 변경이 없습니다`면 위 적용이 끝나지 않은 것입니다.

[조회] 배치를 확인합니다.

```bash
kubectl --context "<context>" -n etch-sso get pods \
  -l app.kubernetes.io/name=traefik -o wide
```

**기대 결과:** `<IP 목록>`의 각 Worker에 Traefik이 하나씩 `1/1 Running`입니다.

**실패 확인:**

- `failedStep`이 `ingress-check`면 클러스터는 바뀌지 않았습니다. 표시된 문제를 해결하고 검사부터 다시 실행합니다.
- `failedStep`이 `ingress-up`이면 Pod 상태별 확인은 [Traefik 셋업](setup.md#3-traefik-설치갱신--관리-호스트)의 표를 따릅니다. rollout이 실패한 상태에서는 새 LB backend를 활성화하지 않습니다.
- `failedStep`이 `ingress-smoke`면 Traefik은 적용된 상태이고 관리 호스트에서 Traefik 노드의 443에 닿지 않는 것입니다. 복구 파일을 만든 뒤 [방화벽](../infrastructure/access.md#방화벽) 절로 경로를 확인합니다.
- 동시 변경 오류(`the object has been modified`)는 조회 이후 리소스가 바뀌었다는 뜻입니다. 백업을 보존하고 검사부터 다시 실행합니다.

## 5. Worker 직접 접속 → VIP 순서로 검증

이미 동작하는 Ingress의 도메인·인증서·경로를 사용합니다. OS가 사내 CA를 신뢰하면 `--cacert <CA PEM 파일>`을 생략할 수 있습니다.
`--resolve`는 실제 DNS를 바꾸지 않고 해당 도메인의 TLS·라우팅을 확인합니다.

[조회] `<IP 목록>`의 주소를 공백으로 나눠 `for` 줄에 넣고 모든 Worker에 직접 요청합니다.

```bash
for worker_ip in <Worker IP 1> <Worker IP 2>; do
  curl --fail --show-error --connect-timeout 5 --max-time 20 --cacert <CA PEM 파일> \
    --resolve "<공개 host>:443:$worker_ip" "https://<공개 host><경로>" || echo "실패: $worker_ip"
done
```

성공: Worker마다 정상 응답이 출력되고 `실패:` 줄이 없습니다.

[변경] 모든 요청이 정상이면 LB에서 새 backend를 활성화하고 Health Check가 UP인지 확인합니다. 방법은 [APP VIP와 LB](../infrastructure/access.md#app-vip와-lb) 절입니다.

[조회] 그다음 APP VIP로 검사합니다.

```bash
curl --fail --show-error --connect-timeout 5 --max-time 20 --cacert <CA PEM 파일> \
  --resolve "<공개 host>:443:<APP VIP 주소>" "https://<공개 host><경로>"
```

**실패 확인:** 한 번의 VIP 성공만으로 모든 backend가 정상이라고 판단하지 않고 각 Worker 직접 요청과 LB 상태를 함께 확인합니다.
Ingress가 없는 `/`의 404는 VIP 장애의 근거가 아닙니다.

서비스 도메인의 DNS가 APP VIP를 가리키는지 `getent hosts <공개 host>`로 확인한 뒤 실제 로그인까지 [화면 기능 확인](../infrastructure/access.md#화면-기능-확인) 절의 방법으로 검사합니다.
Keycloak DNS 변경은 별도 전환 작업이며 이 절차에서 변경하지 않습니다.

## 6. 실패 시 복구 — 관리 호스트

새 backend를 이미 활성화했다면 [APP VIP와 LB](../infrastructure/access.md#app-vip와-lb) 절의 방법으로 **추가한 대상만 비활성화**하고 기존 정상 backend를 유지합니다.
Traefik 배치를 되돌려야 하면 4단계의 복구 파일을 사용합니다. 복구 파일은 적용 뒤의 다른 spec 변경을 덮어쓰지 않으며 VIP annotation을 이전 값으로 되돌립니다.

1. [검사] 복구 파일을 서버 dry-run으로 검사합니다.
   ```bash
   kubectl --context "<context>" -n etch-sso patch deployment traefik \
     --type=json --patch-file "<작업 폴더>/rollback.json" --dry-run=server -o name
   ```
   성공: `deployment.apps/traefik`. 실패하면 적용하지 않습니다. 다른 작업이나 admission 정책이 spec을 바꿨다면 복구의 test가 실패합니다. 이때는 멈추고 `<작업 폴더>`의 `before.json`·`after.json`과 현재 Deployment의 차이를 보고합니다. test를 제거해 덮어쓰지 않습니다.
2. [승인] 배치를 이전 상태로 되돌리고 배포 기록을 갱신합니다. 4단계에서 승인받은 backend 변경을 되돌리는 범위입니다.
   ```bash
   kubectl --context "<context>" -n etch-sso patch deployment traefik \
     --type=json --patch-file "<작업 폴더>/rollback.json"
   kubectl --context "<context>" -n etch-sso rollout status deployment/traefik --timeout=600s
   make deploy-record APP=ingress KUBE_CONTEXT="<context>"
   ```
   성공: `deployment.apps/traefik patched`, `deployment "traefik" successfully rolled out`, `배포 기록 저장: etch-sso/deploy-record-ingress`.
3. [조회] 5단계의 Worker 직접 요청을 기존 Worker 주소로 다시 실행하고 APP VIP도 확인합니다.

- `rollout undo`만으로는 replicas와 VIP annotation까지 복구되지 않으므로 위 복구 파일을 사용합니다.
- `make ops-deploy APP=ingress`로는 backend를 줄일 수 없습니다. 도구가 기존 backend 제거를 차단합니다.
- 새 Worker의 drain·삭제·reset은 수행하지 않습니다.

## 7. 완료 기준과 이후 운영

- 새 Worker가 Ready이고 선택한 각 Worker에 Traefik이 하나씩 Ready
- 각 Worker 직접 HTTPS 요청과 APP VIP 요청이 정상
- LB에서 모든 활성 backend가 UP이며 실패 backend 제외 동작 확인
- 사용 도메인의 DNS·인증서·앱 로그인 정상
- 실제 backend 목록으로 [네트워크 원본](../infrastructure/network.md#vipdns접속-경로)의 backend와 확인 상태를 갱신하고 `<작업 폴더>`의 위치를 보고에 남김

VIP 배치 목록은 Deployment annotation에 남으며 `ingress-up`과 앱별 배포 도구가 이를 재사용합니다.
추가 Worker가 생기면 기존 IP 전체와 새 IP를 함께 지정해 이 절차를 반복합니다.
기존 backend의 제거·교체는 LB 전환과 별도 계획이 필요하며 공통 로직도 묵시적인 제거를 차단합니다.
공용 원본 직접 적용 금지는 [운영 기준](operations.md#적용-명령과-주의)을 따릅니다. 새 namespace의 앱(예: Headlamp) 연결은 해당 앱 가이드의 배포 명령을 사용합니다.

공식 참고: [kubectl patch](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_patch/),
[Deployment 업데이트 전략](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).
