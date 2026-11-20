# 차트·이미지·ODBC 준비

[Airflow 가이드](../README.md)

설치·업데이트 절차는 [Airflow 가이드](../README.md)에 있습니다. 이 문서는 고정 chart, DAG 포함 이미지, 빌드 도구, ODBC 설정을 준비하는 방법과 원리입니다.
실행 위치는 각 절에 표시한 호스트의 저장소 루트입니다. chart 받기·빌드 도구 설치·이미지 빌드와 push는 `make ops-deploy APP=airflow`가 수행하므로, 아래 명령은 그 단계만 따로 실행하거나 실패 원인을 확인할 때 씁니다.

- [1. 공식 chart 준비](#1-공식-chart-준비)
- [2. DAG 포함 이미지 준비](#2-dag-포함-이미지-준비): [containerd 빌드 도구 준비](#containerd-빌드-도구-준비) · [두 단계 이미지 빌드](#두-단계-이미지-빌드) · [이미지 전달](#이미지-전달)
- [3. ODBC 설정 준비](#3-odbc-설정-준비)

## 1. 공식 chart 준비

chart 파일이 없으면 `make ops-deploy`의 준비 검사가 아래 명령을 자동으로 실행합니다. Python 3.10 이상과 Helm 3.19.0 이상이 필요합니다.

[변경] chart만 따로 받을 때 관리 호스트 저장소 루트에서 실행합니다.

```bash
make airflow-fetch-chart
```

`helm/chart.lock.json`의 `repository`(사내 Helm 미러)에서 `helm pull --repo ... --version 1.22.0`으로 받습니다.
성공: `사내 Helm 미러 chart 다운로드·SHA-256 검사 완료`. SHA-256이 일치할 때만 `deploy/airflow/helm/vendor/airflow-1.22.0.tgz`에 저장하며 검증 실패 시 기존 캐시를 보존합니다.
실패: 관리 호스트에서 미러 DNS·접근 권한·chart 제공 여부를 확인합니다. 미러 주소는 [사내 저장소·미러](../../shared/docs/infrastructure/repositories.md)에 있습니다.

미러에서 받을 수 없으면 [파일 반입](../../shared/docs/infrastructure/access.md#파일-반입) 절의 방법으로 `airflow-1.22.0.tgz`를 `deploy/airflow/helm/vendor/`에 둡니다. 공식 배포 주소와 SHA-256은 `deploy/airflow/helm/chart.lock.json`의 `url`·`sha256`입니다.

[조회] 반입한 파일의 SHA-256이 lock의 값과 같은지 확인합니다.

```bash
sha256sum deploy/airflow/helm/vendor/airflow-1.22.0.tgz
grep '"sha256"' deploy/airflow/helm/chart.lock.json
```

성공: 두 줄의 해시가 같습니다.

다른 위치의 파일은 환경변수 `AIRFLOW_CHART_FILE`로 지정합니다. 명령마다 새 셸이 열릴 수 있으므로 검사·렌더·배포의 각 명령 앞에 같은 값을 붙입니다. 아래는 [검사] 명령의 예입니다.

```bash
AIRFLOW_CHART_FILE=<반입한 chart의 절대 경로> make airflow-check KUBE_CONTEXT="<context>"
```

`airflow-check`·`airflow-up`·렌더는 chart를 내려받지 않으며 고정 SHA-256이 다르면 중단합니다. dependency가 압축 파일에 포함되어 `helm dependency update`가 필요하지 않습니다.

## 2. DAG 포함 이미지 준비

실행 위치는 관리 호스트의 저장소 전체 checkout 루트(운영 agent가 실행되는 곳)입니다. 기존 containerd에 nerdctl·BuildKit을 연결해 Docker Engine 없이 빌드합니다.
control plane에서는 빌드하지 않습니다. 관리 호스트는 MinIO·Registry도 실행하므로 BuildKit의 동시 빌드 단계를 2로 제한합니다(`max-parallelism`).

한 타깃이 빌드와 사내 이미지 저장소 push를 수행합니다. `make ops-deploy APP=airflow`에서는 검사(`airflow-check`) 다음 단계입니다.

[검사]
```bash
make build-tools-check
```

성공: `빌드 도구 준비 완료`.

[변경] 클러스터는 바꾸지 않고 사내 이미지 저장소에 이미지를 올립니다. 저장소 밖 env를 쓰면 `AIRFLOW_ENV=<경로>`, push 계정 파일을 따로 두었으면 `REGISTRY_PUSH_ENV=<경로>`를 같은 명령에 붙입니다.
```bash
make airflow-image KUBE_CONTEXT="<context>"
```

성공: `Airflow 이미지 push 완료: store.etch.samsungds.net/airflow:3.3.2-<12자리>` 또는 `registry에 이미 있는 tag라 빌드하지 않았습니다: <이미지>`.

- 이미지 이름은 `k8s.env`의 `AIRFLOW_IMAGE_REPOSITORY`(`store.etch.samsungds.net/airflow`)와 `AIRFLOW_IMAGE_TAG`입니다. tag `3.3.2-auto`는 `apps/airflow` 소스(DAG 공유 폴더를 쓰면 `dags` 제외)와 `build.env` 내용으로 `3.3.2-<12자리>`가 됩니다. 소스가 바뀌면 tag가 바뀌므로 env를 고칠 필요가 없습니다. 고정하려면 `3.3.2-<이름>`을 직접 씁니다.
- registry에 같은 tag가 있으면 빌드하지 않고 끝납니다. 없으면 빌드 후 push 계정(`REGISTRY_PUSH_ENV`, 기본 `deploy/registry/env/push-initial.env`)으로 로그인해 올립니다.
- 로그인은 계정 파일의 `REGISTRY_USER`·`REGISTRY_PASSWORD`를 읽어 비밀번호를 표준 입력(`--password-stdin`)으로 전달하므로 입력을 기다리지 않습니다. containerd 소켓에 쓸 수 없는 계정은 nerdctl을 `sudo -n`으로 실행하므로 비밀번호 없는 sudo가 필요합니다([관리 호스트 sudo](../../shared/docs/infrastructure/access.md#관리-호스트-sudo)).
- 관리 호스트와 각 노드는 저장소 인증서를 신뢰해야 합니다([노드와 관리 호스트의 CA 신뢰](../../registry/docs/01-operations.md#노드와-관리-호스트의-ca-신뢰)).

아래는 빌드 단계를 직접 실행하는 `manage.py build-image`·`publish-image`의 옵션입니다. `make airflow-image`는 기본값을 씁니다.

| 빌드 옵션 | 기본값·용도 |
| --- | --- |
| `--builder` | `auto`: nerdctl이 있으면 nerdctl, 없으면 Docker. 선택한 빌더 검사에 실패하면 다른 빌더로 전환하지 않음. `publish-image`는 항상 nerdctl |
| `--containerd-namespace` | `default`. nerdctl·BuildKit worker의 공통 namespace |
| `--containerd-address` | `/run/containerd/containerd.sock`. nerdctl이 접속할 소켓 |
| `--buildkit-host` | `unix:///run/buildkit/buildkitd.sock`. nerdctl·buildctl이 접속할 주소 |

커스텀 소켓·namespace나 rootless 환경은 이 옵션을 실제 daemon과 일치시킵니다.
Docker를 쓰는 빌드 호스트는 `command -v docker`, `docker info`가 성공해야 하며 설치는 [공식 안내](https://docs.docker.com/engine/install/)와
[사내 패키지 미러](../../shared/docs/infrastructure/repositories.md)를 사용합니다.

### containerd 빌드 도구 준비

관리 호스트에 nerdctl·BuildKit이 없으면 `make ops-deploy`의 준비 검사가 `make build-tools-install`을 실행합니다. 직접 확인·설치할 때는 아래 두 명령을 씁니다. 실행 위치는 관리 호스트 저장소 루트입니다.

[검사] 설치·서비스·worker 상태만 조회합니다.

```bash
make build-tools-check
```

성공: `[통과]` 줄들과 마지막 줄 `빌드 도구 준비 완료`.

[변경] 없는 것만 설치합니다. 비밀번호 없는 sudo와 curl·tar·sha256sum·systemctl이 필요하고 containerd는 재시작하지 않습니다.

```bash
make build-tools-install
```

성공: `빌드 도구 준비 완료`.
실패: `비밀번호 없는 sudo 권한이 필요합니다`면 [관리 호스트 sudo](../../shared/docs/infrastructure/access.md#관리-호스트-sudo), `다운로드 실패`면 아래 표의 파일을 [파일 반입](../../shared/docs/infrastructure/access.md#파일-반입) 절의 방법으로 관리 호스트의 `$HOME/build-tools`에 둔 뒤 같은 명령을 다시 실행합니다. `SHA-256 불일치`면 `$HOME/build-tools`의 그 파일을 지우고 같은 명령을 다시 실행합니다.

설치 내용은 다음과 같습니다. Ubuntu 22.04·amd64(`x86_64`)와 기존 containerd 2.2.1 기준이며, 실제 설치 상태는 [서버 원본](../../shared/docs/infrastructure/servers.md#확인된-worker-설치-기준)을 따릅니다.

| 대상 | 내용 |
| --- | --- |
| 설치 조건 | `x86_64`, containerd 소켓 `/run/containerd/containerd.sock`이 있어야 함 |
| nerdctl | [2.4.2](https://github.com/containerd/nerdctl/releases/tag/v2.4.2) `nerdctl-2.4.2-linux-amd64.tar.gz`. SHA-256 `41a66995888043c0ba05f8061574eaba1b9e06b9b21c2a238215179df2728d3f`. 기존 containerd를 사용하므로 `nerdctl-full`이 아닌 **nerdctl 단독 패키지**를 `/usr/local/bin/nerdctl`에 설치 |
| BuildKit | [0.34.1](https://github.com/moby/buildkit/releases/tag/v0.34.1) `buildkit-v0.34.1.linux-amd64.tar.gz`. SHA-256 `a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b`. `/usr/local` 아래에 풀어 `/usr/local/bin/buildctl`·`buildkitd`를 설치 |
| 받는 곳 | [사내 저장소 원본](../../shared/docs/infrastructure/repositories.md#패키지chartartifact-주소)의 GitHub 미러. 미러의 파일 제공은 미확인. 받은 파일은 `$HOME/build-tools`에 두고 공식 릴리스의 SHA-256으로 검증. 버전을 바꾸면 파일 이름과 checksum을 함께 갱신 |
| 설정 파일 | `/etc/buildkit/buildkitd.toml`. 없을 때만 생성 |
| 서비스 | `/etc/systemd/system/buildkit.service`. 없을 때만 생성하고 `systemctl enable --now buildkit`으로 시작 |

생성하는 `/etc/buildkit/buildkitd.toml`의 내용입니다.

```toml
[worker.oci]
  enabled = false

[worker.containerd]
  enabled = true
  address = "/run/containerd/containerd.sock"
  namespace = "default"
  max-parallelism = 2
```

생성하는 `/etc/systemd/system/buildkit.service`의 내용입니다.

```ini
[Unit]
Description=이미지 빌드용 BuildKit
Requires=containerd.service
After=containerd.service

[Service]
Type=simple
ExecStart=/usr/local/bin/buildkitd --config /etc/buildkit/buildkitd.toml --addr unix:///run/buildkit/buildkitd.sock
Restart=on-failure
Delegate=yes

[Install]
WantedBy=multi-user.target
```

두 단계 빌드는 첫 단계의 로컬 의존성 이미지를 두 번째 단계의 `FROM`으로 사용하므로 같은 namespace의 containerd worker가 필요합니다.
OCI worker는 containerd의 로컬 이미지를 읽지 못합니다. containerd namespace `default`는 Kubernetes namespace `airflow`와 별개이며, `max-parallelism = 2`는 동시 빌드 단계를 제한해 같은 Worker에서 실행 중인 Pod와 자원을 나눠 쓰게 합니다.
사내 registry CA·미러 설정은 [BuildKit registry 설정](https://github.com/moby/buildkit/blob/v0.34.1/docs/buildkitd.toml.md)에 반영하며
containerd의 CRI 설정이 BuildKit에 자동 적용되지 않습니다. 원리는 [nerdctl 빌드 안내](https://github.com/containerd/nerdctl/blob/v2.4.2/docs/build.md)를 참고합니다.

기존 `/etc/buildkit/buildkitd.toml`이나 서비스가 있으면 설치 도구는 덮어쓰지 않습니다. 이때 `make build-tools-check`가 `BuildKit worker가 containerd(default)가 아닙니다`로 실패하면 [변경] 기존 파일의 CA·registry·서비스 설정은 그대로 두고 `[worker.oci]`의 `enabled = false`와 `[worker.containerd]`의 `enabled = true`·`address`·`namespace` 네 값만 위 내용과 같게 맞춥니다([관리 호스트 sudo](../../shared/docs/infrastructure/access.md#관리-호스트-sudo) 필요). 기존 서비스의 실제 `--config` 경로도 확인합니다.

[변경] 기존 BuildKit 설정을 바꿨을 때만 BuildKit 서비스를 다시 시작합니다. containerd 재시작은 필요하지 않습니다. 이어서 위의 `make build-tools-check`로 확인합니다.

```bash
sudo -n systemctl restart buildkit
```

[조회] 검사가 실패하면 상태를 자세히 봅니다. 실행 계정에 소켓 권한이 있으면 nerdctl·buildctl의 `sudo -n`을 생략할 수 있으며, 빌드·registry 인증·이미지 전달은 같은 계정으로 수행합니다.

```bash
uname -m
containerd --version
sudo -n systemctl is-active containerd buildkit
sudo -n sh -c 'command -v nerdctl buildctl buildkitd'
sudo -n nerdctl --address /run/containerd/containerd.sock --namespace default info
sudo -n buildctl --addr unix:///run/buildkit/buildkitd.sock debug workers --verbose
sudo -n journalctl -u buildkit -n 80 --no-pager
```

성공: `x86_64`, 두 서비스 `active`, 세 명령이 `/usr/local/bin/` 경로로 조회되고 nerdctl 연결이 성공하며 worker에 다음 두 label이 표시됩니다.

```text
org.mobyproject.buildkit.worker.executor: containerd
org.mobyproject.buildkit.worker.containerd.namespace: default
```

| 증상 | 조치 |
| --- | --- |
| 서비스 실패 | 위 `journalctl` 출력으로 로그 확인 |
| `docker` 실행 파일 없음 | nerdctl·BuildKit을 준비하고 `--builder nerdctl`로 실행 |
| `nerdctl`·`buildctl` 실행 파일 없음 | `make build-tools-install`, sudo의 PATH 확인 |
| containerd 연결 오류 | nerdctl 소켓 주소·실행 계정 권한·containerd 상태 확인 |
| BuildKit worker·namespace 오류 | buildkitd 실행·주소·권한과 containerd worker 설정 확인, OCI worker 비활성화 |
| `이미지 빌드 소스(apps/airflow)가 없습니다` | 저장소 전체 checkout의 루트에서 실행 |

### 두 단계 이미지 빌드

`make airflow-image`가 내부에서 수행하는 빌드의 설명입니다. 배포에는 `make airflow-image`를 쓰며 아래 빌드 명령은 절차로 실행하지 않습니다.

빌드 도구는 `env/build.env`를 build arg로 전달합니다. 사내 base image(`apache/airflow:3.3.2-python3.12` 미러)·APT/PIP mirror·trusted hosts·ODBC artifact URL과
`INSTALL_BIGDATAQUERY_PYTHON=true`, `INSTALL_BIGDATAQUERY_ODBC=true`가 기본값이며 `apps/airflow/image/Dockerfile.dependencies`의 기본값과 같습니다.
환경별 값은 `build.env`에서 바꾸고 비밀번호·접근 토큰은 넣지 않습니다.

빌드 도구는 이미지 이름(`AIRFLOW_IMAGE_REPOSITORY`·`AIRFLOW_IMAGE_TAG`)을 읽으려고 배포용 `k8s.env` 전체를 먼저 검사합니다.
그래서 빌드 host에도 배포와 같은 실제 값의 `k8s.env`가 필요하며, 자리표시자가 남아 있으면 `실제 값으로 교체하세요`로 중단합니다.
저장소 밖 env를 쓰면 관리 호스트에서 배포에 쓰는 파일과 같은 내용을 권한 `0600`으로 두고 `--env`로 지정합니다. kubeconfig는 두지 않습니다.

push 없이 빌드만 하는 명령의 형식입니다. 이 명령은 nerdctl을 실행 계정 그대로 호출하므로 containerd 소켓에 쓸 수 있는 계정이나 root 권한으로 실행합니다. Docker 빌드는 `--builder docker`를 사용합니다.

```text
python3 deploy/airflow/scripts/manage.py build-image --builder nerdctl \
  --build-env deploy/airflow/env/build.env --env <k8s.env 경로>
```

도구는 소스·빌더·daemon 접속을 먼저 확인한 뒤 다음 순서로 빌드합니다.

1. `apps/airflow/image/Dockerfile.dependencies`로 의존성 이미지(`<repository>:<tag>-dependencies`)를 만듭니다.
2. `apps/airflow/image/Dockerfile`로 DAG·플러그인을 추가합니다. 빌드 context는 `apps/airflow`이며 실제 env·로그·DSN 파일은 보내지 않습니다.

빌드 단계가 끝나면 `Airflow 이미지 빌드 완료`가 출력됩니다. `build-image`는 이미지를 push하지 않고, `make airflow-image`는 이어서 push합니다.
BigDataQuery Python·ODBC의 설치·import·DSN 접속과 mirror의 패키지 제공은 사내 빌드 호스트·서버에서 확인합니다.
`PIP_TRUSTED_HOST`는 pip 저장소 접근 설정이며 업무 API의 TLS 신뢰를 대신하지 않습니다. OIDC CA는 [별도 마운트](03-deploy.md#oidc-ca-configmap)를 사용합니다.
추가 Python 의존성은 의존성 Dockerfile에 넣고 새 태그로 빌드합니다. DAG의 pip·가상환경 동작 등 개발 안내는 [Airflow 개발 안내](../../../apps/airflow/README.md)를 따릅니다.

[검사] Docker daemon과 캐시된 `apache/airflow:3.3.2-python3.12`가 있는 개발 환경에서는 네트워크를 차단한 검사용 빌드로 최종 이미지의 코드 포함과 pip 기본값을 확인할 수 있습니다. Docker가 없는 관리 호스트에서는 실행하지 않습니다.

```bash
AIRFLOW_DOCKER_TESTS=1 python3 -m unittest discover \
  -s deploy/airflow/tests -p test_manage.py -k ImageBuildIntegrationTests -v
```

### 이미지 전달

빌드한 이미지는 빌드 서버 containerd의 빌드용 `default` namespace에 저장됩니다. `make airflow-image`는 사내 이미지 저장소로 push하고 각 노드가 거기서 내려받습니다.
registry를 쓸 수 없을 때만 아래처럼 `.tar`로 저장해 Worker에 반입하고, 이 경우 `AIRFLOW_IMAGE_REPOSITORY`에 registry 주소 없는 이름을 씁니다. PostgreSQL 이미지도 같은 기준으로 준비합니다.
공유 폴더의 DAG 변경은 [공유 폴더 관리](04-operations.md#dag-파일-추가수정삭제)를 따릅니다. 플러그인, 패키지, ODBC가 바뀌면 새 이미지 태그로 빌드하고 배포합니다. 이미지에 포함된 DAG는 로컬 개발과 최초 공유 폴더 준비에 사용할 수 있습니다.

#### Registry를 사용하는 경우

빌드 호스트와 Worker가 접근할 수 있고 업로드 권한이 있는 registry를 사용합니다. `k8s.env`의 `AIRFLOW_IMAGE_REPOSITORY`에 registry 주소를 포함하고 같은 이름으로 빌드합니다.
private registry 인증이 필요하면 대상 namespace에 imagePullSecret을 만들고 `IMAGE_PULL_SECRET`에 이름을 입력합니다.

사내 이미지 저장소를 사용하면 `AIRFLOW_IMAGE_REPOSITORY=store.etch.samsungds.net/airflow`로 지정합니다. 익명 pull이므로 `IMAGE_PULL_SECRET`은 비워 둡니다.
빌드 호스트와 Worker의 HTTPS 인증서 신뢰 설정은 [노드와 관리 호스트의 CA 신뢰](../../registry/docs/01-operations.md#노드와-관리-호스트의-ca-신뢰)를 따릅니다.

로그인과 push는 `make airflow-image`가 수행하므로 보통은 아래 명령이 필요 없습니다.

[변경] 이미 빌드한 이미지를 따로 push할 때만 빌드한 서버의 저장소 루트에서 실행합니다. `<repository:tag>`는 env와 같은 이미지 이름으로 바꿉니다. 계정과 비밀번호는 push 계정 파일에서 읽어 전달하므로 입력을 기다리지 않습니다.

```bash
sudo -n nerdctl --address /run/containerd/containerd.sock --namespace default image inspect <repository:tag> >/dev/null
sed -n 's/^REGISTRY_PASSWORD=//p' deploy/registry/env/push-initial.env |
  sudo -n nerdctl --address /run/containerd/containerd.sock --namespace default login \
    --username "$(sed -n 's/^REGISTRY_USER=//p' deploy/registry/env/push-initial.env)" --password-stdin store.etch.samsungds.net
sudo -n nerdctl --address /run/containerd/containerd.sock --namespace default push <repository:tag>
```

성공: 세 명령이 오류 없이 끝납니다. [검사] 이어서 `make airflow-image KUBE_CONTEXT="<context>"`를 실행해 `registry에 이미 있는 tag라 빌드하지 않았습니다`가 나오면 registry에 env의 tag가 있는 것입니다. 선택한 Worker는 인증·CA·네트워크 설정으로 그 이미지를 내려받을 수 있어야 합니다.

#### Registry 없이 전달하는 경우

관리 호스트가 아닌 노드에서 실행하는 블록은 관리 호스트의 저장소 밖 파일에 저장해 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행)의 `--script`로 전달합니다. `<repository:tag>`는 `AIRFLOW_IMAGE_REPOSITORY:AIRFLOW_IMAGE_TAG`와 같은 이름으로 바꿉니다. registry 없이 쓸 때의 이름은 `airflow:3.3.2-release-1`처럼 registry 주소가 없는 형식입니다.

**1. 빌드한 Worker 자신에 등록**

[변경] 이미지를 빌드한 Worker에서 실행합니다. 빌드한 이미지를 파일 복사 없이 Kubernetes용 `k8s.io` namespace에 등록합니다.

```bash
sudo -n nerdctl --address /run/containerd/containerd.sock --namespace default image inspect <repository:tag> >/dev/null
sudo -n nerdctl --address /run/containerd/containerd.sock --namespace default save <repository:tag> \
  | sudo -n ctr --address /run/containerd/containerd.sock --namespace k8s.io images import -
sudo -n ctr --address /run/containerd/containerd.sock --namespace k8s.io images ls | grep airflow
```

성공: `inspect`가 성공하고 `k8s.io` 목록에 배포할 repository·tag가 있습니다. 짧은 이름은 `docker.io/library/`가 붙어 표시될 수 있습니다.
이미지를 찾지 못하면 `sudo -n nerdctl --address /run/containerd/containerd.sock --namespace default images`로 실제 이름·태그를 확인합니다.
다른 namespace·주소로 빌드했다면 같은 값을 지정하고, Docker로 빌드했다면 `docker save`를 사용합니다.

**2. 다른 Worker에 복사**

Airflow Pod는 `khinfow01`에서만 실행하므로 보통 필요하지 않습니다. [워커 부하 테스트](04-operations.md#6-cpu메모리-부하-테스트)처럼 다른 Worker에서 같은 이미지를 쓸 때만 진행합니다.

[변경] 이미지가 있는 Worker에서 `.tar`로 저장합니다.

```bash
sudo -n nerdctl --address /run/containerd/containerd.sock --namespace default save \
  -o /tmp/airflow-image.tar <repository:tag>
sudo -n chown "$(id -u):$(id -g)" /tmp/airflow-image.tar
```

[변경] `/tmp/airflow-image.tar`를 대상 Worker의 `/tmp/airflow-image.tar`로 옮깁니다. 이미지 tar는 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행)의 `--copy`가 보낼 수 있는 크기(64KiB)를 넘으므로 [파일 반입](../../shared/docs/infrastructure/access.md#파일-반입) 절의 방법으로 같은 파일을 옮깁니다.

[변경] 대상 Worker에서 `k8s.io` namespace에 등록하고 목록을 확인합니다.

```bash
hostname
sudo -n ctr --address /run/containerd/containerd.sock --namespace k8s.io images import /tmp/airflow-image.tar
sudo -n ctr --address /run/containerd/containerd.sock --namespace k8s.io images ls | grep airflow
```

성공: `hostname`이 대상 Worker이고 목록에 배포할 repository·tag가 있습니다.
K3s Worker는 `sudo -n k3s ctr images import /tmp/airflow-image.tar`, `sudo -n k3s ctr images ls`를 사용합니다.
이미지 준비만으로 실행 중인 Airflow는 갱신되지 않습니다.

## 3. ODBC 설정 준비

기존 ODBC 디렉터리 전체를 같은 노드에서 읽기 전용으로 마운트합니다.
`ODBC_HOST_PATH`(현재 `/appdata/airflow/odbc`)에 INI·인증서·하위 파일을 두며, 파일 배치 명령은 [ODBC 파일 안내](../odbc/README.md#worker에-반영)를 따릅니다. 폴더 자체는 없으면 `airflow-up`이 `50000:0`·`0750`으로 만듭니다.
이 저장소에는 실제 DSN·인증서가 없으므로 빈 파일로 대신하지 않습니다. `airflow-up`을 거치지 않는 [직접 deploy](03-deploy.md#직접-deploy와-helm-override)에서 경로가 없으면 Kubernetes가 Pod 기동을 차단합니다.

| 기존 컨테이너 설정 | Kubernetes 유지 값 |
| --- | --- |
| ODBC 디렉터리 | `/usr/local/odbc`, 전체 디렉터리 읽기 전용 |
| `ODBCINI` | `/usr/local/odbc/odbc.ini` |
| `ODBCSYSINI` | `/usr/local/odbc` |
| `CLOUDERAIMPALAINI` | `/etc/cloudera.impalaodbc.ini`, 기존 드라이버 이미지에서 상속 |

Secret 방식은 `ODBC_HOST_PATH=`로 비우고 `NAMESPACE`와 같은 namespace의 기존 Secret 이름을 `ODBC_SECRET_NAME`에 지정합니다. 두 방식을 함께 지정하면 검사에서 중단합니다.

준비가 끝난 상태는 선택한 Worker에 실제 설정 파일이 있고 UID 50000이 읽을 수 있거나, 참조 Secret이 대상 namespace에 있는 것입니다.
