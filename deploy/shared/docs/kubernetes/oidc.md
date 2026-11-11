# API server OIDC 인증

[가이드 홈](../README.md#클러스터) · [CP1~3 셋업](control-plane.md) · [Headlamp 인증](../../../headlamp/docs/02-authentication.md)

**목적:** Kubernetes API server가 Keycloak이 발급한 OIDC 토큰을 신뢰하도록 모든 제어면에 issuer·client ID·claim 매핑·CA를 반영합니다.
Keycloak은 사용자를 인증하고 API server는 그 토큰을 신뢰할지 판단합니다. 이 설정이 없으면 OIDC 로그인 후에도 자원 조회가 실패합니다.

**준비물:**

- 앱이 정한 인증 계약: issuer, audience(client ID), username·groups claim과 prefix, 서명 알고리즘. 현재 사용 앱인 Headlamp의 계약은 [Headlamp 인증](../../../headlamp/docs/02-authentication.md)에 있습니다.
- 운영 issuer: [서비스 원본](../infrastructure/services.md)의 업무 realm OIDC issuer.
- 사내 CA 묶음 PEM 한 파일: [Headlamp TLS 준비](../../../headlamp/docs/01-prepare.md)에서 `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem`으로 생성합니다. PFX·사이트 개인키는 전달하지 않습니다.
- 각 제어면의 SSH/sudo 권한. 작업은 제어면 담당자가 수행하며, 위임할 때는 위 계약과 CA 묶음을 전달합니다.

**실행 위치:** `kubectl` 조회는 CP1 터미널, `/etc/kubernetes` 파일 편집과 `sudo` 명령은 설정할 각 제어면의 SSH 터미널입니다.

SSO 주소를 바꿀 때는 앱 env와 모든 API server의 issuer·CA를 함께 맞춥니다. 다른 인증 공급자 설정은 보존합니다.

| 현재 상황 | 진행 방법 |
| --- | --- |
| kubeadm이고 OIDC 설정이 없음 | 1 → 2 → 3 → 6 |
| 같은 계약의 OIDC 설정이 이미 있음 | 1에서 값 대조. 같으면 중복 추가 없이 파일·마운트·접근을 확인 |
| `--authentication-config` 사용 중 | 1 → 2 → 5 → 6 |
| 다른 앱의 `--oidc-*` 설정이 있음 | 기존 설정을 덮어쓰지 않고 인증 통합을 담당자와 조정 |
| 관리형 클러스터·k3s·RKE2 등 다른 설치 방식 | 담당자에게 계약 전달. 해당 설치 방식의 설정 경로 사용 |

설치 방식을 모르면 먼저 클러스터 담당자에게 확인합니다. kubeadm 파일 경로가 없다는 이유로 새 파일을 만들지 않습니다.

## 1. 계약과 기존 인증 확인

CP1에서 버전과 API server Pod를 조회합니다.

```bash
kubectl --context "$KUBE_CONTEXT" version
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -l component=kube-apiserver -o wide
```

kubeadm이면 **각 제어면**에서 현재 manifest와 인증 옵션을 확인합니다.

```bash
sudo test -f /etc/kubernetes/manifests/kube-apiserver.yaml
sudo grep -nE -- '--(oidc-|authentication-config)' /etc/kubernetes/manifests/kube-apiserver.yaml
```

**기대 결과:** 첫 명령은 출력 없이 성공합니다. 두 번째 명령의 출력이 없으면 해당 옵션이 없는 상태입니다.

**실패 확인:**

- 파일이 없거나 권한 오류가 나면 설치 방식·접속 서버를 확인합니다.
- 옵션이 있으면 위 분기표에 따라 진행하고 전체 파일과 설치 도구의 원본 설정도 확인합니다.
- 기존 `--oidc-*`가 다른 issuer/client에 연결돼 있으면 덮어쓰지 않습니다. 인증 통합이 끝날 때까지 앱 배포만으로 로그인이 완성된 것으로 보지 않습니다.
- 관리형 클러스터처럼 제어면을 직접 수정할 수 없으면 공급자의 OIDC 설정으로 같은 계약을 반영합니다.

## 2. 모든 제어면에 CA 파일 배치

각 제어면에서 **현재 접속한 서버에 복사해 둔 CA PEM 파일 경로**를 입력합니다. CP1의 환경변수나 파일은 다른 서버에 자동으로 전달되지 않습니다.

```bash
read -r -p '전달받은 Keycloak CA PEM 파일의 절대 경로: ' APISERVER_CA_SOURCE
sudo install -d -m 0755 /etc/kubernetes/oidc
sudo install -m 0644 "$APISERVER_CA_SOURCE" /etc/kubernetes/oidc/keycloak-ca-bundle.pem
openssl crl2pkcs7 -nocrl -certfile /etc/kubernetes/oidc/keycloak-ca-bundle.pem |
  openssl pkcs7 -print_certs -noout
```

**기대 결과:** 사내 CA 구성에서는 루트·중간 CA가 표시됩니다.
API server 컨테이너에도 이 파일이 보여야 하므로 3단계에서 마운트합니다. 앱 namespace의 ConfigMap 등록만으로는 부족합니다.
공인 CA를 사용하는 issuer라면 이 단계와 3단계의 CA 플래그·마운트를 생략합니다.

## 3. oidc 플래그 반영 — kubeadm static Pod

현재 issuer/client가 비어 있거나 계약과 같은 경우 사용합니다. 꺾쇠 괄호 예시 문자열을 그대로 넣지 않습니다.

```text
--oidc-issuer-url=<issuer>
--oidc-client-id=<audience / client ID>
--oidc-username-claim=<username claim>
--oidc-username-prefix=<username prefix>
--oidc-groups-claim=<groups claim>
--oidc-groups-prefix=<groups prefix>
--oidc-signing-algs=<서명 알고리즘>
--oidc-ca-file=/etc/kubernetes/oidc/keycloak-ca-bundle.pem
```

각 제어면에서 manifest를 kubelet이 읽는 manifests 폴더 **밖에** 백업한 뒤 편집합니다.

```bash
sudo install -d -m 0700 /etc/kubernetes/backup
sudo cp -p /etc/kubernetes/manifests/kube-apiserver.yaml \
  "/etc/kubernetes/backup/kube-apiserver.$(date +%Y%m%d%H%M%S).yaml"
sudo vi /etc/kubernetes/manifests/kube-apiserver.yaml
```

`kube-apiserver` 컨테이너의 기존 `command` 목록에 같은 들여쓰기로 플래그를 추가합니다. 아래는 Headlamp 계약 값을 넣은 **형식 예시**이며 issuer는 실제 값으로 바꿉니다.

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

- 전체 Pod 정의가 아닙니다. 기존 이미지·다른 command 옵션·인증서·네트워크 설정을 지우지 않습니다.
- 같은 키가 이미 있으면 중복 추가하지 않고 값을 대조합니다.
- 끝에 `:`가 있는 prefix 값은 작은따옴표로 감싸 YAML 문자열로 입력합니다.

CA 마운트를 컨테이너의 `volumeMounts`와 Pod의 `volumes`에 각각 합칩니다.
이미 `volumeMounts:`·`volumes:`가 있으면 **그 아래 목록에 `- name: keycloak-oidc-ca` 항목만 추가**하며, 같은 키를 두 번 만들거나 기존 manifest 전체를 덮어쓰지 않습니다.

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

설치 도구가 관리하는 원본 설정에도 같은 플래그와 마운트를 기록해 재생성·업그레이드 후에도 유지되게 합니다.

## 4. 한 대씩 재시작·복구 — 각 제어면

저장하면 kubelet이 API server를 재시작합니다. 제어면이 한 대라면 잠시 API 요청이 중단됩니다.
여러 대라면 한 대씩 적용하고, 각 서버가 다시 기동된 뒤 바로 6단계 검증을 수행한 다음 서버로 이동합니다.

**복구:** 재기동 후에도 복구되지 않으면 작업을 멈추고, 해당 서버의 SSH 터미널에서 3단계 백업으로 manifest를 되돌립니다.
API가 응답하지 않는 동안에는 kubectl을 사용할 수 없습니다. 이후 YAML 들여쓰기·중복 옵션·CA 마운트 경로를 확인합니다.

```bash
sudo ls -l /etc/kubernetes/backup/
read -r -p '복원할 백업 파일 절대 경로: ' APISERVER_BACKUP
sudo cp -p "$APISERVER_BACKUP" /etc/kubernetes/manifests/kube-apiserver.yaml
```

## 5. AuthenticationConfiguration 방식인 경우

기존 인증 파일에 issuer·audience·CA와 claim 매핑을 반영합니다. 지원 API 버전은 실행 중인 Kubernetes 버전에 맞춥니다.
기존 issuer 항목을 보존하고, 같은 issuer가 이미 있으면 그 항목의 audience·매핑과 다른 앱 영향을 먼저 조정합니다.

```yaml
# 기존 jwt 항목 안에 합칠 매핑의 형식 예시(Headlamp 계약). 전체 인증 파일이 아닙니다.
claimMappings:
  username:
    claim: sub
    prefix: 'headlamp:'
  groups:
    claim: groups
    prefix: 'headlamp:'
```

- `issuer.url`은 공개 issuer, `issuer.audiences`에는 앱의 client ID를 사용합니다.
- 사내 CA는 `issuer.certificateAuthority`에 PEM **내용**을 넣습니다. 파일 경로 필드가 아닙니다.
- 인증 파일과 CA 내용은 모든 API server에 적용하며, 4단계와 같이 한 대씩 재시작·검증합니다.
- 세부 스키마는 [공식 인증 설정](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#authentication-configuration-from-a-file)을 따릅니다.

## 6. 완료 확인 — CP1·각 제어면

각 제어면이 다시 기동된 뒤 관리자 kubeconfig로 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" get --raw=/readyz
kubectl --context "$KUBE_CONTEXT" get nodes
```

**기대 결과:** `readyz`가 `ok`이고 노드 목록이 조회됩니다. 이 결과만으로 OIDC 인증 성공이 검증되지는 않습니다.
LB 뒤의 한 서버만 정상일 수 있으므로 담당자는 각 API server의 상태·적용값을 개별 확인합니다.

| 확인 항목 | 기대 결과 |
| --- | --- |
| 적용 범위 | 모든 제어면에 적용. 일부 서버만 적용한 상태가 아님 |
| issuer·client ID | 앱 계약의 realm URL·client ID와 일치 |
| claim·prefix | 앱 계약과 일치. 그룹 경로의 슬래시는 토큰 값에 포함됨 |
| CA | 모든 API server에서 Keycloak discovery·JWKS의 DNS·HTTPS 검증 가능 |
| 기존 관리자 접속 | `/readyz`는 `ok`, 노드 목록 조회 성공 |

**완료 기준:** 모든 API server에 같은 인증 계약이 적용됐고 기존 관리자 접속이 정상입니다.

## 다음 단계

앱 문서에서 실제 브라우저 로그인과 그룹별 권한을 확인합니다. Headlamp는 [배포와 검증](../../../headlamp/docs/03-deploy.md)입니다.
CA를 교체하면 이 문서의 2~6단계와 앱 쪽 CA 설정을 함께 갱신합니다.

공식 참고: [Kubernetes OIDC](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#openid-connect-tokens),
[kubeadm 제어면 구성](https://kubernetes.io/docs/reference/setup-tools/kubeadm/implementation-details/).
