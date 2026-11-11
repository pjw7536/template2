# Headlamp 로그인과 API server 인증

[앱 안내](../README.md) · 이전: [TLS·CA 준비](01-prepare.md#tlsca-준비) · 다음: [배포와 로그인 검증](03-deploy.md)

- [Keycloak client와 관리자](#keycloak-client와-관리자)
- [API server 인증](#api-server-인증)

## Keycloak client와 관리자

**목적:** `etch` realm에 Headlamp 전용 client를 등록하고, 사용할 사람을 관리자 그룹에 넣은 뒤 client secret을 Kubernetes에 전달합니다.
**준비물:** [TLS·CA 준비](01-prepare.md#tlsca-준비) 완료, Keycloak 관리자 화면 접근.
**실행 위치:** 1·5단계는 CP1 터미널(새 터미널이면 [실행 입력](01-prepare.md#2-대상-context와-실행-입력)을 다시 실행), 2~4단계는 PC의 Keycloak 관리자 화면입니다.
관리자 화면에서는 왼쪽 위 realm을 **etch**로 맞추며 `master` realm에서 client를 만들지 않습니다. Keycloak 26.x 기준이며 화면 언어에 따라 메뉴 이름이 다를 수 있습니다.

### 1. client 등록 파일 생성과 가져오기

`manage.py oidc-client`가 현재 env로 비밀값 없는 client 정의를 만듭니다. Authorization Code + PKCE S256, RS256 ID Token, profile·email scope,
`fullScopeAllowed: false`, `groups` mapper(`headlamp-groups`)가 포함됩니다.

```bash
make headlamp-oidc-client > /tmp/headlamp-client.json
printf 'Client ID: %s\nValid redirect URIs: %s\nKubernetes Secret 이름: %s\n' \
  "$HEADLAMP_OIDC_CLIENT_ID" "$HEADLAMP_CALLBACK_URL" "$HEADLAMP_OIDC_SECRET"
```

파일을 관리자 PC로 옮겨 **etch → Clients → Import client**에서 가져옵니다. 이미 client가 있으면 다시 가져오지 말고 2단계로 값을 대조합니다.
파일을 옮기거나 가져올 수 없으면 **Clients → Create client**에서 아래 값을 직접 입력합니다.

| 화면 위치 | 항목 | 값 |
| --- | --- | --- |
| General settings | Client type / Client ID / Name | `OpenID Connect` / `HEADLAMP_OIDC_CLIENT_ID`(기본 `headlamp`) / `Headlamp` |
| Capability config | Client authentication / Authorization | **On** / Off |
| Capability config | Standard flow | **체크**. Direct access grants·Implicit flow·Service accounts roles·그 외 flow는 해제 |
| Login settings | Valid redirect URIs | 출력된 `HEADLAMP_CALLBACK_URL`(기본 `https://headlamp.etch.samsungds.net/oidc-callback`). 끝에 `/`·`*` 없음 |
| Login settings | Root/Home URL, post logout redirect URIs, Web origins | 비워 둠 |
| Advanced | Proof Key for Code Exchange Code Challenge Method / ID Token Signature Algorithm | `S256` / `RS256` |
| Client scopes | `profile`, `email` | Assigned type **Default** |
| Client scopes → `headlamp-dedicated` → Scope | Full scope allowed | **Off** |
| `headlamp-dedicated` → Mappers → By configuration → Group Membership | Name / Token Claim Name | `headlamp-groups` / `groups` |
| 같은 mapper | Full group path / ID token / access token / userinfo | **On** / **On** / Off / **On** |

왼쪽 메뉴의 공용 **Client scopes**에서 다른 앱이 함께 쓰는 설정은 수정하지 않습니다.

### 2. 등록 결과 확인

client의 **Settings**·**Advanced**·**Client scopes**를 다시 열어 위 표와 같은지 확인합니다.
특히 Client authentication On, redirect URI가 CP1 출력과 정확히 같음, PKCE S256, `headlamp-groups` mapper의 `groups`·Full group path On·Add to ID token On을 확인합니다.
mapper 세 값이 맞아야 API server가 관리자 그룹을 알아봅니다.

### 3. 사용할 사람을 그룹에 넣기

1. **Groups → Create group**에서 `headlamp-admins`를 **최상위**에 만듭니다. 이미 있으면 그대로 사용합니다.
2. **Users**에서 사용할 사람을 선택하고 **Groups → Join Group**에서 `headlamp-admins`에 가입시킵니다. 기본 가입 그룹으로 지정하지 않습니다.
3. 해당 사용자의 Groups 목록에 `/headlamp-admins`가 보이는지 확인합니다. 그룹 이름 입력에는 `/`를 넣지 않으며 토큰에는 전체 경로가 들어갑니다.

사용자는 Keycloak username(EPID `userid`), 사내 로그인 ID(`loginid`), 표시 이름(`display_name`)으로 확인합니다.
CSV로 미리 등록한 사용자는 Account Console에서 첫 사내 로그인을 마치고 Identity provider links에 `oidc`가 연결된 뒤 가입시킵니다.
Headlamp용 계정을 따로 만들거나 EPID를 바꾸지 않으며, SDWT의 `/{SDWT}/admin` 그룹은 이 그룹을 대신하지 않습니다.
이 그룹은 **모든 namespace를 관리하고 Secret도 읽을 수 있는 클러스터 관리자**용입니다. 접근 거부 검증을 위해 그룹 밖 시험 계정도 준비합니다.

### 4. Client secret 확인

**Clients → headlamp → Credentials**에서 **Client secret**을 확인합니다. 사용 중인 client라면 **Regenerate**를 누르지 않습니다.
Credentials 탭이 없으면 Client authentication이 On인지 확인합니다. client를 새로 만들었다면 새 client의 값을 사용합니다.
`headlamp`, `headlamp-oidc` 같은 이름은 비밀값이 아닙니다.

### 5. CP1에서 Client secret 등록

`Headlamp client secret:`이 나오면 4단계의 값을 붙여 넣습니다. 입력 글자는 보이지 않습니다.

```bash
(
  set -euo pipefail
  umask 077
  secret_file=$(mktemp) || exit 1
  trap 'rm -f "$secret_file"' EXIT
  read -r -s -p 'Headlamp client secret: ' headlamp_client_secret
  printf '\n'
  test -n "$headlamp_client_secret" || exit 1
  printf '%s' "$headlamp_client_secret" > "$secret_file"
  unset headlamp_client_secret
  kubectl --context "$KUBE_CONTEXT" -n headlamp create secret generic "$HEADLAMP_OIDC_SECRET" \
    --from-file=OIDC_CLIENT_SECRET="$secret_file" --dry-run=client -o yaml |
    kubectl --context "$KUBE_CONTEXT" apply -f -
)
kubectl --context "$KUBE_CONTEXT" -n headlamp get secret "$HEADLAMP_OIDC_SECRET"
```

**기대 결과:** 등록 블록이 오류 없이 끝나고 조회 결과 TYPE `Opaque`, DATA `1`. 이 조회로 비밀값의 정확성은 알 수 없으며 잘못 넣었다면 블록을 다시 실행합니다.
**실패 확인:** `NotFound`이면 등록·조회의 context·namespace를 확인합니다. 기존 Secret에 다른 키가 있으면 배포 검사에서 거부하므로, 다른 앱의 Secret을 재사용하지 말고 전용 이름을 env에 지정한 뒤 실행 입력을 다시 읽고 등록합니다.

**완료 기준:** 전용 client·S256·groups mapper·관리자 가입·OIDC Secret 등록이 완료됐습니다.
**다음 단계:** [API server 인증](#api-server-인증)(필수).

공식 참고: [Keycloak 26.7 관리자 안내](https://www.keycloak.org/docs/26.7.0/server_admin/).

## API server 인증

**목적:** Headlamp 로그인 토큰을 Kubernetes API server가 받아들이게 합니다. 등록되지 않으면 로그인 후에도 자원 조회가 실패합니다.
**실행 위치:** 계약 출력은 CP1, 적용은 각 제어면 서버(제어면 담당자). 적용 절차는 [API server OIDC 설정](../../shared/docs/kubernetes/oidc.md)을 따르며
아래 계약과 [TLS 준비](01-prepare.md#tlsca-준비)의 CA 묶음을 전달합니다.

### 1. 적용할 계약

```bash
printf 'issuer: %s\naudience / client ID: %s\nCP1의 CA 원본 파일: %s\n' \
  "$HEADLAMP_OIDC_ISSUER_URL" "$HEADLAMP_OIDC_CLIENT_ID" "$HEADLAMP_OIDC_CA_FILE"
```

| 항목 | 적용값 |
| --- | --- |
| issuer | `HEADLAMP_OIDC_ISSUER_URL`(운영 `https://sso.etch.samsungds.net/realms/etch`) |
| audience / client ID | `HEADLAMP_OIDC_CLIENT_ID`(기본 `headlamp`) |
| username claim / prefix | `sub` / `headlamp:` |
| groups claim / prefix | `groups` / `headlamp:` |
| 서명 알고리즘 | `RS256` |
| CA | `HEADLAMP_OIDC_CA_FILE`의 PEM. 공인 CA 분기에서는 생략 |

Keycloak의 `sub`는 사용자 ID이며 username(EPID)·`loginid`·이름과 다릅니다.
ID Token의 그룹 `/headlamp-admins`는 API server에서 `headlamp:/headlamp-admins`가 되며 Helm의 `server-headlamp-admin` ClusterRoleBinding과 일치해야 합니다.
SSO 주소를 바꾸면 Headlamp env와 모든 API server의 issuer·CA를 함께 맞춥니다. 다른 앱의 `--oidc-*`·인증 설정은 덮어쓰지 않습니다.

`--oidc-*` 플래그 방식의 값은 다음과 같습니다. 앞의 두 줄은 위 출력값으로 바꾸고, YAML에서는 `:`로 끝나는 prefix 옵션을 작은따옴표로 감쌉니다.

```text
--oidc-issuer-url=<HEADLAMP_OIDC_ISSUER_URL>
--oidc-client-id=<HEADLAMP_OIDC_CLIENT_ID>
--oidc-username-claim=sub
--oidc-username-prefix=headlamp:
--oidc-groups-claim=groups
--oidc-groups-prefix=headlamp:
--oidc-signing-algs=RS256
--oidc-ca-file=/etc/kubernetes/oidc/keycloak-ca-bundle.pem
```

`--authentication-config` 방식은 기존 jwt 항목에 issuer·audience·CA 내용과 다음 매핑을 합칩니다.

```yaml
claimMappings:
  username:
    claim: sub
    prefix: 'headlamp:'
  groups:
    claim: groups
    prefix: 'headlamp:'
```

### 2. 완료 확인

모든 제어면에 적용한 뒤 CP1의 관리자 kubeconfig로 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" get --raw=/readyz
kubectl --context "$KUBE_CONTEXT" get nodes
```

| 확인 | 기대 결과 |
| --- | --- |
| 적용 범위 | 모든 제어면에 같은 계약 적용. LB 뒤 한 서버만 정상일 수 있으므로 담당자가 서버별로 확인 |
| issuer·client ID | 1단계 출력과 일치 |
| 그룹 claim·prefix | `groups`와 `headlamp:` |
| CA | 모든 API server에서 discovery·JWKS의 HTTPS 검증 가능 |
| 기존 관리자 접속 | `/readyz`는 `ok`, 노드 목록 조회 성공 |

위 명령 성공만으로 OIDC 인증 성공이 검증되지는 않습니다.
**다음 단계:** [배포와 로그인 검증](03-deploy.md)에서 실제 브라우저 로그인과 그룹별 권한을 확인합니다.
