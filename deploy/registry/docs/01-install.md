# 사내 이미지 저장소 설치

[앱 안내](../README.md) · 다음: [운영](02-operations.md)

**목적:** Zot registry를 지정 Worker에 배포하고, 빌드 host의 push와 각 노드의 pull을 확인합니다.
**실행 위치:** 절마다 표시한 호스트. 표시가 없으면 관리 호스트 저장소 루트이며 `kubectl`·`make`는 운영 context `kubernetes-admin@kubernetes`로 실행합니다.

## 0. 먼저 끝나 있어야 하는 일

| 항목 | 확인 방법 | 담당 |
| --- | --- | --- |
| DNS `registry.etch.samsungds.net` → APP VIP | 2절 `getent hosts` | 사용자 |
| APP VIP의 **HTTP 80** 전달: VIP `:80` → Traefik이 실행되는 Worker의 hostPort 80 | 6절 경로 확인. 현재 기록된 VIP 설정은 `:443`뿐이며 80 전달은 [미확인](../../shared/docs/infrastructure/network.md#vip와-backend) | 인프라 담당자 |
| 공용 Traefik이 운영 중 | `kubectl --context kubernetes-admin@kubernetes -n etch-sso get deployment traefik` | 운영자 |
| Worker의 저장 폴더 | 3절 | 사용자(sudo) |

VIP 80 전달이 없으면 배포는 성공해도 노드·빌드 host에서 DNS 이름으로 접속할 수 없습니다. 인프라 담당자에게 VIP `10.172.26.150:80`을 Traefik backend의 80 포트로 전달하도록 요청합니다.

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
**실패 확인:** 노드 Ready·taint, 기존 PV의 경로·노드, 공용 Traefik 존재를 확인합니다.

## 2. DNS 확인

**실행 위치:** 관리 호스트, 각 노드, 빌드 host. DNS 등록은 사용자가 합니다. 현재 값은 [네트워크 원본](../../shared/docs/infrastructure/network.md)에서 확인합니다.

```bash
getent hosts registry.etch.samsungds.net
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

push 계정은 bcrypt htpasswd로 만듭니다. 비밀번호를 두 번 입력하므로 사람이 실행합니다. `htpasswd`가 없으면 사내 Ubuntu 미러에서 `apache2-utils`를 설치합니다.

```bash
read -r -p 'push 계정 이름: ' REGISTRY_USER
htpasswd -nB "$REGISTRY_USER" > /tmp/registry-htpasswd
kubectl --context kubernetes-admin@kubernetes -n registry create secret generic registry-htpasswd \
  --from-file=htpasswd=/tmp/registry-htpasswd
shred -u /tmp/registry-htpasswd
kubectl --context kubernetes-admin@kubernetes -n registry get secret registry-htpasswd
```

**기대 결과:** `registry-htpasswd   Opaque   1`. 비밀번호는 문서·저장소에 기록하지 않고 운영자 보관 위치에만 둡니다.

## 5. 배포

변경 명령입니다. PV·PVC·Deployment·Service·Ingress를 적용하고, 공용 Traefik의 감시 namespace에 `registry`를 추가하므로 Traefik이 재기동됩니다.

```bash
make registry-up KUBE_CONTEXT=kubernetes-admin@kubernetes
kubectl --context kubernetes-admin@kubernetes -n registry get pods,pvc -o wide
```

**기대 결과:** `registry 배포 완료: http://registry.etch.samsungds.net/v2/`, `배포 기록 저장: registry/deploy-record-registry`, PVC `Bound`, Pod `Running`(노드 `NODE_NAME`).
**실패 확인:** Pod가 재시작하면 저장 폴더 권한(1000:1000)·설정 오류를 확인합니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n registry logs deployment/registry --tail=100
kubectl --context kubernetes-admin@kubernetes -n registry get events --sort-by=.lastTimestamp
```

## 6. 공용 Traefik HTTP 설정과 접속 경로 확인

### 6-1. 큰 레이어 업로드 시간 반영

공용 Traefik의 HTTP entrypoint 읽기 제한을 600초로 늘린 설정은 `ingress-up`을 실행해야 서버에 반영됩니다. 이미 반영됐으면 6-2로 갑니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n etch-sso get deployment traefik \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].args}{"\n"}' | grep -c 'readTimeout=600s'
```

결과가 `1`이면 반영된 상태입니다. `0`이면 검사 후 적용합니다. 적용은 Traefik을 재기동하며 기존 감시 namespace·배치는 유지합니다.

```bash
make ingress-check KUBE_CONTEXT=kubernetes-admin@kubernetes
make ingress-up KUBE_CONTEXT=kubernetes-admin@kubernetes
```

**기대 결과:** `공용 Ingress 원본·배치 검사 통과`, `공용 Ingress 준비 완료`. 다시 조회하면 `1`.

### 6-2. 경로 확인

조회 명령입니다. Traefik이 실행되는 노드 IP를 확인한 뒤, 그 노드로 직접 보낸 요청과 DNS 이름 요청이 모두 Zot에 닿는지 봅니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n etch-sso get pods -l app.kubernetes.io/name=traefik -o wide
curl -sS -o /dev/null -D - -H 'Host: registry.etch.samsungds.net' http://<Traefik 노드 IP>/v2/ | grep -i -E '^HTTP/|^docker-distribution-api-version|^www-authenticate'
curl -sS -o /dev/null -D - http://registry.etch.samsungds.net/v2/ | grep -i -E '^HTTP/|^docker-distribution-api-version|^www-authenticate'
```

**기대 결과:** 두 요청 모두 응답 코드가 `200`이거나, `401`이면서 `WWW-Authenticate`에 `realm="registry"`가 보입니다. 둘 다 Zot에 도달했다는 뜻입니다. `Docker-Distribution-Api-Version` 헤더가 함께 보일 수 있습니다.

| 결과 | 원인 |
| --- | --- |
| 첫 요청 `404`, `realm="registry"` 없음 | Traefik이 `registry` namespace를 감시하지 않음. 5절 재실행 |
| 첫 요청은 성공, 두 번째는 연결 실패·timeout | DNS 또는 APP VIP 80 전달 미설정(0절) |
| 첫 요청 연결 거부 | Traefik hostPort 80 미기동. `ingress-up` 상태 확인 |

## 7. 노드와 빌드 host의 HTTP 허용

**실행 위치:** registry 이미지를 받을 **모든 노드**와 **빌드 host**(sudo). containerd는 기본적으로 HTTPS만 사용합니다. 각 서버에서 한 번 수행합니다.

1. containerd가 hosts 디렉터리를 읽는지 확인합니다.

   ```bash
   sudo containerd config dump | grep -n config_path
   ```

   `config_path`에 `/etc/containerd/certs.d`가 포함돼 있으면 2번으로 갑니다. 없으면 `/etc/containerd/config.toml`의 CRI registry 절에 `config_path = "/etc/containerd/certs.d"`를 추가합니다.
   containerd 1.x는 `[plugins."io.containerd.grpc.v1.cri".registry]`, 2.x는 `[plugins."io.containerd.cri.v1.images".registry]`입니다.
   추가한 경우에만 `sudo systemctl restart containerd`를 실행하고 관리 호스트에서 `kubectl --context kubernetes-admin@kubernetes get nodes`로 Ready를 확인합니다.

2. registry 주소의 HTTP 사용을 등록합니다.

   ```bash
   sudo install -d -m 0755 /etc/containerd/certs.d/registry.etch.samsungds.net
   sudo tee /etc/containerd/certs.d/registry.etch.samsungds.net/hosts.toml >/dev/null <<'EOF'
   server = "http://registry.etch.samsungds.net"

   [host."http://registry.etch.samsungds.net"]
     capabilities = ["pull", "resolve", "push"]
   EOF
   ```

   hosts 파일 변경은 containerd 재시작 없이 다음 pull부터 적용됩니다.

## 8. push·pull 검증

**빌드 host:** nerdctl은 `--insecure-registry`로 HTTP를 허용합니다. 로그인에는 4절의 계정을 사용합니다.

```bash
sudo nerdctl --insecure-registry login registry.etch.samsungds.net
sudo nerdctl pull repository.samsungds.net/proxy-docker-registry-1.docker.io/library/busybox:1.37.0
sudo nerdctl tag repository.samsungds.net/proxy-docker-registry-1.docker.io/library/busybox:1.37.0 \
  registry.etch.samsungds.net/test/busybox:1.37.0
sudo nerdctl --insecure-registry push registry.etch.samsungds.net/test/busybox:1.37.0
```

**다른 노드:**

```bash
sudo crictl pull registry.etch.samsungds.net/test/busybox:1.37.0
```

**기대 결과:** push와 pull이 모두 성공합니다. 확인 후 [테스트 이미지 삭제](02-operations.md#이미지-삭제와-용량-정리)를 수행하고, [서버 적용 대기 작업](../../shared/docs/infrastructure/pending.md)의 registry 행을 정리합니다.
**실패 확인:** `http: server gave HTTP response to HTTPS client`는 7절 hosts 설정 누락, `401`은 로그인·Secret, timeout은 6-2 경로, 큰 이미지 push 도중 끊김은 6-1 미반영을 확인합니다.
