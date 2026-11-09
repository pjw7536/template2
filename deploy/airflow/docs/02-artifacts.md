# 차트·이미지·ODBC 준비

[시작 안내](../README.md) · 이전: [환경변수](01-prepare.md#환경설정) · 다음: [단계별 실행](03-deploy.md#배포와-검증)

아래 명령은 저장소 루트에서 실행합니다.
배포할 이미지가 이미 registry에 있으면 빌드를 생략할 수 있습니다.
이 경우에도 선택한 Worker에서 해당 이미지를 가져올 수 있는지 확인합니다.

## 1. 공식 chart 준비

CP1의 저장소 루트에서 다음 명령으로 사내 Helm 미러의 chart를 받고 checksum까지 확인합니다.
Python 3.10 이상과 Helm 3.19.0 이상이 필요하며 Kubernetes context는 사용하지 않습니다.

```bash
python3 deploy/airflow/scripts/manage.py fetch-chart
```

`helm/chart.lock.json`의 `repository`에 지정된 사내 미러에서
`helm pull --repo ... --version 1.22.0`으로 받습니다. 미러 index가 패키지 경로를 결정합니다.
명령이 실패하면 CP1에서 미러 DNS·접근 권한·chart 제공 여부를 확인합니다.
SHA-256이 일치할 때만 기본 캐시에 저장하며 기존 캐시는 검증 실패 시 보존합니다.

미러에서 받을 수 없다면 외부 PC에서 lock의 `url`에 지정된 공개 주소로 받은
`deploy/airflow/helm/vendor/airflow-1.22.0.tgz`를 서버의 같은 위치로 반입합니다.
다른 위치의 파일은 `AIRFLOW_CHART_FILE=/절대경로/airflow-1.22.0.tgz` 환경변수로 지정합니다.
검사·렌더·배포는 차트를 자동 다운로드하지 않으며 고정 SHA-256이 다르면 중단합니다.
차트 dependency도 압축 파일에 포함되어 있어 `helm dependency update`가 필요하지 않습니다.

완료 기준: 고정된 chart 압축 파일이 배포 실행 호스트에 있어야 합니다.
`AIRFLOW_CHART_FILE`을 사용한다면 검사·렌더·배포를 실행하는 같은 셸에서 export합니다.

```bash
read -r -p '반입한 chart의 절대 경로: ' AIRFLOW_CHART_FILE
export AIRFLOW_CHART_FILE
```

## 2. DAG 포함 이미지 준비

`build-image`는 `apps/airflow` 소스와 이미지 빌더가 있는 호스트에서 실행합니다.
CP1에서는 기존 containerd에 nerdctl·BuildKit을 연결해 Docker Engine 없이 빌드할 수 있습니다.
기본 `--builder auto`는 nerdctl 실행 파일이 있으면 nerdctl을, 없으면 Docker를 선택합니다.
선택한 빌더의 연결·설정 검사에 실패하면 중단하며 다른 빌더로 자동 전환하지 않습니다.
`--builder nerdctl` 또는 `--builder docker`로 실행할 빌더를 고정할 수 있습니다.
CP1에 빌드 도구를 준비하지 않는다면
사내 미러·패키지·ODBC artifact에 접근할 수 있는 별도 빌드 호스트에서 빌드하고 최종 이미지를 전달합니다.

### containerd 빌드 도구 준비

CP1에 nerdctl·BuildKit이 없으면 아래 1~5를 진행합니다.
Ubuntu 22.04·amd64와 기존 containerd 2.2.1을 사용하는 최초 설치 기준입니다.
이미 설치했다면 [서비스 실행과 연결 검증](#5-서비스-실행과-연결-검증)에서 현재 설정을 확인합니다.
실제 설치 버전과 상태는 [서버 원본](../../shared/docs/infrastructure/servers.md#확인된-worker-설치-기준)을 따릅니다.

명령은 **CP1 저장소 루트의 같은 Bash 터미널**에서 실행합니다. sudo·curl·tar·sha256sum·systemctl이 필요합니다.
기존 실행 계정에 소켓 권한이 있으면 nerdctl·buildctl의 `sudo`를 생략할 수 있으며,
빌드·registry 인증·이미지 전달은 같은 계정으로 수행합니다.

#### 1. 설치 전 확인

```bash
uname -m
containerd --version
sudo systemctl is-active containerd
sudo test -S /run/containerd/containerd.sock
command -v nerdctl buildctl buildkitd
```

아키텍처는 `x86_64`, containerd 서비스는 `active`여야 하며 소켓 검사는 출력 없이 성공해야 합니다.
도구가 미설치라 마지막 명령에서 경로가 나오지 않으면 다음 단계에서 설치합니다.
기존 containerd를 사용하고, containerd·runc·CNI까지 묶인 `nerdctl-full` 대신 **nerdctl 단독 패키지**를 받습니다.

#### 2. 설치 파일 다운로드와 검증

예시 버전은 [nerdctl 2.4.2](https://github.com/containerd/nerdctl/releases/tag/v2.4.2)와
[BuildKit 0.34.1](https://github.com/moby/buildkit/releases/tag/v0.34.1)입니다.
[사내 저장소 원본](../../shared/docs/infrastructure/repositories.md#이미지패키지별-사용-주소)의 GitHub 미러에서 받습니다.

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

사내 미러의 해당 파일 제공·접속 성공은 미확인입니다. 다운로드에 실패하면 외부 PC에서 위 공식 릴리스의
동일한 파일 두 개를 받아 승인된 방식으로 CP1의 `$AIRFLOW_TOOLS_DIR`에 반입합니다.
다음은 공식 릴리스 파일의 SHA-256이며, 버전을 바꾸면 파일 이름과 checksum을 함께 갱신합니다.

```bash
(
  cd "$AIRFLOW_TOOLS_DIR" &&
  sha256sum -c - <<'EOF'
41a66995888043c0ba05f8061574eaba1b9e06b9b21c2a238215179df2728d3f  nerdctl-2.4.2-linux-amd64.tar.gz
a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b  buildkit-v0.34.1.linux-amd64.tar.gz
EOF
)
```

**두 파일 모두 `OK`일 때만** 다음 단계로 진행합니다.

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

버전 출력이 선택한 배포판과 맞고, sudo 환경에서도 세 명령의 `/usr/local/bin/` 경로가 나와야 합니다.
BuildKit 압축 파일은 `buildctl`·`buildkitd`와 빌드용 보조 바이너리를 설치합니다.

#### 4. BuildKit 설정과 서비스 등록

아래 파일 생성 명령은 **설정·서비스가 없는 최초 설치에만** 사용합니다.
이미 `/etc/buildkit/buildkitd.toml`이나 BuildKit 서비스가 있으면 CA·registry·서비스 설정을 보존하며
아래 주소·worker·namespace 항목을 병합합니다. 기존 서비스의 실제 `--config` 경로도 확인합니다.

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

BuildKit과 nerdctl은 같은 containerd 주소와 namespace를 사용해야 합니다.
containerd namespace `default`는 Kubernetes namespace `airflow`와 별개입니다.
`max-parallelism = 2`는 CP1에서 동시에 실행할 빌드 단계를 제한합니다.
이 빌드는 첫 단계의 의존성 이미지를 두 번째 단계의 `FROM`으로 사용하므로 containerd worker가 필요합니다.
OCI worker는 containerd의 로컬 이미지를 읽지 못합니다.
nerdctl 빌드에는 `--pull=false`를 전달해 같은 namespace의 로컬 의존성 이미지를 우선 사용합니다.
설정 원리는 [nerdctl 빌드 안내](https://github.com/containerd/nerdctl/blob/v2.4.2/docs/build.md)를 따릅니다.
사내 registry에 필요한 CA·미러 설정은 [BuildKit registry 설정](https://github.com/moby/buildkit/blob/v0.34.1/docs/buildkitd.toml.md)에 반영합니다.
containerd의 CRI 설정이 BuildKit에 자동 적용되는 것으로 가정하지 않습니다.

#### 5. 서비스 실행과 연결 검증

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now buildkit
sudo systemctl is-active buildkit
sudo nerdctl --address /run/containerd/containerd.sock --namespace default info
sudo buildctl --addr unix:///run/buildkit/buildkitd.sock debug workers --verbose
```

기존에 실행 중인 BuildKit의 설정을 변경했다면 해당 BuildKit 서비스를 재시작한 뒤 확인합니다.
containerd 서비스 재시작은 필요하지 않습니다.
완료 기준은 BuildKit 서비스 `active`, nerdctl 연결 성공, worker에 아래 두 label이 표시되는 것입니다.

```text
org.mobyproject.buildkit.worker.executor: containerd
org.mobyproject.buildkit.worker.containerd.namespace: default
```

실패하면 `sudo journalctl -u buildkit -n 80 --no-pager`로 서비스 로그를 확인합니다.
검증을 통과하면 [두 단계 이미지 빌드](#두-단계-이미지-빌드)로 진행합니다.

#### 빌드 옵션과 실패 확인

| 빌드 옵션 | 기본값·용도 |
| --- | --- |
| `--builder` | `auto`. nerdctl 우선, Docker 선택 가능 |
| `--containerd-namespace` | `default`. nerdctl·BuildKit worker의 공통 namespace |
| `--containerd-address` | `/run/containerd/containerd.sock`. nerdctl이 접속할 소켓 |
| `--buildkit-host` | `unix:///run/buildkit/buildkitd.sock`. nerdctl·buildctl이 접속할 주소 |

커스텀 소켓·namespace나 rootless 환경은 이 옵션을 실제 실행 중인 daemon과 일치시킵니다.
이 옵션이 nerdctl·BuildKit의 조회와 빌드 주소를 결정합니다.

| 증상 | 조치 |
| --- | --- |
| `docker` 실행 파일 없음 | containerd 빌드를 사용하려면 nerdctl·BuildKit을 준비하고 `--builder nerdctl`로 실행합니다. |
| `nerdctl`·`buildctl` 실행 파일 없음 | [다운로드·검증](#2-설치-파일-다운로드와-검증)과 [바이너리 설치](#3-바이너리-설치)를 진행하고 sudo의 PATH도 확인합니다. |
| containerd 연결 오류 | nerdctl의 소켓 주소·실행 계정의 접근 권한·containerd 상태를 확인합니다. |
| BuildKit worker 조회·namespace 오류 | buildkitd 실행·주소·권한과 containerd worker 설정을 확인합니다. OCI worker는 비활성화합니다. |
| `--with-source` 안내 | 빌드 호스트에서 `bash deploy/shared/scripts/checkout-server.sh airflow --with-source`로 앱 소스를 추가합니다. |

Docker를 사용하는 별도 빌드 호스트는 `command -v docker`, `docker info`가 성공해야 합니다.
Docker Engine 설치는 [공식 설치 안내](https://docs.docker.com/engine/install/)에서 OS에 맞는 방법을 확인하고,
사내망에서는 [승인된 패키지 미러](../../shared/docs/infrastructure/repositories.md)를 사용합니다.

### 두 단계 이미지 빌드

`apps/airflow/image/Dockerfile.dependencies`는 `env/build.env`와 동일한 사내 기본값을 사용합니다.
빌드 도구는 `env/build.env`를 build arg로 전달하며 환경별 값은 이 파일에서 변경합니다.
사내 base image·APT/PIP mirror·trusted hosts·ODBC artifact URL이 지정되어 있고
`INSTALL_BIGDATAQUERY_PYTHON=true`, `INSTALL_BIGDATAQUERY_ODBC=true`가 기본값입니다.
사내 미러에서 `apache/airflow:3.3.2-python3.12`를 가져올 수 있어야 합니다.
BigDataQuery Python·ODBC는 사내 빌드 호스트에서 실제 설치·import·DSN 접속을 확인합니다.
Dockerfile을 직접 빌드할 때도 같은 기본값을 사용하며 필요하면 `--build-arg`로 변경할 수 있습니다.
빌드 인자에는 비밀번호·접근 토큰을 넣지 않습니다.

```bash
sudo python3 deploy/airflow/scripts/manage.py build-image --builder nerdctl \
  --build-env deploy/airflow/env/build.env
```

Docker 빌드는 위 명령의 `--builder nerdctl`을 `--builder docker`로 바꿉니다.
빌드 도구는 소스·선택한 빌더·daemon 접속을 먼저 확인합니다. 빌드는 다음 두 단계로 진행됩니다.

1. `apps/airflow/image/Dockerfile.dependencies`로 의존성 이미지를 만듭니다.
2. `apps/airflow/image/Dockerfile`로 DAG·플러그인을 추가합니다.

최종 빌드 context는 `apps/airflow`입니다. 실제 env·로그·DSN 파일은 context에 보내지 않습니다.
플러그인 소스는 `apps/airflow/plugins`에 두며 최종 이미지에 포함됩니다.

### 사내 실행 기본값

사내 공통 설정은 의존성 이미지에서 준비하고, DAG와 공통 알림 코드를 포함한 최종 이미지가 상속합니다.
각 DAG에서 mirror 주소나 인증값을 반복 선언하지 않습니다.

| 항목 | 적용 방식 |
| --- | --- |
| Python 패키지 | `build.env`의 `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `PIP_TRUSTED_HOST`를 `/etc/pip.conf`의 기본값으로 반영 |
| pip 공통 동작 | 버전 확인 생략, 비대화형 설치. 저장소·config 경로를 환경변수로 강제하지 않음 |
| OS 패키지·ODBC | 사내 APT 입력과 driver artifact를 빌드 때 사용, 실제 DSN·인증서는 운영 마운트로 전달 |
| DAG·실패 알림·SSO | 최종 이미지에 코드를 포함하고 발송 credential·수신자는 Kubernetes Secret으로 전달 |

동일 이미지를 사용하는 DAG의 pip와 하위 Python·가상환경은 위 공통 설정을 기본으로 사용합니다.
pip 기반 `PythonVirtualenvOperator(index_urls=...)`는 가상환경의 `pip.conf`로 지정한 index를 덮어쓸 수 있고,
빈 목록이면 `no-index`가 적용됩니다. 별도 설정이 없는 항목은 pip의 설정 우선순위에 따라 공통값을 유지합니다.
pip 명령 옵션·명시적인 Pod 환경변수도 기본값보다 우선합니다. 다른 Pod·서버·이미지에서 실행하는 작업과
pip 외 패키지 설치 도구에는 이 설정이 자동 적용되지 않습니다.
외부 PC의 `make dev` 빌드는 최종 Dockerfile의 공개 기본 이미지를 직접 사용하므로 사내 mirror에 연결할 필요가 없습니다.
사내 기본값이 있는 의존성 Dockerfile을 직접 빌드하려면 사내망 또는 별도의 build arg 입력이 필요합니다.

필요한 Python 패키지는 이미지 빌드 때 설치합니다. DAG 실행이나 컨테이너 시작 때마다
패키지를 설치하는 방식은 기본 운영 흐름으로 사용하지 않습니다.
추가 의존성이 생기면 의존성 Dockerfile에 추가하고 새 태그로 빌드·배포합니다.

사내 CA·프록시가 필요한 환경은 실제 CA bundle·프록시·우회 대상을 확인해 적용합니다.
현재의 `PIP_TRUSTED_HOST`는 pip 저장소 접근 설정이며 업무 API의 TLS 신뢰 설정을 대신하지 않습니다.
OIDC CA는 [인증 설정](01-prepare.md#keycloak-sso-입력)의 별도 마운트를 사용합니다.
mirror의 실제 패키지 제공·접근 권한·ODBC 접속은 사내 서버에서 검증해야 합니다.

Docker daemon과 캐시된 `apache/airflow:3.3.2-python3.12`가 있으면 다음 검사로 최종 이미지의
코드 포함과 기본 mirror·가상환경별 index·추가 index·no-index·명시적 override를 확인할 수 있습니다.
검사용 빌드는 네트워크를 차단하고 BigDataQuery·ODBC 추가 설치를 생략하며 검사 이미지도 정리합니다.

```bash
AIRFLOW_DOCKER_TESTS=1 python3 -m unittest discover \
  -s deploy/airflow/tests -p test_manage.py -k ImageBuildIntegrationTests -v
```

### 이미지 전달

registry는 컨테이너 이미지를 보관하고 다른 서버가 내려받을 수 있게 제공하는 저장소 서버입니다.
빌드한 이미지는 자동으로 push되지 않습니다. registry가 있으면 이미지를 업로드하고 Worker에서 내려받게 하며,
registry가 없으면 `.tar` 파일로 저장해 Worker의 containerd에 직접 반입합니다.
CP1의 빌드 namespace에만 이미지가 있어서는 다른 Worker의 Kubernetes가 사용할 수 없습니다.
PostgreSQL 이미지도 같은 기준으로 준비합니다.

DAG를 변경하면 이미지를 다시 빌드하고 `AIRFLOW_IMAGE_TAG`를 새 값으로 바꿔 배포합니다.

#### Registry를 사용하는 경우

빌드 호스트와 Worker에서 접근할 수 있고 업로드 권한이 있는 registry를 사용합니다.
`k8s.env`의 이미지 repository에는 registry 주소를 포함하고, 빌드 이미지 이름도 같은 값으로 맞춥니다.
private registry 인증이 필요하면 대상 namespace에 imagePullSecret을 미리 만들고
`IMAGE_PULL_SECRET`에 이름을 입력합니다.

빌드 호스트에서 실행합니다. env를 source하지 않고 이미지 이름을 직접 확인해 입력합니다.

```bash
read -r -p 'env와 동일한 repository:tag: ' AIRFLOW_IMAGE_REF
sudo nerdctl --address /run/containerd/containerd.sock --namespace default image inspect "$AIRFLOW_IMAGE_REF"
sudo nerdctl --address /run/containerd/containerd.sock --namespace default push "$AIRFLOW_IMAGE_REF"
```

완료 기준: registry에 해당 태그가 존재하고, 선택한 Worker가 인증·CA·네트워크 설정으로 내려받을 수 있어야 합니다.

#### Registry 없이 CP1에서 Worker로 직접 전달하는 경우

아래 순서로 **CP1에서 저장 → Worker로 파일 복사 → Worker의 containerd에 등록**합니다.
CP1에는 nerdctl과 SSH·SCP, Worker에는 containerd와 `ctr`이 필요하며 양쪽 계정에 필요한 sudo 권한이 있어야 합니다.
Worker는 `k8s.env`의 `NODE_NAME`에 해당하는 서버를 선택합니다.
노드와 주소는 [서버 원본](../../shared/docs/infrastructure/servers.md#서버-목록)에서 확인하고,
SSH 계정·포트와 CP1에서의 접근 가능 여부는 별도로 확인합니다.

**1. CP1에서 이미지 확인·저장**

CP1의 같은 Bash 터미널에서 실행합니다.
이미지 이름은 `k8s.env`의 `AIRFLOW_IMAGE_REPOSITORY:AIRFLOW_IMAGE_TAG`와 일치해야 합니다.

```bash
read -r -p 'env와 동일한 repository:tag: ' AIRFLOW_IMAGE_REF
sudo nerdctl --address /run/containerd/containerd.sock --namespace default image inspect "$AIRFLOW_IMAGE_REF"

sudo nerdctl --address /run/containerd/containerd.sock --namespace default save \
  -o /tmp/airflow-image.tar "$AIRFLOW_IMAGE_REF"
sudo chown "$(id -u):$(id -g)" /tmp/airflow-image.tar
ls -lh /tmp/airflow-image.tar
```

`inspect`가 성공하고 `.tar` 파일이 생성되어야 합니다. `chown`은 다음 단계의 SCP 실행 계정이 파일을 읽도록 합니다.
이미지를 찾지 못하면 다음 명령으로 실제 빌드한 이름·태그를 확인합니다.

```bash
sudo nerdctl --address /run/containerd/containerd.sock --namespace default images
```

namespace·주소를 바꿔 빌드했다면 inspect·push·save에도 같은 값을 지정합니다.
Docker로 빌드했다면 같은 빌드 계정에서 `docker image inspect`, `docker push` 또는 `docker save`를 사용합니다.

**2. CP1에서 Worker로 파일 복사·접속**

CP1의 같은 터미널에서 Worker SSH 주소를 `계정@호스트명` 또는 `계정@IP` 형식으로 입력합니다.
포트는 실제 SSH 포트를 입력하며, 기본 포트를 쓰는 경우 Enter로 22를 선택합니다.

```bash
read -r -p 'Worker SSH 주소(user@host): ' AIRFLOW_WORKER_SSH
read -r -p 'Worker SSH 포트 [22]: ' AIRFLOW_WORKER_PORT
AIRFLOW_WORKER_PORT="${AIRFLOW_WORKER_PORT:-22}"

scp -P "$AIRFLOW_WORKER_PORT" /tmp/airflow-image.tar \
  "${AIRFLOW_WORKER_SSH}:/tmp/airflow-image.tar"
```

전송이 성공한 뒤 해당 Worker에 접속합니다. SCP의 포트 옵션은 대문자 `-P`, SSH는 소문자 `-p`입니다.

```bash
ssh -p "$AIRFLOW_WORKER_PORT" "$AIRFLOW_WORKER_SSH"
```

SCP를 사용할 수 없는 환경에서는 승인된 전송 수단으로 같은 파일을 Worker에 복사합니다.

**3. Worker에서 containerd에 등록·확인**

아래 명령은 CP1이 아니라 **방금 접속한 Worker에서** 실행합니다.
`hostname`으로 배포 대상 Worker가 맞는지 확인하고, 파일이 있을 때 등록합니다.

```bash
hostname
ls -lh /tmp/airflow-image.tar
sudo ctr --address /run/containerd/containerd.sock --namespace k8s.io images import /tmp/airflow-image.tar
sudo ctr --address /run/containerd/containerd.sock --namespace k8s.io images ls
```

완료 기준: 목록에 배포할 이미지의 repository·tag가 있어야 합니다.
짧은 이미지 이름은 `docker.io/library/`가 붙어 표시될 수 있습니다.
**Worker에서는 Kubernetes용 `k8s.io` namespace에 등록해야 합니다.** CP1 빌드용 `default`와 구분합니다.

K3s를 사용하는 Worker는 해당 배포판의 containerd에 아래 명령으로 등록·확인합니다.

```bash
sudo k3s ctr images import /tmp/airflow-image.tar
sudo k3s ctr images ls
```

PostgreSQL 이미지도 Worker에서 사용 가능해야 합니다. registry에서 내려받을 수 없다면 같은 저장·전송·등록 절차를 적용합니다.
여기까지는 이미지 준비이며, 실행 중인 Airflow가 자동으로 갱신되지는 않습니다.
[ODBC 준비](#3-odbc-설정-준비)와 [배포·검증](03-deploy.md#배포와-검증)을 이어서 진행합니다.

## 3. ODBC 설정 준비

ODBC 기본 방식은 기존 디렉터리 전체를 같은 노드에서 읽기 전용으로 마운트하는 방식입니다.
`ODBC_HOST_PATH`를 기존 서버 ODBC 설정 디렉터리의 절대 경로로 지정하면 INI·인증서·하위 파일을 그대로 사용합니다.
새 서버라면 기존 디렉터리 전체를 `/appdata/airflow/odbc`로 복사하고 Airflow UID 50000이 읽을 수 있게 권한을 유지합니다.
이 저장소에는 실제 DSN·인증서가 없으므로 빈 파일을 생성해서 대신하지 않습니다.
경로가 없으면 Kubernetes가 Pod 기동을 차단합니다. 단일 서버에 고정하므로 다른 노드의 파일을 참조하지 않습니다.

| 기존 컨테이너 설정 | Kubernetes 유지 값 |
| --- | --- |
| ODBC 디렉터리 | `/usr/local/odbc`, 전체 디렉터리 읽기 전용 |
| `ODBCINI` | `/usr/local/odbc/odbc.ini` |
| `ODBCSYSINI` | `/usr/local/odbc` |
| `CLOUDERAIMPALAINI` | `/etc/cloudera.impalaodbc.ini`, 기존 드라이버 이미지에서 상속 |

Secret 방식을 사용하려면 `ODBC_HOST_PATH=`로 비우고 기존 namespace Secret 이름을
`ODBC_SECRET_NAME`에 지정합니다. 두 방식을 동시에 지정하면 설정 검사에서 중단합니다.
namespace는 `kubectl --context "$AIRFLOW_KUBE_CONTEXT" create namespace airflow`로 미리 만들 수 있습니다.

완료 기준: `ODBC_HOST_PATH`를 사용하면 선택한 Worker에 실제 설정 파일이 있고 UID 50000이 읽을 수 있어야 합니다.
Secret 방식이면 `NAMESPACE`와 동일한 namespace에 참조 Secret이 있어야 합니다.
