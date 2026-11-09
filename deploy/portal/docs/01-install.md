# Portal 설치

[앱 안내](../README.md)

- [환경설정](#환경설정)
- [Keycloak client 등록](#keycloak-client-등록)
- [Migration·배포·검증](#migration배포검증)

## 준비 조건

| 대상 | 확인할 내용 |
| --- | --- |
| 배포 파일 | Portal 선택 checkout. 기반 앱 파일을 유지하며 추가할 때는 `all`로 확장 |
| 관리 도구 | Bash·Make·kubectl, 대상 클러스터 kubeconfig와 namespace·Secret·Job·앱 리소스 적용 권한 |
| 이미지 | 실제 registry의 API·Web 고유 태그와 pull 인증. migration도 같은 API 이미지 사용 |
| DB | Portal 전용 외부 PostgreSQL의 DB·계정·접속과 `pg_trgm` extension. Keycloak DB와 별개 |
| 로그인 | Keycloak의 Realm·사내 로그인 준비. Portal client는 Portal 입력으로 등록 |
| 파일 저장소 | 공용 MinIO의 실제 접근 계정·bucket 권한과 필요한 업무 파일 PVC |
| 공개 접속 | 공용 Traefik·DNS/VIP·Portal 도메인 인증서 |

노드·연결 경로는 [사내 인프라 정보](../../shared/docs/infrastructure/README.md)에서 찾고 실제 클러스터를 조회합니다.
[overlay 입력](../k8s/overlays/prod/README.md)의 이미지·스토리지 placeholder를 실제 값으로 바꿔야 합니다.

## 환경설정

**실행 위치:** 관리 호스트의 저장소 루트입니다. 운영 입력은 `deploy/portal/env/prod/`가 소유합니다. Keycloak과 공용 MinIO를 먼저 준비하고, 이미지·영속 저장소는 [운영 overlay](../k8s/overlays/prod/README.md)에서 확인합니다.

### 어떤 파일을 수정하나요?

| 파일 | 넣는 내용 | 주의할 점 |
| --- | --- | --- |
| `env/prod/api.env` | Portal 서버, DB·로그인·업무 연동 설정과 비밀번호·토큰·인증 헤더 | API가 읽는 설정을 이 파일에서 함께 관리 |
| `env/prod/web.env` | 브라우저에서 사용할 Portal·API·파일 주소와 화면 링크 | 브라우저에 공개되므로 비밀번호·토큰을 입력하지 않음 |

API는 Django 업무 기능들이 함께 실행되는 하나의 서버입니다. Assistant·Emails·Drone을
별도 env 파일로 쪼개서 합성하지 않고 `api.env` 안의 기능별 구역으로 관리합니다.
Airflow 서버 자체의 설정은 `../airflow/env/`, API에서 Airflow에 연결하는 설정은 `api.env`에 둡니다.

| 환경 폴더 | 사용처 |
| --- | --- |
| `env/prod/` | 사내 Kubernetes 운영 Portal |
| `local/portal/env/` | 외부망에서도 실행 가능한 Kubernetes 개발 입력 |
| `local/portal/env/api-k8s.env` | 로컬 Kubernetes에서만 적용하는 API 차이. 단독 사용하지 않음 |
| `env/test/` | API 자동 테스트 |

환경끼리 자동 상속하지 않습니다. 로컬 Kubernetes만 `local/portal/env/api.env`에
`local/portal/env/api-k8s.env`를 덮어쓰고 `local/minio/env/minio.env`의 API 접근 키를 선택해 합성합니다.

운영 API 설정은 `env/prod/api.env`, Web 설정은 `env/prod/web.env`에서 관리합니다.
실제 배포 전에 DB 연결값·Keycloak 입력·업무 연동 주소를 확인하고 대상 환경에 맞춥니다.

사내 서버는 Kubernetes로 배포합니다.

### 사내 배포 입력 순서

저장소 루트에서 시작합니다. Git에서 받은 env의 서버별 값을 확인합니다.

```bash

# Git에서 받은 운영 env의 접근 권한을 설정합니다.
chmod 600 deploy/portal/env/prod/api.env deploy/portal/env/prod/web.env
```

1. `api.env`의 **1~4번 구역**에 Portal DNS, DB, 로그인, HTTPS 설정을 작성합니다.
   DB 비밀번호·Django Secret Key·OIDC Client Secret은 `api.env`에 저장합니다.
   Portal DB는 Keycloak 전용 DB와 별개입니다. 공개 주소는 `etch.samsungds.net`으로 설정되어 있습니다.
2. `web.env`에 같은 Portal 공개 주소와 파일 접근 주소를 작성합니다.
3. [공용 MinIO](../../minio/README.md)를 별도로 준비하고 Portal의 `api.env`에 endpoint와 접근 키를 작성합니다. 실제 MinIO 계정·bucket 권한도 준비합니다.
4. 업무 기능을 연결할 때 `api.env`에 해당 구역을 추가합니다.
   비밀번호·토큰·인증 헤더는 같은 `api.env`에 입력합니다.
   [전체 설정 설명](../../../docs/reference/01-configuration.md)을 보고 필요한 값만 입력합니다.
   기존 다른 환경 파일을 통째로 복사하면 dummy 주소나 다른 환경의 계정까지 가져올 수 있습니다.

API 파일의 구역 번호는 모든 환경에서 같습니다. 설정이 없는 구역은 생략되므로
`env/prod/api.env`에 모든 번호가 보이지 않아도 정상입니다. timeout·cache 같은 선택 설정은
해당 profile의 입력값과 코드 기본값을 확인합니다. 빈 값과 변수 생략은 의미가 다를 수 있습니다.

### 서로 맞춰야 하는 값

| 기준 | 함께 확인할 항목 |
| --- | --- |
| Portal 공개 주소 | API의 `FRONTEND_BASE_URL`, CORS·CSRF 주소, Web의 `VITE_SITE_URL`, Ingress host·TLS |
| Portal API 주소 | Web의 `VITE_BACKEND_URL`은 Portal origin, reverse proxy는 `/api/v1/` 경로를 API로 전달. `PUBLIC_API_BASE_URL`은 운영 env 검사 대상이며 라우팅·URL 생성에는 사용하지 않음 |
| Portal 로그인 | `OIDC_REDIRECT_URI`와 Keycloak Portal client의 허용 callback |
| Portal client 계정 | API의 `OIDC_CLIENT_ID`·`OIDC_CLIENT_SECRET`과 Keycloak에 등록한 Portal client |
| 파일 저장소 계정 | API의 `MINIO_ACCESS_KEY`·`MINIO_SECRET_KEY`와 실제 MinIO 접근 계정 |

사내 Kubernetes의 API Secret은 `api.env`만 읽습니다. 파일 기능을 사용할 때는
`MINIO_ENDPOINT=http://minio.minio.svc.cluster.local:9000` 및 필요한 접근 키를 `api.env`에도 명시합니다.

`local/minio/env/minio.env`의 client 키가 API에 자동으로 합쳐지는 것은 로컬 Kubernetes 경로뿐입니다.
업무 기능에서 요구하는 bucket과 권한도 별도로 준비합니다.

Portal은 `OIDC_PROVIDER=keycloak`만 지원합니다. `OIDC_AUTH_URL`과
`OIDC_LOGOUT_URL`에는 Keycloak endpoint를 입력합니다. 이전 `ADFS_*` 인증 설정은 제거합니다.
Portal client secret과 사내 OIDC client secret은 서로 다른 값입니다.

Web의 `VITE_*`, `BACKEND_API_URL`, `BACKEND_URL`, `MINIO_ENDPOINT`는
브라우저 설정에 공개됩니다. `BACKEND_API_URL`도 비밀 서버 전용 주소가 아니라
브라우저 API 주소의 fallback으로 쓰이므로, 새 설정에는 브라우저에서 접근 가능한 주소를 넣습니다.

### 공용 MinIO 연결

MinIO의 설치·credential·Ingress·PVC는 [독립 MinIO 앱](../../minio/README.md)이 소유합니다.
Portal overlay는 MinIO 리소스를 생성하지 않습니다.
API는 `MINIO_ENDPOINT=http://minio.minio.svc.cluster.local:9000`과 Portal 접근 키를 사용합니다.
Web은 기존 `VITE_MINIO_ENDPOINT=https://etch.samsungds.net/minio`를 사용합니다.
`/minio/`와 `/minio-console/`은 공용 Traefik이 MinIO namespace로 직접 전달합니다.

### 검사와 적용

```bash
make env-check APP=portal PROFILE=prod COMPONENT=api
make env-check APP=portal PROFILE=prod COMPONENT=web
make env-check APP=portal PROFILE=prod COMPONENT=client
```

필수값이 비어 있거나 임시값이면 배포 전 검사가 실패합니다.
검사 통과는 필수 입력 확인이며 DB 접속이나 로그인 성공을 보장하지 않습니다.

`make prod-profile-env-check`는 같은 운영 API 검사를 실행합니다. Airflow·RAG 등 선택 업무
연동을 필수로 강제하지 않으므로 해당 기능을 사용할 때는 endpoint와 계정을 별도로 확인합니다.

prod Web의 API 주소는 브라우저에서 접근 가능한 전체 origin URL로 작성합니다.

Namespace와 배포 리소스 준비 후 필요한 Secret만 등록합니다.

```bash
make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT="$KUBE_CONTEXT"
make k8s-env APP=portal PROFILE=prod COMPONENT=web KUBE_CONTEXT="$KUBE_CONTEXT"
```

Secret 등록 후에도 실행 중인 Pod는 자동으로 재시작되지 않습니다.
이미 설치된 Portal에서 설정만 바꿨다면 [설정 변경 반영](03-operations.md#5-설정-변경-반영)의
대응 Deployment를 재시작하고 실제 동작까지 확인합니다.

Portal client 등록에는 별도 입력 등록과 Job 실행이 필요합니다. [운영 overlay 배포 순서](../k8s/overlays/prod/README.md)와
[client 등록 안내](#keycloak-client-등록)를 따릅니다.

`env/prod/api.env`, `web.env`는 Git에서 관리합니다. MinIO 서버 입력은 `deploy/minio/env/prod.env`가 소유합니다.
Portal의 비밀번호·토큰·인증 헤더는 `api.env`에 저장합니다.
공용 검사·Secret 등록 도구는 지정한 env 하나를 읽습니다. `*.pre-k8s.bak`와 인증서·개인키 파일은 Git에서 제외됩니다.

env는 clone으로 전달됩니다. 인증서·개인키 파일은 CP1에 별도로 준비합니다.

**완료 기준:** API·Web·client 입력 검사를 통과했습니다. [배포 절차](#migration배포검증)에서 namespace·client 등록·migration·앱 적용을 진행합니다.

## Keycloak client 등록

Keycloak 자체 설정과 사내 시험 로그인을 마친 뒤 Portal 전용 client·token mapper를 등록합니다.
공개 Portal URL과 callback은 실제 사용할 값으로 정합니다.

### 입력 준비

저장소 루트의 Bash에서 실행합니다.

```bash
kubectl config current-context
kubectl config get-contexts
read -r -p 'Keycloak이 설치된 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
vi deploy/portal/env/prod/api.env
```

`OIDC_PROVIDER=keycloak`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_ISSUER`,
`OIDC_REDIRECT_URI`, `FRONTEND_BASE_URL`을 입력합니다.
사내 AD FS client와 별개의 Portal 전용 ID·secret을 사용합니다.
issuer는 Keycloak `etch` realm의 discovery에 나온 값과 같아야 합니다.

### client 등록

```bash
make keycloak-portal-client-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_PORTAL_ENV="$PWD/deploy/portal/env/prod/api.env"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/portal-keycloak-client
```

명령은 입력 검사·관리 ConfigMap·client Secret 준비 후 Job을 실행하고 완료를 기다립니다.
사내 IdP·User Profile·수신 mapper는 이 단계에서 설정하지 않습니다.

`checkout-server.sh portal`로 준비한 서버에도 필요한 Keycloak 등록 지원 코드가 포함됩니다.
등록 입력은 Portal의 `api.env`만 사용하며 Keycloak env는 읽지 않습니다.

사내 claim 16개와 소속 2개를 ID Token·Access Token·UserInfo에 발급합니다.
전체 필드는 [claim 매핑 계약](../../keycloak/docs/05-reference.md#사용자-필드와-claim)을 따릅니다.
SDWT 그룹을 발급하려면 [앱 그룹 연결](../../keycloak/docs/03-configure.md#sdwt-그룹을-portal에-전달하는-경우)을 수행합니다.

### Portal 배포와 확인

같은 `api.env`를 사용해 [Portal 배포 안내](../README.md)에 따라 API Secret·앱을 배포합니다.
이 client 등록 명령만으로 Portal API가 배포되지는 않습니다.
시험 계정으로 로그인해 callback, 신원 claim, 필요한 소속·그룹과 앱 접근 판정을 확인합니다.
Keycloak의 소속·그룹을 발급하는 것과 Portal의 실제 권한 판정 구현은 별개입니다.

client 등록 도구는 신원·소속 claim 외에 다음 권한 설정을 준비합니다.

- 앱 역할과 `resource_access.<client-id>.roles`, `groups` mapper
- `portal-members` 그룹과 이 그룹의 `portal-all-apps` 역할 연결

운영 사용자에게 역할을 자동으로 부여하지는 않습니다. 운영자가 조직 정책에 따라 그룹 구성원을 지정하고,
제한 사용자에게는 개별 앱 역할을 부여합니다.

Portal은 발급된 client 역할로 앱 접근을 판단합니다. `deptid`나 그룹 이름으로 앱 접근을 추정하지 않습니다.
상세 정책과 최초 관리자 설정은 [Portal 배포 안내](02-access.md#keycloak-권한과-새-db-시작)를 따릅니다.

그룹 역할 연결은 [Keycloak 공식 Admin CLI](https://www.keycloak.org/docs/latest/server_admin/#admin-cli)의 `add-roles --gname ... --cclientid ...`를 사용합니다.

## Migration·배포·검증

**실행 위치:** CP1의 checkout 루트입니다. [서버 준비](01-install.md#준비-조건), [환경설정](#환경설정), [운영 overlay 입력](../k8s/overlays/prod/README.md)을 확인한 뒤 진행합니다. 실제 실행은 아래 **배포 순서**를 따르며, Traefik 연결 명령은 앱 overlay 적용 후에 수행합니다.

### 배포 순서

[공통 배포 준비](../../shared/docs/operations/02-deploy.md#배포-준비)를 마친 뒤 CP1의 checkout 루트에서 실행합니다.
각 명령이 성공한 후 다음 명령을 실행합니다. 아래 명령은 실제 클러스터를 변경합니다.

#### 1. 대상과 입력 확인

```bash
kubectl config get-contexts
read -r -p '배포할 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -o wide

# client Job 안내에서 사용하는 current-context도 맞춥니다.
kubectl config use-context "$KUBE_CONTEXT"
make server-check APP=portal PROFILE=prod
```

이미지·TLS·영속 저장소의 미확정 값은 [overlay 입력](../k8s/overlays/prod/README.md#원본과-입력)에 따라 준비합니다.

Keycloak은 [전용 안내](../../keycloak/README.md)의 `keycloak-check/up`과 사내 OIDC·claim 작업을 먼저 완료합니다.
기존 정상 스택을 Portal 배포 때문에 정적 YAML로 다시 적용하지 않습니다.

Portal 외부 PostgreSQL의 DB·계정·접속과 `pg_trgm` extension을 DB 담당자에게 확인합니다.
[Portal 입력 안내](../README.md)의 api/web/client 검사를 모두 통과한 뒤
[Portal client 등록](#keycloak-client-등록)을 수행합니다.

#### 2. Namespace·Secret·TLS

```bash
kubectl --context "$KUBE_CONTEXT" apply -f deploy/portal/k8s/overlays/prod/namespace.yaml
make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT="$KUBE_CONTEXT"
make k8s-env APP=portal PROFILE=prod COMPONENT=web KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n etch-sso get secret traefik-tls
```

Portal 도메인 인증서는 [공용 TLS 등록](../../shared/docs/certificates/apply.md#2-2-kubernetes-tls-secret에-등록-또는-갱신)을 사용합니다.
이미 업무 도메인을 등록했다면 추가 인증서는 필요하지 않습니다.

```bash
read -r -p '업무 도메인 full chain 파일: ' PORTAL_CERT_FILE
read -r -p '업무 도메인 개인키 파일: ' PORTAL_KEY_FILE
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST=etch.samsungds.net \
  TLS_CERT_FILE="$PORTAL_CERT_FILE" TLS_KEY_FILE="$PORTAL_KEY_FILE"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

#### 3. Migration

신규 DB는 `pg_trgm` extension을 준비한 뒤 앱 시작 전에 migration을 실행합니다.
신규 설치에서는 같은 터미널에 남은 복원 입력을 사용하지 않도록 `unset PORTAL_API_REPLICAS`를 실행합니다.
기존 DB 갱신은 적용할 migration의 SQL·데이터 변경과 관련 작업의 호환성을 검토하고,
아래 쓰기 중지·백업·사전 검사부터 진행합니다. 작업 중 API와 쓰기 작업을 재개하지 않습니다.
`migrate/kustomization.yaml`의 API 이미지가 앱 overlay와 동일해야 합니다.

##### 검사 Job 준비

같은 Bash 세션에서 아래 함수를 정의합니다. migration overlay를 읽어 동일 이미지·namespace·
`api-env` Secret의 검사 Job을 만들며, `backoffLimit=0`으로 자동 재시도하지 않습니다.
검사마다 사용하지 않은 Job 이름을 지정합니다. 같은 이름이 있으면 `create`가 중단하므로 먼저 기존 결과를 확인합니다.

```bash
portal_permission_check() (
  set -euo pipefail
  local check_name="$1" check_phase="$2"
  case "$check_phase" in
    pre-migration|post-migration) ;;
    *) echo '검사 phase는 pre-migration 또는 post-migration이어야 합니다.' >&2; return 1 ;;
  esac
  kubectl --context "$KUBE_CONTEXT" create --dry-run=client \
    -k deploy/portal/k8s/overlays/prod/migrate -o json |
    python3 -c '
import json
import sys

job = json.load(sys.stdin)
job["metadata"]["name"] = sys.argv[1]
job["spec"]["backoffLimit"] = 0
container = next(item for item in job["spec"]["template"]["spec"]["containers"] if item["name"] == "migrate")
container["command"] = ["python"]
container["args"] = ["manage.py", "check_access_permission_integrity", "--phase", sys.argv[2]]
json.dump(job, sys.stdout)
' "$check_name" "$check_phase" |
    kubectl --context "$KUBE_CONTEXT" create -f -
  kubectl --context "$KUBE_CONTEXT" -n tailwind-internal wait \
    --for=condition=complete "job/$check_name" --timeout=15m
  kubectl --context "$KUBE_CONTEXT" -n tailwind-internal logs "job/$check_name" --tail=100
)
```

wait가 실패하면 Job·Pod 상태와 로그를 확인하고 다음 단계로 넘어가지 않습니다.
검사 명령은 DB를 읽으며, 위 함수는 검사 Job을 클러스터에 생성합니다.

##### 기존 DB 갱신 전 쓰기 중지와 사전 검사

**신규 DB는 이 절을 건너뜁니다.** 업무 테이블이 없으므로 `pre-migration` 검사를 실행하지 않습니다.
기존 환경은 DB에 쓰는 worker·Airflow 작업을 중지하고 진행 중인 요청을 마친 뒤 API를 중지합니다.
중지한 작업과 API replica 수는 쓰기 재개 때 복원할 입력입니다.

```bash
PORTAL_API_REPLICAS=$(kubectl --context "$KUBE_CONTEXT" -n tailwind-internal \
  get deployment api -o jsonpath='{.spec.replicas}')
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal scale deployment/api --replicas=0
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/api --timeout=5m
```

API와 관련 쓰기가 모두 중지됐는지 확인한 뒤 DB 백업·복구 가능 여부·migration ledger·대상 테이블 row 수를 확인합니다.
사전 검사가 실패하면 migration을 실행하지 않습니다.

```bash
read -r -p '사전 검사 Job의 고유 이름: ' PORTAL_PRECHECK_JOB
portal_permission_check "$PORTAL_PRECHECK_JOB" pre-migration
```

##### Migration Job 실행

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

##### 사후 검사

신규 설치와 기존 DB 갱신 모두 다음 검사를 통과해야 앱을 시작합니다.

```bash
read -r -p '사후 검사 Job의 고유 이름: ' PORTAL_POSTCHECK_JOB
portal_permission_check "$PORTAL_POSTCHECK_JOB" post-migration
```

실패하면 API와 쓰기 작업을 시작하지 않습니다. 신규 설치는 오류를 해결한 뒤 다시 검사합니다.
기존 DB는 백업·변경분을 확인하고 준비한 복구 절차를 따릅니다.

#### 4. 앱과 라우팅 적용

공용 MinIO 독립 설치·연결과 위 사후 검사를 마친 상태에서 Portal 리소스를 적용합니다.
기존 환경은 위에서 기록한 replica 수를 복원하고 신규 설치는 overlay의 replica 수로 시작합니다.

```bash
kubectl --context "$KUBE_CONTEXT" apply -k deploy/portal/k8s/overlays/prod
if [[ -n "${PORTAL_API_REPLICAS:-}" ]]; then
  kubectl --context "$KUBE_CONTEXT" -n tailwind-internal scale deployment/api --replicas="$PORTAL_API_REPLICAS"
fi
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/api --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/web --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/edge-nginx --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal get pods,pvc,ingress
```

아래 [공용 Traefik에 Portal 연결](#공용-traefik에-portal-연결) 절차로 감시 목록을 확장합니다.
PVC가 Pending이면 StorageClass/PV·노드 affinity를 먼저 확인합니다.

[접속 검증](../../shared/docs/operations/02-deploy.md#접속기능-검증)에 따라 API health,
Keycloak login/callback/logout, MinIO 시험 파일 업로드·다운로드를 확인해야 배포 완료입니다.
API가 정상 동작하고 검증이 끝난 뒤 중지했던 worker·Airflow 작업을 재개합니다.

### 공용 Traefik에 Portal 연결

Portal overlay는 `traefik-rbac.yaml`로 `etch-sso/traefik` ServiceAccount에 Portal namespace의
라우팅 권한을 부여합니다. `platform` checkout으로 기반 앱을 먼저 운영했다면
[선택 checkout](../../shared/docs/operations/01-checkout.md#선택-checkout)을 `all`로 확장합니다. `portal` 단독 선택은 기존 범위를 교체합니다.

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

Keycloak DB의 구성·백업과 Worker 교체 조건은 [Keycloak 서버 준비](../../keycloak/docs/01-prepare.md#서버-준비)를 따릅니다.

배포 완료 후 [최초 운영자 권한](02-access.md)을 확인합니다. 설정만 바꾸는 경우에는 [설정 변경 반영](03-operations.md#5-설정-변경-반영)을 따릅니다.
