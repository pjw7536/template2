# Headlamp 서버 운영 UI

[배포 문서 안내](../README.md) · [Kubernetes 입문 가이드](../shared/docs/kubernetes/README.md)

Keycloak OIDC로 로그인하며 `/headlamp-admins` 그룹에 `cluster-admin` 전체 관리 권한을 부여합니다.
모든 namespace의 조회·수정·삭제, Secret 접근과 RBAC 관리를 포함합니다. 다른 RBAC 권한은 합산됩니다.
Headlamp Pod 자체에는 사용자 조회 권한을 부여하지 않으며 공용 로그인용 `headlamp-viewer` 계정은 제거합니다.

## 기본 운영 설정

| 항목 | 값 |
| --- | --- |
| 접속 주소 | `https://etch.samsungds.net/headlamp/` |
| Keycloak issuer | `https://etch-sso.samsungds.net/realms/etch` |
| Client ID | `headlamp` |
| TLS Secret | `headlamp/headlamp-tls` |
| Client secret 저장소 | `headlamp/headlamp-oidc`, 키 `OIDC_CLIENT_SECRET` |
| Keycloak CA | `headlamp/headlamp-oidc-ca`, 키 `ca.crt` |
| 인증서 폴더 | `deploy/shared/certs/etch.samsungds.net/` |

`make headlamp-*`는 실제 설정 파일 `env/k8s.env`를 사용합니다.
이 파일은 일반 설정만 담으며 Git에 포함합니다. Client Secret은 Kubernetes Secret에서 관리합니다.
`env/k8s.env`를 배포·검사의 단일 입력으로 사용하고 Git에서 추적합니다.
다른 설정은 `HEADLAMP_ENV=/절대경로/k8s.env`로 지정할 수 있습니다.
기존 실제 env는 자동으로 덮어쓰지 않습니다. 오래된 파일은 운영 기본값과 비교합니다.

## 준비와 검사

Python 3.10+, Helm 3, kubectl과 대상 클러스터 배포 권한이 필요합니다.
선택 checkout은 `bash deploy/shared/scripts/checkout-server.sh headlamp`입니다.
`local/`이나 다른 앱 소스 없이 실행하며 namespace·Helm release 이름은 `headlamp`입니다.

1. [공용 인증서 안내](../shared/certs/README.md)에서 Headlamp 인증서를 검증하고 TLS Secret에 등록합니다.
2. [Keycloak 로그인 안내](OIDC.md)에서 client·그룹·로그인 Secret·CA·API server 인증을 준비합니다.
3. 고정 chart를 준비하고 검사합니다.

```bash
make headlamp-fetch-chart
make server-check APP=headlamp PROFILE=prod
make headlamp-check
```

chart는 `helm/chart.lock.json`의 사내 미러에서 받으며 SHA-256을 검증합니다.
외부 PC에서는 [공식 chart](https://github.com/kubernetes-sigs/headlamp/releases/download/headlamp-helm-0.45.0/headlamp-0.45.0.tgz)를
다운로드해 `deploy/headlamp/helm/vendor/headlamp-0.45.0.tgz`로 반입하거나 `HEADLAMP_CHART_FILE`로 지정합니다.
검사·배포는 자동 다운로드하지 않습니다. 이미지 태그는 `v0.45.0`입니다.
registry 인증이 필요한 환경에서는 `IMAGE_PULL_SECRET`을 별도로 준비합니다.

## 적용과 확인

저장소 루트에서 context를 명시합니다. 앞 명령이 실패하면 해결한 뒤 다음으로 진행합니다.

```bash
kubectl config get-contexts
read -r -p '대상 context: ' KUBE_CONTEXT
export KUBE_CONTEXT
make headlamp-up KUBE_CONTEXT="$KUBE_CONTEXT"
make headlamp-ui KUBE_CONTEXT="$KUBE_CONTEXT"
```

`headlamp-up`은 OIDC Secret·선택 CA·TLS Secret과 기존 Traefik을 검사한 뒤 Helm으로 적용합니다.
기존 Traefik의 namespace 감시 목록과 배치를 보존합니다. RBAC·Deployment 변경 권한이 필요합니다.
Headlamp는 `/headlamp` baseURL을 사용하며 StripPrefix를 적용하지 않습니다.
`headlamp-ui`는 배포된 HTTPS 주소를 출력합니다. 공용 토큰을 발급하거나 port-forward를 실행하지 않습니다.

정적 검사 성공은 실제 image pull·인증서·로그인 성공과 다릅니다.
[HTTPS 확인](HTTPS_CERTIFICATE_GUIDE.md)과 [그룹별 로그인 검증](OIDC.md)을 수행합니다.
Helm 성공 후 Traefik 연결만 실패했다면 오류를 해결하고 다시 실행합니다. release를 자동 삭제하지 않습니다.
CPU·메모리 실시간 수치는 metrics-server가 있어야 합니다. 로컬 `make k8s-ui`는 기존 로컬 구성을 사용합니다.
