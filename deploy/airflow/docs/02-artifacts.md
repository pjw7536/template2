# 차트·이미지·ODBC 준비

[앱 안내](../README.md) · 이전: [환경설정](01-prepare.md#환경설정) · 다음: [Keycloak 로그인](03-deploy.md#keycloak-로그인)

**목적:** 고정 chart, DAG 포함 이미지, ODBC 설정을 배포 실행 호스트와 Worker에 준비합니다.
**실행 위치:** 각 절에 표시한 호스트의 저장소 루트. 배포할 이미지가 이미 registry에 있으면 빌드를 생략하고 Worker에서 가져올 수 있는지만 확인합니다.

## 1. 공식 chart 준비

**실행 위치:** CP1 저장소 루트. Python 3.10 이상과 Helm 3.19.0 이상이 필요하며 Kubernetes context는 사용하지 않습니다.

```bash
python3 deploy/airflow/scripts/manage.py fetch-chart
```

`helm/chart.lock.json`의 `repository`(사내 Helm 미러)에서 `helm pull --repo ... --version 1.22.0`으로 받습니다.
**기대 결과:** `사내 Helm 미러 chart 다운로드·SHA-256 검사 완료`. SHA-256이 일치할 때만 `deploy/airflow/helm/vendor/airflow-1.22.0.tgz`에 저장하며 검증 실패 시 기존 캐시를 보존합니다.
**실패 확인:** CP1에서 미러 DNS·접근 권한·chart 제공 여부를 확인합니다.

미러에서 받을 수 없으면 외부 PC에서 lock의 `url`(공개 주소)로 받은 `airflow-1.22.0.tgz`를 서버의 같은 위치로 반입합니다.
다른 위치의 파일은 검사·렌더·배포를 실행하는 같은 셸에서 지정합니다.

```bash
read -r -p '반입한 chart의 절대 경로: ' AIRFLOW_CHART_FILE
export AIRFLOW_CHART_FILE
```

검사·렌더·배포는 chart를 자동 다운로드하지 않으며 고정 SHA-256이 다르면 중단합니다. dependency가 압축 파일에 포함되어 `helm dependency update`가 필요하지 않습니다.

## 2. DAG 포함 이미지 준비

**실행 위치:** `apps/airflow` 소스와 이미지 빌더가 있는 호스트. CP1은 기존 containerd에 nerdctl·BuildKit을 연결해 Docker Engine 없이 빌드할 수 있습니다.
CP1에 빌드 도구를 두지 않으면 사내 미러·패키지·ODBC artifact에 접근할 수 있는 별도 빌드 호스트에서 빌드하고 최종 이미지를 전달합니다.

| 빌드 옵션 | 기본값·용도 |
| --- | --- |
| `--builder` | `auto`: nerdctl이 있으면 nerdctl, 없으면 Docker. 선택한 빌더 검사에 실패하면 다른 빌더로 전환하지 않음 |
| `--containerd-namespace` | `default`. nerdctl·BuildKit worker의 공통 namespace |
| `--containerd-address` | `/run/containerd/containerd.sock`. nerdctl이 접속할 소켓 |
| `--buildkit-host` | `unix:///run/buildkit/buildkitd.sock`. nerdctl·buildctl이 접속할 주소 |

커스텀 소켓·namespace나 rootless 환경은 이 옵션을 실제 daemon과 일치시킵니다.
Docker를 쓰는 빌드 호스트는 `command -v docker`, `docker info`가 성공해야 하며 설치는 [공식 안내](https://docs.docker.com/engine/install/)와
[승인된 패키지 미러](../../shared/docs/infrastructure/repositories.md)를 사용합니다.

### containerd 빌드 도구 준비

CP1에 nerdctl·BuildKit이 없을 때 아래 1~5를 진행합니다. Ubuntu 22.04·amd64와 기존 containerd 2.2.1 기준의 최초 설치입니다.
이미 설치했다면 [5. 서비스 실행과 연결 검증](#5-서비스-실행과-연결-검증)만 실행합니다. 실제 설치 상태는 [서버 원본](../../shared/docs/infrastructure/servers.md#확인된-worker-설치-기준)을 따릅니다.

**실행 위치:** CP1 저장소 루트의 같은 Bash 터미널. sudo·curl·tar·sha256sum·systemctl이 필요합니다.
실행 계정에 소켓 권한이 있으면 nerdctl·buildctl의 `sudo`를 생략할 수 있으며, 빌드·registry 인증·이미지 전달은 같은 계정으로 수행합니다.

#### 1. 설치 전 확인

```bash
uname -m
containerd --version
sudo systemctl is-active containerd
sudo test -S /run/containerd/containerd.sock
command -v nerdctl buildctl buildkitd
```

**기대 결과:** `x86_64`, containerd `active`, 소켓 검사는 출력 없이 성공. 마지막 명령에 경로가 없으면 다음 단계에서 설치합니다.
기존 containerd를 사용하므로 `nerdctl-full`이 아닌 **nerdctl 단독 패키지**를 받습니다.

#### 2. 설치 파일 다운로드와 검증

버전은 [nerdctl 2.4.2](https://github.com/containerd/nerdctl/releases/tag/v2.4.2)와 [BuildKit 0.34.1](https://github.com/moby/buildkit/releases/tag/v0.34.1)이며
[사내 저장소 원본](../../shared/docs/infrastructure/repositories.md#패키지chartartifact-주소)의 GitHub 미러에서 받습니다.

```bash
AIRFLOW_TOOLS_DIR="$HOME/airflow-build-tools"
mkdir -p "$AIRFLOW_TOOLS_DIR"
GITHUB_MIRROR="http://repository.samsungds.net/repository/proxy-raw-github.com"

curl -fL \
  "$GITHUB_MIRROR/containerd/nerdctl/releases/download/v2.4.2/nerdctl-2.4.2-linux-amd64.tar.gz" \
  -o "$AIRFLOW_TOOLS_DIR/nerdctl-2.4.2-linux-amd64.tar.gz"
curl -fL \
  "$GITHUB_MIRROR/moby/buildkit/releases/download/v0.34.1/buildkit-v0.34.1.linux-amd64.tar.gz" \
  -o "$AIRFLOW_TOOLS_DIR/buildkit-v0.34.1.linux-amd64.tar.gz"
```

사내 미러의 파일 제공은 미확인입니다. 다운로드에 실패하면 외부 PC에서 같은 공식 릴리스 파일을 받아 승인된 방식으로 `$AIRFLOW_TOOLS_DIR`에 반입합니다.
아래는 공식 릴리스 파일의 SHA-256이며, 버전을 바꾸면 파일 이름과 checksum을 함께 갱신합니다.

```bash
(
  cd "$AIRFLOW_TOOLS_DIR" &&
  sha256sum -c - <<'EOF'
41a66995888043c0ba05f8061574eaba1b9e06b9b21c2a238215179df2728d3f  nerdctl-2.4.2-linux-amd64.tar.gz
a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b  buildkit-v0.34.1.linux-amd64.tar.gz
EOF
)
```

**기대 결과:** 두 파일 모두 `OK`. 하나라도 실패하면 진행하지 않습니다.

#### 3. 바이너리 설치

```bash
sudo install -d -m 0755 /usr/local/bin
sudo tar -xzf "$AIRFLOW_TOOLS_DIR/nerdctl-2.4.2-linux-amd64.tar.gz" \
  -C /usr/local/bin nerdctl
sudo tar -xzf "$AIRFLOW_TOOLS_DIR/buildkit-v0.34.1.linux-amd64.tar.gz" \
  -C /usr/local

/usr/local/bin/nerdctl --version
/usr/local/bin/buildctl --version
/usr/local/bin/buildkitd --version
sudo sh -c 'command -v nerdctl buildctl buildkitd'
```

**기대 결과:** 선택한 버전이 출력되고 sudo 환경에서도 세 명령이 `/usr/local/bin/` 경로로 조회됩니다.

#### 4. BuildKit 설정과 서비스 등록

아래 파일 생성은 **설정·서비스가 없는 최초 설치에만** 사용합니다. 기존 `/etc/buildkit/buildkitd.toml`이나 서비스가 있으면
CA·registry·서비스 설정을 보존하며 주소·worker·namespace 항목만 병합하고, 기존 서비스의 실제 `--config` 경로도 확인합니다.

```bash
sudo install -d -m 0755 /etc/buildkit
sudo tee /etc/buildkit/buildkitd.toml >/dev/null <<'EOF'
[worker.oci]
  enabled = false

[worker.containerd]
  enabled = true
  address = "/run/containerd/containerd.sock"
  namespace = "default"
  max-parallelism = 2
EOF

sudo tee /etc/systemd/system/buildkit.service >/dev/null <<'EOF'
[Unit]
Description=Airflow 이미지 빌드용 BuildKit
Requires=containerd.service
After=containerd.service

[Service]
Type=simple
ExecStart=/usr/local/bin/buildkitd --config /etc/buildkit/buildkitd.toml --addr unix:///run/buildkit/buildkitd.sock
Restart=on-failure
Delegate=yes

[Install]
WantedBy=multi-user.target
EOF
```

두 단계 빌드는 첫 단계의 로컬 의존성 이미지를 두 번째 단계의 `FROM`으로 사용하므로 같은 namespace의 containerd worker가 필요합니다.
OCI worker는 containerd의 로컬 이미지를 읽지 못합니다. containerd namespace `default`는 Kubernetes namespace `airflow`와 별개이며, `max-parallelism = 2`는 CP1의 동시 빌드 단계를 제한합니다.
사내 registry CA·미러 설정은 [BuildKit registry 설정](https://github.com/moby/buildkit/blob/v0.34.1/docs/buildkitd.toml.md)에 반영하며
containerd의 CRI 설정이 BuildKit에 자동 적용되지 않습니다. 원리는 [nerdctl 빌드 안내](https://github.com/containerd/nerdctl/blob/v2.4.2/docs/build.md)를 참고합니다.

#### 5. 서비스 실행과 연결 검증

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now buildkit
sudo systemctl is-active buildkit
sudo nerdctl --address /run/containerd/containerd.sock --namespace default info
sudo buildctl --addr unix:///run/buildkit/buildkitd.sock debug workers --verbose
```

기존 BuildKit 설정을 바꿨다면 BuildKit 서비스만 재시작한 뒤 확인합니다. containerd 재시작은 필요하지 않습니다.
**기대 결과:** BuildKit `active`, nerdctl 연결 성공, worker에 다음 두 label이 표시됩니다.

```text
org.mobyproject.buildkit.worker.executor: containerd
org.mobyproject.buildkit.worker.containerd.namespace: default
```

| 증상 | 조치 |
| --- | --- |
| 서비스 실패 | `sudo journalctl -u buildkit -n 80 --no-pager`로 로그 확인 |
| `docker` 실행 파일 없음 | nerdctl·BuildKit을 준비하고 `--builder nerdctl`로 실행 |
| `nerdctl`·`buildctl` 실행 파일 없음 | 위 2~3단계 진행, sudo의 PATH 확인 |
| containerd 연결 오류 | nerdctl 소켓 주소·실행 계정 권한·containerd 상태 확인 |
| BuildKit worker·namespace 오류 | buildkitd 실행·주소·권한과 containerd worker 설정 확인, OCI worker 비활성화 |
| `이미지 빌드 소스(apps/airflow)가 없습니다` | 저장소 전체 checkout의 루트에서 실행 |

### 두 단계 이미지 빌드

빌드 도구는 `env/build.env`를 build arg로 전달합니다. 사내 base image(`apache/airflow:3.3.2-python3.12` 미러)·APT/PIP mirror·trusted hosts·ODBC artifact URL과
`INSTALL_BIGDATAQUERY_PYTHON=true`, `INSTALL_BIGDATAQUERY_ODBC=true`가 기본값이며 `apps/airflow/image/Dockerfile.dependencies`의 기본값과 같습니다.
환경별 값은 `build.env`에서 바꾸고 비밀번호·접근 토큰은 넣지 않습니다.

```bash
sudo python3 deploy/airflow/scripts/manage.py build-image --builder nerdctl \
  --build-env deploy/airflow/env/build.env
```

Docker 빌드는 `--builder docker`를 사용합니다. 도구는 소스·빌더·daemon 접속을 먼저 확인한 뒤 다음 순서로 빌드합니다.

1. `apps/airflow/image/Dockerfile.dependencies`로 의존성 이미지(`<repository>:<tag>-dependencies`)를 만듭니다.
2. `apps/airflow/image/Dockerfile`로 DAG·플러그인을 추가합니다. 빌드 context는 `apps/airflow`이며 실제 env·로그·DSN 파일은 보내지 않습니다.

**기대 결과:** `Airflow 이미지 빌드 완료`. 이미지는 자동 push하지 않습니다.
BigDataQuery Python·ODBC의 설치·import·DSN 접속과 mirror의 패키지 제공은 사내 빌드 호스트·서버에서 확인합니다.
`PIP_TRUSTED_HOST`는 pip 저장소 접근 설정이며 업무 API의 TLS 신뢰를 대신하지 않습니다. OIDC CA는 [별도 마운트](03-deploy.md#2-oidc-ca-configmap-준비)를 사용합니다.
추가 Python 의존성은 의존성 Dockerfile에 넣고 새 태그로 빌드합니다. DAG의 pip·가상환경 동작 등 개발 안내는 [Airflow 개발 안내](../../../apps/airflow/README.md)를 따릅니다.

Docker daemon과 캐시된 `apache/airflow:3.3.2-python3.12`가 있으면 네트워크를 차단한 검사용 빌드로 최종 이미지의 코드 포함과 pip 기본값을 확인할 수 있습니다.

```bash
AIRFLOW_DOCKER_TESTS=1 python3 -m unittest discover \
  -s deploy/airflow/tests -p test_manage.py -k ImageBuildIntegrationTests -v
```

### 이미지 전달

빌드한 이미지는 Worker의 containerd가 사용할 수 있어야 합니다. CP1 빌드 namespace에만 있는 이미지는 다른 Worker의 Kubernetes가 사용할 수 없습니다.
registry가 있으면 push하고, 없으면 `.tar`로 저장해 Worker에 반입합니다. PostgreSQL 이미지도 같은 기준으로 준비합니다.
DAG를 바꾸면 이미지를 다시 빌드하고 `AIRFLOW_IMAGE_TAG`를 새 값으로 바꿔 배포합니다.

#### Registry를 사용하는 경우

빌드 호스트와 Worker가 접근할 수 있고 업로드 권한이 있는 registry를 사용합니다. `k8s.env`의 `AIRFLOW_IMAGE_REPOSITORY`에 registry 주소를 포함하고 같은 이름으로 빌드합니다.
private registry 인증이 필요하면 대상 namespace에 imagePullSecret을 만들고 `IMAGE_PULL_SECRET`에 이름을 입력합니다.

**실행 위치:** 빌드 호스트. env를 source하지 않고 이미지 이름을 직접 입력합니다.

```bash
read -r -p 'env와 동일한 repository:tag: ' AIRFLOW_IMAGE_REF
sudo nerdctl --address /run/containerd/containerd.sock --namespace default image inspect "$AIRFLOW_IMAGE_REF"
sudo nerdctl --address /run/containerd/containerd.sock --namespace default push "$AIRFLOW_IMAGE_REF"
```

**기대 결과:** registry에 태그가 있고 선택한 Worker가 인증·CA·네트워크 설정으로 내려받을 수 있습니다.

#### Registry 없이 CP1에서 Worker로 직접 전달하는 경우

순서는 **CP1에서 저장 → Worker로 복사 → Worker의 containerd에 등록**입니다. CP1에는 nerdctl·SSH·SCP, Worker에는 containerd와 `ctr`, 양쪽에 필요한 sudo 권한이 있어야 합니다.
대상은 `NODE_NAME`의 Worker이며 현재 [서버 목록](../../shared/docs/infrastructure/servers.md#서버-목록)의 `khinfow01`(`10.172.117.91`)입니다. SSH 계정·포트와 CP1에서의 접근 가능 여부는 별도로 확인합니다.

**1. CP1에서 이미지 저장**

이미지 이름은 `AIRFLOW_IMAGE_REPOSITORY:AIRFLOW_IMAGE_TAG`와 같아야 합니다. 아래 값은 [현재 서버 env](../env/k8s.env)의 선언입니다.

```bash
AIRFLOW_IMAGE_REF=airflow:3.3.2-release-1
sudo nerdctl --address /run/containerd/containerd.sock --namespace default image inspect "$AIRFLOW_IMAGE_REF"
sudo nerdctl --address /run/containerd/containerd.sock --namespace default save \
  -o /tmp/airflow-image.tar "$AIRFLOW_IMAGE_REF"
sudo chown "$(id -u):$(id -g)" /tmp/airflow-image.tar
ls -lh /tmp/airflow-image.tar
```

**기대 결과:** `inspect`가 성공하고 `.tar`가 생성됩니다. 이미지를 찾지 못하면 `sudo nerdctl --address /run/containerd/containerd.sock --namespace default images`로 실제 이름·태그를 확인합니다.
다른 namespace·주소로 빌드했다면 같은 값을 지정하고, Docker로 빌드했다면 `docker image inspect`·`docker push`·`docker save`를 사용합니다.

**2. CP1에서 Worker로 복사·접속**

배포 대상을 바꿨다면 주소도 바꿉니다. SCP 포트 옵션은 대문자 `-P`, SSH는 소문자 `-p`입니다.

```bash
read -r -p 'Worker SSH 계정: ' AIRFLOW_WORKER_USER
read -r -p 'Worker SSH 포트 [22]: ' AIRFLOW_WORKER_PORT
AIRFLOW_WORKER_PORT="${AIRFLOW_WORKER_PORT:-22}"

scp -P "$AIRFLOW_WORKER_PORT" /tmp/airflow-image.tar \
  "${AIRFLOW_WORKER_USER}@10.172.117.91:/tmp/airflow-image.tar"
ssh -p "$AIRFLOW_WORKER_PORT" "${AIRFLOW_WORKER_USER}@10.172.117.91"
```

SCP를 쓸 수 없으면 승인된 전송 수단으로 같은 파일을 복사합니다.

**3. Worker에서 containerd에 등록**

**실행 위치:** 방금 접속한 Worker. **Kubernetes용 `k8s.io` namespace**에 등록하며 CP1 빌드용 `default`와 구분합니다.

```bash
hostname
ls -lh /tmp/airflow-image.tar
sudo ctr --address /run/containerd/containerd.sock --namespace k8s.io images import /tmp/airflow-image.tar
sudo ctr --address /run/containerd/containerd.sock --namespace k8s.io images ls
```

**기대 결과:** 목록에 배포할 repository·tag가 있습니다. 짧은 이름은 `docker.io/library/`가 붙어 표시될 수 있습니다.
K3s Worker는 `sudo k3s ctr images import /tmp/airflow-image.tar`, `sudo k3s ctr images ls`를 사용합니다.
이미지 준비만으로 실행 중인 Airflow는 갱신되지 않습니다.

## 3. ODBC 설정 준비

**목적:** 기존 ODBC 디렉터리 전체를 같은 노드에서 읽기 전용으로 마운트합니다.
`ODBC_HOST_PATH`(현재 `/appdata/airflow/odbc`)에 INI·인증서·하위 파일을 두며, 파일 배치 명령은 [ODBC 파일 안내](../odbc/README.md)를 따릅니다.
이 저장소에는 실제 DSN·인증서가 없으므로 빈 파일로 대신하지 않습니다. 경로가 없으면 Kubernetes가 Pod 기동을 차단합니다.

| 기존 컨테이너 설정 | Kubernetes 유지 값 |
| --- | --- |
| ODBC 디렉터리 | `/usr/local/odbc`, 전체 디렉터리 읽기 전용 |
| `ODBCINI` | `/usr/local/odbc/odbc.ini` |
| `ODBCSYSINI` | `/usr/local/odbc` |
| `CLOUDERAIMPALAINI` | `/etc/cloudera.impalaodbc.ini`, 기존 드라이버 이미지에서 상속 |

Secret 방식은 `ODBC_HOST_PATH=`로 비우고 `NAMESPACE`와 같은 namespace의 기존 Secret 이름을 `ODBC_SECRET_NAME`에 지정합니다. 두 방식을 함께 지정하면 검사에서 중단합니다.

**완료 기준:** 선택한 Worker에 실제 설정 파일이 있고 UID 50000이 읽을 수 있거나, 참조 Secret이 대상 namespace에 있습니다.
**다음 단계:** [Keycloak 로그인](03-deploy.md#keycloak-로그인).
