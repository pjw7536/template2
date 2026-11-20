# Headlamp 배포 동작과 로그인 검증

[Headlamp 가이드](../README.md)

설치·업데이트 절차는 [Headlamp 가이드](../README.md)에 있습니다. 이 문서는 배포 도구가 하는 일과, 가이드의 C 이후에 사내 로그인과 실제 Kubernetes 자원 접근까지 확인하는 방법입니다.

- [배포 도구의 동작](#배포-도구의-동작)
- [실제 HTTPS 확인](#실제-https-확인)
- [Kubernetes RBAC 확인](#kubernetes-rbac-확인)
- [실제 사용자 로그인](#실제-사용자-로그인)
- [설치 완료 기준](#설치-완료-기준)

## 배포 도구의 동작

`make ops-deploy APP=headlamp`가 실행하는 단계입니다.

| 단계 | 하는 일 |
| --- | --- |
| `headlamp-oidc-setup` | Keycloak client·관리자 그룹과 `headlamp` namespace·client secret Secret·CA ConfigMap 준비. [상세](02-authentication.md#keycloak-client와-관리자) |
| `headlamp-check` | env·chart 해시·Helm 렌더 검사. 클러스터를 바꾸지 않음 |
| `headlamp-up` | 아래 설명 |
| `headlamp-smoke` | 워크로드 준비 상태와 공개 주소의 HTTPS 응답을 조회. 로그인·권한은 확인하지 않음 |

`headlamp-up`은 OIDC Secret의 필수 키·선택 CA·공용 TLS 인증서·기존 Traefik을 확인한 뒤 Helm release `headlamp`를 namespace `headlamp`에 설치하고 최대 5분 동안 준비를 기다립니다.
이후 기존 Traefik의 감시 namespace·배치를 보존하면서 `headlamp` namespace를 추가합니다. Ingress 경로는 `/`이며 StripPrefix를 적용하지 않습니다.
성공하면 `접속 주소: https://headlamp.etch.samsungds.net/`를 출력합니다.

[조회] 배포 상태와 접속 주소:

```bash
make headlamp-ui KUBE_CONTEXT="<context>"
kubectl --context "<context>" -n headlamp get deployment,pods,svc,ingress
```

성공: Deployment READY `1/1`, Pod `Running` READY `1/1`, Service `ClusterIP`. Service 내부 IP는 브라우저 접속 주소가 아닙니다.
단계별 실패의 조치는 [가이드의 문제 해결](../README.md#문제-해결과-멈춤-조건)에 있습니다.

## 실제 HTTPS 확인

[조회] 관리 호스트에서 Headlamp 응답을 확인합니다. 현재 사내 CA 구성에서는 Keycloak CA 묶음이 사이트 인증서와 같은 루트·중간 CA를 포함합니다.

```bash
curl --fail --silent --show-error --cacert deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem https://headlamp.etch.samsungds.net/ -o /dev/null && echo 'Headlamp HTTPS 응답 확인 완료'
```

성공: `Headlamp HTTPS 응답 확인 완료`.
`404`면 Ingress host/path와 Traefik 감시 namespace, `503`이면 Pod 준비 상태와 Service 연결, 인증서 오류면 DNS·Traefik·TLS Secret·fullchain을 확인합니다.
공인·다른 CA 사이트는 해당 신뢰 체인을 `--cacert`에 지정합니다. 관리 호스트에서 성공해도 PC 브라우저에 경고가 뜨면 PC의 CA 신뢰와 DNS를 확인합니다.

[사람] 제공 중인 인증서와 로컬 fullchain의 일치는 [실제 제공되는 인증서 확인](../../shared/docs/certificates/apply.md#3-실제-제공-인증서-확인--관리-호스트)으로 검사합니다. 그 문서의 입력은 공개 host `headlamp.etch.samsungds.net`, 사이트 폴더 `deploy/shared/certs/etch.samsungds.net`, CA 폴더 `deploy/shared/certs/ca`입니다.

## Kubernetes RBAC 확인

관리자 kubeconfig로 사용자 권한을 흉내 내는 **권한 검사**이며 실제 OIDC 검사는 아닙니다. 검사용 사용자는 Keycloak에 만들 필요가 없습니다.
`cannot impersonate`가 나오면 그룹 문제로 판정하지 말고 현재 kubeconfig가 관리자 권한인지 확인합니다.

[조회] 가이드 C의 두 검사에 더해 관리자 그룹의 전체 권한과 그룹 밖 사용자의 거부를 확인합니다.

```bash
kubectl --context "<context>" auth can-i list nodes \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-admins --as-group=system:authenticated
# 기대: yes
kubectl --context "<context>" auth can-i create deployments --all-namespaces \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-admins --as-group=system:authenticated
# 기대: yes
kubectl --context "<context>" auth can-i get secrets --all-namespaces \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-admins --as-group=system:authenticated
# 기대: yes
kubectl --context "<context>" auth can-i '*' '*' --all-namespaces \
  --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-admins --as-group=system:authenticated
# 기대: yes
kubectl --context "<context>" auth can-i list nodes \
  --as=headlamp:rbac-outsider --as-group=system:authenticated
# 기대: no
```

Kubernetes 권한은 합산되므로 `headlamp:` 접두사 그룹·사용자에 연결된 다른 RBAC 바인딩이 없는지도 확인합니다.

## 실제 사용자 로그인

PC 브라우저에서 확인합니다.

1. `https://headlamp.etch.samsungds.net/`에서 **Sign in**을 누르고 `etch` realm의 사내 `oidc` provider를 선택합니다. 기존 SSO 세션이 있으면 인증 화면이 생략될 수 있습니다.
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
