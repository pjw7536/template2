# 사내 이미지 저장소 설치

[앱 안내](../README.md) · 다음: [운영](02-operations.md)

**목적:** Zot registry를 지정 Worker에 배포하고, 빌드 host의 push와 각 노드의 pull을 확인합니다.
**실행 위치:** 절마다 표시한 호스트. 표시가 없으면 관리 호스트 저장소 루트이며 `kubectl`·`make`는 운영 context `kubernetes-admin@kubernetes`로 실행합니다.

## 0. 먼저 끝나 있어야 하는 일

| 항목 | 확인 방법 | 담당 |
| --- | --- | --- |
| DNS `store.etch.samsungds.net` → APP VIP | 2절 `getent hosts` | 사용자 |
| APP VIP `:443` → Traefik Worker hostPort 443 | 6절 경로 확인 | 인프라 담당자 |
| 공용 Traefik이 운영 중 | `kubectl --context kubernetes-admin@kubernetes -n etch-sso get deployment traefik` | 운영자 |
| 공용 TLS 인증서 | DNS SAN에 `store.etch.samsungds.net`이 포함된 업무 인증서를 [공용 TLS Secret에 등록](../../shared/docs/certificates/apply.md#2-공용-tls-secret-등록갱신--관리-호스트) | 운영자 |
| Worker의 저장 폴더 | 3절 | 사용자(sudo) |

업무 인증서 파일을 사용할 때의 등록 명령입니다. 성공하면 `공용 TLS 등록 완료: store.etch.samsungds.net`이 표시됩니다.

```bash
make ingress-tls-up KUBE_CONTEXT=kubernetes-admin@kubernetes TLS_HOST=store.etch.samsungds.net \
  TLS_CERT_FILE="$PWD/deploy/shared/certs/etch.samsungds.net/fullchain.crt" \
  TLS_KEY_FILE="$PWD/deploy/shared/certs/etch.samsungds.net/private.key"
```

## 1. 입력 확인

[env/k8s.env](../env/k8s.env)를 확인합니다.

| 키 | 의미 |
| --- | --- |
| `NODE_NAME` | registry를 실행할 Worker의 `kubernetes.io/hostname` 값 |
| `REGISTRY_IMAGE` | 사내 ghcr.io 미러의 Zot 고정 tag 이미지 |
| `IMAGE_PULL_SECRET` | Zot 이미지를 받을 때 필요한 pull Secret 이름. 인증이 없으면 비움 |
| `REGISTRY_HOST` | 노드·빌드 host가 접근할 DNS 이름. scheme·포트 없이 입력 |
| `DATA_HOST_PATH` | Worker의 이미지 저장 폴더 |
| `STORAGE_SIZE` | PV/PVC 용량. 디스크 여유에 맞춰 지정 |

조회·검사이며 클러스터를 바꾸지 않습니다.

```bash
make registry-check KUBE_CONTEXT=kubernetes-admin@kubernetes
```

**기대 결과:** `registry 입력·노드·저장소·라우팅 검사 통과. 클러스터를 변경하지 않았습니다.` 처음 설치라면 신규 PV 생성 예정과 namespace 생성 안내가 함께 표시됩니다.
**실패 확인:** 노드 Ready·taint, 기존 PV의 경로·노드, 공용 Traefik과 `REGISTRY_HOST`용 인증서 등록을 확인합니다.

## 2. DNS 확인

**실행 위치:** 관리 호스트, 각 노드, 빌드 host. DNS 등록은 사용자가 합니다. 현재 값은 [네트워크 원본](../../shared/docs/infrastructure/network.md)에서 확인합니다.

```bash
getent hosts store.etch.samsungds.net
```

**기대 결과:** APP VIP `10.172.26.150`이 조회됩니다.

## 3. 저장 폴더 준비

**실행 위치:** `NODE_NAME` Worker(sudo). Zot은 UID·GID 1000으로 실행합니다.

```bash
sudo install -d -o 1000 -g 1000 -m 0750 /appdata/registry
ls -ld /appdata/registry
```

**기대 결과:** `drwxr-x--- ... 1000 1000 ... /appdata/registry`. 기존 폴더가 있으면 내용과 소유자를 먼저 확인하고 덮어쓰지 않습니다.

## 4. namespace와 push 계정 준비

처음 `up`을 실행하면 namespace만 만들고 **실패 종료 코드로 중단**합니다. 계정 Secret이 없을 때의 정상 동작입니다.

```bash
make registry-up KUBE_CONTEXT=kubernetes-admin@kubernetes
```

**기대 결과:** `registry namespace를 만들었습니다. Secret registry-htpasswd을 만든 뒤 up을 다시 실행하세요.`와 make 오류 종료. 배포 기록은 남지 않습니다.

처음 생성할 때는 준비된 push 계정 파일로 bcrypt htpasswd를 만듭니다. 기존 Secret이 있으면 이 단계를 건너뜁니다. `htpasswd`는 사내 Ubuntu 미러의 `apache2-utils`가 제공합니다. Bash에서 실행합니다.

```bash
(
  set -euo pipefail
  source deploy/shared/scripts/env-lib.sh
  load_env deploy/registry/env/push-initial.env
  require_env_keys REGISTRY_USER REGISTRY_PASSWORD
  umask 077
  account_file=$(mktemp)
  trap 'rm -f -- "$account_file"' EXIT
  printf '%s\n' "${ENV_VALUES[REGISTRY_PASSWORD]}" |
    htpasswd -niB "${ENV_VALUES[REGISTRY_USER]}" > "$account_file"
  kubectl --context kubernetes-admin@kubernetes -n registry create secret generic registry-htpasswd --from-file="htpasswd=$account_file"
)
```

**기대 결과:** `secret/registry-htpasswd created`. 빌드 호스트는 같은 push 계정을 사용합니다.

## 5. 배포

변경 명령입니다. PV·PVC·Deployment·Service·Ingress를 적용하고, 공용 Traefik의 감시 namespace에 `registry`를 추가하므로 Traefik이 재기동됩니다.

```bash
make registry-up KUBE_CONTEXT=kubernetes-admin@kubernetes
kubectl --context kubernetes-admin@kubernetes -n registry get pods,pvc -o wide
```

**기대 결과:** `registry 배포 완료: https://store.etch.samsungds.net/v2/`, `배포 기록 저장: registry/deploy-record-registry`, PVC `Bound`, Pod `Running`(노드 `NODE_NAME`).
**실패 확인:** Pod가 재시작하면 저장 폴더 권한(1000:1000)·설정 오류를 확인합니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n registry logs deployment/registry --tail=100
kubectl --context kubernetes-admin@kubernetes -n registry get events --sort-by=.lastTimestamp
```

## 6. 공용 Traefik HTTPS 설정과 접속 경로 확인

### 6-1. 큰 레이어 업로드 시간 반영

공용 Traefik의 HTTPS entrypoint(`websecure`) 읽기 제한은 600초입니다. 현재 서버에 반영됐으면 6-2로 갑니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n etch-sso get deployment traefik \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].args}{"\n"}' \
  | grep -Fc -- '--entrypoints.websecure.transport.respondingTimeouts.readTimeout=600s'
```

결과가 `1`이면 반영된 상태입니다. `0`이면 검사 후 적용합니다. 적용은 Traefik을 재기동하며 기존 감시 namespace·배치는 유지합니다.

```bash
make ingress-check KUBE_CONTEXT=kubernetes-admin@kubernetes
make ingress-up KUBE_CONTEXT=kubernetes-admin@kubernetes
```

**기대 결과:** `공용 Ingress 원본·배치 검사 통과`, `공용 Ingress 준비 완료`. 다시 조회하면 `1`.

### 6-2. 경로 확인

조회 명령입니다. 관리 호스트에서 사내 CA를 신뢰한 상태에서 Traefik 노드 직접 경로와 DNS·VIP 경로를 각각 확인합니다. `--resolve`는 직접 경로에서도 요청 호스트와 TLS 검증 이름을 유지합니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n etch-sso get pods -l app.kubernetes.io/name=traefik -o wide
read -r -p 'Traefik 노드 IP: ' TRAEFIK_NODE_IP
curl -sS -o /dev/null -D - --resolve "store.etch.samsungds.net:443:$TRAEFIK_NODE_IP" \
  https://store.etch.samsungds.net/v2/ | grep -i -E '^HTTP/|^docker-distribution-api-version|^www-authenticate'
curl -sS -o /dev/null -D - https://store.etch.samsungds.net/v2/ \
  | grep -i -E '^HTTP/|^docker-distribution-api-version|^www-authenticate'
```

**기대 결과:** 두 요청 모두 응답 코드가 `200`이거나, `401`이면서 `WWW-Authenticate`에 `realm="registry"`가 보입니다. 둘 다 Zot에 도달했다는 뜻입니다. `Docker-Distribution-Api-Version` 헤더가 함께 보일 수 있습니다.

| 결과 | 원인 |
| --- | --- |
| 첫 요청 `404` | registry Ingress의 호스트·entrypoint와 Traefik의 `registry` namespace 감시 확인 |
| 첫 요청은 성공, 두 번째는 연결 실패·timeout | DNS 또는 APP VIP 443 전달 확인 |
| 첫 요청 연결 거부 | Traefik hostPort 443과 Pod 상태 확인 |
| 인증서 오류 | 공용 TLS 등록·DNS SAN·인증서 체인과 관리 호스트의 사내 CA 확인 |

## 7. 노드와 빌드 호스트의 CA 신뢰

**실행 위치:** registry 이미지를 받을 모든 노드와 빌드 호스트. 각 서버에서 시스템 신뢰 설정으로 HTTPS 연결을 확인합니다.

```bash
curl -sS -o /dev/null -D - https://store.etch.samsungds.net/v2/
```

신뢰 오류가 나면 [Ubuntu 서버·클라이언트 CA 등록](../../shared/docs/certificates/apply.md#ubuntu-서버클라이언트) 절차를 따릅니다. `curl`은 성공하고 `crictl`만 신뢰 오류가 나면 containerd의 해당 호스트 설정에 별도 endpoint나 CA가 지정돼 있는지 확인합니다. CA를 새로 등록한 노드에서 containerd가 이전 신뢰 설정을 사용하면 운영자가 영향을 확인하고 containerd를 재시작합니다.

## 8. push·pull 검증

**빌드 host:** 로그인에는 4절의 계정을 사용합니다.

```bash
sudo nerdctl login store.etch.samsungds.net
sudo nerdctl pull repository.samsungds.net/proxy-docker-registry-1.docker.io/library/busybox:1.37.0
sudo nerdctl tag repository.samsungds.net/proxy-docker-registry-1.docker.io/library/busybox:1.37.0 \
  store.etch.samsungds.net/test/busybox:1.37.0
sudo nerdctl push store.etch.samsungds.net/test/busybox:1.37.0
```

**다른 노드:**

```bash
sudo crictl pull store.etch.samsungds.net/test/busybox:1.37.0
```

**기대 결과:** push와 pull이 모두 성공합니다. 확인 후 [테스트 이미지 삭제](02-operations.md#이미지-삭제와-용량-정리)를 수행하고, [서버 적용 대기 작업](../../shared/docs/infrastructure/pending.md)의 registry 행을 정리합니다.
**실패 확인:** `x509` 오류는 인증서 SAN·CA 신뢰, push 중 `401`은 로그인·Secret, timeout은 6절 경로와 큰 레이어 업로드 시간 설정을 확인합니다.
