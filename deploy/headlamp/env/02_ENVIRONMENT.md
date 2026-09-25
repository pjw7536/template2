# 02. Headlamp 환경변수

[전체 순서](../README.md) · [서버 준비](../01_SERVER_SETUP.md)

`env/k8s.env`가 검사·배포·client JSON 생성의 단일 입력입니다.
일반 설정만 담고 Git으로 전달합니다. Client secret은 Kubernetes Secret에 등록합니다.
Keycloak env를 자동으로 읽거나 복제하지 않으므로 주소가 바뀌면 아래 값을 함께 맞춥니다.

| 변수 | 의미와 확인 위치 |
| --- | --- |
| `HEADLAMP_REGISTRY` | Headlamp 이미지 미러. `https://` 없이 입력 |
| `IMAGE_PULL_SECRET` | `headlamp` namespace의 이미지 인증 Secret. 불필요하면 빈 값 |
| `HEADLAMP_HOST` | 브라우저 접속 DNS 이름. scheme·경로 제외 |
| `HEADLAMP_TLS_SECRET` | 같은 namespace의 사이트 TLS Secret |
| `HEADLAMP_OIDC_ISSUER_URL` | Keycloak의 `keycloak-public-url` + `/realms/etch`. discovery issuer와 정확히 일치, 끝 `/` 제외 |
| `HEADLAMP_OIDC_CLIENT_ID` | 전용 client ID. 기본 `headlamp`. API server audience도 동일하게 설정 |
| `HEADLAMP_OIDC_SECRET` | 같은 namespace의 Secret 이름. 비어 있지 않은 `OIDC_CLIENT_SECRET` 키 하나만 등록 |
| `HEADLAMP_OIDC_CA_CONFIGMAP` | 같은 namespace의 Keycloak CA ConfigMap 이름. PEM `ca.crt` 키 필요. 공개 CA이면 빈 값 |

`KEY=value` 형식으로 입력합니다. 값에 shell 따옴표·변수 치환을 넣지 않습니다.
`.secrets.env`를 읽지 않으며 client secret 값을 이 파일에 추가하면 검사에서 거부합니다.

## Make 명령에 전달하는 값

다음 항목은 `k8s.env`에 추가하지 않고 Make 인자 또는 프로세스 환경변수로 전달합니다.

| 변수 | 용도 |
| --- | --- |
| `HEADLAMP_ENV` | 다른 일반 설정 파일의 경로 |
| `KUBE_CONTEXT` | 배포·접속 확인 대상. `headlamp-up`, `headlamp-ui`에서 필수 |
| `HEADLAMP_CHART_FILE` | 반입한 고정 chart 경로. 동일 SHA-256 검사 적용 |
| `HEADLAMP_OIDC_CA_FILE` | `headlamp-oidc-check`가 실행 서버에서 읽을 PEM CA 파일 |
| `HELM_BIN` | Helm 실행 파일 경로. 기본 `helm` |

## 검사 범위

| 명령 | 확인하는 내용 |
| --- | --- |
| `make headlamp-setup-env` | 선택한 env 검증 후 안내 명령용 공개 변수 출력. chart·클러스터 불필요 |
| `make headlamp-check` | 선택한 `HEADLAMP_ENV`·chart 해시·Helm 렌더. 클러스터 접속 없음 |
| `make server-check APP=headlamp PROFILE=prod` | 저장소 기본 `env/k8s.env`의 정적 검사. 사용자 지정 env는 위 headlamp-check로 검사 |
| `make headlamp-oidc-client` | 현재 env에 맞는 비밀값 없는 client JSON 출력. Keycloak에 자동 등록하지 않음 |
| `make headlamp-oidc-check HEADLAMP_OIDC_CA_FILE=/경로/ca.pem` | 실행 서버에서 Keycloak TLS·discovery·issuer·code flow·S256·RS256 공개키 검사. chart·관리자 credential 불필요 |
| `make headlamp-up KUBE_CONTEXT=대상` | Secret·CA 키·TLS·Traefik 사전 검사 후 Helm 적용 |
| `make headlamp-ui KUBE_CONTEXT=대상` | 배포 상태와 접속 주소 확인 |

OIDC 연결 검사는 client 존재·secret 유효성·그룹 가입·실제 토큰 서명·Kubernetes 권한까지 검사하지 않습니다.
Pod와 모든 API server에서도 discovery·JWKS 접근이 가능해야 합니다.
Keycloak 인증서 갱신으로 CA가 바뀌면 로컬 검사 파일, Headlamp ConfigMap, API server CA를 모두 갱신합니다.
Secret 또는 CA 변경 후 Headlamp를 재시작하는 절차는 [운영 참고](../operations/README.md)를 따릅니다.

## 고정 계약과 파일 역할

namespace·Helm release는 `headlamp`, baseURL은 `/headlamp`, 관리 그룹은 `/headlamp-admins`입니다.
설치 명령은 기존 `etch-sso/traefik`을 사용합니다. 이 이름들은 env로 변경하는 항목이 아닙니다.
`HEADLAMP_OIDC_CLIENT_ID`를 바꾸면 Keycloak client와 API server audience도 함께 맞춥니다.

| 파일 | 역할 |
| --- | --- |
| `helm/chart.lock.json` | 고정 chart 버전·미러 URL·SHA-256 |
| `helm/values.yaml` | 보안 설정·서비스·관리자 RBAC의 기본 원본 |
| `scripts/manage.py` | env 검증·chart 렌더·Secret 검사·Helm 적용·기존 Traefik 연결 |
| `env/k8s.env` | 배포할 공개 주소·registry·Secret/CA 이름 |

`helm/values.yaml`만 직접 설치하면 env의 OIDC·Ingress 설정이 빠집니다. 루트 Make 명령으로 적용합니다.
`HEADLAMP_SSO_HOST`·`HEADLAMP_CALLBACK_URL`은 setup-env가 계산하는 값이며 입력 파일에 추가하지 않습니다.
`01`은 로컬 인증서 경로도 현재 host 기준으로 준비합니다. 다른 위치에 보관한다면 그 단계 후
`HEADLAMP_CERT_DIR`·`HEADLAMP_CA_DIR`·`HEADLAMP_OIDC_CA_FILE`을 실제 경로로 지정합니다.
