# Headlamp 로그인과 API server 인증

[Headlamp 가이드](../README.md)

설치·업데이트 절차는 [Headlamp 가이드](../README.md)에 있습니다. 이 문서는 Keycloak client·관리자 그룹의 등록 내용과 수동 등록 방법, API server에 적용할 인증 계약입니다.

- [Keycloak client와 관리자](#keycloak-client와-관리자)
- [API server 인증](#api-server-인증)

## Keycloak client와 관리자

`etch` realm에 Headlamp 전용 client를 등록하고, 사용할 사람을 관리자 그룹에 넣은 뒤 client secret을 Kubernetes에 전달하는 일입니다.
`make ops-deploy APP=headlamp`의 첫 단계인 `headlamp-oidc-setup`이 이 일을 수행합니다([가이드 A-5](../README.md#a-최초-설치), [B](../README.md#b-업데이트)).

- client와 `headlamp-admins` 그룹이 없으면 만듭니다. 기존 client 설정은 바꾸지 않습니다.
- `HEADLAMP_ADMINS`로 받은 Keycloak username을 `headlamp-admins`에 가입시킵니다. 사용자를 찾지 못하면 오류로 멈춥니다.
- Keycloak의 client secret을 `headlamp` namespace의 Secret(`headlamp-oidc`)으로, CA 묶음을 ConfigMap(`headlamp-oidc-ca`)으로 등록합니다. namespace가 없으면 만듭니다.
- Keycloak 관리자 계정은 `KEYCLOAK_ENV`에서 읽습니다.

성공 문구는 `Headlamp OIDC 준비 완료: Keycloak client·관리자 그룹, namespace, client secret, CA ConfigMap`입니다.

아래 1~5단계는 관리자 화면에서 직접 등록하거나 도구의 결과를 대조할 때 쓰는 방법입니다. 1·5단계는 관리 호스트 터미널, 2~4단계는 PC의 Keycloak 관리자 화면에서 합니다.
관리자 화면에서는 왼쪽 위 realm을 **etch**로 맞추며 `master` realm에서 client를 만들지 않습니다. Keycloak 26.x 기준이며 화면 언어에 따라 메뉴 이름이 다를 수 있습니다.

### 1. client 등록 파일 생성과 가져오기

`manage.py oidc-client`가 현재 env로 비밀값 없는 client 정의를 만듭니다. `headlamp-oidc-setup`이 등록하는 정의와 같습니다. Authorization Code + PKCE S256, RS256 ID Token, profile·email scope,
`fullScopeAllowed: false`, `groups` mapper(`headlamp-groups`)가 포함됩니다.

[조회] client 정의와 등록에 쓸 공개 값을 출력합니다. `HEADLAMP_OIDC_CLIENT_ID`가 Client ID, `HEADLAMP_CALLBACK_URL`이 Valid redirect URIs, `HEADLAMP_OIDC_SECRET`이 Kubernetes Secret 이름입니다.

```bash
make headlamp-oidc-client > /tmp/headlamp-client.json
make -s headlamp-setup-env
```

[사람] 파일을 관리자 PC로 옮겨 **etch → Clients → Import client**에서 가져옵니다. 이미 client가 있으면 다시 가져오지 말고 2단계로 값을 대조합니다.
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
특히 Client authentication On, redirect URI가 관리 호스트 출력과 정확히 같음, PKCE S256, `headlamp-groups` mapper의 `groups`·Full group path On·Add to ID token On을 확인합니다.
mapper 세 값이 맞아야 API server가 관리자 그룹을 알아봅니다.

### 3. 사용할 사람을 그룹에 넣기

관리자 화면에서 직접 가입시키거나 그룹에서 뺄 때의 방법입니다. 가입은 `HEADLAMP_ADMINS`로도 할 수 있습니다.

1. **Groups → Create group**에서 `headlamp-admins`를 **최상위**에 만듭니다. 이미 있으면 그대로 사용합니다.
2. **Users**에서 사용할 사람을 선택하고 **Groups → Join Group**에서 `headlamp-admins`에 가입시킵니다. 기본 가입 그룹으로 지정하지 않습니다.
3. 해당 사용자의 Groups 목록에 `/headlamp-admins`가 보이는지 확인합니다. 그룹 이름 입력에는 `/`를 넣지 않으며 토큰에는 전체 경로가 들어갑니다.

사용자는 Keycloak username(EPID `userid`), 사내 로그인 ID(`loginid`), 표시 이름(`display_name`)으로 확인합니다.
CSV로 미리 등록한 사용자는 Account Console에서 첫 사내 로그인을 마치고 Identity provider links에 `oidc`가 연결된 뒤 가입시킵니다.
Headlamp용 계정을 따로 만들거나 EPID를 바꾸지 않으며, SDWT의 `/{SDWT}/admin` 그룹은 이 그룹을 대신하지 않습니다.
이 그룹은 **모든 namespace를 관리하고 Secret도 읽을 수 있는 클러스터 관리자**용입니다. 접근 거부 검증을 위해 그룹 밖 시험 계정도 준비합니다.
그룹 변경은 기존 ID Token이 만료되거나 새로 로그인할 때 반영됩니다.

### 4. Client secret 확인

**Clients → headlamp → Credentials**에서 **Client secret**을 확인합니다. 사용 중인 client라면 **Regenerate**를 누르지 않습니다.
Credentials 탭이 없으면 Client authentication이 On인지 확인합니다. client를 새로 만들었다면 새 client의 값을 사용합니다.
`headlamp`, `headlamp-oidc` 같은 이름은 비밀값이 아닙니다.

### 5. 관리 호스트에서 Client secret 등록

`headlamp-oidc-setup`은 Keycloak에서 client secret을 읽어 Secret으로 등록하므로 보통은 이 단계가 필요 없습니다.
[사람] 도구를 쓰지 않고 직접 등록할 때만 실행합니다. `Headlamp client secret:`이 나오면 4단계의 값을 붙여 넣습니다. 입력 글자는 보이지 않습니다. Secret 이름 `headlamp-oidc`는 env의 `HEADLAMP_OIDC_SECRET` 값입니다. `headlamp` namespace가 아직 없으면 [이미지 인증 Secret](01-prepare.md#이미지-인증-secret)의 첫 명령으로 먼저 만듭니다.

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
  kubectl --context "<context>" -n headlamp create secret generic headlamp-oidc \
    --from-file=OIDC_CLIENT_SECRET="$secret_file" --dry-run=client -o yaml |
    kubectl --context "<context>" apply -f -
)
```

[조회] 등록 결과:

```bash
kubectl --context "<context>" -n headlamp get secret headlamp-oidc
```

성공: TYPE `Opaque`, DATA `1`. 이 조회로 비밀값의 정확성은 알 수 없습니다.
`NotFound`이면 등록·조회의 context·namespace를 확인합니다. 기존 Secret에 다른 키가 있으면 배포 검사에서 거부하므로, 다른 앱의 Secret을 재사용하지 말고 전용 이름을 env에 지정합니다.
Secret을 바꾼 뒤에는 [재시작](04-operations.md#재시작과-복구)해야 새 값이 적용됩니다.

공식 참고: [Keycloak 26.7 관리자 안내](https://www.keycloak.org/docs/26.7.0/server_admin/).

## API server 인증

Headlamp 로그인 토큰을 Kubernetes API server가 받아들이게 하는 설정입니다. 등록되지 않으면 로그인 후에도 자원 조회가 실패합니다.
적용은 제어면 담당자가 각 제어면 서버에서 하며 절차는 [API server OIDC 설정](../../shared/docs/kubernetes/oidc.md)을 따릅니다. 아래 계약과 [TLS·CA 준비](01-prepare.md#tlsca-준비)의 CA 묶음을 전달합니다.

### 1. 적용할 계약

| 항목 | 적용값 |
| --- | --- |
| issuer | `HEADLAMP_OIDC_ISSUER_URL`(운영 `https://sso.etch.samsungds.net/realms/etch`) |
| audience / client ID | `HEADLAMP_OIDC_CLIENT_ID`(기본 `headlamp`) |
| username claim / prefix | `sub` / `headlamp:` |
| groups claim / prefix | `groups` / `headlamp:` |
| 서명 알고리즘 | `RS256` |
| CA | `HEADLAMP_OIDC_CA_FILE`의 PEM(기본 `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem`). 공인 CA 분기에서는 생략 |

[조회] 현재 env의 issuer와 client ID는 `make -s headlamp-setup-env`로 확인합니다.

Keycloak의 `sub`는 사용자 ID이며 username(EPID)·`loginid`·이름과 다릅니다.
ID Token의 그룹 `/headlamp-admins`는 API server에서 `headlamp:/headlamp-admins`가 되며 Helm의 `server-headlamp-admin` ClusterRoleBinding과 일치해야 합니다. 이 바인딩이 그룹에 `cluster-admin`을 부여합니다.
SSO 주소를 바꾸면 Headlamp env와 모든 API server의 issuer·CA를 함께 맞춥니다. 다른 앱의 `--oidc-*`·인증 설정은 덮어쓰지 않습니다.

`--oidc-*` 플래그 방식의 값은 다음과 같습니다. 앞의 두 줄은 위 계약의 값으로 바꾸고, YAML에서는 `:`로 끝나는 prefix 옵션을 작은따옴표로 감쌉니다.

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

[조회] 모든 제어면에 적용한 뒤 관리 호스트의 관리자 kubeconfig로 확인합니다. OIDC 플래그가 적용된 제어면 수는 [가이드의 완료 확인 명령](../README.md#사람이-하는-일)으로 셉니다.

```bash
kubectl --context "<context>" get --raw=/readyz
kubectl --context "<context>" get nodes
```

| 확인 | 기대 결과 |
| --- | --- |
| 적용 범위 | 모든 제어면에 같은 계약 적용. LB 뒤 한 서버만 정상일 수 있으므로 담당자가 서버별로 확인 |
| issuer·client ID | 1단계 계약과 일치 |
| 그룹 claim·prefix | `groups`와 `headlamp:` |
| CA | 모든 API server에서 discovery·JWKS의 HTTPS 검증 가능 |
| 기존 관리자 접속 | `/readyz`는 `ok`, 노드 목록 조회 성공 |

위 명령 성공만으로 OIDC 인증 성공이 검증되지는 않습니다. 실제 브라우저 로그인과 그룹별 권한은 [배포 동작과 로그인 검증](03-deploy.md)에서 확인합니다.
