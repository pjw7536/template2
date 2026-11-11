# Headlamp 운영 참고

[앱 안내](../README.md) · 이전: [배포와 로그인 검증](03-deploy.md)

**목적:** 설치 후 설정 갱신·장애 확인·재시작·복구·재설치를 수행합니다. 처음 설치한다면 [앱 안내](../README.md)의 순서를 따릅니다.
**실행 위치:** CP1 저장소 루트. 새 터미널이면 [실행 입력](01-prepare.md#2-대상-context와-실행-입력)을 다시 준비합니다.

## 변경 종류별 반영

| 변경 | 실행할 절차 |
| --- | --- |
| env·chart·이미지 설정 | [배포](03-deploy.md)의 검사·적용·로그인 검증 |
| 사이트 TLS 인증서 | [공용 TLS 등록](../../shared/docs/certificates/apply.md#2-공용-tls-secret-등록갱신--cp1) 후 [실제 HTTPS 확인](03-deploy.md#2-실제-https-확인) |
| client secret | [Secret 등록](02-authentication.md#5-cp1에서-client-secret-등록) 후 [재시작](#재시작과-복구) |
| Keycloak CA | [TLS·CA 준비](01-prepare.md#tlsca-준비)의 CA 재등록·연결 검사, [API server](02-authentication.md#api-server-인증)의 모든 제어면 신뢰 갱신 후 [재시작](#재시작과-복구) |
| 관리자 추가·제거 | [그룹 가입](02-authentication.md#3-사용할-사람을-그룹에-넣기) 변경 후 새 토큰으로 [권한 확인](03-deploy.md#3-kubernetes-rbac-확인) |
| CPU·메모리 수치 없음 | [metrics-server 설치](../../shared/docs/kubernetes/control-plane.md#metrics-server-설치) 후 Headlamp 새로고침 |

## 장애 확인

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp get pods,svc,ingress
kubectl --context "$KUBE_CONTEXT" -n headlamp describe deployment headlamp
kubectl --context "$KUBE_CONTEXT" -n headlamp get events --sort-by=.lastTimestamp
kubectl --context "$KUBE_CONTEXT" -n headlamp logs deployment/headlamp --tail=100
```

| 보이는 문제 | 먼저 확인할 내용 |
| --- | --- |
| `invalid redirect URI` | Keycloak headlamp client에 `HEADLAMP_CALLBACK_URL` 값이 등록됐는지 |
| 사내 로그인 자체가 실패함 | Keycloak Account Console의 `oidc` 로그인. Headlamp client secret과 사내 IdP secret은 서로 다름 |
| `invalid_client` / token 교환 실패 | Client authentication On, Credentials와 `HEADLAMP_OIDC_SECRET` Secret 값 일치, PKCE S256 |
| `x509` 또는 인증서 오류 | [TLS·CA](01-prepare.md#tlsca-준비)와 [API server](02-authentication.md#api-server-인증)의 CA 신뢰 |
| 로그인 후 `401` | API server OIDC 설정이 모든 API server에 반영됐는지 담당자에게 확인 |
| 허용한 사람도 `403` | 그룹 이름·사용자 가입 여부와 [권한 검사](03-deploy.md#3-kubernetes-rbac-확인) |
| 그룹 밖 사람도 데이터가 보임 | 다른 Kubernetes 권한이 추가로 부여됐는지 담당자에게 확인 |
| `ImagePullBackOff` | registry 주소·노드 CA 신뢰·이미지 반입·`IMAGE_PULL_SECRET` |
| HTTPS 404 | Ingress host/path·Traefik 감시 namespace. StripPrefix를 추가하지 않음 |
| HTTPS 503 | Service Endpoint·Pod readiness·이벤트 |
| PC에서만 인증서 오류 | 브라우저의 CA 신뢰·DNS·프록시. [Keycloak 클라이언트 신뢰](../../keycloak/docs/01-prepare.md#tlsca-준비) |
| 로그인 중 `invalid request` | 배포·재시작으로 로그인 state가 사라졌는지 확인 후 처음부터 재로그인 |

기본 replica는 1입니다. 로그인 state·갱신 토큰이 프로세스 내에 있으므로 임의로 다중 replica로 확장하지 않습니다.

## 재시작과 복구

client secret이나 CA를 갱신한 뒤에는 Deployment를 재시작해야 새 값이 적용됩니다. 일반 설정이 같으면 `headlamp-up`만으로 Pod가 재생성되지 않을 수 있습니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp rollout restart deployment/headlamp
kubectl --context "$KUBE_CONTEXT" -n headlamp rollout status deployment/headlamp --timeout=180s
```

**기대 결과:** `successfully rolled out`. 이후 사내 로그인과 관리자·비관리자 권한을 다시 확인합니다.

복구는 관리자 kubeconfig로 env·Helm revision·외부 Secret·API server 원본을 확인한 뒤 해당 구성으로 되돌립니다.
`helm rollback`은 Keycloak·제어면·외부 Secret을 되돌리지 않으며, 이전 revision의 RBAC가 다시 적용될 수 있으므로 복구 후 권한을 확인합니다.

```bash
helm --kube-context "$KUBE_CONTEXT" -n headlamp history headlamp
```

복원 후 [배포와 로그인 검증](03-deploy.md)을 다시 수행합니다.

## 초기화 후 재설치

namespace나 Keycloak client를 삭제한 뒤 다시 설치할 때 다음 상태에서 [서버 준비](01-prepare.md#서버실행-입력)부터 진행합니다.

- Keycloak의 `etch` realm·사내 IdP `oidc`·기존 사용자는 유지되고 Account Console 사내 로그인이 됩니다.
- `headlamp` namespace가 없으면 다시 만들고 이미지 인증·OIDC Secret과 CA ConfigMap을 다시 등록합니다. 사이트 인증서는 공용 Traefik에 유지됩니다.
- Headlamp client·관리자 그룹이 없으면 [Keycloak 설정](02-authentication.md#keycloak-client와-관리자)에서 새로 만들고, 있으면 값을 대조합니다. 새 client는 새 secret을 사용합니다.
- API server의 OIDC 설정은 남아 있을 수 있으므로 [API server 인증](02-authentication.md#api-server-인증)의 계약과 대조하고 중복 추가하지 않습니다.
- 인증서 원본·개인키·CA 파일은 CP1에 준비되어 있어야 합니다.

## 기존 조회 그룹에서 전환

`headlamp-viewers` 조회 그룹을 쓰던 설치에만 적용합니다.
`headlamp-admins`를 새 최상위 그룹으로 만들고 전체 관리 권한이 필요한 사람만 가입시킵니다. 기존 `headlamp-viewers`의 이름을 바꾸면 조회 사용자 전원이 관리자가 되므로 새 그룹을 별도로 만듭니다.

`make headlamp-up`은 `server-headlamp-admin` 바인딩을 만들고 Helm이 관리하던 `server-headlamp-viewer` 바인딩과 `server-headlamp-discovery` 역할·바인딩을 제거합니다.
새 바인딩 이름을 사용하므로 변경 불가능한 기존 `roleRef`를 수정하지 않습니다.
관리자 재로그인과 [권한 검사](03-deploy.md#3-kubernetes-rbac-확인)를 통과한 뒤 Keycloak의 `headlamp-viewers` 그룹을 삭제하고, Helm 외부에서 만든 바인딩은 별도로 확인·정리합니다.
