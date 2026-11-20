# Headlamp 로그인과 API server 인증

[Headlamp 가이드](../README.md)

설치·업데이트 절차는 [Headlamp 가이드](../README.md)에 있습니다. 이 문서는 Keycloak client·관리자 그룹의 등록 내용, 도구가 다루지 않는 작업(기존 client 대조, 관리자 제거, client secret 직접 등록), API server에 적용할 인증 계약입니다.

- [Keycloak client와 관리자](#keycloak-client와-관리자)
- [API server 인증](#api-server-인증)

## Keycloak client와 관리자

`etch` realm에 Headlamp 전용 client를 등록하고, 사용할 사람을 관리자 그룹에 넣은 뒤 client secret을 Kubernetes에 전달하는 일입니다.
`make ops-deploy APP=headlamp`의 `headlamp-oidc-setup` 단계가 Keycloak 관리 API로 이 일을 수행합니다([가이드 A](../README.md#a-최초-설치), [B](../README.md#b-업데이트)).

- client와 `headlamp-admins` 그룹이 없으면 만듭니다. 기존 client 설정은 바꾸지 않습니다.
- `HEADLAMP_ADMINS`로 받은 Keycloak username을 `headlamp-admins`에 가입시킵니다. 지정하지 않으면 그룹만 만들고 구성원은 넣지 않습니다. 사용자를 찾지 못하면 오류로 멈춥니다.
- Keycloak의 client secret을 `headlamp` namespace의 Secret(`headlamp-oidc`)으로, CA 묶음을 ConfigMap(`headlamp-oidc-ca`)으로 등록합니다. namespace가 없으면 만듭니다.
- Keycloak 관리자 계정은 `KEYCLOAK_ENV`에서 읽습니다([Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api)).

성공 문구는 `Headlamp OIDC 준비 완료: Keycloak client·관리자 그룹, namespace, client secret, CA ConfigMap`입니다. 그 앞에 한 일이 줄마다 나옵니다.

| 출력 | 뜻 |
| --- | --- |
| `Keycloak client 등록: headlamp` | client를 새로 만듦 |
| `Keycloak client가 이미 있어 설정을 바꾸지 않았습니다: headlamp` | 기존 client를 그대로 씀. [2. 기존 client 대조](#2-기존-client-대조)를 수행 |
| `Keycloak 그룹 생성: /headlamp-admins` | 관리자 그룹을 새로 만듦 |
| `관리자 그룹 가입: <username>` | `HEADLAMP_ADMINS`의 사용자를 가입시킴 |

아래 1~5는 도구가 등록하는 내용과 도구가 다루지 않는 작업입니다. Keycloak 설정의 조회·변경은 관리 화면이 아니라 [Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api) 절의 방법으로 합니다. realm은 `etch`이며 `master` realm에 client를 만들지 않습니다. Keycloak 26.x 기준입니다.

### 1. client 등록 내용

`headlamp-oidc-setup`이 등록하는 client 정의는 현재 env로 만든 비밀값 없는 JSON입니다. Authorization Code + PKCE S256, RS256 ID Token, profile·email scope,
`fullScopeAllowed: false`, `groups` mapper(`headlamp-groups`)가 포함됩니다.

[조회] client 정의와 등록에 쓰는 공개 값을 출력합니다. Keycloak에 접속하지 않습니다. `HEADLAMP_OIDC_CLIENT_ID`가 Client ID, `HEADLAMP_CALLBACK_URL`이 Valid redirect URIs, `HEADLAMP_OIDC_SECRET`이 Kubernetes Secret 이름입니다.

```bash
make headlamp-oidc-client
make -s headlamp-setup-env
```

정의의 값을 관리 화면의 항목 이름으로 옮기면 다음과 같습니다.

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

다른 앱이 함께 쓰는 공용 **Client scopes**의 설정은 수정하지 않습니다.

### 2. 기존 client 대조

`headlamp-oidc-setup`이 `Keycloak client가 이미 있어 설정을 바꾸지 않았습니다`를 출력했을 때 수행합니다.

[조회] [Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api) 절의 방법으로 `etch` realm의 `clients?clientId=headlamp` 응답을 받아 1번의 `make headlamp-oidc-client` 출력과 대조합니다. 응답의 `secret` 값은 출력하거나 기록하지 않습니다.

- `publicClient`가 `false`(Client authentication On)
- `redirectUris`가 `HEADLAMP_CALLBACK_URL`과 정확히 같음
- `attributes`의 `pkce.code.challenge.method`가 `S256`
- `protocolMappers`의 `headlamp-groups`가 `claim.name` `groups`, `full.path` `true`, `id.token.claim` `true`

mapper의 세 값이 맞아야 API server가 관리자 그룹을 알아봅니다.
다른 항목이 있으면 멈추고 다른 항목의 이름과 두 값을 보고합니다. client를 지우고 다시 만들거나 client secret을 Regenerate하지 않습니다.

### 3. 사용할 사람을 그룹에 넣기

- 가입: [가이드 B](../README.md#b-업데이트)의 `관리자 추가`(`HEADLAMP_ADMINS`)로 합니다. 그룹은 도구가 **최상위**에 `headlamp-admins`로 만듭니다. 그룹 이름에는 `/`가 없고 토큰에는 전체 경로 `/headlamp-admins`가 들어갑니다. 기본 가입 그룹으로 지정하지 않습니다.
- 그룹에서 빼기: [변경] 도구에 제거 기능이 없으므로 [Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api) 절의 방법으로 `etch` realm의 `users/<사용자 id>/groups/<그룹 id>`를 `DELETE`합니다. 가입에 쓰는 것과 같은 자원이며, 사용자 id는 `users?username=<username>&exact=true`, 그룹 id는 `groups?search=headlamp-admins&exact=true`로 조회합니다.
  확인: `users/<사용자 id>/groups` 응답에 `/headlamp-admins`가 없습니다. 이후 새 토큰으로 [권한 확인](03-deploy.md#kubernetes-rbac-확인)을 합니다.

사용자는 Keycloak username(EPID `userid`), 사내 로그인 ID(`loginid`), 표시 이름(`display_name`)으로 확인합니다.
CSV로 미리 등록한 사용자는 Account Console에서 첫 사내 로그인을 마치고 Identity provider links에 `oidc`가 연결된 뒤 가입시킵니다.
Headlamp용 계정을 따로 만들거나 EPID를 바꾸지 않으며, SDWT의 `/{SDWT}/admin` 그룹은 이 그룹을 대신하지 않습니다.
이 그룹은 **모든 namespace를 관리하고 Secret도 읽을 수 있는 클러스터 관리자**용입니다. 접근 거부 검증에는 그룹 밖 시험 계정을 씁니다.
그룹 변경은 기존 ID Token이 만료되거나 새로 로그인할 때 반영됩니다.

### 4. Client secret 확인

client secret은 `headlamp-oidc-setup`이 Keycloak에서 읽어 Secret으로 등록하므로 값을 따로 확인하거나 옮겨 적지 않습니다. 사용 중인 client의 secret을 **Regenerate**하지 않습니다.
`Keycloak client secret을 읽지 못했습니다`가 나오면 그 client의 Client authentication이 꺼져 있는 것입니다. 2번으로 대조합니다.
`headlamp`, `headlamp-oidc` 같은 이름은 비밀값이 아닙니다.

[조회] 등록 결과:

```bash
kubectl --context "<context>" -n headlamp get secret headlamp-oidc
```

성공: TYPE `Opaque`, DATA `1`. 이 조회로 비밀값의 정확성은 알 수 없습니다.
`NotFound`이면 등록·조회의 context·namespace를 확인합니다. 기존 Secret에 다른 키가 있으면 배포 검사에서 거부하므로, 다른 앱의 Secret을 재사용하지 말고 전용 이름을 env의 `HEADLAMP_OIDC_SECRET`에 지정합니다.
Secret을 바꾼 뒤에는 [재시작](04-operations.md#재시작과-복구)해야 새 값이 적용됩니다.

### 5. 관리 호스트에서 Client secret 등록

**대체 절차입니다.** `make headlamp-oidc-setup`이 Keycloak 관리 API에 닿지 않아 실패하고 [Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api) 절로도 해결되지 않을 때만 씁니다. 보통은 `headlamp-oidc-setup`이 같은 Secret을 등록합니다.

client secret 값은 명령에 쓰지 않고 파일로 전달합니다. 파일에는 값만 줄바꿈 없이 들어 있어야 하며 권한은 0600입니다. 파일은 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 위치에 두고 내용을 출력하지 않습니다.
Secret 이름 `headlamp-oidc`는 env의 `HEADLAMP_OIDC_SECRET` 값입니다. `headlamp` namespace가 아직 없으면 [이미지 인증 Secret](01-prepare.md#이미지-인증-secret)의 첫 명령으로 먼저 만듭니다.

[변경] 파일의 값을 `OIDC_CLIENT_SECRET` 키 하나로 등록하고 결과를 조회합니다.

```bash
kubectl --context "<context>" -n headlamp create secret generic headlamp-oidc \
  --from-file=OIDC_CLIENT_SECRET=<client secret 파일의 절대 경로> --dry-run=client -o yaml |
  kubectl --context "<context>" apply -f -
kubectl --context "<context>" -n headlamp get secret headlamp-oidc
```

성공: TYPE `Opaque`, DATA `1`. 등록 뒤 [재시작](04-operations.md#재시작과-복구)합니다.

공식 참고: [Keycloak 26.7 관리자 안내](https://www.keycloak.org/docs/26.7.0/server_admin/).

## API server 인증

Headlamp 로그인 토큰을 Kubernetes API server가 받아들이게 하는 설정입니다. 등록되지 않으면 로그인 후에도 자원 조회가 실패합니다.

[승인] 각 제어면에서 [API server OIDC 인증](../../shared/docs/kubernetes/oidc.md) 문서의 절차를 [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)로 수행합니다. API server가 다시 시작되므로 한 번에 한 대씩 적용하고, 그 제어면이 `Ready`이고 아래 [완료 확인](#2-완료-확인)이 통과한 뒤 다음 제어면으로 갑니다. 적용값은 아래 계약이고 CA 파일은 [TLS·CA 준비](01-prepare.md#tlsca-준비)의 CA 묶음입니다.

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
SSO 주소를 바꾸면 Headlamp env와 모든 API server의 issuer·CA를 함께 맞춥니다. 다른 앱의 `--oidc-*`·인증 설정은 덮어쓰지 않습니다. 다른 issuer·client의 설정이 이미 있으면 멈추고 보고합니다.

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

[조회] 제어면 한 대에 적용할 때마다, 그리고 모든 제어면에 적용한 뒤 관리 호스트에서 확인합니다. OIDC 플래그가 적용된 제어면은 [가이드의 완료 확인 명령](../README.md#사전-준비)이 제어면마다 한 줄씩 보여 줍니다.

```bash
kubectl --context "<context>" get --raw=/readyz
kubectl --context "<context>" get nodes
```

| 확인 | 기대 결과 |
| --- | --- |
| 적용 범위 | 모든 제어면에 같은 계약 적용. LB 뒤 한 서버만 정상일 수 있으므로 가이드의 완료 확인 명령으로 제어면마다 확인 |
| issuer·client ID | 1단계 계약과 일치 |
| 그룹 claim·prefix | `groups`와 `headlamp:` |
| CA | 모든 API server에서 discovery·JWKS의 HTTPS 검증 가능 |
| 기존 관리자 접속 | `/readyz`는 `ok`, 노드 목록 조회 성공 |

위 명령 성공만으로 OIDC 인증 성공이 검증되지는 않습니다. 실제 브라우저 로그인과 그룹별 권한은 [배포 동작과 로그인 검증](03-deploy.md)에서 확인합니다.
