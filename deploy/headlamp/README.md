# Headlamp 서버 운영 UI

[배포 문서 안내](../README.md)

Keycloak/OIDC 연동 없이 Kubernetes ServiceAccount 토큰으로 로그인합니다.
기존 로컬 Headlamp처럼 `view`와 nodes/namespaces 조회 권한을 사용합니다.
기본 Kubernetes `view`는 Secret 조회·리소스 수정·Pod exec 권한을 포함하지 않습니다.
클러스터에서 `view`에 추가한 집계 권한은 그대로 적용됩니다.
Headlamp 서버 Pod의 계정과 로그인용 `headlamp-viewer` 계정은 분리합니다.

## 준비와 검사

Python 3.10+, Helm 3, kubectl과 클러스터 배포·RBAC 생성 권한이 필요합니다.
선택 checkout은 `bash deploy/shared/scripts/checkout-server.sh headlamp`입니다.
`local/`이나 다른 앱 없이 동작합니다. namespace와 release 이름은 `headlamp`로 고정합니다.

### 서버에 Helm이 없는 경우

Linux x86_64 서버용 공식 Helm 3.19.0 압축 파일을
`deploy/shared/tools/helm-v3.19.0-linux-amd64.tar.gz`에 포함합니다. 약 17MiB이며
서버 선택 checkout의 공통 경로에 포함되므로 Git으로 받을 수 있습니다.
[공식 다운로드 원본](https://get.helm.sh/helm-v3.19.0-linux-amd64.tar.gz) 그대로이며
압축 파일 안에 LICENSE와 README가 포함되어 있습니다. ARM 서버에는 사용하지 않습니다.

서버의 저장소 루트에서 실행합니다. 체크섬 검사에 실패하면 설치하지 않습니다.

```bash
uname -m
printf '%s  %s\n' \
  a7f81ce08007091b86d8bd696eb4d86b8d0f2e1b9f6c714be62f82f96a594496 \
  deploy/shared/tools/helm-v3.19.0-linux-amd64.tar.gz | sha256sum -c -

# x86_64 및 체크섬 OK를 확인한 뒤 설치합니다.
mkdir -p .tools/helm-v3.19.0
tar -xzf deploy/shared/tools/helm-v3.19.0-linux-amd64.tar.gz -C .tools/helm-v3.19.0
sudo install -m 0755 .tools/helm-v3.19.0/linux-amd64/helm /usr/local/bin/helm
helm version --short
```

### 설정과 chart 준비

```bash
cp deploy/headlamp/env/k8s.env.example deploy/headlamp/env/k8s.env
# 예시의 사내 미러 경로를 확인하고 필요한 경우 IMAGE_PULL_SECRET을 입력합니다.
make headlamp-fetch-chart
make server-check APP=headlamp
make headlamp-check
```

`make headlamp-fetch-chart`는 `helm/chart.lock.json`에 지정된 사내 GitHub 파일 미러
`http://repository.samsungds.net/repository/proxy-raw-github.com`에서 chart를 받습니다.
이미지용 `HEADLAMP_REGISTRY`와 chart 다운로드 주소는 별도입니다.

사내 미러에 접근할 수 없는 외부 PC에서는
[공식 원본](https://github.com/kubernetes-sigs/headlamp/releases/download/headlamp-helm-0.45.0/headlamp-0.45.0.tgz)을
직접 다운로드해 `deploy/headlamp/helm/vendor/headlamp-0.45.0.tgz`로 서버에 반입합니다.
`HEADLAMP_CHART_FILE`로 외부 파일도 지정할 수 있습니다.
SHA-256은 `helm/chart.lock.json`으로 검증하며 검사·배포 시 자동 다운로드하지 않습니다.
이미지는 `<HEADLAMP_REGISTRY>/headlamp-k8s/headlamp:v0.45.0`이며 사내 미러에 준비해야 합니다.
인증이 필요하면 `headlamp` namespace에 registry Secret을 미리 생성하고 `IMAGE_PULL_SECRET`에 이름을 입력합니다.

```bash
python3 deploy/headlamp/scripts/manage.py render --env deploy/headlamp/env/k8s.env
make headlamp-up KUBE_CONTEXT=<대상-context>
make headlamp-ui KUBE_CONTEXT=<대상-context>
```

`HEADLAMP_ENV=/절대경로/k8s.env`로 외부 설정을 지정할 수 있습니다.
`headlamp-up`은 고정 chart로 Helm 설치/갱신하고 최대 5분 동안 준비를 기다립니다.
실패 시 namespace나 release를 자동 삭제하지 않습니다.

## 접속

`headlamp-ui`가 발급한 조회 token을 `http://localhost:4466` 로그인 화면에 붙여 넣습니다.
토큰은 1시간 유효기간을 요청하며 실제 기간은 API server 정책에 따릅니다. 만료되면 명령을 다시 실행합니다.
토큰을 저장소·공용 로그에 저장하지 않습니다. port-forward는 127.0.0.1에만 바인딩합니다.
서버에서 명령을 실행했다면 PC에서 `ssh -L 4466:127.0.0.1:4466 <서버>` 터널을 열어 접속합니다.
사용자에게 토큰을 발급하려면 해당 ServiceAccount의 token 생성 권한이 필요합니다.

클러스터 리소스·Pod 로그를 조회할 수 있으며 변경 작업은 권한에 의해 차단됩니다.
Ingress·NodePort·OIDC·동적 플러그인 다운로드·영속 볼륨은 사용하지 않습니다.
CPU/메모리의 실시간 수치는 클러스터에 metrics-server가 있어야 표시됩니다.
로컬 개발의 기존 `make k8s-ui`는 그대로 사용합니다.

공식 근거: [Headlamp 설치·토큰 접속](https://headlamp.dev/docs/latest/installation/in-cluster/).
