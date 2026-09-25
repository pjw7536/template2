# Headlamp 운영 참고

최초 설치는 [시작 안내](../README.md)의 순서를 따릅니다.
이 문서는 설치 후 갱신·장애·기존 구성 전환·복구에 사용합니다.
새 터미널에서는 [실행 입력](../01_SERVER_SETUP.md#2-대상-context와-실행-입력)을 먼저 준비합니다.

## 변경 종류별 반영

| 변경 | 실행할 절차 |
| --- | --- |
| env·chart·이미지 설정 | [06 배포](../06_DEPLOY_VERIFY.md)의 검사·적용·로그인 검증 |
| 사이트 TLS 인증서 | [03 TLS](../03_TLS.md)의 사이트 검증·Secret 등록 후 실제 HTTPS 확인 |
| client secret | [04 Keycloak](../04_KEYCLOAK_SETUP.md)의 Secret 등록 후 아래 재시작 |
| Keycloak CA | [03 TLS](../03_TLS.md)의 CA 재등록 및 연결 검사, [05 API server](../05_APISERVER_SETUP.md)의 모든 제어면 신뢰 갱신 후 아래 재시작 |
| 관리자 추가·제거 | [04 Keycloak](../04_KEYCLOAK_SETUP.md)의 그룹 가입 변경 후 새 토큰으로 [06 권한 확인](../06_DEPLOY_VERIFY.md) |

## 장애 확인

| 보이는 문제 | 먼저 확인할 내용 |
| --- | --- |
| `invalid redirect URI` | Keycloak의 headlamp client에 `HEADLAMP_CALLBACK_URL` 값이 등록됐는지 확인 |
| 사내 로그인 자체가 실패함 | 먼저 Keycloak Account Console의 `oidc` 로그인을 확인. Headlamp client secret과 사내 IdP secret은 서로 다름 |
| `invalid_client` / token 교환 실패 | Client authentication On, Credentials와 `HEADLAMP_OIDC_SECRET`의 값 일치, PKCE S256 설정 확인 |
| `x509` 또는 인증서 오류 | [03 TLS](../03_TLS.md)와 [05 API server](../05_APISERVER_SETUP.md)의 CA 신뢰 설정 확인 |
| 로그인 후 `401` | API server OIDC 설정이 모든 API server에 반영됐는지 담당자에게 확인 |
| 허용한 사람도 `403` | 그룹 이름·사용자 가입 여부와 [06 권한 검사](../06_DEPLOY_VERIFY.md) 확인 |
| 그룹 밖 사람도 데이터가 보임 | 담당자에게 다른 Kubernetes 권한이 추가로 부여됐는지 확인 요청 |
| `ImagePullBackOff` | registry 주소·노드 CA 신뢰·이미지 반입·IMAGE_PULL_SECRET |
| HTTPS 404 | Ingress host/path·Traefik 감시 namespace. StripPrefix를 추가하지 않음 |
| HTTPS 503 | Service Endpoint·Pod readiness·이벤트 |
| PC에서만 인증서 오류 | 브라우저의 CA 신뢰·DNS·프록시. [Keycloak 클라이언트 신뢰](../../keycloak/03_TLS.md) 참고 |
| 로그인 중 `invalid request` | 배포·재시작으로 로그인 state가 사라졌는지 확인 후 처음부터 재로그인 |

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp get pods,svc,ingress
kubectl --context "$KUBE_CONTEXT" -n headlamp describe deployment headlamp
kubectl --context "$KUBE_CONTEXT" -n headlamp get events --sort-by=.lastTimestamp
kubectl --context "$KUBE_CONTEXT" -n headlamp logs deployment/headlamp --tail=100
```

CPU·메모리 수치가 없으면 metrics-server 설치 여부를 확인합니다.
기본 replica는 1입니다. 로그인 state·갱신 토큰이 프로세스 내에 있으므로 임의로 다중 replica로 확장하지 않습니다.

## 기존 조회 그룹에서 전환

`headlamp-admins`는 새 최상위 그룹으로 만들고 전체 관리할 사람만 가입시킵니다.
기존 `headlamp-viewers`를 이름 변경하면 모든 기존 조회 사용자가 관리자가 되므로 이름을 변경하지 않습니다.
`make headlamp-up`은 새 `server-headlamp-admin` 바인딩을 만들고 Helm이 관리하던
`server-headlamp-viewer` 바인딩과 `server-headlamp-discovery` 역할·바인딩을 제거합니다.
새 바인딩 이름을 사용하므로 변경 불가능한 기존 `roleRef`를 수정하지 않습니다.
관리자 재로그인과 [06 권한 검사](../06_DEPLOY_VERIFY.md)를 통과한 뒤 Keycloak의 기존 `headlamp-viewers` 그룹을 삭제합니다.
Helm 외부에서 만든 기존 바인딩은 별도로 확인·정리합니다.

## 재시작과 복구

client secret이나 CA를 갱신한 뒤에는 Headlamp Deployment를 재시작해야 새 값이 적용됩니다.
일반 설정이 같으면 `headlamp-up`만으로 Pod가 재생성되지 않을 수 있습니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp rollout restart deployment/headlamp
kubectl --context "$KUBE_CONTEXT" -n headlamp rollout status deployment/headlamp --timeout=180s
```

재시작 후 사내 로그인과 관리자·비관리자 권한을 다시 확인합니다.
복구는 관리자 kubeconfig로 이전 env·Helm revision·제어면 설정을 복원합니다.
`helm rollback`만으로 Keycloak·제어면·외부 Secret은 복구되지 않습니다.
이전 revision이 공용 토큰 계정을 다시 만들 수 있으므로 복구 후 권한을 확인합니다.

Helm revision은 다음 읽기 명령으로 확인합니다.

```bash
helm --kube-context "$KUBE_CONTEXT" -n headlamp history headlamp
```

복구할 revision·env·외부 Secret·API server 원본을 먼저 확인한 뒤 해당 구성으로 복원합니다.
복원 후 [06 검증](../06_DEPLOY_VERIFY.md)을 다시 수행합니다.
