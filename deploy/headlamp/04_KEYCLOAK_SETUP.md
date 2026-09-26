# 04. Keycloak client와 관리자 등록

[전체 순서](README.md) · 이전: [03 TLS](03_TLS.md) · 다음: [05 API server](05_APISERVER_SETUP.md)

`01`에서 선택한 env·context를 유지한 CP1 터미널과 Keycloak 관리자 화면을 사용합니다.
`03`의 TLS Secret·OIDC CA·연결 검사를 완료한 뒤 진행합니다.
새 터미널이면 [01 실행 입력](01_SERVER_SETUP.md#2-대상-context와-실행-입력)을 다시 준비합니다.
Keycloak 자체 설정은 이미 완료한 상태이며 여기서는 Headlamp 전용 client만 등록합니다.

**실행 위치:** 1~4번은 PC의 Keycloak 관리자 웹 화면, 5번은 CP1 터미널입니다.
**목표:** Headlamp를 로그인 가능한 앱으로 등록하고, 사용할 사람에게 그룹을 부여한 뒤 비밀값을 Kubernetes에 전달합니다.

먼저 CP1에서 아래 공개값을 출력해 브라우저 옆에 두고 입력합니다.

```bash
printf 'Client ID: %s\nValid redirect URIs: %s\nKubernetes Secret 이름: %s\n' \
  "$HEADLAMP_OIDC_CLIENT_ID" "$HEADLAMP_CALLBACK_URL" "$HEADLAMP_OIDC_SECRET"
```

빈 값이면 01의 실행 입력부터 다시 수행합니다. Keycloak 관리자 화면에서는 왼쪽 위 realm 선택을 **etch**로 맞춥니다.
`master` realm에서 client를 만들지 않습니다. Headlamp 초기화 중 client를 삭제했다면 아래에서 새로 생성합니다.

파일 임포트가 제한되어 있으면 **아래 순서대로 관리자 화면에서 직접 입력**합니다.
`headlamp-client.json`을 만들거나 PC로 가져올 필요가 없습니다.
Keycloak 26.x 기준이며 화면 언어에 따라 메뉴 이름이 조금 다를 수 있습니다.

## 1. Headlamp client 만들기

Keycloak 관리자 화면에서 **etch** realm을 선택한 뒤 **Clients → Create client**를 누릅니다.
이미 해당 client가 있으면 새로 만들지 말고 값을 확인합니다.
이 문서의 `headlamp`는 기본값이며 변경했다면 `HEADLAMP_OIDC_CLIENT_ID`와 해당 dedicated scope를 선택합니다.

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

`01`에서 출력한 `HEADLAMP_CALLBACK_URL`을 그대로 입력합니다. 위 주소는 기본 env의 예입니다.
주소 끝에 `/`나 `*`를 추가하지 않습니다.

저장 후 **Clients → headlamp → Advanced**에서 **Proof Key for Code Exchange Code Challenge Method**
항목을 찾아 **S256**으로 설정하고 저장합니다. 보통 **Advanced settings** 영역에 있습니다.
생성 화면에 같은 PKCE 항목이 보이면 그곳에서 설정해도 됩니다.

여기까지 저장한 뒤 client의 **Settings**를 다시 열어 Client authentication이 On이고,
Standard flow가 켜져 있으며 redirect URI가 CP1 출력과 정확히 같은지 확인합니다.
redirect URI는 Headlamp 첫 화면 주소가 아니라 로그인 결과를 받는 `/headlamp/oidc-callback` 주소입니다.

client의 서명 알고리즘은 RS256이어야 합니다. `Clients → 해당 client → Advanced`의
ID Token Signature Algorithm을 RS256으로 맞춥니다. 미설정 시 realm 기본값이 사용되므로 확인합니다.

## 2. 로그인 정보에 그룹 이름 넣기 — 반드시 필요

이 설정이 있어야 Kubernetes가 사용자의 `headlamp-admins` 가입 여부를 알 수 있습니다.

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

`headlamp-dedicated`가 보이지 않으면 먼저 **Clients → 해당 client → Client scopes** 안에 있는지 확인합니다.
client ID를 변경했다면 dedicated 이름도 그 client에 맞게 표시됩니다.
저장한 mapper를 다시 열어 `groups`, Full group path On, Add to ID token On을 확인하세요.
이 세 값이 맞아야 05의 API server가 관리자 그룹을 알아볼 수 있습니다.

## 3. 사용할 사람을 그룹에 넣기

1. 왼쪽 **Groups → Create group**에서 `headlamp-admins`를 만듭니다. 다른 그룹 아래가 아닌 **최상위**에 만듭니다. 이미 있으면 그대로 사용합니다.
2. **Users**에서 Headlamp를 사용할 사람을 선택합니다.
3. 그 사용자의 **Groups → Join Group**에서 `headlamp-admins`를 선택해 가입시킵니다.
4. 허용할 사람마다 반복합니다. 모든 사용자의 기본 가입 그룹으로 지정하지 않습니다.

현재 Keycloak의 기본 **username은 EPID(`userid`)**입니다. 사내 로그인 ID는 `loginid`,
사람 이름은 `display_name`에 저장되므로 동명이인이나 별도 계정을 잘못 선택하지 않도록 함께 확인합니다.
CSV로 미리 등록한 사람은 Account Console에서 첫 사내 로그인을 마친 뒤
**Identity provider links → oidc**가 연결된 그 계정에 그룹을 부여합니다.
Headlamp용 계정을 새로 만들거나 기존 EPID를 로그인 ID로 변경하지 않습니다.
SDWT의 `/{SDWT}/admin` 그룹은 이 관리자 그룹을 대신하지 않습니다.

그룹 이름을 입력할 때 `/`는 넣지 않습니다. 2번에서 **Full group path**를 켰으므로
로그인 정보에는 자동으로 `/headlamp-admins`라는 전체 경로가 들어갑니다.

가입 후 해당 사용자의 Groups 목록에 `/headlamp-admins`가 보이는지 확인합니다.
이 그룹은 **모든 namespace를 관리하고 Secret도 읽을 수 있는 클러스터 관리자**용입니다.
마지막 접근 거부 검증을 위해 별도 권한이 없는 그룹 밖 시험 계정도 준비합니다.

## 4. Client secret 확인

**Clients → headlamp → Credentials**에서 **Client secret**을 확인합니다.
아래 5번의 CP1 명령이 비밀값을 물어볼 때 이 값을 입력합니다.
이미 사용 중인 client라면 **Regenerate**를 누르지 않습니다.
**Credentials** 탭이 없으면 1번의 **Client authentication**이 On인지 확인합니다.

Client secret은 자동으로 발급되는 긴 비밀 문자열입니다. `headlamp`, `headlamp-oidc` 같은 이름을 대신 입력하면 안 됩니다.
client를 삭제하고 새로 만들었다면 **새 client의 Credentials 값**을 사용합니다. 과거 비밀값은 재사용하지 않습니다.

**완료 기준:** `headlamp` client와 `headlamp-groups` mapper가 있고,
허용할 사용자가 `headlamp-admins` 그룹에 들어 있으며 Client secret을 확인했습니다.
아래 5번에서 Secret을 등록합니다.

<details>
<summary>파일 임포트가 가능한 환경에서의 대체 방법</summary>

CP1에서 다음 명령으로 등록 파일을 만들 수 있습니다. 비밀번호는 포함되지 않습니다.

```bash
make headlamp-oidc-client > /tmp/headlamp-client.json
```

관리자 PC로 파일을 가져와 **etch → Clients → Import client**에서 등록합니다.
이 방법은 1번과 2번을 대신합니다. 그룹 가입과 비밀값 확인은 **3번, 4번**을 그대로 진행합니다.
이미 있는 client를 다시 import하거나 비밀값을 재발급하지 않습니다.

</details>

## 5. CP1에서 Client secret 등록

아래 블록을 CP1 터미널에 붙여 넣습니다. `Headlamp client secret:`이 나오면
4번에서 확인한 값을 붙여 넣고 Enter를 누릅니다. 입력하는 글자가 화면에 보이지 않는 것이 정상입니다.

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
```

비밀값은 Kubernetes의 `HEADLAMP_OIDC_SECRET` 이름의 Secret에 저장됩니다.
`OIDC_CLIENT_SECRET`이라는 항목 하나만 등록하며 임시 파일은 자동으로 지웁니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp get secret "$HEADLAMP_OIDC_SECRET"
```

TYPE은 `Opaque`, DATA는 `1`이어야 합니다. 등록 블록의 마지막 명령이 오류 없이 끝났는지도 확인하세요.
`NotFound`면 같은 context·namespace에 등록했는지 확인합니다.
이 조회는 Secret의 존재만 확인하므로 비밀값을 잘못 붙여 넣었다면 5번 블록을 다시 실행해 올바른 값으로 갱신합니다.

기존 Secret에 다른 키가 있으면 배포 검사에서 거부합니다. 다른 앱의 Secret을 재사용하지 말고
Headlamp 전용 Secret 이름을 env에 지정한 뒤 `01`의 입력을 다시 읽고 등록합니다.

**완료 기준:** 전용 client·S256·groups mapper·관리자 가입·OIDC Secret 등록이 모두 완료됐습니다.
다음 [05 API server 설정](05_APISERVER_SETUP.md)은 필수입니다.

공식 참고: [Keycloak 26.7 관리자 안내](https://www.keycloak.org/docs/26.7.0/server_admin/).
