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

- `khinfow01`은 Portal 앱을 한 worker에서 통합 시험하기 위한 노드입니다.
- 계획 사양은 12 vCPU, 72GiB memory, 1TB disk입니다.
- Kubernetes 조인과 `Ready` 상태는 배포 전에 확인해야 합니다.
- `10.172.117.91`에서 control-plane과 Pod/Service network로 통신 가능한지 확인해야 합니다.
- 업무 공개 DNS는 `etch.samsungds.net`으로 확정됐습니다. Portal 배포 범위, TLS 준비 상태, StorageClass 또는 local PV 경로와 용량은 아직 미확정입니다.
- Portal API/Web image registry 경로, image tag와 pull 인증 방식은 아직 미확정입니다.

## 반드시 확정할 값

- `kustomization.yaml`: API/Web 내부 registry와 immutable image tag
- `ingress.yaml`: Portal DNS host와 TLS Secret
- `deploy/keycloak/k8s/server/stack.yaml`: `etch-sso.samsungds.net` TLS Secret
- `api-env` Secret: Portal용 외부 PostgreSQL, Keycloak OIDC, Django 보안과 외부 연동 설정
- `keycloak-runtime` Secret: Keycloak 관리자, PostgreSQL과 Keycloak 공개 URL
- `web-env` Secret: 브라우저에 공개 가능한 Portal URL과 runtime 설정
- `minio-env` Secret: MinIO credential과 공개 URL
- `minio-data` PVC: 사내 StorageClass와 용량
- API 업무 파일 데이터: 사내 NFS/CSI 기준 read-only PVC와 `/data/<domain>` mount

## Keycloak 설정

Portal API의 입력 예시는 `deploy/portal/env/prod/api.env.example`이며 실제 값은 Git 제외된
`api.env`에 작성합니다. client 등록과 API가 같은 파일을 읽습니다.
[Portal client 등록 안내](../../jobs/keycloak-client/README.md)에 따라 client와 token mapper를
먼저 준비합니다. 다른 환경의 값을 자동으로 상속하지 않습니다.

사내 Keycloak과 전용 PostgreSQL은 `deploy/keycloak/k8s`의 독립 스택이 전용 `etch-sso` namespace에서 worker
`khplane01w09`에 배포합니다. StorageClass가 없으므로 PostgreSQL 데이터는 worker의
`/appdata/keycloak-postgres` 경로를 50Gi 정적 local PersistentVolume으로 사용합니다.
IngressClass는 Keycloak 스택이 배포하는 Traefik을 사용하며 worker host port 80/443을
점유합니다. 상세 준비와 단독 배포 절차는 [Keycloak 안내](../../../../keycloak/README.md)를
따릅니다. Portal overlay를 적용해도 Keycloak은 배포되지 않습니다.

공유 Traefik은 `etch-sso,tailwind-internal`을 감시해야 합니다. 이 overlay는
`traefik-rbac.yaml`로 `etch-sso/traefik` ServiceAccount에 Portal namespace의 라우팅
권한을 부여합니다. Keycloak 단독 스택은 `etch-sso`만 감시하므로 Portal overlay 적용
후에만 아래 선택 패치를 실행합니다. Ingress에서 TLS를 종료한 뒤 Nginx는 전달된
`X-Forwarded-Proto`를 유지하여 HTTPS 재접속 반복을 방지합니다.

```bash
# Portal overlay로 Namespace와 RBAC를 준비한 뒤 실행합니다.
kubectl patch deployment traefik -n etch-sso --type=json \
  --patch-file deploy/portal/k8s/overlays/prod/traefik-watch-patch.json
kubectl rollout status deployment/traefik -n etch-sso --timeout=3m
```

패치는 기존 인자를 검사하며 이미 확장됐거나 구성이 다른 경우 실패합니다. 이미
`etch-sso,tailwind-internal`을 감시한다면 재실행할 필요가 없습니다. Keycloak 단독 스택을
재적용하면 `etch-sso`로 복원되므로 이 패치도 다시 적용합니다. 재기동 중 일시적으로
접속이 끊길 수 있습니다. CP1에 YAML만 전달할 때는 이 JSON 파일도 별도로 전달합니다.

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

1. worker의 `/appdata/keycloak-postgres`와 host port 80/443을 확인합니다.
2. `etch-sso` namespace, `keycloak-runtime`, 세 Portal Secret과 TLS Secret을 준비합니다.
3. DNS와 Ingress host의 placeholder를 실제 값으로 교체합니다.
4. `deploy/keycloak/k8s` 스택을 적용하고 PostgreSQL, Keycloak, Traefik rollout을 확인합니다. 사내 OIDC 설정 후 claim 등록 Job을 별도 실행합니다.
5. Portal용 외부 PostgreSQL 연결과 `pg_trgm` extension을 확인합니다.
6. `migrate` overlay의 Job을 실행하고 완료를 확인합니다.
7. `deploy/portal/k8s/overlays/prod` overlay를 적용합니다.
8. 위의 `traefik-watch-patch.json`으로 Portal 감시를 확장하고 rollout을 확인합니다.
9. API health, Keycloak login/callback/logout, MinIO 업로드를 smoke test합니다.
