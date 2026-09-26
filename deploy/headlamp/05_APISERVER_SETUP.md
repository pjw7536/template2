# 05. Kubernetes API server의 Keycloak 인증

[전체 순서](README.md) · 이전: [04 Keycloak](04_KEYCLOAK_SETUP.md) · 다음: [06 배포·검증](06_DEPLOY_VERIFY.md)

**필수 단계입니다.** Headlamp client만 등록하면 Kubernetes 데이터를 볼 수 없습니다.
이 문서는 제어면 담당자가 실행합니다. 위임하는 경우 아래 계약과 03의 CA 묶음을 전달하고
모든 API server에 반영됐다는 확인을 받은 뒤 06으로 진행합니다.

**이 단계가 필요한 이유:** Keycloak은 사용자가 누구인지 확인하고, Kubernetes API server는 그 사용자가 제시한
Keycloak 토큰을 받아들일지 결정합니다. API server가 issuer와 client ID를 모르면 Headlamp 로그인 뒤 자원 조회가 실패합니다.

**실행 위치를 구분하세요.** `kubectl` 조회는 CP1에서 실행합니다. `/etc/kubernetes` 파일 변경과 `sudo` 명령은
**설정할 각 제어면 서버에 SSH 접속해서** 실행합니다. 아래 kubeadm 예시는 설치 방식이 kubeadm인 경우에만 적용합니다.

| 현재 상황 | 진행 방법 |
| --- | --- |
| kubeadm이고 OIDC 설정이 없음 | 1번 확인 → 2번 CA 배치 → 3번 플래그·마운트 → 5번 검증 |
| 초기화 전 Headlamp OIDC 설정이 남아 있음 | 1번 계약과 현재 설정을 대조. 값이 같으면 중복 추가 없이 파일·마운트·접근을 확인 |
| `--authentication-config` 사용 중 | 1번 확인 → 4번 기존 인증 파일에 반영 → 5번 검증 |
| 다른 앱의 `--oidc-*` 설정이 있음 | 기존 설정을 덮어쓰지 않고 인증 통합을 담당자와 조정 |
| 관리형 클러스터·k3s·RKE2 등 다른 설치 방식 | 담당자에게 1번 계약 전달. 해당 설치 방식의 설정 경로 사용 |

설치 방식을 모르면 먼저 클러스터 담당자에게 확인합니다. kubeadm 파일 경로가 없다는 이유로 새 파일을 만들지 않습니다.

## 1. 적용할 계약과 기존 인증 확인

01을 실행했던 CP1 터미널에서 이번 설치의 실제 값을 출력합니다. 이 공개값을 제어면 담당자에게 전달하거나 작업 메모에 둡니다.

```bash
printf 'issuer: %s\naudience / client ID: %s\nCP1의 CA 원본 파일: %s\n' \
  "$HEADLAMP_OIDC_ISSUER_URL" "$HEADLAMP_OIDC_CLIENT_ID" "$HEADLAMP_OIDC_CA_FILE"
```

issuer와 client ID가 비어 있으면 01의 실행 입력부터 다시 수행합니다.

| 항목 | 적용값 |
| --- | --- |
| issuer | 01의 `HEADLAMP_OIDC_ISSUER_URL` |
| audience / client ID | 01의 `HEADLAMP_OIDC_CLIENT_ID` |
| username claim / prefix | `sub` / `headlamp:` |
| groups claim / prefix | `groups` / `headlamp:` |
| 서명 알고리즘 | `RS256` |
| CA | 03의 `HEADLAMP_OIDC_CA_FILE`에 생성한 PEM 파일 |

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
담당자가 먼저 완료해야 하며, 그동안 06의 배포만으로 로그인이 완성된 것으로 보지 않습니다.

kubeadm이면 **각 제어면 서버의 터미널**에서 현재 파일 존재 여부와 인증 옵션을 확인할 수 있습니다.

```bash
sudo test -f /etc/kubernetes/manifests/kube-apiserver.yaml
sudo grep -nE -- '--(oidc-|authentication-config)' /etc/kubernetes/manifests/kube-apiserver.yaml
```

첫 명령은 파일이 있으면 출력 없이 성공합니다. 파일이 없거나 권한 오류가 나면 설치 방식·접속 서버를 확인합니다.
파일을 정상적으로 읽었는데 두 번째 명령의 출력이 없다면 해당 옵션이 없는 상태입니다.
옵션이 있다면 위 분기표에 따라 진행하며, 전체 파일과 설치 도구의 원본 설정도 함께 확인합니다.

## 2. 모든 제어면에 CA 파일 배치

03의 CA 묶음 **한 파일만** 각 제어면으로 전달합니다. PFX·사이트 개인키는 전달하지 않습니다.
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

## 3. oidc 플래그 방식에 반영

현재 issuer/client가 비어 있거나 위 계약과 같은 경우 사용합니다.
실제 값은 01의 설정에서 복사합니다. 꺾쇠 괄호를 포함한 예시 문자열을 그대로 넣지 않습니다.

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

### kubeadm static Pod인 경우

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

저장하면 kubelet이 API server를 재시작합니다. 단일 제어면은 잠시 API 요청이 중단됩니다.
다중 제어면은 한 대씩 적용하고 해당 서버의 재기동·정상 접속을 확인한 후 다음으로 이동합니다.
설치 도구가 관리하는 원본 설정에도 같은 플래그와 마운트를 기록해 재생성·업그레이드 시 유지합니다.

한 대를 저장한 뒤 바로 5번 확인을 수행하세요. 재기동 후에도 복구되지 않으면 다음 서버로 넘어가지 말고,
해당 서버에서 방금 만든 백업으로 manifest를 복원한 뒤 YAML 들여쓰기·중복 옵션·CA 마운트 경로를 점검합니다.
API가 응답하지 않는 동안에는 해당 서버의 SSH 터미널에서 복원해야 합니다.

## 4. AuthenticationConfiguration 방식인 경우

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

## 5. 완료 확인

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
다음 [06 배포·검증](06_DEPLOY_VERIFY.md)에서 실제 브라우저 로그인과 그룹별 권한을 확인합니다.

공식 참고: [Kubernetes OIDC](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#openid-connect-tokens),
[kubeadm 제어면 구성](https://kubernetes.io/docs/reference/setup-tools/kubeadm/implementation-details/).
