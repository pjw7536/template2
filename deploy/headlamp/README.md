# Headlamp 서버 운영 UI

[배포 문서 안내](../README.md) · [Kubernetes 입문 가이드](../shared/docs/kubernetes/README.md)

Keycloak/OIDC 연동 없이 Kubernetes ServiceAccount 토큰으로 로그인합니다.
기존 로컬 Headlamp처럼 `view`와 nodes/namespaces 조회 권한을 사용합니다.
기본 Kubernetes `view`는 Secret 조회·리소스 수정·Pod exec 권한을 포함하지 않습니다.
클러스터에서 `view`에 추가한 집계 권한은 그대로 적용됩니다.
Headlamp 서버 Pod의 계정과 로그인용 `headlamp-viewer` 계정은 분리합니다.

## 준비와 검사

Python 3.10+, Helm 3, kubectl과 클러스터 배포·RBAC 생성 권한이 필요합니다.
선택 checkout은 `bash deploy/shared/scripts/checkout-server.sh headlamp`입니다.
`local/`이나 다른 앱 없이 동작합니다. namespace와 release 이름은 `headlamp`로 고정합니다.

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
# HTTPS 배포는 아래 인증서 등록을 먼저 완료합니다.
make headlamp-up KUBE_CONTEXT=<대상-context>
```

`HEADLAMP_ENV=/절대경로/k8s.env`로 외부 설정을 지정할 수 있습니다.
`headlamp-up`은 고정 chart로 Helm 설치/갱신하고 최대 5분 동안 준비를 기다립니다.
실패 시 namespace나 release를 자동 삭제하지 않습니다.

## APP VIP로 HTTPS 접속 — 인증서부터 준비

PFX/P7B를 이미 받았다면 [인증서 추출부터 배포까지 전체 가이드](HTTPS_CERTIFICATE_GUIDE.md)를 순서대로 따릅니다.
CP1의 `/appdata/certs` 기준으로 풀체인 생성·검증·Secret 등록·접속 확인까지 설명합니다.

목표 주소는 `https://etch.samsungds.net/headlamp/`입니다.
`PC → APP VIP:443 → Worker의 Traefik → Headlamp Service → Headlamp Pod`로 연결합니다.
CP1은 명령 실행 위치이며 port-forward를 켜 두지 않습니다.

### 1. 사내 인증서 발급

사내 인증서 담당자에게 아래 조건으로 발급을 요청합니다.

- 서버 도메인/SAN: `etch.samsungds.net` (URL 경로 `/headlamp/`는 인증서에 넣지 않음)
- 용도: 사내 Kubernetes Traefik에서 HTTPS 종료
- 형식: PEM 서버 인증서와 중간 인증서 체인. 해당 인증서와 짝인 PEM 개인키도 필요
- 사용자 PC가 발급 CA를 신뢰하도록 사내 루트 CA 배포 확인

사내 절차가 CSR을 요구하면 인증서 담당자의 키·CSR 생성 지침을 따릅니다.
개인키는 서버의 제한된 디렉터리에 보관하고 Git에 넣거나 대화에 붙여 넣지 않습니다.
이미 동일 도메인의 유효한 인증서가 있으면 담당자와 재사용을 확인합니다.
같은 Traefik에서 같은 도메인으로 운영하는 다른 앱의 인증서도 동일하게 갱신 관리합니다.
인증서가 없으면 이 단계까지 준비하고 발급 후 아래 절차를 진행합니다.

### 2. 인증서를 Kubernetes에 등록 — CP1

서버 인증서가 먼저, 이어서 중간 인증서 순서인 `fullchain.pem`과 짝인 `privkey.pem`을 서버에 준비합니다.
다음 파일 경로는 실제 보관 위치로 바꿉니다. `openssl`은 서버 인증서 도메인·만료를 확인합니다.

```bash
kubectl config current-context
export KUBE_CONTEXT="$(kubectl config current-context)"
export TLS_CERT_FILE='/실제/인증서/fullchain.pem'
export TLS_KEY_FILE='/실제/인증서/privkey.pem'

openssl x509 -in "$TLS_CERT_FILE" -noout -subject -issuer -dates -ext subjectAltName
openssl x509 -in "$TLS_CERT_FILE" -noout -checkhost etch.samsungds.net
openssl x509 -in "$TLS_CERT_FILE" -noout -checkend 0
```

도메인 불일치·만료이면 먼저 재발급합니다. 아래 블록은 Secret 내용을 화면이나 파일에 출력하지 않습니다.
개인키가 인증서와 다르면 Secret 생성이 실패합니다.

```bash
set -o pipefail
kubectl --context "$KUBE_CONTEXT" create namespace headlamp --dry-run=client -o yaml | \
  kubectl --context "$KUBE_CONTEXT" apply -f -
kubectl --context "$KUBE_CONTEXT" -n headlamp create secret tls headlamp-tls \
  --cert="$TLS_CERT_FILE" --key="$TLS_KEY_FILE" --dry-run=client -o yaml | \
  kubectl --context "$KUBE_CONTEXT" apply -f -
```

Ingress와 TLS Secret은 같은 `headlamp` namespace에 둡니다.
Secret 등록 성공이 인증서 체인·PC 신뢰까지 보장하지는 않으므로 마지막 HTTPS 검사도 수행합니다.

### 3. env 설정 후 배포 — CP1 프로젝트 루트

기존 `deploy/headlamp/env/k8s.env`의 이미지 설정을 유지하고 다음 두 항목을 추가하거나 수정합니다.
이미 있는 키를 중복해서 추가하지 않습니다. 새로운 예시 env에는 아래 값이 포함되어 있습니다.

```dotenv
HEADLAMP_HOST=etch.samsungds.net
HEADLAMP_TLS_SECRET=headlamp-tls
```

```bash
make server-check APP=headlamp
make headlamp-check
make headlamp-up KUBE_CONTEXT="$KUBE_CONTEXT"

kubectl --context "$KUBE_CONTEXT" -n headlamp get pods,svc,ingress -o wide
kubectl --context "$KUBE_CONTEXT" -n etch-sso get pods -l app.kubernetes.io/name=traefik -o wide
```

`headlamp-up`은 TLS Secret 타입·필수 키와 기존 Traefik을 사전 확인합니다.
Headlamp는 `/headlamp` baseURL과 해당 경로의 health probe로 실행하며 Ingress는 HTTPS만 연결합니다.
경로를 지우는 StripPrefix는 사용하지 않습니다. Traefik의 기존 namespace 감시 목록을 유지하면서
`headlamp`를 추가하고 해당 namespace의 라우팅 조회 권한을 준비합니다.
기존 Traefik의 이미지·replica·VIP 배치·Service는 유지합니다. 감시 목록 변경으로 Pod가 교체될 수 있습니다.
배포 계정에는 Helm 배포 외에도 Traefik Deployment 조회·patch와 headlamp Role·RoleBinding 관리 권한이 필요합니다.

Helm 성공 후 Traefik 연결만 실패했다면 Headlamp는 남아 있습니다. 오류 원인을 해결한 뒤 같은 명령으로 재실행합니다.
resourceVersion 오류는 동시 변경을 감지한 것이므로 다른 배포 작업을 확인합니다.
`kubectl apply -k deploy/shared/ingress`로 덮어쓰지 않습니다.

### 4. VIP·DNS·로그인 확인

APP VIP의 Backend가 정상인 상태에서 DNS 담당자가 `etch.samsungds.net`을 `10.172.26.150`으로 연결합니다.
DNS 변경 전에도 아래 명령으로 VIP·인증서·Headlamp 경로를 함께 검사할 수 있습니다.
사내 CA가 검사 PC에 설치되지 않았다면 `--cacert /실제/사내-ca.pem`을 추가합니다.

```bash
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --resolve etch.samsungds.net:443:10.172.26.150 \
  https://etch.samsungds.net/headlamp/ -o /dev/null

kubectl --context "$KUBE_CONTEXT" -n headlamp create token headlamp-viewer --duration=1h
```

브라우저에서 **https://etch.samsungds.net/headlamp/** 를 열고 발급된 토큰으로 로그인합니다.
정적 파일 로딩·노드 목록·Pod 로그 조회까지 확인합니다. 브라우저가 인증서를 신뢰하지 않으면 CA 설정을 먼저 해결합니다.
인증서 오류는 SAN·기간·체인·PC 신뢰, 404는 Ingress·namespace 감시, 503은 Headlamp Pod·Service endpoint를 확인합니다.

## 임시 접속

HTTPS 설정 없이 기존 port-forward 방식만 쓰려면 env의 `HEADLAMP_HOST`와 `HEADLAMP_TLS_SECRET`을 모두 비웁니다.
HTTPS 설정으로 배포한 Pod를 port-forward로 확인할 때도 URL 끝에 `/headlamp/`를 붙입니다.


### localhost 또는 SSH 터널로 접속

`make headlamp-ui KUBE_CONTEXT=<대상-context>`가 출력한 주소의 로그인 화면에 조회 token을 붙여 넣습니다.
토큰은 1시간 유효기간을 요청하며 실제 기간은 API server 정책에 따릅니다. 만료되면 명령을 다시 실행합니다.
토큰을 저장소·공용 로그에 저장하지 않습니다. `make headlamp-ui`의 port-forward는 127.0.0.1에만 바인딩합니다.
서버에서 명령을 실행했다면 PC에서 `ssh -L 4466:127.0.0.1:4466 <서버>` 터널을 열어 접속합니다.
사용자에게 토큰을 발급하려면 해당 ServiceAccount의 token 생성 권한이 필요합니다.

### SSH 없이 CP1 주소로 접속

CP1에서 port-forward를 실행하면 PC 브라우저의 접속 주소는 `http://<CP1 IP>:4466`입니다.
Headlamp Pod가 다른 노드에 있어도 CP1이 연결을 전달합니다.

```text
내 PC 브라우저 → CP1 IP:4466 → CP1의 port-forward → Headlamp Service → Headlamp Pod
```

1. CP1에서 기존 `make headlamp-ui`가 실행 중이면 `Ctrl+C`로 종료합니다.
2. 아래 두 값을 실제 context 이름과 CP1에 할당된 IP로 바꾸고 CP1에서 실행합니다.

   ```bash
   export HEADLAMP_CONTEXT='실제-context-이름'
   export CP1_IP='CP1의-실제-IP'

   kubectl --context "$HEADLAMP_CONTEXT" -n headlamp \
     create token headlamp-viewer --duration=1h

   kubectl --context "$HEADLAMP_CONTEXT" -n headlamp \
     port-forward --address "$CP1_IP" svc/headlamp 4466:80
   ```

3. 이 터미널을 켜 둔 채 내 PC 브라우저에서 `http://<CP1 IP>:4466`을 엽니다. 출력된 token을 로그인 화면에 붙여 넣습니다.

`--address`는 명령을 실행하는 CP1의 IP입니다. 다른 노드나 Pod의 IP를 넣지 않습니다.
`Forwarding from ...`은 연결 대기, `Handling connection for 4466`은 접속 요청을 전달 중이라는 정상 로그입니다.
명령이 브라우저를 자동으로 열지는 않습니다.

PC에서 연결되지 않으면 PC → CP1의 TCP 4466 접근을 확인하고 방화벽 허용 범위는 필요한 사내 PC로 제한합니다.
이 방식은 HTTP를 사용하는 임시 접속이며 port-forward를 종료하면 연결도 끊깁니다.
상시 공개 주소나 HTTPS 접속을 제공하는 배포 설정은 아닙니다.

### 조회 범위

클러스터 리소스·Pod 로그를 조회할 수 있으며 변경 작업은 권한에 의해 차단됩니다.
Ingress는 HTTPS 설정 시 사용합니다. NodePort·OIDC·동적 플러그인 다운로드·영속 볼륨은 사용하지 않습니다.
CPU/메모리의 실시간 수치는 클러스터에 metrics-server가 있어야 표시됩니다.
로컬 개발의 기존 `make k8s-ui`는 그대로 사용합니다.

공식 근거: [Headlamp 설치·토큰 접속](https://headlamp.dev/docs/latest/installation/in-cluster/).

공식 근거: [Headlamp baseURL·probe 설정](https://headlamp.dev/docs/latest/installation/base-url/), [Kubernetes Ingress TLS](https://kubernetes.io/docs/concepts/services-networking/ingress/#tls).
