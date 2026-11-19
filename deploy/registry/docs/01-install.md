# 사내 이미지 저장소 설치

[앱 안내](../README.md) · 다음: [운영](02-operations.md)

**목적:** Zot registry를 지정 Worker에 배포하고, 빌드 host의 push와 각 노드의 pull을 확인합니다.
**실행 위치:** 절마다 표시한 호스트. `kubectl` 명령은 관리 호스트 저장소 루트에서 운영 context로 실행합니다.

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

```bash
make registry-check KUBE_CONTEXT=kubernetes-admin@kubernetes
```

**기대 결과:** `registry 입력·노드·저장소·라우팅 검사 통과`. 처음 설치라면 신규 PV 생성 예정과 namespace 생성 안내가 표시됩니다.

## 2. DNS 등록

`REGISTRY_HOST`를 공용 APP VIP에 연결합니다. 현재 값은 [네트워크 원본](../../shared/docs/infrastructure/network.md)에서 확인합니다.

```bash
getent hosts registry.etch.samsungds.net
```

**기대 결과:** 노드와 빌드 host에서 APP VIP 주소가 조회됩니다.

## 3. 저장 폴더 준비

**실행 위치:** `NODE_NAME` Worker. Zot은 UID·GID 1000으로 실행합니다.

```bash
sudo install -d -o 1000 -g 1000 -m 0750 /appdata/registry
ls -ld /appdata/registry
```

기존 폴더가 있으면 내용과 소유자를 먼저 확인하고 덮어쓰지 않습니다.

## 4. namespace와 push 계정 준비

처음 `up`을 실행하면 namespace만 만들고 계정 Secret 준비를 안내하며 중단합니다.

```bash
make registry-up KUBE_CONTEXT=kubernetes-admin@kubernetes
```

push 계정은 bcrypt htpasswd로 만듭니다. `htpasswd`가 없으면 사내 Ubuntu 미러에서 `apache2-utils`를 설치합니다.

```bash
read -r -p 'push 계정 이름: ' REGISTRY_USER
htpasswd -nB "$REGISTRY_USER" > /tmp/registry-htpasswd
kubectl --context kubernetes-admin@kubernetes -n registry create secret generic registry-htpasswd \
  --from-file=htpasswd=/tmp/registry-htpasswd
shred -u /tmp/registry-htpasswd
```

비밀번호는 문서·저장소에 기록하지 않고 운영자 보관 위치에만 둡니다.

## 5. 배포

```bash
make registry-up KUBE_CONTEXT=kubernetes-admin@kubernetes
kubectl --context kubernetes-admin@kubernetes -n registry get pods,pvc -o wide
```

**기대 결과:** `registry 배포 완료: http://registry.etch.samsungds.net/v2/`, PVC `Bound`, Pod `Running`.
**실패 확인:** Pod가 재시작하면 `kubectl -n registry logs deployment/registry`로 저장 폴더 권한·설정 오류를 확인합니다.

## 6. 노드와 빌드 host의 HTTP 허용

containerd는 기본적으로 HTTPS만 사용합니다. registry 이미지를 받을 **모든 노드**와 **빌드 host**에서 아래를 한 번 수행합니다.

1. containerd가 hosts 디렉터리를 읽는지 확인합니다.

   ```bash
   sudo containerd config dump | grep -n config_path
   ```

   `config_path = "/etc/containerd/certs.d"`가 없으면 `/etc/containerd/config.toml`의 CRI registry 절에 추가합니다.
   containerd 1.x는 `[plugins."io.containerd.grpc.v1.cri".registry]`, 2.x는 `[plugins."io.containerd.cri.v1.images".registry]`입니다.
   추가한 경우에만 `sudo systemctl restart containerd`를 실행하고 `kubectl get nodes`로 Ready를 확인합니다.

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

## 7. push·pull 검증

**빌드 host:** nerdctl은 `--insecure-registry`로 HTTP를 허용합니다.

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

**기대 결과:** push와 pull이 모두 성공합니다. 확인 후 [테스트 이미지 삭제](02-operations.md#이미지-삭제와-용량-정리)를 수행합니다.
**실패 확인:** `http: server gave HTTP response to HTTPS client`는 6단계 hosts 설정 누락, `401`은 로그인·Secret, timeout은 DNS·Traefik 연결을 확인합니다.
