# 배포와 로그인 검증

[앱 안내](../README.md) · 이전: [API server 인증](02-authentication.md#api-server-인증) · 설치 후: [운영 참고](04-operations.md)

**목적:** Headlamp를 배포하고 Pod 기동뿐 아니라 사내 로그인과 실제 Kubernetes 자원 접근까지 확인합니다.
**준비물:** 아래 항목 완료. 빠진 항목이 있으면 해당 문서로 돌아갑니다. 기존 조회 전용 설치를 전환한다면 먼저 [전환 안내](04-operations.md#기존-조회-그룹에서-전환)를 확인합니다.

- [서버 준비](01-prepare.md#서버실행-입력): context·env·chart 검사, `headlamp` namespace와 필요한 이미지 인증 Secret
- [TLS 준비](01-prepare.md#tlsca-준비): 공용 Traefik 인증서와 필요한 Keycloak CA ConfigMap, OIDC 연결 검사
- [Keycloak 설정](02-authentication.md#keycloak-client와-관리자): client·S256·groups mapper·관리자 그룹 가입, client secret 등록
- [API server 인증](02-authentication.md#api-server-인증): 모든 API server 적용과 기존 관리자 접속

**실행 위치:** 1~3단계는 CP1 저장소 루트의 같은 Bash 터미널(새 터미널이면 [실행 입력](01-prepare.md#2-대상-context와-실행-입력)을 다시 실행), 4단계는 PC 브라우저입니다.

## 1. 검사와 적용

```bash
make headlamp-check
make headlamp-up KUBE_CONTEXT="$KUBE_CONTEXT"
make headlamp-ui KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n headlamp get deployment,pods,svc,ingress
```

`headlamp-up`은 OIDC Secret의 필수 키·선택 CA·공용 TLS 인증서·기존 Traefik을 확인한 뒤 Helm release `headlamp`를 namespace `headlamp`에 설치하고 최대 5분 동안 준비를 기다립니다.
이후 기존 Traefik의 감시 namespace·배치를 보존하면서 `headlamp` namespace를 추가합니다. Ingress 경로는 `/`이며 StripPrefix를 적용하지 않습니다.

**기대 결과:** `접속 주소: https://headlamp.etch.samsungds.net/`, Deployment READY `1/1`, Pod `Running` READY `1/1`, Service `ClusterIP`.
Service 내부 IP는 브라우저 접속 주소가 아닙니다.

| 실패한 지점 | 다음에 할 일 |
| --- | --- |
| OIDC Secret·CA·TLS 사전 검사 | TLS·Keycloak 단계의 등록 결과와 namespace·이름 확인 |
| `ImagePullBackOff` | [서버 준비](01-prepare.md#서버실행-입력)의 registry 경로·이미지 인증 Secret·노드의 registry CA 신뢰 |
| 대기 시간 초과·Pod 반복 재시작 | 아래 이벤트·로그 확인. 시간 초과를 성공으로 간주하지 않음 |
| Helm은 성공했으나 Traefik 연결 실패 | 표시된 권한·controller 오류 해결 후 같은 `make headlamp-up` 재실행 |

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp get events --sort-by=.lastTimestamp
kubectl --context "$KUBE_CONTEXT" -n headlamp logs deployment/headlamp --tail=100
```

## 2. 실제 HTTPS 확인

제공 중인 인증서와 로컬 fullchain의 일치는 [실제 제공되는 인증서 확인](../../shared/docs/certificates/apply.md#3-실제-제공-인증서-확인--cp1)으로 검사합니다.
그 문서의 입력은 이 터미널 변수로 지정합니다.

```bash
export TLS_HOST="$HEADLAMP_HOST" CERT_SITE_DIR="$HEADLAMP_CERT_DIR" CERT_CA_DIR="$HEADLAMP_CA_DIR"
```

이어서 Headlamp 응답을 확인합니다. 현재 사내 CA 구성에서는 Keycloak CA 묶음이 같은 루트·중간 CA를 포함합니다.

```bash
curl --fail --silent --show-error --cacert "$HEADLAMP_OIDC_CA_FILE" "https://$HEADLAMP_HOST/" -o /dev/null && echo 'Headlamp HTTPS 응답 확인 완료'
```

**기대 결과:** 공통 검사의 완료 메시지와 `Headlamp HTTPS 응답 확인 완료`.
**실패 확인:** `404`면 Ingress host/path와 Traefik 감시 namespace, `503`이면 Pod 준비 상태와 Service 연결, 인증서 오류면 DNS·Traefik·TLS Secret·fullchain을 확인합니다.
공인·다른 CA 사이트는 해당 신뢰 체인을 `--cacert`에 지정합니다. CP1에서 성공해도 PC 브라우저에 경고가 뜨면 PC의 CA 신뢰와 DNS를 확인합니다.

## 3. Kubernetes RBAC 확인

관리자 kubeconfig로 사용자 권한을 흉내 내는 **권한 검사**이며 실제 OIDC 검사는 아닙니다. 검사용 사용자는 Keycloak에 만들 필요가 없습니다.
`cannot impersonate`가 나오면 그룹 문제로 판정하지 말고 현재 kubeconfig가 관리자 권한인지 확인합니다.

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

Kubernetes 권한은 합산되므로 다른 RBAC 바인딩도 확인합니다. Helm release 밖에서 만든 `headlamp-viewer` 관련 리소스가 있다면 소유권과 권한을 별도로 점검합니다.

## 4. 실제 사용자 로그인

1. 출력된 HTTPS 주소에서 **Sign in**을 누르고 `etch` realm의 사내 `oidc` provider를 선택합니다. 기존 SSO 세션이 있으면 인증 화면이 생략될 수 있습니다.
2. `headlamp-admins` 가입 계정으로 클러스터를 선택하고 노드 목록, namespace별 Pod 목록, 실행 중인 Pod의 Logs가 조회되는지 확인합니다. 자원을 삭제할 필요는 없습니다.
3. 새로고침·재접속과 ID Token 유효기간이 지난 뒤에도 로그인과 조회가 유지되는지 확인합니다.
4. 시크릿 창에서 그룹 밖 시험 계정으로 로그인하고 노드·Pod 접근이 거부되는지 확인합니다. 사내 로그인 자체는 성공할 수 있습니다.

그룹 변경은 기존 ID Token이 만료되거나 새로 로그인할 때 반영됩니다.
허용한 계정이 403이면 그룹 가입·mapper·prefix를, 401이면 API server의 issuer·audience·CA·토큰 만료를 확인합니다.
ID Token의 `iss`는 공개 realm URL, `aud`는 Headlamp client ID, `sub`는 Keycloak 사용자 ID, `groups`는 `/headlamp-admins`를 포함한 문자열 배열이어야 합니다. 토큰을 외부 사이트에 붙여 넣지 않습니다.

## 설치 완료 기준

| 확인 대상 | 통과 기준 |
| --- | --- |
| 배포 | Pod Ready, Ingress·Service 정상, image pull 오류 없음 |
| HTTPS | 사이트 인증서·체인·도메인 정상, 브라우저 경고 없음 |
| 인증 | 사내 계정으로 로그인·callback·재접속·갱신 성공 |
| 관리자 권한 | RBAC 검사 yes, 실제 노드·Pod·로그 접근 성공 |
| 비관리자 권한 | 별도 권한 없는 그룹 밖 계정의 자원 접근 거부 |

정적 검사나 Pod Ready만으로 로그인 완료를 판정하지 않습니다. 문제가 있으면 [장애 확인](04-operations.md#장애-확인)을 따릅니다.
