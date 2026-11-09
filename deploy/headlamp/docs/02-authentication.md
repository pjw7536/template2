# Headlamp 로그인과 API server 인증

[앱 안내](../README.md)

- [Keycloak client와 관리자](#keycloak-client와-관리자)
- [API server 인증](#api-server-인증)

## Keycloak client와 관리자

[TLS 준비](01-prepare.md#tlsca-준비)의 공용 TLS·OIDC CA 등록과 연결 검사를 마친 뒤 진행합니다.
Keycloak 자체 설정은 완료되어 있어야 합니다. 이 단계에서는 Headlamp 전용 client를 등록합니다.

[서버 준비](01-prepare.md#서버실행-입력)에서 사용한 env·context를 유지한 CP1 터미널과 Keycloak 관리자 화면을 준비합니다.
새 터미널이면 [실행 입력](01-prepare.md#2-대상-context와-실행-입력)을 다시 설정합니다.

**실행 위치:** 1~4번은 PC의 Keycloak 관리자 웹 화면, 5번은 CP1 터미널입니다.
**목표:** Headlamp를 로그인 가능한 앱으로 등록하고, 사용할 사람에게 그룹을 부여한 뒤 비밀값을 Kubernetes에 전달합니다.

먼저 CP1에서 아래 공개값을 출력해 브라우저 옆에 두고 입력합니다.

```bash
printf 'Client ID: %s\nValid redirect URIs: %s\nKubernetes Secret 이름: %s\n' \
  "$HEADLAMP_OIDC_CLIENT_ID" "$HEADLAMP_CALLBACK_URL" "$HEADLAMP_OIDC_SECRET"
```

빈 값이면 [서버 준비](01-prepare.md#서버실행-입력)의 실행 입력부터 다시 수행합니다. Keycloak 관리자 화면에서는 왼쪽 위 realm 선택을 **etch**로 맞춥니다.
`master` realm에서 client를 만들지 않습니다. Headlamp 초기화 중 client를 삭제했다면 아래에서 새로 생성합니다.

파일 임포트가 제한되어 있으면 **아래 순서대로 관리자 화면에서 직접 입력**합니다.
`headlamp-client.json`을 만들거나 PC로 가져올 필요가 없습니다.
Keycloak 26.x 기준이며 화면 언어에 따라 메뉴 이름이 조금 다를 수 있습니다.

### 1. Headlamp client 만들기

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

[서버 준비](01-prepare.md#서버실행-입력)에서 출력한 `HEADLAMP_CALLBACK_URL`을 그대로 입력합니다. 위 주소는 기본 env의 예입니다.
주소 끝에 `/`나 `*`를 추가하지 않습니다.

저장 후 **Clients → headlamp → Advanced**에서 **Proof Key for Code Exchange Code Challenge Method**
항목을 찾아 **S256**으로 설정하고 저장합니다. 보통 **Advanced settings** 영역에 있습니다.
생성 화면에 같은 PKCE 항목이 보이면 그곳에서 설정해도 됩니다.

여기까지 저장한 뒤 client의 **Settings**를 다시 열어 Client authentication이 On이고,
Standard flow가 켜져 있으며 redirect URI가 CP1 출력과 정확히 같은지 확인합니다.
redirect URI는 Headlamp 첫 화면 주소가 아니라 로그인 결과를 받는 `/headlamp/oidc-callback` 주소입니다.

client의 서명 알고리즘은 RS256이어야 합니다. `Clients → 해당 client → Advanced`의
ID Token Signature Algorithm을 RS256으로 맞춥니다. 미설정 시 realm 기본값이 사용되므로 확인합니다.

### 2. 로그인 정보에 그룹 이름 넣기 — 반드시 필요

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
이 세 값이 맞아야 [API server 인증](#api-server-인증)의 API server가 관리자 그룹을 알아볼 수 있습니다.

### 3. 사용할 사람을 그룹에 넣기

1. 왼쪽 **Groups → Create group**에서 `headlamp-admins`를 만듭니다. 다른 그룹 아래가 아닌 **최상위**에 만듭니다. 이미 있으면 그대로 사용합니다.
2. **Users**에서 Headlamp를 사용할 사람을 선택합니다.
3. 그 사용자의 **Groups → Join Group**에서 `headlamp-admins`를 선택해 가입시킵니다.
4. 허용할 사람마다 반복합니다. 모든 사용자의 기본 가입 그룹으로 지정하지 않습니다.

사용자를 고를 때는 다음 세 값을 함께 확인합니다.

- Keycloak username: EPID(`userid`)
- 사내 로그인 ID: `loginid`
- 표시 이름: `display_name`

CSV로 미리 등록한 사용자는 Account Console에서 첫 사내 로그인을 마친 뒤 처리합니다.
그 사용자의 Identity provider links에 `oidc`가 연결된 계정인지 확인하고 그룹을 부여합니다.

Headlamp용 계정을 따로 만들거나 기존 EPID를 로그인 ID로 바꾸지 않습니다.
SDWT의 `/{SDWT}/admin` 그룹은 Headlamp 관리자 그룹을 대신하지 않습니다.

그룹 이름을 입력할 때 `/`는 넣지 않습니다. 2번에서 **Full group path**를 켰으므로
로그인 정보에는 자동으로 `/headlamp-admins`라는 전체 경로가 들어갑니다.

가입 후 해당 사용자의 Groups 목록에 `/headlamp-admins`가 보이는지 확인합니다.
이 그룹은 **모든 namespace를 관리하고 Secret도 읽을 수 있는 클러스터 관리자**용입니다.
마지막 접근 거부 검증을 위해 별도 권한이 없는 그룹 밖 시험 계정도 준비합니다.

### 4. Client secret 확인

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

### 5. CP1에서 Client secret 등록

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

정상 등록 여부는 다음 두 항목으로 확인합니다.

- 등록 블록의 마지막 명령이 오류 없이 끝납니다.
- 조회 결과의 TYPE은 `Opaque`, DATA는 `1`입니다.

`NotFound`이면 등록할 때와 조회할 때의 context·namespace가 같은지 확인합니다.
이 조회로는 비밀값의 정확성까지 알 수 없습니다.
잘못 붙여 넣었다면 5번 블록을 다시 실행해 올바른 값으로 갱신합니다.

기존 Secret에 다른 키가 있으면 배포 검사에서 거부합니다. 다른 앱의 Secret을 재사용하지 말고
Headlamp 전용 Secret 이름을 env에 지정한 뒤 [서버 준비](01-prepare.md#서버실행-입력)의 입력을 다시 읽고 등록합니다.

**완료 기준:** 전용 client·S256·groups mapper·관리자 가입·OIDC Secret 등록이 모두 완료됐습니다.
다음 [API server 설정](#api-server-인증)은 필수입니다.

공식 참고: [Keycloak 26.7 관리자 안내](https://www.keycloak.org/docs/26.7.0/server_admin/).

## API server 인증

Headlamp 로그인에 사용하는 Keycloak 토큰을 Kubernetes API server가 받아들이도록 설정하는 필수 단계입니다.
Keycloak은 사용자를 인증하고, API server는 그 토큰을 신뢰할지 판단합니다.
API server에 issuer와 client ID가 등록되지 않으면 로그인 후에도 자원 조회가 실패합니다.

작업은 제어면 담당자가 수행합니다. 위임할 때는 아래 인증 계약과 [TLS 준비](01-prepare.md#tlsca-준비)의 CA 묶음을 전달합니다.
모든 API server에 반영됐다는 확인을 받은 뒤 [배포·검증](03-deploy.md)으로 이동합니다.

실행 위치는 다음과 같이 구분합니다.

- `kubectl` 조회: CP1 터미널
- `/etc/kubernetes` 파일 편집과 `sudo` 명령: 설정할 각 제어면 서버에 SSH로 접속한 터미널

아래 kubeadm 예시는 실제 설치 방식이 kubeadm일 때만 사용합니다.

| 현재 상황 | 진행 방법 |
| --- | --- |
| kubeadm이고 OIDC 설정이 없음 | 1번 확인 → 2번 CA 배치 → 3번 플래그·마운트 → 5번 검증 |
| 초기화 전 Headlamp OIDC 설정이 남아 있음 | 1번 계약과 현재 설정을 대조. 값이 같으면 중복 추가 없이 파일·마운트·접근을 확인 |
| `--authentication-config` 사용 중 | 1번 확인 → 4번 기존 인증 파일에 반영 → 5번 검증 |
| 다른 앱의 `--oidc-*` 설정이 있음 | 기존 설정을 덮어쓰지 않고 인증 통합을 담당자와 조정 |
| 관리형 클러스터·k3s·RKE2 등 다른 설치 방식 | 담당자에게 1번 계약 전달. 해당 설치 방식의 설정 경로 사용 |

설치 방식을 모르면 먼저 클러스터 담당자에게 확인합니다. kubeadm 파일 경로가 없다는 이유로 새 파일을 만들지 않습니다.

### 1. 적용할 계약과 기존 인증 확인

[서버 준비](01-prepare.md#서버실행-입력)를 수행했던 CP1 터미널에서 이번 설치의 실제 값을 출력합니다. 이 공개값을 제어면 담당자에게 전달하거나 작업 메모에 둡니다.

```bash
printf 'issuer: %s\naudience / client ID: %s\nCP1의 CA 원본 파일: %s\n' \
  "$HEADLAMP_OIDC_ISSUER_URL" "$HEADLAMP_OIDC_CLIENT_ID" "$HEADLAMP_OIDC_CA_FILE"
```

issuer와 client ID가 비어 있으면 [서버 준비](01-prepare.md#서버실행-입력)의 실행 입력부터 다시 수행합니다.

| 항목 | 적용값 |
| --- | --- |
| issuer | [서버 준비](01-prepare.md#서버실행-입력)의 `HEADLAMP_OIDC_ISSUER_URL` |
| audience / client ID | [서버 준비](01-prepare.md#서버실행-입력)의 `HEADLAMP_OIDC_CLIENT_ID` |
| username claim / prefix | `sub` / `headlamp:` |
| groups claim / prefix | `groups` / `headlamp:` |
| 서명 알고리즘 | `RS256` |
| CA | [TLS 준비](01-prepare.md#tlsca-준비)의 `HEADLAMP_OIDC_CA_FILE`에 생성한 PEM 파일 |

Keycloak의 `sub`는 사용자 ID입니다. 기본 username(EPID)·`loginid`·사람 이름과 다릅니다.
ID Token의 전체 그룹 경로 `/headlamp-admins`는 API server에서 `headlamp:/headlamp-admins`가 됩니다.
이 계약은 Helm의 `server-headlamp-admin` ClusterRoleBinding과 일치해야 합니다.

먼저 Kubernetes 버전과 설치 도구, 현재 API server 인증 설정을 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" version
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -l component=kube-apiserver -o wide
```

관리형 클러스터처럼 제어면을 직접 수정할 수 없다면 공급자의 OIDC 설정으로 같은 계약을 반영합니다.
`--authentication-config`를 이미 사용한다면 아래 플래그와 혼용하지 않고 4번으로 진행합니다.
기존 `--oidc-*`가 다른 issuer/client에 연결돼 있다면 덮어쓰지 않습니다. 기존 사용자를 포함한 인증 통합을
담당자가 먼저 완료해야 하며, 그동안 [배포·검증](03-deploy.md)의 배포만으로 로그인이 완성된 것으로 보지 않습니다.

kubeadm이면 **각 제어면 서버의 터미널**에서 현재 파일 존재 여부와 인증 옵션을 확인할 수 있습니다.

```bash
sudo test -f /etc/kubernetes/manifests/kube-apiserver.yaml
sudo grep -nE -- '--(oidc-|authentication-config)' /etc/kubernetes/manifests/kube-apiserver.yaml
```

첫 명령은 파일이 있으면 출력 없이 성공합니다. 파일이 없거나 권한 오류가 나면 설치 방식·접속 서버를 확인합니다.
파일을 정상적으로 읽었는데 두 번째 명령의 출력이 없다면 해당 옵션이 없는 상태입니다.
옵션이 있다면 위 분기표에 따라 진행하며, 전체 파일과 설치 도구의 원본 설정도 함께 확인합니다.

### 2. 모든 제어면에 CA 파일 배치

[TLS 준비](01-prepare.md#tlsca-준비)의 CA 묶음 **한 파일만** 각 제어면으로 전달합니다. PFX·사이트 개인키는 전달하지 않습니다.
각 제어면에서 전달받은 파일 경로를 입력합니다.

```bash
read -r -p '전달받은 Keycloak CA PEM 파일의 절대 경로: ' APISERVER_CA_SOURCE
sudo install -d -m 0755 /etc/kubernetes/oidc
sudo install -m 0644 "$APISERVER_CA_SOURCE" /etc/kubernetes/oidc/keycloak-ca-bundle.pem
```

API server 컨테이너에도 이 파일이 보여야 합니다. ConfigMap을 Headlamp에 등록하는 것만으로는 부족합니다.

`전달받은 ... 경로:`에는 **현재 접속한 제어면 서버에 복사해 둔 PEM 파일 경로**를 입력합니다.
CP1의 환경변수나 파일은 다른 서버에 자동으로 전달되지 않습니다.
등록 후 다음으로 PEM 인증서 목록이 읽히는지 확인합니다.

```bash
openssl crl2pkcs7 -nocrl -certfile /etc/kubernetes/oidc/keycloak-ca-bundle.pem |
  openssl pkcs7 -print_certs -noout
```

현재 사내 CA 구성에서는 루트·중간 CA가 나와야 합니다. 공인 CA 분기라면 이 파일 배치와 3번의 CA 플래그·마운트는 생략합니다.

### 3. oidc 플래그 방식에 반영

현재 issuer/client가 비어 있거나 위 계약과 같은 경우 사용합니다.
실제 값은 [서버 준비](01-prepare.md#서버실행-입력)의 설정에서 복사합니다. 꺾쇠 괄호를 포함한 예시 문자열을 그대로 넣지 않습니다.

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

앞의 두 줄에는 1번에서 출력한 실제 issuer와 client ID를 넣습니다. 나머지 claim·prefix·서명 값은 표 그대로 유지합니다.
manifest의 `command` 아래에는 기존 `- --...` 줄과 같은 들여쓰기로 다음 형태가 됩니다.
아래는 **형식 예시**이며 주소는 1번 출력값으로 바꿔야 합니다.

```yaml
spec:
  containers:
    - name: kube-apiserver
      command:
        - kube-apiserver
        # 기존 command 옵션들을 유지하고 아래 인증 옵션을 합칩니다.
        - --oidc-issuer-url=https://sso.example.test/realms/etch
        - --oidc-client-id=headlamp
        - --oidc-username-claim=sub
        - '--oidc-username-prefix=headlamp:'
        - --oidc-groups-claim=groups
        - '--oidc-groups-prefix=headlamp:'
        - --oidc-signing-algs=RS256
        - --oidc-ca-file=/etc/kubernetes/oidc/keycloak-ca-bundle.pem
```

이 예시는 전체 Pod 정의가 아닙니다. 기존 이미지·다른 command 옵션·인증서·네트워크 설정 등을 지우지 않습니다.
끝에 `:`가 있는 두 prefix 옵션은 예시처럼 작은따옴표로 감싸 YAML 문자열로 입력합니다.

#### kubeadm static Pod인 경우

실제 kubeadm 구성인지 확인한 경우에만 `/etc/kubernetes/manifests/kube-apiserver.yaml`을 편집합니다.
백업은 kubelet이 읽는 manifests 폴더 **밖에** 둡니다. 아래 블록은 각 제어면에서 실행합니다.

```bash
sudo install -d -m 0700 /etc/kubernetes/backup
sudo cp -p /etc/kubernetes/manifests/kube-apiserver.yaml \
  "/etc/kubernetes/backup/kube-apiserver.$(date +%Y%m%d%H%M%S).yaml"
sudo vi /etc/kubernetes/manifests/kube-apiserver.yaml
```

`kube-apiserver` 컨테이너의 기존 `command` 목록에 위 플래그를 추가합니다.
같은 키가 이미 있으면 중복 추가하지 않고 값을 대조합니다.
아래 항목을 해당 컨테이너의 `volumeMounts`와 Pod의 `volumes`에 각각 합칩니다.
**아래 조각으로 기존 manifest 전체를 덮어쓰지 않습니다.**

이미 `volumeMounts:` 또는 `volumes:`가 있으면 **그 아래 목록에 `- name: keycloak-oidc-ca` 항목만 추가**합니다.
같은 위치에 `volumeMounts:`·`volumes:` 키를 두 번 만들지 않습니다. 이름이 같은 항목이 있으면 기존 내용을 대조합니다.

```yaml

# spec.containers의 kube-apiserver 컨테이너에 추가
volumeMounts:
  - name: keycloak-oidc-ca
    mountPath: /etc/kubernetes/oidc
    readOnly: true

# spec.volumes에 추가
volumes:
  - name: keycloak-oidc-ca
    hostPath:
      path: /etc/kubernetes/oidc
      type: Directory
```

저장하면 kubelet이 API server를 재시작합니다. 제어면이 한 대라면 잠시 API 요청이 중단됩니다.
여러 대라면 한 대씩 적용하고, 각 서버가 다시 기동된 뒤 바로 5번 검증을 수행합니다.
정상 접속을 확인한 후 다음 서버로 이동합니다.

재기동 후에도 복구되지 않으면 작업을 멈춥니다.
해당 서버의 SSH 터미널에서 방금 만든 백업으로 manifest를 복원하고,
YAML 들여쓰기·중복 옵션·CA 마운트 경로를 확인합니다.
API가 응답하지 않는 동안에는 kubectl 대신 그 서버의 SSH 터미널에서 복원해야 합니다.

설치 도구가 관리하는 원본 설정에도 같은 플래그와 마운트를 기록합니다.
그래야 재생성하거나 업그레이드할 때 설정이 유지됩니다.

### 4. AuthenticationConfiguration 방식인 경우

기존 인증 파일에 issuer·audience·CA와 아래 claim 매핑을 반영합니다.
지원 API 버전은 실행 중인 Kubernetes 버전에 맞춥니다. 기존 issuer 항목을 보존하고
같은 issuer가 이미 있으면 그 항목의 audience·매핑과 다른 앱 영향을 먼저 조정합니다.

```yaml

# 기존 jwt 항목 안에 합칠 매핑. 전체 인증 파일이 아닙니다.
claimMappings:
  username:
    claim: sub
    prefix: 'headlamp:'
  groups:
    claim: groups
    prefix: 'headlamp:'
```

`issuer.url`은 공개 issuer, `issuer.audiences`에는 Headlamp client ID를 사용합니다.
사내 CA는 `issuer.certificateAuthority`에 PEM 내용을 넣습니다. 파일 경로를 넣는 필드가 아닙니다.
`--authentication-config`의 파일과 CA 내용은 모든 API server에 적용해야 합니다.
세부 스키마는 [공식 인증 설정](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#authentication-configuration-from-a-file)을 따릅니다.

### 5. 완료 확인

모든 제어면에서 Keycloak discovery·JWKS의 DNS·HTTPS·CA 신뢰가 정상인지 확인합니다.
각 제어면이 다시 기동된 뒤 관리자 kubeconfig로 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" get --raw=/readyz
kubectl --context "$KUBE_CONTEXT" get nodes
```

`readyz`는 `ok`여야 합니다. LB 뒤의 한 서버만 정상일 수 있으므로 담당자는 각 API server의
상태·적용값을 개별 확인합니다. 위 명령 성공만으로 OIDC 인증 성공이 검증되지는 않습니다.

| 다음 단계로 가기 전 확인 | 기대 결과 |
| --- | --- |
| 모든 제어면에 적용됐는가 | 일부 서버만 적용한 상태가 아님 |
| issuer·client ID가 1번 출력과 같은가 | 각각 Keycloak realm URL·Headlamp client ID와 일치 |
| 그룹 claim·prefix가 맞는가 | `groups`와 `headlamp:`. 슬래시는 토큰의 그룹 경로에 포함됨 |
| 사내 CA 파일 또는 인증 설정의 CA 내용이 유효한가 | 모든 API server에서 discovery·JWKS의 HTTPS 검증 가능 |
| 기존 관리자 접속이 정상인가 | `/readyz`는 `ok`, 노드 목록 조회 성공 |

**완료 기준:** 모든 API server에 같은 인증 계약이 적용됐고 기존 관리자 접속이 정상입니다.
다음 [배포·검증](03-deploy.md)에서 실제 브라우저 로그인과 그룹별 권한을 확인합니다.

공식 참고: [Kubernetes OIDC](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#openid-connect-tokens),
[kubeadm 제어면 구성](https://kubernetes.io/docs/reference/setup-tools/kubeadm/implementation-details/).
