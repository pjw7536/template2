# Headlamp 운영 참고

[Headlamp 가이드](../README.md)

설치·업데이트 절차는 [Headlamp 가이드](../README.md)에 있습니다. 이 문서는 설치 후의 변경 반영·장애 확인·재시작·복구·재설치입니다.

- [변경 종류별 반영](#변경-종류별-반영)
- [장애 확인](#장애-확인)
- [재시작과 복구](#재시작과-복구)
- [초기화 후 재설치](#초기화-후-재설치)

## 변경 종류별 반영

env·chart·이미지, 관리자 추가, client secret·CA 갱신, 사이트 인증서는 [가이드 B](../README.md#b-업데이트)의 표를 따릅니다. 그 밖의 변경입니다.

| 변경 | 실행할 절차 |
| --- | --- |
| 사이트 TLS 인증서 갱신 후 확인 | [조회] [실제 HTTPS 확인](03-deploy.md#실제-https-확인) |
| Keycloak CA | [승인] 모든 제어면의 API server가 한 대씩 다시 시작됩니다. 순서: [TLS·CA 준비](01-prepare.md#tlsca-준비)의 CA 파일 교체와 `make ca-bundle` → [가이드 C](../README.md#c-배포-후-확인)의 OIDC 연결 검사 → [API server 인증](02-authentication.md#api-server-인증)으로 모든 제어면의 CA 갱신 → 가이드 B의 `client secret·CA 갱신`과 재시작 |
| 관리자 제거 | [변경] [그룹에서 빼기](02-authentication.md#3-사용할-사람을-그룹에-넣기). 새 토큰으로 [권한 확인](03-deploy.md#kubernetes-rbac-확인) |
| CPU·메모리 수치 없음 | [변경] [metrics-server 설치](../../shared/docs/kubernetes/control-plane.md#metrics-server-설치) 후 Headlamp 새로고침 |

## 장애 확인

[조회] Pod·이벤트·로그를 봅니다. 한 번에 모으려면 [장애 조회](../../README.md#장애-조회)의 `make ops-diagnose APP=headlamp KUBE_CONTEXT="<context>"`를 씁니다.

```bash
kubectl --context "<context>" -n headlamp get pods,svc,ingress
kubectl --context "<context>" -n headlamp describe deployment headlamp
kubectl --context "<context>" -n headlamp get events --sort-by=.lastTimestamp
kubectl --context "<context>" -n headlamp logs deployment/headlamp --tail=100
```

| 보이는 문제 | 먼저 확인할 내용 |
| --- | --- |
| `invalid redirect URI` | Keycloak headlamp client에 `HEADLAMP_CALLBACK_URL` 값이 등록됐는지 |
| 사내 로그인 자체가 실패함 | Keycloak Account Console의 `oidc` 로그인. Headlamp client secret과 사내 IdP secret은 서로 다름 |
| `invalid_client` / token 교환 실패 | Client authentication On, Credentials와 `HEADLAMP_OIDC_SECRET` Secret 값 일치, PKCE S256 |
| `x509` 또는 인증서 오류 | [TLS·CA](01-prepare.md#tlsca-준비)와 [API server](02-authentication.md#api-server-인증)의 CA 신뢰 |
| 로그인 후 `401` | API server OIDC 설정이 모든 제어면에 반영됐는지 [가이드 사전 준비](../README.md#사전-준비)의 완료 확인 명령으로 조회. 빠진 제어면이 있으면 [가이드 A](../README.md#a-최초-설치) 2단계 |
| 허용한 사람도 `403` | 그룹 이름·사용자 가입 여부와 [권한 검사](03-deploy.md#kubernetes-rbac-확인) |
| 그룹 밖 사람도 데이터가 보임 | `kubectl --context "<context>" get clusterrolebindings,rolebindings -A -o wide`로 `headlamp:` 접두사 그룹·사용자와 `system:authenticated`에 연결된 다른 바인딩을 조회해 보고. 바인딩을 지우지 않음 |
| `ImagePullBackOff` | registry 주소·노드 CA 신뢰·이미지 반입·`IMAGE_PULL_SECRET` |
| HTTPS 404 | Ingress host/path·Traefik 감시 namespace. StripPrefix를 추가하지 않음 |
| HTTPS 503 | Service Endpoint·Pod readiness·이벤트 |
| PC에서만 인증서 오류 | 브라우저의 CA 신뢰·DNS·프록시. [클라이언트 PC 신뢰 등록](../../shared/docs/certificates/apply.md#클라이언트-pc-신뢰-등록) |
| 로그인 중 `invalid request` | 배포·재시작으로 로그인 state가 사라졌는지 확인 후 처음부터 재로그인 |

기본 replica는 1입니다. 로그인 state·갱신 토큰이 프로세스 내에 있으므로 임의로 다중 replica로 확장하지 않습니다.

## 재시작과 복구

client secret이나 CA를 갱신한 뒤에는 Deployment를 재시작해야 새 값이 적용됩니다. 일반 설정이 같으면 `headlamp-up`만으로 Pod가 재생성되지 않을 수 있습니다.
재시작 명령은 [가이드 B](../README.md#b-업데이트)의 재시작 블록입니다. 성공하면 `successfully rolled out`이 나오며, 이후 사내 로그인과 관리자·비관리자 권한을 다시 확인합니다.

복구는 관리자 kubeconfig로 env·Helm revision·외부 Secret·API server 원본을 확인한 뒤 해당 구성으로 되돌립니다.

[조회] Helm revision:

```bash
helm --kube-context "<context>" -n headlamp history headlamp
```

성공: revision 목록이 나오고 마지막 줄의 STATUS가 `deployed`입니다.

[승인] Helm 롤백. 이전 revision으로 되돌리면서 Pod가 다시 만들어지면 진행 중인 로그인 세션이 끊깁니다. 대상 revision, 현재 revision과의 RBAC 차이, 영향을 보여 주고 승인받은 뒤 실행합니다. Helm은 release의 리소스만 되돌리므로 Keycloak client·그룹, API server 설정, OIDC Secret·CA ConfigMap은 바뀌지 않습니다.

```bash
helm --kube-context "<context>" -n headlamp rollback headlamp <revision>
kubectl --context "<context>" -n headlamp rollout status deployment/headlamp --timeout=180s
```

성공: `deployment "headlamp" successfully rolled out`. 이어서 [가이드 C](../README.md#c-배포-후-확인)와 [로그인 검증](03-deploy.md#실제-사용자-로그인)을 다시 수행합니다.
롤백한 뒤에는 클러스터가 현재 checkout과 다르므로 `make drift-check APP=headlamp KUBE_CONTEXT="<context>"`가 그 차이를 표시합니다. 표시된 차이를 보고에 남깁니다.

## 초기화 후 재설치

namespace나 Keycloak client를 삭제한 뒤 다시 설치할 때 다음 상태를 확인하고 [가이드 A](../README.md#a-최초-설치)부터 진행합니다.

- Keycloak의 `etch` realm·사내 IdP `oidc`·기존 사용자는 유지되고 Account Console 사내 로그인이 됩니다.
- `headlamp` namespace·OIDC Secret·CA ConfigMap이 없으면 `headlamp-oidc-setup`이 다시 만듭니다. `IMAGE_PULL_SECRET`을 쓰면 [이미지 인증 Secret](01-prepare.md#이미지-인증-secret)은 직접 다시 등록합니다. 사이트 인증서는 공용 Traefik에 유지됩니다.
- Headlamp client·관리자 그룹이 없으면 `headlamp-oidc-setup`이 새로 만들고, 있으면 바꾸지 않으므로 [기존 client 대조](02-authentication.md#2-기존-client-대조)를 수행합니다. 새 client는 새 secret을 사용합니다.
- API server의 OIDC 설정은 남아 있을 수 있으므로 [API server 인증](02-authentication.md#api-server-인증)의 계약과 대조하고 중복 추가하지 않습니다.
- 인증서 원본·개인키·CA 파일은 관리 호스트에 준비되어 있어야 합니다.
