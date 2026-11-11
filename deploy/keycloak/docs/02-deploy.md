# Keycloak 서버 배포와 기동 확인

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

**목적:** PostgreSQL·Keycloak·공용 Traefik을 적용하고 기동을 확인합니다. 설정 Job은 실행하지 않습니다.

**준비물:** [서버 준비](01-prepare.md#서버-준비)의 Worker 디스크·env 검사·TLS 등록 완료.

**실행 위치:** 관리 호스트의 저장소 루트입니다. 새 터미널이라면 [실행 위치와 입력](01-prepare.md#실행-위치와-입력)의 `KEYCLOAK_KUBE_CONTEXT`를 다시 입력합니다.

## 1. 검사 후 서버 배포

검사가 실패하면 원인을 해결한 뒤 배포합니다.

```bash
make keycloak-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
make keycloak-up KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

| 명령 | 처리 범위 |
| --- | --- |
| `keycloak-check` | env·인증서·manifest·기존 Secret·PV/PVC·worker 상태를 조회하고 검사. 클러스터 변경 없음 |
| `keycloak-up` | 없는 runtime Secret 생성, 공용 TLS 확인, PostgreSQL·Keycloak·Traefik 적용 후 rollout 대기 |

최초 기동 시 관리자 계정을 만들고 이후 설정 Job도 같은 runtime Secret으로 로그인합니다.
`etch-sso` namespace가 없을 때만 원본의 label·annotation으로 생성하며, 이미 있으면 namespace 설정은 변경하지 않습니다.

| 선택 입력 | 사용하는 경우 |
| --- | --- |
| `KEYCLOAK_ENV=/절대/경로/prod.env` | 다른 env 파일 사용. 검사·배포 양쪽에 동일하게 전달 |
| `KEYCLOAK_CERTS=/인증서/폴더` | 해당 폴더의 PEM을 공용 TLS에 등록하는 선택적 호환 입력 |
| `VIP_BACKENDS=...` | VIP 최초 배치 지정. 검사·배포 양쪽에 동일하게 전달 |

VIP backend 값은 [네트워크 정보](../../shared/docs/infrastructure/network.md)에서 확인합니다.
공용 Ingress가 이미 운영 중이면 기존 감시 namespace·replica·Worker pool·affinity·VIP annotation을 유지합니다.
기록된 VIP와 배치가 다르면 검사에서 중단하며, 확인한 `VIP_BACKENDS`를 검사·배포 양쪽에 명시하면 기존 Backend를 포함해 배치를 다시 계산합니다. Keycloak·DB의 전용 Worker 조건은 별도로 유지합니다.

**기대 결과:** `keycloak-up`이 `Keycloak 배포 완료: <공개 URL>`을 출력합니다.

### 기존 DB·namespace를 복구하는 경우

`keycloak-runtime`이 없고 DB의 PVC 또는 PV가 남아 있으면 검사·배포 모두 적용 전에 중단합니다.
PV가 `Available`이어도 디스크가 비어 있다고 단정할 수 없으므로 같은 규칙을 적용합니다.
기존 DB의 실제 비밀번호·관리자 설정을 확인하고 runtime Secret을 먼저 복원한 뒤 다시 검사합니다.

namespace 삭제로 PVC·Secret이 사라져도 `Retain` PV와 Worker의 DB 파일은 남을 수 있습니다.
아래 조회로 바인딩 상태를 확인하고, DB 백업·실제 credential과 대조해 운영자가 복구합니다.

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" get pv keycloak-postgres-data \
  -o jsonpath='{.status.phase}{"\n"}{.spec.claimRef}{"\n"}'
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get pvc keycloak-postgres-data \
  -o jsonpath='{.metadata.uid}{"\n"}'
```

PV가 `Released`이거나 이전 PVC의 UID를 참조하면 runtime Secret을 복원했어도 배포를 중단합니다.
도구는 PV의 `claimRef`를 지우거나 데이터·namespace·PVC를 삭제하지 않습니다.
운영자가 보존할 DB와 바인딩 복구를 확인한 뒤 `keycloak-check`부터 다시 실행합니다.

## 2. 서버 기동 확인

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" get pv keycloak-postgres-data
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get pvc keycloak-postgres-data
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status statefulset/keycloak-postgres --timeout=5m
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status deployment/keycloak --timeout=10m
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status deployment/traefik --timeout=5m
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get pods -o wide
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get ingress
curl -fsS https://sso.etch.samsungds.net/realms/etch/.well-known/openid-configuration
```

**기대 결과:**

- PV·PVC가 `Bound`이고 Keycloak·PostgreSQL이 원본에 지정된 worker에서 실행됩니다.
- Traefik은 VIP·배포 방식에 맞는 노드에서 실행되며 여러 노드에 배치될 수 있습니다.
- 공개 주소의 discovery 응답에 `https://sso.etch.samsungds.net/realms/etch` issuer가 있습니다.

**실패 확인:** 이미지 pull, worker 파일 권한·디스크, 실제 외부 접속은 서버에서 확인합니다.

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get events --sort-by=.lastTimestamp
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs statefulset/keycloak-postgres
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs deployment/keycloak
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs deployment/traefik
```

**다음 단계:** [Realm과 사내 로그인](03-configure.md#realm과-사내-로그인)을 설정합니다. 시험 로그인을 확인하기 전에는 앱을 연결하지 않습니다.
