# 운영 Portal Kubernetes overlay 입력값

[Portal 배포 안내](../../../README.md)

이 overlay는 사내 클러스터가 발급된 뒤 실제 값으로 교체할 template입니다.
placeholder가 남아 있는 상태에서는 배포하지 않습니다.
운영 설정은 `deploy/portal/env/prod/`에서 관리합니다. 이전 internal overlay에서 폴더 이름만
변경했으며 `tailwind-internal` Namespace와 리소스 이름은 그대로 유지합니다.

## 사내 운영 클러스터

노드·VIP·DNS와 확인 시점은 [공통 클러스터 현황](../../../../shared/docs/infrastructure/cluster.md)을 참고합니다.
Portal 전용 배포 계획과 입력값은 아래에서 관리합니다.

### Portal worker 계획과 확인 필요 항목

- 현재 등록된 Worker는 공통 현황의 `khplane01w09`, `khplanew01`입니다. Portal 배치 위치는 자원·스토리지 확인 후 정합니다.
- `khinfow01`(12 vCPU, 72GiB memory, 1TB disk)은 과거 통합 시험 계획이며 2026-09-16 사용자 제공 노드 목록에는 없습니다.
- 과거 예정 주소를 현재 배포 노드로 사용하지 않습니다. 사용할 Worker의 Ready·자원·스토리지·Pod/Service 통신을 확인합니다.
- 업무 공개 DNS는 `etch.samsungds.net`으로 확정됐습니다. Portal 배포 범위, TLS 준비 상태, StorageClass 또는 local PV 경로와 용량은 아직 미확정입니다.
- Portal API/Web image registry 경로, image tag와 pull 인증 방식은 아직 미확정입니다.

## 반드시 확정할 값

- `kustomization.yaml`: API/Web 내부 registry와 immutable image tag. `migrate/kustomization.yaml`도 같은 API 이미지로 맞춤
- `ingress.yaml`: Portal DNS host와 TLS Secret
- `deploy/keycloak/k8s/server/stack.yaml`: `etch-sso.samsungds.net` TLS Secret
- `api-env` Secret: Portal용 외부 PostgreSQL, Keycloak OIDC, Django 보안과 외부 연동 설정
- `keycloak-runtime` Secret: Keycloak 관리자, PostgreSQL과 Keycloak 공개 URL
- `web-env` Secret: 브라우저에 공개 가능한 Portal URL과 runtime 설정
- `minio-env` Secret: MinIO credential과 공개 URL
- `minio-data` PVC: 사내 StorageClass와 용량
- API 업무 파일 데이터: 사내 NFS/CSI 기준 read-only PVC와 `/data/<domain>` mount

기본 API 원본의 업무 파일 볼륨은 `emptyDir`입니다. 영속 데이터가 필요한 경로는 실제 PVC로
교체하고, 참고·원본 데이터는 readOnly로 연결합니다. StorageClass/PV 공급 없이 PVC만 만들면 Pending일 수 있습니다.

## Keycloak 설정

Portal API 일반 설정은 Git에 포함된 `deploy/portal/env/prod/api.env`에 작성하며,
비밀값은 Git 제외 파일 `api.secrets.env`에 보관합니다. client 등록과 API 입력 도구가 두 파일을 병합합니다.
[Portal client 등록 안내](../../jobs/keycloak-client/README.md)에 따라 client와 token mapper를
먼저 준비합니다. 다른 환경의 값을 자동으로 상속하지 않습니다.

사내 Keycloak과 전용 PostgreSQL은 `deploy/keycloak/k8s`의 독립 스택이 전용 `etch-sso` namespace에서 worker
`khplane01w09`에 배포합니다. Keycloak 원본은 동적 StorageClass 대신 PostgreSQL 데이터에 worker의
`/appdata/keycloak-postgres` 경로를 50Gi 정적 local PersistentVolume으로 사용합니다.
IngressClass는 Keycloak 스택이 배포하는 Traefik을 사용하며 worker host port 80/443을
점유합니다. 상세 준비와 단독 배포 절차는 [Keycloak 안내](../../../../keycloak/README.md)를
따릅니다. Portal overlay를 적용해도 Keycloak은 배포되지 않습니다.

## 공용 Traefik에 Portal 연결

Portal overlay는 `traefik-rbac.yaml`로 `etch-sso/traefik` ServiceAccount에 Portal namespace의
라우팅 권한을 부여합니다. 아래 작업은 **배포 순서의 앱 overlay 적용 후** CP1에서 수행합니다.
`KUBE_CONTEXT`는 배포 순서에서 선택한 context입니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n etch-sso get deployment traefik \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].args}{"\n"}'
```

출력의 `--providers.kubernetesingress.namespaces=` 값을 확인합니다.

- `etch-sso`만 있으면 아래 정적 패치를 사용합니다. 원본의 컨테이너·인자 위치와 다르면 검사에서 중단합니다.
- 목록에 `tailwind-internal`이 이미 있거나 인자가 없거나 값이 비어 전체 namespace를 감시하면 수정하지 않습니다.
- Airflow 등 다른 namespace가 명시돼 있으면 정적 패치를 사용하지 않고 아래 편집 방법으로 목록에 추가합니다.

```bash
# etch-sso만 감시하는 원본 구성에서만 실행합니다.
kubectl --context "$KUBE_CONTEXT" patch deployment traefik -n etch-sso --type=json \
  --patch-file deploy/portal/k8s/overlays/prod/traefik-watch-patch.json
```

다른 앱을 이미 감시하거나 정적 패치의 인자 위치 검사가 실패한 경우:

```bash
kubectl --context "$KUBE_CONTEXT" -n etch-sso edit deployment traefik
```

편집기에서 `spec.template.spec.containers`의 `name: traefik`인 컨테이너를 찾습니다.
`args`의 namespace 인자 하나에 기존 목록을 그대로 두고 `,tailwind-internal`을 추가한 뒤 저장합니다.
예를 들어 값이 `etch-sso,airflow`라면 `etch-sso,airflow,tailwind-internal`로 바꿉니다.
다른 인자·replica·nodeSelector·affinity·VIP annotation은 수정하지 않습니다.
인자가 중복되거나 목록의 의미가 불분명하면 편집을 취소하고 담당자에게 현재 설정을 확인합니다.

변경 후에는 다음을 확인합니다. 기존 앱 접속도 함께 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" rollout status deployment/traefik -n etch-sso --timeout=3m
kubectl --context "$KUBE_CONTEXT" -n etch-sso get deployment traefik \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].args}{"\n"}'
```

Traefik 재기동 중 개별 연결은 재시도가 필요할 수 있습니다. 공유 환경의 이후 Keycloak 재배포는
`make keycloak-up`을 사용해 기존 namespace 감시와 VIP 배치를 유지합니다. 정적 Keycloak 스택은 직접 apply하지 않습니다.
Ingress에서 TLS를 종료한 뒤 Nginx는 전달된 `X-Forwarded-Proto`를 유지합니다.

Portal API Secret에는 아래 값을 넣어 연결합니다.

- `OIDC_PROVIDER=keycloak`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET`
- `OIDC_ISSUER`
- `ADFS_AUTH_URL`
- `ADFS_LOGOUT_URL`
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
# make k8s-env와 client Job 안내가 사용하는 current-context도 맞춥니다.
kubectl config use-context "$KUBE_CONTEXT"
make server-check APP=portal PROFILE=prod
```

이미지·DNS·TLS·영속 저장소의 미확정 값을 위 목록에 따라 준비합니다.
Keycloak은 [전용 안내](../../../../keycloak/README.md)의 `keycloak-check/up`과 사내 OIDC·claim 작업을 먼저 완료합니다.
기존 정상 스택을 Portal 배포 때문에 정적 YAML로 다시 적용하지 않습니다.
Portal 외부 PostgreSQL의 DB·계정·접속과 `pg_trgm` extension을 DB 담당자에게 확인합니다.
[Portal 입력 안내](../../../README.md)의 api/web/minio/client 검사를 모두 통과한 뒤
[Portal client 등록](../../jobs/keycloak-client/README.md)을 수행합니다.

### 2. Namespace·Secret·TLS

```bash
kubectl --context "$KUBE_CONTEXT" apply -f deploy/portal/k8s/overlays/prod/namespace.yaml
make k8s-env APP=portal PROFILE=prod COMPONENT=api
make k8s-env APP=portal PROFILE=prod COMPONENT=web
make k8s-env APP=portal PROFILE=prod COMPONENT=minio
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal get secret portal-tls --ignore-not-found
```

TLS Secret이 없을 때만 도메인이 검증된 인증서로 생성합니다. 기존 Secret의 교체는 별도 갱신 작업입니다.
인증서 도메인은 이 overlay의 Ingress host와 같아야 합니다.

```bash
read -r -p 'Portal 인증서 full chain 파일: ' PORTAL_CERT_FILE
read -r -p 'Portal 개인키 파일: ' PORTAL_KEY_FILE
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal create secret tls portal-tls \
  --cert="$PORTAL_CERT_FILE" --key="$PORTAL_KEY_FILE"
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

```bash
kubectl --context "$KUBE_CONTEXT" apply -k deploy/portal/k8s/overlays/prod
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/api --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/web --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/edge-nginx --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/minio --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal wait --for=condition=complete job/minio-init --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal get pods,pvc,ingress
```

이 문서의 **공용 Traefik에 Portal 연결** 절차로 감시 목록을 확장합니다.
PVC가 Pending이면 StorageClass/PV·노드 affinity를 먼저 확인합니다.
[접속 검증](../../../../shared/docs/kubernetes/06-verification.md)에 따라 API health,
Keycloak login/callback/logout, MinIO 시험 파일 업로드·다운로드를 확인해야 배포 완료입니다.
