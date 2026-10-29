# 운영 Portal Kubernetes overlay 입력값

[Portal 배포 안내](../../../README.md)

이 overlay는 운영 환경에 맞게 값을 채운 뒤 배포하는 템플릿입니다.
placeholder가 남아 있으면 먼저 실제 값으로 교체합니다. 운영 설정은 `deploy/portal/env/prod/`에서 관리합니다.

운영 namespace는 `tailwind-internal`입니다. 이미지·Secret·스토리지 입력을 실제 환경에 맞춥니다.

## 사내 운영 클러스터

노드·VIP·DNS·스토리지는 [클러스터 구성과 상태 확인](../../../../shared/docs/infrastructure/cluster.md)에 따라 조회합니다.
Portal의 현재 배포 입력과 확인 사항은 아래에서 관리합니다.

### Portal Worker와 저장소 선택

- 사용할 Worker의 Ready·자원·스토리지·Pod/Service 통신을 확인합니다.
- MinIO는 [독립 앱](../../../../minio/README.md)으로 배포합니다. 이 overlay는 MinIO 리소스를 생성하지 않습니다.
- Ingress host·TLS·StorageClass 또는 local PV 경로·용량을 실제 대상 환경에 맞춥니다.
- API/Web 이미지 registry·태그·pull 인증과 migration 이미지가 일치하는지 확인합니다.

## 반드시 확정할 값

- `kustomization.yaml`: API/Web 내부 registry와 immutable image tag. `migrate/kustomization.yaml`도 같은 API 이미지로 맞춤
- `ingress.yaml`: `etch.samsungds.net` 인증서를 공용 Traefik에 등록
- `deploy/keycloak/k8s/server/stack.yaml`: `etch-sso.samsungds.net` 인증서도 공용 Traefik에서 관리
- `api-env` Secret: Portal용 외부 PostgreSQL, Keycloak OIDC, Django 보안과 외부 연동 설정
- `keycloak-runtime` Secret: Keycloak 관리자, PostgreSQL과 Keycloak 공개 URL
- `web-env` Secret: 브라우저에 공개 가능한 Portal URL과 runtime 설정
- API 업무 파일 데이터: 사내 NFS/CSI 기준 read-only PVC와 `/data/<domain>` mount

기본 API 원본의 업무 파일 볼륨은 `emptyDir`입니다. 영속 데이터가 필요한 경로는 실제 PVC로
교체하고, 참고·원본 데이터는 readOnly로 연결합니다. StorageClass/PV 공급 없이 PVC만 만들면 Pending일 수 있습니다.

## Keycloak 설정

Portal API 일반 설정은 Git에 포함된 `deploy/portal/env/prod/api.env`에 작성하며,
비밀번호·토큰도 `api.env`에 함께 저장하고 Git에 포함합니다. client 등록과 API 입력 도구는 같은 파일을 읽습니다.
[Portal client 등록 안내](../../jobs/keycloak-client/README.md)에 따라 client와 token mapper를
먼저 준비합니다. 다른 환경의 값을 자동으로 상속하지 않습니다.

Keycloak과 전용 PostgreSQL은 `deploy/keycloak/k8s`의 독립 스택으로 배포합니다.
전용 `etch-sso` namespace와 Worker `khplane01w09`를 사용합니다.
PostgreSQL 데이터는 Worker의 `/appdata/keycloak-postgres` 경로에 50Gi 정적 local PersistentVolume으로 저장합니다.

IngressClass는 Keycloak 스택의 Traefik을 사용합니다. Traefik은 Worker의 host port 80/443을 점유합니다.
상세 준비와 단독 배포 절차는 [Keycloak 안내](../../../../keycloak/README.md)를 따릅니다.
Portal overlay를 적용해도 Keycloak은 배포되지 않습니다.

## 공용 Traefik에 Portal 연결

Portal overlay는 `traefik-rbac.yaml`로 `etch-sso/traefik` ServiceAccount에 Portal namespace의
라우팅 권한을 부여합니다. `platform` checkout으로 기반 앱을 먼저 운영했다면
[선택 checkout](../../../../01-SERVER_CHECKOUT.md)을 `all`로 확장합니다. `portal` 단독 선택은 기존 범위를 교체합니다.

**배포 순서의 앱 overlay 적용 후** CP1에서 실행합니다. `KUBE_CONTEXT`는 배포 순서에서 선택한 context입니다.

```bash
make ingress-connect APP=portal KUBE_CONTEXT="$KUBE_CONTEXT"
```

이 명령은 기존 `portal-traefik` Role·RoleBinding과 공용 ServiceAccount 연결을 확인하고
감시 목록에 `tailwind-internal`만 추가합니다. Airflow·Headlamp 등 기존 감시 목록과
replica·nodeSelector·affinity·VIP annotation은 보존합니다. 이미 연결됐거나 전체 namespace를 감시하면 변경하지 않습니다.
controller·권한이 없거나 실행 중 동시 변경이 감지되면 실패합니다. 원인을 확인한 뒤 같은 명령으로 다시 검사합니다.
RBAC를 생성·삭제하거나 다른 앱을 재배포하지 않습니다.

변경 후 기존 앱과 Portal 접속을 함께 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" rollout status deployment/traefik -n etch-sso --timeout=3m
kubectl --context "$KUBE_CONTEXT" -n etch-sso get deployment traefik \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].args}{"\n"}'
```

Traefik 재기동 중 개별 연결은 재시도가 필요할 수 있습니다. 공유 환경의 이후 Keycloak 재배포는
`make keycloak-up`을 사용해 기존 namespace 감시와 VIP 배치를 유지합니다. 정적 Keycloak 스택은 직접 apply하지 않습니다.
Ingress에서 TLS를 종료한 뒤 Nginx는 전달된 `X-Forwarded-Proto`를 유지합니다.

아래 연결값은 Portal의 `api.env`에 입력합니다. Secret 등록 도구가 이 파일에서 API Secret을 준비합니다.

- `OIDC_PROVIDER=keycloak`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET`
- `OIDC_ISSUER`
- `OIDC_AUTH_URL`
- `OIDC_LOGOUT_URL`
- `OIDC_REDIRECT_URI`
- `OIDC_TOKEN_URL`
- `OIDC_JWKS_URL`

브라우저가 접근하는 authorize/logout URL과 issuer는 공개 Keycloak URL을 사용합니다.
API가 호출하는 token/JWKS URL은 cluster 내부에서 접근 가능한 URL을 사용할 수 있습니다.

Keycloak과 PostgreSQL은 단일 worker/로컬 디스크 구성이라 HA가 아닙니다. PostgreSQL
외부 백업을 별도로 준비하고, worker를 교체할 때는 local PV 데이터 이전을 먼저 수행합니다.

## 배포 순서

[공통 배포 준비](../../../../shared/docs/kubernetes/04-prerequisites.md)를 마친 뒤 CP1의 checkout 루트에서 실행합니다.
각 명령이 성공한 후 다음 명령을 실행합니다. 아래 명령은 실제 클러스터를 변경합니다.

### 1. 대상과 입력 확인

```bash
kubectl config get-contexts
read -r -p '배포할 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
# client Job 안내에서 사용하는 current-context도 맞춥니다.
kubectl config use-context "$KUBE_CONTEXT"
make server-check APP=portal PROFILE=prod
```

이미지·TLS·영속 저장소의 미확정 값을 위 목록에 따라 준비합니다.

Keycloak은 [전용 안내](../../../../keycloak/README.md)의 `keycloak-check/up`과 사내 OIDC·claim 작업을 먼저 완료합니다.
기존 정상 스택을 Portal 배포 때문에 정적 YAML로 다시 적용하지 않습니다.

Portal 외부 PostgreSQL의 DB·계정·접속과 `pg_trgm` extension을 DB 담당자에게 확인합니다.
[Portal 입력 안내](../../../README.md)의 api/web/client 검사를 모두 통과한 뒤
[Portal client 등록](../../jobs/keycloak-client/README.md)을 수행합니다.

### 2. Namespace·Secret·TLS

```bash
kubectl --context "$KUBE_CONTEXT" apply -f deploy/portal/k8s/overlays/prod/namespace.yaml
make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT="$KUBE_CONTEXT"
make k8s-env APP=portal PROFILE=prod COMPONENT=web KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n etch-sso get secret traefik-tls
```

Portal 도메인 인증서는 [공용 TLS 등록](../../../../shared/ingress/README.md#인증서-최초-등록과-갱신)을 사용합니다.
이미 업무 도메인을 등록했다면 추가 인증서는 필요하지 않습니다.

```bash
read -r -p '업무 도메인 full chain 파일: ' PORTAL_CERT_FILE
read -r -p '업무 도메인 개인키 파일: ' PORTAL_KEY_FILE
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST=etch.samsungds.net \
  TLS_CERT_FILE="$PORTAL_CERT_FILE" TLS_KEY_FILE="$PORTAL_KEY_FILE"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

### 3. Migration

운영 DB가 있다면 먼저 DB 백업과 migration 호환성을 확인합니다.
`migrate/kustomization.yaml`의 API 이미지가 앱 overlay와 동일해야 합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal get job portal-migrate --ignore-not-found
```

최초 설치라면 Job이 없습니다. 이전 완료 Job이 있고 새 migration을 수행할 때는 완료 상태와
백업을 확인한 뒤 해당 Job만 삭제하고 다음 블록으로 재생성합니다. DB·PVC는 삭제하지 않습니다.

진행 중이거나 실패한 Job이면 로그·DB 원인부터 확인하고 중복 실행하지 않습니다.

```bash
kubectl --context "$KUBE_CONTEXT" apply -k deploy/portal/k8s/overlays/prod/migrate
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal wait --for=condition=complete job/portal-migrate --timeout=15m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal logs job/portal-migrate --tail=100
```

실패하면 앱 배포를 진행하지 않습니다. `describe job`·Job Pod 로그로 DB 연결과 migration 오류를 확인합니다.

### 4. 앱과 라우팅 적용

공용 MinIO는 독립 설치·연결을 마친 상태에서 아래 Portal 리소스만 적용합니다.

```bash
kubectl --context "$KUBE_CONTEXT" apply -k deploy/portal/k8s/overlays/prod
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/api --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/web --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/edge-nginx --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal get pods,pvc,ingress
```

이 문서의 **공용 Traefik에 Portal 연결** 절차로 감시 목록을 확장합니다.
PVC가 Pending이면 StorageClass/PV·노드 affinity를 먼저 확인합니다.

[접속 검증](../../../../shared/docs/kubernetes/06-verification.md)에 따라 API health,
Keycloak login/callback/logout, MinIO 시험 파일 업로드·다운로드를 확인해야 배포 완료입니다.

### 5. 설정 변경 반영

최초 설치는 위 1~4단계를 따릅니다. 이미 설치된 Portal에서 env만 변경했다면
해당 입력을 검사하고 Secret으로 등록한 뒤, 아래 표의 Deployment를 재시작합니다.
같은 manifest를 다시 apply하거나 `rollout status`만 실행하면 Secret 변경이 Pod에 반영되지 않습니다.

| 변경 파일 | 검사·Secret 등록의 COMPONENT | 재시작 대상 | 확인할 동작 |
| --- | --- | --- | --- |
| `api.env` | `api` | `api`, `edge-nginx` | API health·로그인, collectstatic 초기화 완료 |
| `web.env` | `web` | `web` | 브라우저 runtime 설정·API 주소·화면 링크 |

각 파일에 대해 `make env-check APP=portal PROFILE=prod COMPONENT=<표의 값>`을 통과한 뒤
같은 COMPONENT와 `KUBE_CONTEXT`로 `make k8s-env`를 실행합니다.

API 설정을 변경한 경우:

```bash
make env-check APP=portal PROFILE=prod COMPONENT=api
make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout restart deployment/api
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/api --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout restart deployment/edge-nginx
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/edge-nginx --timeout=10m
```

Web 설정을 변경한 경우에는 다음 블록만 실행합니다. MinIO 서버 설정은 독립 앱의 `make minio-up`을 사용합니다.

```bash
make env-check APP=portal PROFILE=prod COMPONENT=web
make k8s-env APP=portal PROFILE=prod COMPONENT=web KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout restart deployment/web
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/web --timeout=10m
```


DB·Keycloak client·MinIO API 계정의 비밀번호를 바꾼다면 해당 서비스의 실제 계정도 먼저 맞춥니다.
Secret 등록과 Pod 재시작만으로 외부 계정이 변경되지는 않습니다.
OIDC client 설정 변경은 [client 등록 절차](../../jobs/keycloak-client/README.md),
DB schema 변경은 위 migration 단계를 함께 수행합니다. `minio-init`은 버킷 준비용이며,
설정 변경 때마다 다시 실행하지 않습니다.

재시작 후 표의 실제 동작과 [접속 검증](../../../../shared/docs/kubernetes/06-verification.md)을 확인합니다.
