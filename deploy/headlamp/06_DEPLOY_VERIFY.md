# 06. 배포와 로그인 검증

[전체 순서](README.md) · 이전: [05 API server](05_APISERVER_SETUP.md) · 설치 후: [운영 참고](operations/README.md)

01~05의 완료 기준을 모두 만족한 뒤 실행합니다. 같은 Bash 터미널을 사용합니다.
새 터미널이면 [01 실행 입력](01_SERVER_SETUP.md#2-대상-context와-실행-입력)을 다시 준비합니다.
기존 조회 전용 설치를 전환한다면 먼저 [전환 안내](operations/README.md#기존-조회-그룹에서-전환)를 확인합니다.

## 1. 검사와 적용

```bash
make headlamp-check
```

통과하면 적용합니다.

```bash
make headlamp-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

`headlamp-up`은 OIDC Secret의 필수 키·선택 CA·TLS Secret·기존 Traefik을 확인한 뒤
Helm release `headlamp`를 namespace `headlamp`에 설치하고 준비 상태를 기다립니다.
기존 Traefik의 감시 namespace·배치를 보존하면서 Headlamp 접근을 연결합니다.
Helm 성공 후 Traefik 단계만 실패했다면 원인을 해결하고 같은 명령을 다시 실행합니다.

```bash
make headlamp-ui KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n headlamp get deployment,pods,svc,ingress
```

Deployment가 Ready이고 HTTPS 주소가 출력돼야 합니다.
Ingress 경로는 `/headlamp`이며 StripPrefix를 적용하지 않습니다.

## 2. 실제 HTTPS 확인

현재 사내 CA 구성에서는 다음으로 실제 서버 체인·도메인·로컬 인증서와의 일치를 확인합니다.

```bash
(
  set -euo pipefail
  work=$(mktemp -d)
  trap 'rm -rf "$work"' EXIT
  if ! openssl x509 -inform PEM -in "$HEADLAMP_CA_DIR/SECDS-T2RootCA.crt" \
    -out "$work/root.pem" 2>/dev/null; then
    openssl x509 -inform DER -in "$HEADLAMP_CA_DIR/SECDS-T2RootCA.crt" -out "$work/root.pem"
  fi
  openssl s_client -connect "$HEADLAMP_HOST:443" -servername "$HEADLAMP_HOST" \
    -verify_hostname "$HEADLAMP_HOST" -verify_return_error -CAfile "$work/root.pem" \
    -showcerts </dev/null > "$work/live.pem"
  openssl x509 -in "$HEADLAMP_CERT_DIR/fullchain.crt" -noout -fingerprint -sha256 > "$work/expected"
  openssl x509 -in "$work/live.pem" -noout -fingerprint -sha256 > "$work/actual"
  cmp "$work/expected" "$work/actual"
  curl --fail --silent --show-error --cacert "$work/root.pem" "https://$HEADLAMP_HOST/headlamp/" -o /dev/null
  echo '실제 HTTPS 인증서·Headlamp 응답 확인 완료'
)
```

오류가 나면 DNS·Traefik·TLS Secret·fullchain을 확인합니다. 브라우저 PC에도 루트 CA 신뢰가 필요합니다.
공인/다른 CA 사이트는 03에서 준비한 해당 신뢰 체인으로 검증합니다.

## 3. Kubernetes RBAC 확인

관리자 kubeconfig로 실행합니다. 아래 명령은 사용자 인증을 흉내 낸 **권한 검사**이며 실제 OIDC 검사는 아닙니다.

```bash
kubectl --context "$KUBE_CONTEXT" auth can-i list nodes \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-admins --as-group=system:authenticated
# 기대: yes
kubectl --context "$KUBE_CONTEXT" auth can-i create deployments --all-namespaces \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-admins --as-group=system:authenticated
# 기대: yes
kubectl --context "$KUBE_CONTEXT" auth can-i get secrets --all-namespaces \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-admins --as-group=system:authenticated
# 기대: yes
kubectl --context "$KUBE_CONTEXT" auth can-i '*' '*' --all-namespaces \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-admins --as-group=system:authenticated
# 기대: yes
kubectl --context "$KUBE_CONTEXT" auth can-i list nodes \
  --as=headlamp:old-viewer --as-group=headlamp:/headlamp-viewers --as-group=system:authenticated
# 기대: no
kubectl --context "$KUBE_CONTEXT" auth can-i list nodes \
  --as=headlamp:rbac-outsider --as-group=system:authenticated
# 기대: no
```

Kubernetes 권한은 합산됩니다. 다른 RBAC 바인딩도 확인합니다.
기존 Helm release 밖에서 만든 `headlamp-viewer` 관련 리소스가 있다면 소유권과 권한을 별도로 점검합니다.
그룹 탈퇴는 기존 ID token이 만료될 때까지 즉시 반영되지 않을 수 있습니다.
토큰 갱신 후 로그인 유지·권한 반영도 확인합니다.

## 4. 실제 사용자 로그인

1. 출력된 Headlamp HTTPS 주소에서 **Sign in**을 누릅니다.
2. `etch` realm의 사내 `oidc` provider를 선택합니다. 기존 사내 SSO 세션이 있으면 인증 화면이 생략될 수 있습니다.
3. `headlamp-admins` 가입 계정으로 노드·Pod·로그가 조회되는지 확인합니다.
4. 새로고침·재접속과 토큰 갱신 뒤에도 로그인과 접근이 유지되는지 확인합니다.
5. 시크릿 창에서 그룹 밖의 시험 계정으로 로그인하고 노드·Pod 등 자원 접근이 거부되는지 확인합니다.

그룹 밖 계정도 사내 로그인 자체는 성공할 수 있습니다. 다른 RBAC를 받지 않은 계정의 자원 접근은 거부돼야 합니다.
허용한 계정이 403이면 그룹 가입·mapper·prefix를, 401이면 API server의 issuer·audience·CA·토큰 만료를 확인합니다.
ID Token의 `iss`는 공개 realm URL, `aud`는 Headlamp client ID, `sub`는 Keycloak 사용자 ID,
`groups`는 `/headlamp-admins`를 포함하는 문자열 배열이어야 합니다. 토큰을 외부 사이트에 붙여 넣지 않습니다.

## 설치 완료 기준

| 확인 대상 | 통과 기준 |
| --- | --- |
| 배포 | Pod Ready, Ingress·Service 정상, image pull 오류 없음 |
| HTTPS | 사이트 인증서·체인·도메인 정상, 브라우저 경고 없음 |
| 인증 | 사내 계정으로 로그인·callback·재접속·갱신 성공 |
| 관리자 권한 | 관리자 그룹 RBAC 검사 yes, 실제 노드·Pod·로그 접근 성공 |
| 비관리자 권한 | 별도 권한 없는 그룹 밖 계정의 자원 접근 거부 |

여기까지 통과하면 최초 셋업 완료입니다. 정적 검사나 Pod Ready만으로 로그인 완료를 판정하지 않습니다.
문제가 있으면 [운영 참고](operations/README.md#장애-확인)의 증상별 절차를 따릅니다.
