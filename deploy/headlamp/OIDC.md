# Headlamp를 Keycloak 로그인으로 바꾸기

[Headlamp 운영 안내](README.md) · [공용 인증서 폴더](../shared/certs/README.md)

이 작업을 마치면 Headlamp에서 **Sign in → Keycloak 로그인**으로 접속합니다.
`headlamp-viewers` 그룹에 넣은 사람만 노드·Pod·로그를 볼 수 있습니다. 수정 권한은 주지 않습니다.

**CP1의 `deploy/shared/certs/`의 사이트별 하위 폴더에 아래 10개 파일을 이미 넣었다는 전제입니다.**
Keycloak은 기존 HTTPS 주소로 접속되는 상태에서 진행합니다.
Headlamp 최초 설치에도 이 가이드를 사용할 수 있습니다. 먼저 [공용 인증서 안내](../shared/certs/README.md)에 따라
`headlamp` namespace와 TLS Secret을 준비하고 1~4번을 마친 뒤 5번에서 처음 배포합니다.
이미 운영 중인 Headlamp의 로그인 전환도 같은 순서로 진행합니다.
이번 작업에서는 인증서를 다시 발급하거나 PFX/P7B에서 추출하지 않습니다.

| 보관 폴더 (`deploy/shared/certs/` 아래) | 준비된 파일 | 이번 작업에서의 사용 |
| --- | --- | --- |
| `ca/` | `SECDS-T2RootCA.crt`, `SECDS-T2IssuingCA.crt` | Keycloak을 신뢰하기 위한 CA 묶음 생성 |
| `etch-sso.samsungds.net/` | `fullchain.crt`, `private.key` | 기존 Keycloak HTTPS용. fullchain으로 CA 체인 확인 |
| `etch.samsungds.net/` | `fullchain.crt`, `private.key` | 기존 Headlamp HTTPS용. 정상 운영 중이면 그대로 유지 |
| `etch-sso.samsungds.net/` | `etch-sso.samsungds.net.p7b`, `etch-sso.samsungds.net.pfx` | 원본 보관, 이번 절차에서는 사용하지 않음 |
| `etch.samsungds.net/` | `etch.samsungds.net.p7b`, `etch.samsungds.net.pfx` | 원본 보관, 이번 절차에서는 사용하지 않음 |

이 절차에서 새로 만드는 파일은 **`deploy/shared/certs/etch-sso.samsungds.net/keycloak-ca-bundle.pem`**입니다.
공용 폴더의 기존 파일과 마찬가지로 Git에서 제외됩니다.

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
아래 명령은 같은 Bash 터미널에서 순서대로 실행합니다. 먼저 파일 위치를 확인합니다.

```bash
ls deploy/shared/certs/etch-sso.samsungds.net
ls deploy/shared/certs/etch.samsungds.net
ls deploy/shared/certs/ca
```

위 표의 파일이 보이면 진행합니다. 파일 내용이나 개인키를 화면에 출력할 필요는 없습니다.

먼저 작업할 클러스터를 선택합니다.

```bash
kubectl config get-contexts
read -r -p '위 목록에서 대상 context 이름을 입력하세요: ' KUBE_CONTEXT
export KUBE_CONTEXT
set -o pipefail
```

`context`는 **어느 Kubernetes 클러스터에 명령을 보낼지 정하는 이름**입니다.
운영 대상 이름을 입력합니다.

실행 설정은 `deploy/headlamp/env/k8s.env`에 저장합니다.
`make headlamp-*`는 이 실제 파일을 사용합니다. 일반 설정 파일은 Git으로 전달되며 Client Secret은 Kubernetes Secret에 별도로 등록합니다.

```dotenv
HEADLAMP_HOST=etch.samsungds.net
HEADLAMP_TLS_SECRET=headlamp-tls
HEADLAMP_OIDC_ISSUER_URL=https://etch-sso.samsungds.net/realms/etch
HEADLAMP_OIDC_CLIENT_ID=headlamp
HEADLAMP_OIDC_SECRET=headlamp-oidc
HEADLAMP_OIDC_CA_CONFIGMAP=headlamp-oidc-ca
```

기존 `deploy/headlamp/env/k8s.env`가 있으면 그 파일이 우선합니다. 과거 예시 주소가 남았다면
위 운영값과 비교합니다. 이미지·인증 설정이 별도로 있는 실제 파일은 예시로 덮어쓰지 않습니다.

`HEADLAMP_OIDC_SECRET`과 `HEADLAMP_OIDC_CA_CONFIGMAP`은 비밀번호·파일 경로가 아니라
3번에서 만들 Kubernetes 저장소 이름입니다. 이번에는 보유한 사내 CA를 사용합니다.
Keycloak의 **etch → Realm settings → OpenID Endpoint Configuration**에서 `issuer`가 위 값인지 확인합니다.

**완료 기준:** 기본 운영값 또는 기존 실제 env가 현재 주소와 일치합니다. 다음은 Keycloak 등록입니다.

## 2. Keycloak에 Headlamp와 사용자 등록

파일 임포트가 제한되어 있으면 **아래 순서대로 관리자 화면에서 직접 입력**합니다.
`headlamp-client.json`을 만들거나 PC로 가져올 필요가 없습니다.
Keycloak 26.x 기준이며 화면 언어에 따라 메뉴 이름이 조금 다를 수 있습니다.

### 2-1. Headlamp client 만들기

Keycloak 관리자 화면에서 **etch** realm을 선택한 뒤 **Clients → Create client**를 누릅니다.
이미 `headlamp`가 있으면 새로 만들지 말고 해당 client를 열어 아래 값을 확인합니다.

**General settings**에서 입력하고 **Next**를 누릅니다.

| 화면 항목 | 입력값 |
| --- | --- |
| Client type | `OpenID Connect` |
| Client ID | `headlamp` — env의 `HEADLAMP_OIDC_CLIENT_ID`와 같아야 함 |
| Name | `Headlamp` |

**Capability config**는 다음처럼 설정하고 **Next**를 누릅니다.

| 화면 항목 | 설정 |
| --- | --- |
| Client authentication | **On** |
| Authorization | **Off** |
| Standard flow | **체크** |
| Direct access grants | **체크 해제** |
| Implicit flow / Service accounts roles | **체크 해제** |
| 그 외 인증 flow | **체크 해제** |

**Login settings**에서 아래처럼 입력하고 **Save**를 누릅니다.

| 화면 항목 | 입력값 |
| --- | --- |
| Root URL / Home URL | 비워 둠 |
| Valid redirect URIs | `https://etch.samsungds.net/headlamp/oidc-callback` |
| Valid post logout redirect URIs / Web origins | 비워 둠 |

1번에서 `HEADLAMP_HOST`를 다른 주소로 정했다면 위 주소의 도메인도 동일하게 바꿉니다.
주소 끝에 `/`나 `*`를 추가하지 않습니다.

저장 후 **Clients → headlamp → Advanced**에서 **Proof Key for Code Exchange Code Challenge Method**
항목을 찾아 **S256**으로 설정하고 저장합니다. 보통 **Advanced settings** 영역에 있습니다.
생성 화면에 같은 PKCE 항목이 보이면 그곳에서 설정해도 됩니다.

### 2-2. 로그인 정보에 그룹 이름 넣기 — 반드시 필요

이 설정이 있어야 Kubernetes가 사용자의 `headlamp-viewers` 가입 여부를 알 수 있습니다.

1. **Clients → headlamp → Client scopes**를 엽니다.
2. `profile`, `email`의 **Assigned type**이 **Default**인지 확인합니다. 없으면 **Add client scope**로 추가합니다.
3. 같은 목록의 **headlamp-dedicated**를 엽니다. 이것은 Headlamp에만 적용할 설정 영역입니다.
4. **Scope** 탭에서 **Full scope allowed**를 **Off**로 설정합니다. 저장 버튼이 있으면 저장합니다.
5. **Mappers** 탭에서 **Configure a new mapper**를 누릅니다. 기존 mapper가 보이는 화면에서는 **Add mapper → By configuration**을 선택합니다.
6. **Group Membership**을 선택하고 다음 값을 입력한 뒤 **Save**를 누릅니다.

| 화면 항목 | 입력값 |
| --- | --- |
| Name | `headlamp-groups` |
| Token Claim Name | `groups` |
| Full group path | **On** |
| Add to ID token | **On** |
| Add to access token | **Off** |
| Add to userinfo | **On** |

이미 `headlamp-groups` mapper가 있으면 새로 추가하지 말고 값을 확인·수정합니다.
왼쪽 메뉴의 공용 **Client scopes**에서 다른 앱이 함께 쓰는 설정을 수정하지 않습니다.

### 2-3. 사용할 사람을 그룹에 넣기

1. 왼쪽 **Groups → Create group**에서 `headlamp-viewers`를 만듭니다. 다른 그룹 아래가 아닌 **최상위**에 만듭니다. 이미 있으면 그대로 사용합니다.
2. **Users**에서 Headlamp를 사용할 사람을 선택합니다.
3. 그 사용자의 **Groups → Join Group**에서 `headlamp-viewers`를 선택해 가입시킵니다.
4. 허용할 사람마다 반복합니다. 모든 사용자의 기본 가입 그룹으로 지정하지 않습니다.

그룹 이름을 입력할 때 `/`는 넣지 않습니다. 2-2에서 **Full group path**를 켰으므로
로그인 정보에는 자동으로 `/headlamp-viewers`라는 전체 경로가 들어갑니다.

### 2-4. Client secret 확인

**Clients → headlamp → Credentials**에서 **Client secret**을 확인합니다.
다음 3번의 CP1 명령이 비밀값을 물어볼 때 이 값을 입력합니다.
이미 사용 중인 client라면 **Regenerate**를 누르지 않습니다.
**Credentials** 탭이 없으면 2-1의 **Client authentication**이 On인지 확인합니다.

**완료 기준:** `headlamp` client와 `headlamp-groups` mapper가 있고,
허용할 사용자가 `headlamp-viewers` 그룹에 들어 있으며 Client secret을 확인했습니다.
이제 3번으로 넘어갑니다.

<details>
<summary>파일 임포트가 가능한 환경에서의 대체 방법</summary>

CP1에서 다음 명령으로 등록 파일을 만들 수 있습니다. 비밀번호는 포함되지 않습니다.

```bash
make headlamp-oidc-client > /tmp/headlamp-client.json
```

관리자 PC로 파일을 가져와 **etch → Clients → Import client**에서 등록합니다.
이 방법은 2-1과 2-2를 대신합니다. 그룹 가입과 비밀값 확인은 **2-3, 2-4**를 그대로 진행합니다.
이미 있는 client를 다시 import하거나 비밀값을 재발급하지 않습니다.

</details>

## 3. CP1에서 로그인 비밀값과 인증기관 등록

### Client secret 등록

아래 블록을 CP1 터미널에 붙여 넣습니다. `Headlamp client secret:`이 나오면
2번에서 확인한 값을 붙여 넣고 Enter를 누릅니다. 입력하는 글자가 화면에 보이지 않는 것이 정상입니다.

```bash
kubectl --context "$KUBE_CONTEXT" create namespace headlamp --dry-run=client -o yaml |
  kubectl --context "$KUBE_CONTEXT" apply -f -

(
  umask 077
  secret_file=$(mktemp) || exit 1
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

### 3-1. 폴더의 CA 두 파일로 묶음 만들기

아래 블록을 **CP1의 저장소 루트**에서 통째로 실행합니다.
`.crt`가 PEM 또는 DER 형식인지 확인해 PEM으로 읽고, Keycloak 인증서의 발급 체인이
맞는지 검사한 다음 두 CA만 묶습니다. 기존 원본 파일은 그대로 둡니다.

```bash
(
  set -euo pipefail
  cert_dir="$PWD/deploy/shared/certs/etch-sso.samsungds.net"
  ca_dir="$PWD/deploy/shared/certs/ca"
  ca_work=$(mktemp -d "$cert_dir/.ca-build.XXXXXX")
  trap 'rm -rf "$ca_work"' EXIT

  # 원본 형식과 관계없이 CA 두 파일을 PEM으로 준비합니다.
  for ca_name in SECDS-T2RootCA SECDS-T2IssuingCA; do
    if ! openssl x509 -inform PEM -in "$ca_dir/$ca_name.crt" \
      -out "$ca_work/$ca_name.pem" 2>/dev/null; then
      openssl x509 -inform DER -in "$ca_dir/$ca_name.crt" \
        -out "$ca_work/$ca_name.pem"
    fi
  done

  # 루트·중간 CA로 Keycloak 서버 인증서의 체인·기간·도메인을 확인합니다.
  openssl verify -purpose sslserver -verify_hostname etch-sso.samsungds.net \
    -CAfile "$ca_work/SECDS-T2RootCA.pem" \
    -untrusted "$ca_work/SECDS-T2IssuingCA.pem" \
    "$cert_dir/fullchain.crt"

  cat "$ca_work/SECDS-T2RootCA.pem" "$ca_work/SECDS-T2IssuingCA.pem" \
    > "$ca_work/keycloak-ca-bundle.pem"
  mv "$ca_work/keycloak-ca-bundle.pem" "$cert_dir/keycloak-ca-bundle.pem"
  echo 'CA 묶음 생성 완료: deploy/shared/certs/etch-sso.samsungds.net/keycloak-ca-bundle.pem'
)
```

실제 Keycloak 도메인이 다르다면 `-verify_hostname` 뒤의 주소도 바꿉니다.
`fullchain.crt: OK`와 **CA 묶음 생성 완료**가 나오면 성공입니다.
오류가 나면 다음 등록 명령으로 넘어가지 않습니다. 만료·다른 도메인·발급 CA 불일치를 확인합니다.
이 검사는 폴더에 있는 인증서를 대상으로 하므로 실제 Keycloak 서버도 같은 인증서를 제공하는지 확인해야 합니다.
명령 참고: [OpenSSL 형식 변환](https://docs.openssl.org/3.0/man1/openssl-x509/),
[인증서 검증 옵션](https://docs.openssl.org/3.0/man1/openssl-verification-options/).

### 3-2. 생성한 묶음을 Headlamp에 등록하기

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp create configmap headlamp-oidc-ca \
  --from-file=ca.crt=deploy/shared/certs/etch-sso.samsungds.net/keycloak-ca-bundle.pem \
  --dry-run=client -o yaml |
  kubectl --context "$KUBE_CONTEXT" apply -f -
```

등록 결과를 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp get secret headlamp-oidc
kubectl --context "$KUBE_CONTEXT" -n headlamp get configmap headlamp-oidc-ca
```

**완료 기준:** Secret과 ConfigMap이 모두 조회됩니다.
Headlamp가 사용할 CA 준비는 끝났으며, 다음 단계에서 API server에도 같은 CA를 연결합니다.

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
> - CA 파일: CP1 저장소의 `deploy/shared/certs/etch-sso.samsungds.net/keycloak-ca-bundle.pem`
> - 이 CA 묶음을 모든 API server에 배치하고 신뢰하도록 설정 필요
> - 모든 API server와 Headlamp Pod에서 Keycloak 주소에 HTTPS 접근 가능해야 함
>
> 기존 인증 설정을 보존하고, 아래 담당자용 상세 설정을 참고해 주세요.

담당자에게 전달할 인증서 파일은 **3번에서 만든 `keycloak-ca-bundle.pem` 하나**입니다.
PFX나 각 사이트의 `private.key`를 API server에 전달할 필요는 없습니다.

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
| `invalid redirect URI` | Keycloak의 headlamp client에 `https://etch.samsungds.net/headlamp/oidc-callback`이 등록됐는지 확인 |
| `x509` 또는 인증서 오류 | 3번 CA 파일과 4번 API server의 CA 신뢰 설정 확인 |
| 로그인 후 `401` | 4번 설정이 모든 API server에 반영됐는지 담당자에게 확인 |
| 허용한 사람도 `403` | 그룹 이름·사용자 가입 여부와 아래의 그룹 매핑 확인 |
| 그룹 밖 사람도 데이터가 보임 | 담당자에게 다른 Kubernetes 권한이 추가로 부여됐는지 확인 요청 |

<details>
<summary>담당자용 상세 설정·권한 검사·복구</summary>

### Keycloak client 설정

2번의 수동 등록과 임포트 파일은 아래 설정을 사용합니다. 기존 client를 수정할 때 비교합니다.

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

먼저 3번에서 만든 CA 묶음을 각 제어면 서버로 전달합니다.
각 서버에도 같은 저장소 경로 구조로 파일을 준비했다면, 그 서버의 저장소 루트에서 실행합니다.

```bash
sudo install -d -m 0755 /etc/kubernetes/oidc
sudo install -m 0644 deploy/shared/certs/etch-sso.samsungds.net/keycloak-ca-bundle.pem \
  /etc/kubernetes/oidc/keycloak-ca-bundle.pem
```

파일을 이 경로에 놓는 것만으로 API server가 읽을 수 있는 것은 아닙니다.
실제 설치 방식에 맞게 `/etc/kubernetes/oidc`를 API server 컨테이너의 같은 경로에
읽기 전용으로 마운트합니다. static Pod라면 해당 컨테이너의 `volumeMounts`와
Pod의 `volumes`에 연결해야 합니다.

기존 `--oidc-*` 플래그 방식이라면 다음 값을 반영합니다.

```text
--oidc-issuer-url=<HEADLAMP_OIDC_ISSUER_URL>
--oidc-client-id=headlamp
--oidc-username-claim=sub
--oidc-username-prefix=headlamp:
--oidc-groups-claim=groups
--oidc-groups-prefix=headlamp:
--oidc-signing-algs=RS256
--oidc-ca-file=/etc/kubernetes/oidc/keycloak-ca-bundle.pem
```

이번 절차에서는 위 CA 파일 경로를 사용합니다. **3번의 ConfigMap은 Headlamp에만 적용되므로
API server의 파일 배치·마운트·인증 설정은 별도로 완료해야 합니다.**
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
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-viewers --as-group=system:authenticated
# 기대: yes
kubectl --context "$KUBE_CONTEXT" auth can-i create deployments --all-namespaces \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-viewers --as-group=system:authenticated
# 기대: no
kubectl --context "$KUBE_CONTEXT" auth can-i get secrets --all-namespaces \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-viewers --as-group=system:authenticated
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

공식 참고: [Keycloak 26.7 관리자 안내](https://www.keycloak.org/docs/26.7.0/server_admin/),
[Headlamp OIDC](https://headlamp.dev/docs/latest/installation/in-cluster/oidc/),
[Keycloak 연동 예제](https://headlamp.dev/docs/latest/installation/in-cluster/keycloak/),
[Kubernetes OIDC 인증](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#openid-connect-tokens).

</details>
