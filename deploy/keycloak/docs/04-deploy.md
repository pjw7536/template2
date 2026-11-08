# Keycloak 서버 배포와 기동 확인

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

**실행 위치:** 관리 호스트의 저장소 루트입니다. [서버 준비](01-setup.md)의 도구·디스크·계정과 실행 입력을 먼저 준비합니다. 새 터미널에서는 준비 문서의 context와 env 입력을 다시 설정합니다.

## 3. 검사 후 서버 배포

저장소 루트에서 순서대로 실행합니다. 검사가 실패하면 원인을 해결한 뒤 배포합니다.

```bash
make keycloak-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
make keycloak-up KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

| 명령 | 처리 범위 |
| --- | --- |
| `keycloak-check` | env·인증서·manifest·기존 Secret·worker 상태를 조회하고 검사 |
| `keycloak-up` | 없는 runtime Secret 준비, 공용 TLS 확인, PostgreSQL·Keycloak·Traefik 적용 |

최초 기동 시 관리자 계정을 만들고 이후 설정 Job도 같은 runtime Secret으로 로그인합니다.
`etch-sso` namespace가 없을 때만 원본의 label·annotation을 포함해 생성하며, 이미 있으면 namespace 설정은 변경하지 않습니다.

| 선택 입력 | 사용하는 경우 |
| --- | --- |
| `KEYCLOAK_ENV=/절대/경로/prod.env` | 다른 env 파일 사용 |
| `KEYCLOAK_CERTS=/인증서/폴더` | 해당 폴더의 PEM을 공용 TLS에 등록하는 선택적 호환 입력 |
| `VIP_BACKENDS=...` | VIP 최초 배치 지정. 검사·배포 양쪽에 동일하게 전달 |

현재 인프라의 VIP 최초 배치 예시는 `10.172.40.117,10.172.40.87`입니다. 실제 운영 대상과 일치하는지 확인합니다.

공용 Ingress를 먼저 준비했다면 기존 감시 namespace·replica·Worker pool·affinity·VIP annotation을 유지합니다.
Keycloak도 공통 Ingress 배치 검사를 사용하며 실제 보존할 배치가 유효한지 적용 전에 확인합니다.
기록된 VIP와 배치가 다르면 검사에서 중단합니다. 확인한 `VIP_BACKENDS`를 검사·배포 양쪽에 명시하면
기존 Backend를 포함한 배치를 다시 계산합니다. Keycloak·DB의 전용 Worker 조건은 별도로 유지합니다.

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

## 4. 서버 기동 확인

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" get pv keycloak-postgres-data
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get pvc keycloak-postgres-data
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status statefulset/keycloak-postgres --timeout=5m
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status deployment/keycloak --timeout=10m
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status deployment/traefik --timeout=5m
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get pods -o wide
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get ingress
```

다음 항목을 확인합니다.

- Keycloak·PostgreSQL이 원본에 지정된 worker에서 실행됩니다.
- Traefik은 VIP·배포 방식에 맞는 노드에서 실행됩니다. 여러 노드에 배치될 수 있습니다.
- 외부 DNS/TLS 준비 후 공개 주소에서 로그인 화면과 realm discovery 응답을 확인할 수 있습니다.

```bash
curl -fsS https://etch-sso.samsungds.net/realms/etch/.well-known/openid-configuration
```

실패하면 event·로그로 원인을 확인합니다. 이미지 pull, worker 파일 권한·디스크, 실제 외부 접속은 서버에서 확인해야 합니다.

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get events --sort-by=.lastTimestamp
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs statefulset/keycloak-postgres
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs deployment/keycloak
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs deployment/traefik
```

## 5. 다음 작업

서버 배포는 설정 Job을 실행하지 않습니다. [Keycloak 자체 설정](05-keycloak.md)으로 이동합니다.
Realm·사내 로그인·사용자 필드·필요한 그룹까지 준비하고 시험 로그인을 확인한 뒤 앱을 연결합니다.
