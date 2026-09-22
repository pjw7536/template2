# Headlamp를 Keycloak 로그인으로 바꾸기

[Headlamp 운영 안내](README.md) · [HTTPS 인증서 준비](HTTPS_CERTIFICATE_GUIDE.md)

이 작업을 마치면 Headlamp에서 **Sign in → Keycloak 로그인**으로 접속합니다.
`headlamp-viewers` 그룹에 넣은 사람만 노드·Pod·로그를 볼 수 있습니다. 수정 권한은 주지 않습니다.

**이미 Headlamp와 Keycloak이 실행 중인 서버에서 진행하는 안내입니다.**
Headlamp가 HTTPS로 열리지 않으면 먼저 위의 HTTPS 인증서 준비를 완료하세요.

## 전체 순서

| 순서 | 할 일 | 작업 위치 |
| --- | --- | --- |
| 1 | 접속 주소와 설정 입력 | CP1 터미널 |
| 2 | Headlamp 등록, 사용할 사람 지정 | Keycloak 관리자 화면 |
| 3 | 로그인 비밀값과 인증기관 인증서 등록 | CP1 터미널 |
| 4 | Kubernetes가 Keycloak 로그인을 받아들이도록 설정 | Kubernetes 인프라 담당자 |
| 5 | Headlamp에 적용하고 로그인 확인 | CP1 터미널 → 브라우저 |

**4번도 반드시 필요합니다.** Keycloak에 Headlamp를 등록하는 것만으로는 Kubernetes 데이터를 볼 수 없습니다.
먼저 인프라 담당자에게 4번 내용을 전달하고, 준비하는 동안 1~3번을 진행해도 됩니다.

## 1. CP1에서 설정 파일 준비

CP1에서 저장소 폴더로 이동합니다. `ls Makefile`을 실행했을 때 파일이 보여야 합니다.
아래 명령은 같은 Bash 터미널에서 순서대로 실행합니다.

먼저 작업할 클러스터를 선택합니다.

```bash
kubectl config get-contexts
read -r -p '위 목록에서 대상 context 이름을 입력하세요: ' KUBE_CONTEXT
export KUBE_CONTEXT
set -o pipefail
```

`context`는 **어느 Kubernetes 클러스터에 명령을 보낼지 정하는 이름**입니다.
운영 대상 이름을 입력합니다.

설정 파일이 없을 때만 예시를 복사하고 편집합니다.

```bash
test -f deploy/headlamp/env/k8s.env || cp deploy/headlamp/env/k8s.env.example deploy/headlamp/env/k8s.env
vi deploy/headlamp/env/k8s.env
```

기존 이미지 설정은 그대로 두고 아래 항목을 확인합니다. 같은 항목이 있으면 값을 고칩니다.

```dotenv
HEADLAMP_HOST=내-Headlamp-도메인
HEADLAMP_TLS_SECRET=headlamp-tls
HEADLAMP_OIDC_ISSUER_URL=https://내-Keycloak-도메인/realms/etch
HEADLAMP_OIDC_CLIENT_ID=headlamp
HEADLAMP_OIDC_SECRET=headlamp-oidc
HEADLAMP_OIDC_CA_CONFIGMAP=headlamp-oidc-ca
```

- `HEADLAMP_HOST`: 현재 Headlamp 주소에서 도메인만 입력합니다. `https://`나 `/headlamp/`는 넣지 않습니다.
- `HEADLAMP_TLS_SECRET`: 기존 Headlamp HTTPS 인증서를 등록한 Secret 이름입니다. 현재 이름이 다르면 그 이름을 유지합니다.
- `HEADLAMP_OIDC_ISSUER_URL`: Keycloak 주소 뒤에 `/realms/etch`를 붙입니다. 끝에 `/`는 붙이지 않습니다. `etch`는 기존 사용자들이 있는 로그인 영역(realm)의 이름입니다.
- 나머지 세 항목은 위 이름을 그대로 사용하면 됩니다. **비밀번호를 이 파일에 넣지는 않습니다.**

이 안내는 사내 인증기관의 인증서를 사용하는 경우를 기준으로 합니다.
Keycloak이 공개 인증기관의 인증서를 사용하고 Headlamp가 이미 신뢰한다면 마지막 항목만
`HEADLAMP_OIDC_CA_CONFIGMAP=`으로 비우고 3번의 인증기관 등록을 건너뜁니다.

**완료 기준:** 두 도메인이 실제 주소이고 기존 HTTPS·이미지 설정도 남아 있습니다.

## 2. Keycloak에 Headlamp와 사용자 등록

### CP1에서 등록 파일 만들기

```bash
make headlamp-oidc-client > /tmp/headlamp-client.json
```

생성된 `/tmp/headlamp-client.json`을 관리자 브라우저를 사용하는 PC로 가져옵니다.
이 파일에는 비밀번호가 없습니다. 평소 사용하는 서버 파일 전송 도구로 복사하면 됩니다.

### Keycloak 관리자 화면에서 등록하기

1. Keycloak 관리자 화면에 접속하고 **etch** realm을 선택합니다.
2. **Clients → Import client**에서 `headlamp-client.json`을 선택하고 저장합니다.
3. **Groups**에서 `headlamp-viewers`라는 그룹을 만듭니다. 다른 그룹 아래에 넣지 말고 최상위에 만듭니다.
4. **Users**에서 Headlamp를 사용할 사람을 선택하고, 그 사용자의 **Groups**에서 `headlamp-viewers`에 가입시킵니다. 허용할 사람마다 반복합니다.
5. **Clients → headlamp → Credentials**에서 **Client secret**을 확인합니다. 다음 단계에서 입력할 Headlamp 전용 로그인 비밀값입니다.

이미 `headlamp` client가 있다면 다시 만들거나 비밀값을 재발급하지 말고, 아래의 담당자용 설정표와 비교해 기존 항목을 수정합니다.
그룹을 모든 사용자의 기본 가입 그룹으로 지정하지 않습니다.

**완료 기준:** `headlamp` client가 있고, 허용할 사용자가 `headlamp-viewers` 그룹에 들어 있습니다.

## 3. CP1에서 로그인 비밀값과 인증기관 등록

### Client secret 등록

아래 블록을 CP1 터미널에 붙여 넣습니다. `Headlamp client secret:`이 나오면
2번에서 확인한 값을 붙여 넣고 Enter를 누릅니다. 입력하는 글자가 화면에 보이지 않는 것이 정상입니다.

```bash
kubectl --context "$KUBE_CONTEXT" create namespace headlamp --dry-run=client -o yaml |
  kubectl --context "$KUBE_CONTEXT" apply -f -

(
  umask 077
  secret_file=$(mktemp)
  trap 'rm -f "$secret_file"' EXIT
  read -r -s -p 'Headlamp client secret: ' headlamp_client_secret
  printf '\n'
  test -n "$headlamp_client_secret" || exit 1
  printf '%s' "$headlamp_client_secret" > "$secret_file"
  unset headlamp_client_secret
  kubectl --context "$KUBE_CONTEXT" -n headlamp create secret generic headlamp-oidc \
    --from-file=OIDC_CLIENT_SECRET="$secret_file" --dry-run=client -o yaml |
    kubectl --context "$KUBE_CONTEXT" apply -f -
)
```

비밀값은 Kubernetes의 `headlamp-oidc` Secret에 저장됩니다.
`OIDC_CLIENT_SECRET`이라는 항목 하나만 등록하며 임시 파일은 자동으로 지웁니다.

### Keycloak 인증기관 등록 — 사내 인증서 사용 시

인증서 담당자에게 **“Keycloak HTTPS 인증서를 발급한 루트·중간 CA의 PEM 묶음 파일”**을 받습니다.
이것은 Headlamp 서버 인증서나 개인키가 아닙니다.
파일을 CP1에 놓고, 아래 명령의 `/실제/경로/keycloak-ca-bundle.pem`만 해당 파일 경로로 바꿉니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp create configmap headlamp-oidc-ca \
  --from-file=ca.crt=/실제/경로/keycloak-ca-bundle.pem --dry-run=client -o yaml |
  kubectl --context "$KUBE_CONTEXT" apply -f -
```

**완료 기준:** 각 명령이 오류 없이 `created`, `configured` 또는 `unchanged`로 끝납니다.

## 4. 인프라 담당자에게 Kubernetes 로그인 설정 요청

아래 내용을 담당자에게 전달합니다. 주소는 1번에 입력한 실제 값으로 채웁니다.

> Headlamp를 Keycloak 로그인으로 전환하려고 합니다.
> Kubernetes API server가 아래 Keycloak에서 발급한 로그인 정보를 받아들이도록 OIDC 인증을 설정해 주세요.
>
> - Keycloak issuer URL: `1번의 HEADLAMP_OIDC_ISSUER_URL 값`
> - Client ID: `headlamp`
> - 허용 그룹: Keycloak의 최상위 `/headlamp-viewers`
> - Kubernetes 사용자 이름: `sub` 값, 앞에 `headlamp:` 추가
> - Kubernetes 그룹 이름: `groups` 값, 앞에 `headlamp:` 추가
> - 서명 알고리즘: `RS256` — Keycloak realm 설정도 확인
> - 사내 CA를 사용하므로 모든 API server에 CA 신뢰 설정 필요
> - 모든 API server와 Headlamp Pod에서 Keycloak 주소에 HTTPS 접근 가능해야 함
>
> 기존 인증 설정을 보존하고, 아래 담당자용 상세 설정을 참고해 주세요.

직접 인프라도 관리한다면 아래 상세 설정을 확인합니다.
클러스터 설치 방식에 따라 수정 위치가 달라지므로 설정 파일 경로를 임의로 정해 편집하지 않습니다.

**완료 기준:** 담당자가 **“모든 API server에 반영했고 기존 관리자 접속도 정상”**이라고 확인했습니다.
확인 후 5번으로 넘어갑니다.

## 5. CP1에서 적용하고 브라우저로 확인

먼저 설정을 검사합니다. 오류가 나면 해결한 뒤 다음 명령으로 넘어갑니다.

```bash
make server-check APP=headlamp PROFILE=prod
make headlamp-check
```

이 검사는 설정 파일과 배포 문법을 확인합니다. 실제 로그인 성공까지 확인하는 명령은 아닙니다.
chart나 Helm이 없다는 오류라면 [운영 안내의 준비와 검사](README.md#준비와-검사)를 따릅니다.

검사를 통과하면 적용합니다.

```bash
make headlamp-up KUBE_CONTEXT="$KUBE_CONTEXT"
make headlamp-ui KUBE_CONTEXT="$KUBE_CONTEXT"
```

출력된 HTTPS 주소를 브라우저에서 엽니다.

1. **Sign in**을 누르고 Keycloak으로 로그인합니다.
2. 그룹에 가입한 계정으로 노드·Pod·로그가 보이는지 확인합니다.
3. 별도 브라우저나 시크릿 창에서 그룹에 넣지 않은 계정으로 로그인합니다. 이 계정은 리소스를 볼 수 없어야 합니다.
4. 새로고침·재접속 후 수동 토큰 입력을 요구하지 않는지 확인합니다.

**완료 기준:** 허용한 사용자만 리소스를 조회할 수 있고, 수정·Secret 조회·Pod exec 권한은 없습니다.
기존 공용 토큰용 `headlamp-viewer` 계정은 이번 배포에서 제거됩니다.

## 잘 안 될 때

| 보이는 문제 | 먼저 확인할 내용 |
| --- | --- |
| `invalid redirect URI` | Keycloak의 headlamp client에 `https://실제-Headlamp-도메인/headlamp/oidc-callback`이 등록됐는지 확인 |
| `x509` 또는 인증서 오류 | 3번 CA 파일과 4번 API server의 CA 신뢰 설정 확인 |
| 로그인 후 `401` | 4번 설정이 모든 API server에 반영됐는지 담당자에게 확인 |
| 허용한 사람도 `403` | 그룹 이름·사용자 가입 여부와 아래의 그룹 매핑 확인 |
| 그룹 밖 사람도 데이터가 보임 | 담당자에게 다른 Kubernetes 권한이 추가로 부여됐는지 확인 요청 |

<details>
<summary>담당자용 상세 설정·권한 검사·복구</summary>

### Keycloak client 설정

2번의 생성 파일에 아래 설정이 포함됩니다. 기존 client를 수정할 때 비교합니다.

| 항목 | 값 |
| --- | --- |
| Client authentication / Standard flow | On |
| Implicit / Direct access grants / Service accounts | Off |
| PKCE | S256 |
| Valid redirect URIs | `https://<HEADLAMP_HOST>/headlamp/oidc-callback` 하나 |
| Default scopes | profile, email |
| 전용 mapper | Group Membership → `groups`, Full group path On, ID token On |

기존 realm 전체를 다시 import하지 않습니다. 전용 client 설정만 변경합니다.
issuer URL은 Keycloak discovery 문서의 `issuer`와 정확히 일치해야 합니다.

### API server 설정

기존 `--oidc-*` 플래그 방식이라면 다음 값을 반영합니다.

```text
--oidc-issuer-url=<HEADLAMP_OIDC_ISSUER_URL>
--oidc-client-id=headlamp
--oidc-username-claim=sub
--oidc-username-prefix=headlamp:
--oidc-groups-claim=groups
--oidc-groups-prefix=headlamp:
--oidc-signing-algs=RS256
--oidc-ca-file=<API server 컨테이너 안의 Keycloak CA PEM 경로>
```

공개 CA를 신뢰하는 환경은 `--oidc-ca-file`을 생략할 수 있습니다.
사내 CA는 각 API server 컨테이너에 마운트합니다. 3번의 ConfigMap은 Headlamp에만 적용됩니다.
Headlamp는 `SSL_CERT_FILE`로 CA를 읽으며 TLS 검증을 끄지 않습니다.
모든 API server와 Headlamp Pod에서 issuer의 discovery·JWKS 주소에 접근할 수 있어야 합니다.

이미 `--authentication-config`를 사용한다면 위 플래그를 추가하지 않습니다.
현재 Kubernetes 버전의 AuthenticationConfiguration에 issuer·audience(client ID)·CA와
동일한 username·groups 매핑을 반영합니다. 기존 issuer를 덮어쓰지 말고 필요한 경우
지원 버전의 다중 issuer 설정으로 통합합니다. 같은 issuer의 매핑 변경은 기존 사용자에게 영향을 줄 수 있습니다.

설치 도구의 원본 설정도 갱신합니다. 관리자 kubeconfig를 유지한 채 제어면을 한 대씩 반영하고,
각 단계에서 기존 관리자 접속과 다음 명령의 `ok`를 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" get --raw=/readyz
```

### 권한 검사

ID token에 `groups: ["/headlamp-viewers"]`가 있어야 합니다.
API server가 prefix를 붙여 `headlamp:/headlamp-viewers`로 인식하고, 이 그룹에
`view`와 nodes/namespaces 조회 권한이 연결됩니다.

아래는 관리자 kubeconfig로 실행하는 RBAC 검사입니다. 실제 브라우저 로그인 검사도 별도로 수행합니다.

```bash
kubectl --context "$KUBE_CONTEXT" auth can-i list nodes \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-viewers
# 기대: yes
kubectl --context "$KUBE_CONTEXT" auth can-i create deployments --all-namespaces \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-viewers
# 기대: no
kubectl --context "$KUBE_CONTEXT" auth can-i get secrets --all-namespaces \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-viewers
# 기대: no
kubectl --context "$KUBE_CONTEXT" auth can-i list nodes \
  --as=headlamp:rbac-outsider --as-group=system:authenticated
# 기대: no
```

Kubernetes 권한은 합산됩니다. 다른 RBAC 바인딩이나 `view` 집계 확장도 확인합니다.
기존 Helm release 밖에서 만든 `headlamp-viewer` 관련 리소스가 있다면 소유권과 권한을 별도로 점검합니다.
그룹 탈퇴는 기존 ID token이 만료될 때까지 즉시 반영되지 않을 수 있습니다.
토큰 갱신 후 로그인 유지·권한 반영도 확인합니다.

### 갱신·복구

client secret을 갱신한 뒤에는 Headlamp Deployment를 재시작해야 새 값이 적용됩니다.
복구는 관리자 kubeconfig로 이전 env·Helm revision·제어면 설정을 복원합니다.
`helm rollback`만으로 Keycloak·제어면·외부 Secret은 복구되지 않습니다.
이전 revision이 공용 토큰 계정을 다시 만들 수 있으므로 복구 후 권한을 확인합니다.

공식 참고: [Headlamp OIDC](https://headlamp.dev/docs/latest/installation/in-cluster/oidc/),
[Keycloak 연동 예제](https://headlamp.dev/docs/latest/installation/in-cluster/keycloak/),
[Kubernetes OIDC 인증](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#openid-connect-tokens).

</details>
