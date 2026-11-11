# Portal 설치

[앱 안내](../README.md)

- [준비 조건](#준비-조건)
- [환경설정](#환경설정)
- [Keycloak client 등록](#keycloak-client-등록)
- [Migration·배포·검증](#migration배포검증)

## 준비 조건

| 대상 | 확인할 내용 |
| --- | --- |
| 배포 파일 | CP1의 [저장소 checkout](../../shared/docs/operations/01-checkout.md#저장소-clone) |
| 관리 도구 | Bash·Make·kubectl·Python 3, 대상 클러스터 kubeconfig와 namespace·Secret·Job·앱 리소스 적용 권한 |
| 이미지 | 실제 registry의 API·Web 고유 태그와 pull 인증. migration도 같은 API 이미지 사용 |
| DB | Portal 전용 외부 PostgreSQL의 DB·계정·접속과 `pg_trgm` extension. Keycloak DB와 별개 |
| 로그인 | Keycloak의 [설정 완료 확인](../../keycloak/docs/03-configure.md#설정-완료-확인)까지 완료 |
| 파일 저장소 | [공용 MinIO](../../minio/README.md)의 실제 접근 계정·bucket 권한과 필요한 업무 파일 PVC |
| 공개 접속 | 공용 Traefik·DNS/VIP·Portal 도메인 인증서 |

노드·연결 경로는 [사내 인프라 정보](../../shared/docs/infrastructure/README.md)에서 찾고 실제 클러스터를 조회합니다.
[overlay 입력](../k8s/overlays/prod/README.md#원본과-입력)의 이미지·스토리지 placeholder를 실제 값으로 바꿔야 합니다.

## 환경설정

**목적:** API·Web 운영 입력을 작성하고 검사합니다. 이 단계는 클러스터를 변경하지 않습니다.

**실행 위치:** 관리 호스트의 저장소 루트입니다. 운영 입력은 `deploy/portal/env/prod/`가 소유하며 Git으로 전달됩니다. 인증서·개인키 파일은 CP1에 별도로 준비합니다.

### 1. env 파일 작성

| 파일 | 넣는 내용 | 주의할 점 |
| --- | --- | --- |
| `env/prod/api.env` | Portal 서버, DB·로그인·MinIO·업무 연동 설정과 비밀번호·토큰·인증 헤더 | API Secret `api-env`의 유일한 입력 |
| `env/prod/web.env` | 브라우저에서 사용할 Portal·API·파일 주소와 화면 링크 | 브라우저에 공개되므로 비밀번호·토큰을 입력하지 않음 |

API는 Django 업무 기능이 함께 실행되는 하나의 서버이므로 Assistant·Emails·Drone 등도 `api.env`의 기능별 구역으로 관리합니다.
Airflow 서버 자체의 설정은 `deploy/airflow/env/`, API에서 Airflow에 연결하는 설정은 `api.env`에 둡니다.

| 환경 폴더 | 사용처 |
| --- | --- |
| `env/prod/` | 사내 Kubernetes 운영 Portal |
| `env/test/` | API 자동 테스트 |

환경끼리 자동 상속하지 않습니다. 운영 Portal은 `env/prod/`의 파일만 사용합니다.

```bash
chmod 600 deploy/portal/env/prod/api.env deploy/portal/env/prod/web.env
vi deploy/portal/env/prod/api.env
vi deploy/portal/env/prod/web.env
```

1. `api.env`의 **1~4번 구역**에 Portal DNS, DB, 로그인, HTTPS 설정을 작성합니다. 공개 주소는 `etch.samsungds.net`입니다.
2. `api.env`에 MinIO endpoint와 Portal 접근 키를 작성합니다.
3. `web.env`에 같은 Portal 공개 주소와 파일 접근 주소를 작성합니다.
4. 연결할 업무 기능의 구역만 [전체 설정 설명](../../../docs/reference/01-configuration.md)을 보고 `api.env`에 추가합니다. 다른 환경 파일을 통째로 복사하면 dummy 주소나 다른 환경의 계정까지 가져옵니다.

API 파일의 구역 번호는 모든 환경에서 같고 설정이 없는 구역은 생략됩니다. timeout·cache 같은 선택 설정은 입력값과 코드 기본값을 확인하며, 빈 값과 변수 생략은 의미가 다를 수 있습니다.

### 2. 서로 맞춰야 하는 값

| 기준 | 함께 확인할 항목 |
| --- | --- |
| Portal 공개 주소 | API의 `FRONTEND_BASE_URL`, CORS·CSRF 주소, `DJANGO_ALLOWED_HOSTS`, Web의 `VITE_SITE_URL`, Ingress host·TLS |
| Portal API 주소 | Web의 `VITE_BACKEND_URL`은 Portal origin이며 reverse proxy가 `/api/`·`/auth/`를 API로 전달. `PUBLIC_API_BASE_URL`은 운영 env 검사 대상이며 라우팅·URL 생성에는 사용하지 않음 |
| Portal 로그인 | `OIDC_REDIRECT_URI`와 Keycloak Portal client의 허용 callback |
| Portal client 계정 | API의 `OIDC_CLIENT_ID`·`OIDC_CLIENT_SECRET`과 Keycloak에 등록한 Portal client |
| 파일 저장소 계정 | API의 `MINIO_ACCESS_KEY`·`MINIO_SECRET_KEY`와 실제 MinIO 접근 계정 |

`DJANGO_ALLOWED_HOSTS`에는 health probe용 `localhost`도 포함합니다(예: `etch.samsungds.net,api,localhost`).

**로그인 입력:** Portal은 `OIDC_PROVIDER=keycloak`만 지원하며 아래 값을 `api.env`에 입력합니다. Portal client secret과 사내 OIDC client secret은 서로 다른 값입니다.

| 키 | 값 |
| --- | --- |
| `OIDC_PROVIDER` | `keycloak` |
| `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` | Portal 전용 client. 사내 AD FS client와 별개 |
| `OIDC_ISSUER` | Keycloak `etch` realm discovery의 issuer와 동일 |
| `OIDC_AUTH_URL`, `OIDC_LOGOUT_URL` | 브라우저가 접근하는 공개 Keycloak endpoint |
| `OIDC_TOKEN_URL`, `OIDC_JWKS_URL` | API가 호출하는 endpoint. cluster 내부 URL 사용 가능 |
| `OIDC_REDIRECT_URI` | Portal callback. Keycloak client 허용 callback으로 등록 |
| `FRONTEND_BASE_URL` | Portal 공개 주소. client의 web origin·logout redirect로 등록 |

**파일 저장소:** MinIO의 설치·credential·Ingress·PVC는 [독립 MinIO 앱](../../minio/README.md)이 소유하며 Portal overlay는 MinIO 리소스를 만들지 않습니다.
API는 `MINIO_ENDPOINT=http://minio.minio.svc.cluster.local:9000`과 Portal 접근 키, Web은 `VITE_MINIO_ENDPOINT=https://s3.etch.samsungds.net`를 사용합니다.
업무 기능에서 요구하는 bucket·권한과 브라우저 파일 읽기·업로드의 CORS는 실제 Portal origin에서 확인합니다.

**브라우저 공개값:** Web의 `VITE_*`, `BACKEND_API_URL`, `BACKEND_URL`, `MINIO_ENDPOINT`는 브라우저 설정에 공개됩니다.
`BACKEND_API_URL`은 브라우저 API 주소의 fallback이므로 브라우저에서 접근 가능한 전체 origin URL을 넣습니다.

### 3. 입력 검사

```bash
make env-check APP=portal PROFILE=prod COMPONENT=api
make env-check APP=portal PROFILE=prod COMPONENT=web
make env-check APP=portal PROFILE=prod COMPONENT=client
```

**기대 결과:** 세 검사가 통과합니다. 필수값이 비어 있거나 임시값이면 실패합니다.
검사 통과는 필수 입력 확인이며 DB 접속이나 로그인 성공을 보장하지 않습니다. Airflow·RAG 등 선택 업무 연동은 필수로 검사하지 않으므로 사용할 때 endpoint와 계정을 별도로 확인합니다.

**다음 단계:** [Keycloak client 등록](#keycloak-client-등록). Secret 등록은 namespace를 만든 뒤 [배포 단계](#2-namespacesecrettls)에서 수행합니다.

## Keycloak client 등록

**목적:** Portal 전용 client·token mapper·앱 역할을 Keycloak에 등록합니다. 사내 IdP·User Profile·수신 mapper는 변경하지 않습니다.

**준비물:** [입력 검사](#3-입력-검사) 통과, Keycloak [설정 완료 확인](../../keycloak/docs/03-configure.md#설정-완료-확인).

### 1. 실행 위치와 입력

저장소 루트의 Bash에서 Keycloak이 설치된 context를 선택합니다. 등록 입력은 Portal `api.env`의 [로그인 입력](#2-서로-맞춰야-하는-값) 중 `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_ISSUER`, `OIDC_REDIRECT_URI`, `FRONTEND_BASE_URL`만 사용하며 Keycloak env는 읽지 않습니다.

```bash
kubectl config get-contexts
read -r -p 'Keycloak이 설치된 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
```


### 2. client 등록

```bash
make keycloak-portal-client-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_PORTAL_ENV="$PWD/deploy/portal/env/prod/api.env"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/portal-keycloak-client
```

명령은 입력 검사 → 관리 ConfigMap·`portal-keycloak-client` Secret 준비 → Job 실행 순서로 진행하고 완료를 기다립니다.

**기대 결과:** 로그 끝에 `portal-members 표준 그룹 준비 완료`가 있습니다. 실패하면 위 로그와 `kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso describe job portal-keycloak-client`로 원인을 확인합니다. issuer가 Keycloak 공개 URL의 `etch` realm과 다르면 Job이 중단됩니다.

### 3. 등록 결과

| 항목 | 내용 |
| --- | --- |
| 신원·소속 claim | 사내 claim 16개와 소속 2개를 ID Token·Access Token·UserInfo에 발급. [사용자 필드와 claim](../../keycloak/docs/03-configure.md#사용자-필드와-claim) |
| `groups` | `sdwt-groups` mapper가 SDWT 그룹 전체 경로 배열을 발급 |
| 앱 역할 | client 역할과 `resource_access.<client-id>.roles` mapper |
| 기본 그룹 | `portal-members` 그룹과 `portal-all-apps` 역할 연결 |

사용자에게 역할을 자동 부여하지 않습니다. 운영자가 조직 정책에 따라 그룹 구성원을 지정하고 제한 사용자에게는 개별 앱 역할을 부여합니다.
Portal은 발급된 client 역할로 앱 접근을 판단하며 `deptid`나 그룹 이름으로 앱 접근을 추정하지 않습니다.

SDWT CSV가 준비되면 [SDWT 공통 scope 연결](../../keycloak/docs/03-configure.md#sdwt-공통-scope-연결)로 `sdwt-groups` mapper를 공통 scope로 옮기고 Access Token 수명을 300초로 설정합니다.

**다음 단계:** [Migration·배포·검증](#migration배포검증). client 등록만으로 Portal API가 배포되지는 않습니다.

## Migration·배포·검증

**목적:** namespace·Secret·TLS 준비, DB migration, 앱·라우팅 적용, 실제 기능 검증을 수행합니다. 아래 명령은 실제 클러스터를 변경합니다.

**준비물:** [환경설정](#환경설정)·[Keycloak client 등록](#keycloak-client-등록) 완료, [overlay 입력](../k8s/overlays/prod/README.md#원본과-입력)의 실제 이미지·저장소 값, [공통 배포 준비](../../shared/docs/operations/02-deploy.md#배포-준비).

**실행 위치:** CP1의 checkout 루트입니다. 각 명령이 성공한 뒤 다음 명령을 실행합니다.

### 1. 대상과 입력 확인

```bash
kubectl config get-contexts
read -r -p '배포할 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
make server-check APP=portal PROFILE=prod
```

**기대 결과:** 대상 노드가 조회되고 `server-check`가 통과합니다. Keycloak 정상 스택을 Portal 배포 때문에 정적 YAML로 다시 적용하지 않습니다.
Portal 외부 PostgreSQL의 DB·계정·접속과 `pg_trgm` extension은 DB 담당자에게 확인합니다.

### 2. Namespace·Secret·TLS

```bash
kubectl --context "$KUBE_CONTEXT" apply -f deploy/portal/k8s/overlays/prod/namespace.yaml
make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT="$KUBE_CONTEXT"
make k8s-env APP=portal PROFILE=prod COMPONENT=web KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n etch-sso get secret traefik-tls
```

Portal 도메인 인증서는 [공용 TLS 등록](../../shared/docs/certificates/apply.md#2-공용-tls-secret-등록갱신--cp1)을 사용합니다. 업무 도메인을 이미 등록했다면 이 블록은 생략합니다.

```bash
read -r -p '업무 도메인 full chain 파일: ' PORTAL_CERT_FILE
read -r -p '업무 도메인 개인키 파일: ' PORTAL_KEY_FILE
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST=etch.samsungds.net \
  TLS_CERT_FILE="$PORTAL_CERT_FILE" TLS_KEY_FILE="$PORTAL_KEY_FILE"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

**기대 결과:** `tailwind-internal`에 `api-env`·`web-env` Secret이 있고 `etch-sso/traefik-tls`가 조회됩니다.

### 3. Migration

신규 DB는 `pg_trgm` extension을 준비한 뒤 앱 시작 전에 migration을 실행합니다. 같은 터미널에 남은 복원 입력을 쓰지 않도록 신규 설치에서는 `unset PORTAL_API_REPLICAS`를 실행합니다.
기존 DB 갱신은 적용할 migration의 SQL·데이터 변경과 관련 작업의 호환성을 검토하고, 아래 쓰기 중지·백업·사전 검사부터 진행합니다. 작업 중 API와 쓰기 작업을 재개하지 않습니다.
`migrate/kustomization.yaml`의 API 이미지가 앱 overlay와 동일해야 합니다.

#### 검사 Job 준비

같은 Bash 세션에서 아래 함수를 정의합니다. `portal_wait_job`은 Job의 성공·실패를 감지하고 로그를 출력하며 최대 15분 기다립니다.
`portal_permission_check`는 migration overlay에서 동일 이미지·namespace·`api-env` Secret의 검사 Job을 만들며 `backoffLimit=0`으로 자동 재시도하지 않습니다.
검사마다 사용하지 않은 Job 이름을 지정합니다. 같은 이름이 있으면 `create`가 중단하므로 먼저 기존 결과를 확인합니다.

```bash
portal_wait_job() (
  set -euo pipefail
  local name="$1" status
  for _ in $(seq 180); do
    status="$(kubectl --context "$KUBE_CONTEXT" -n tailwind-internal get job "$name" \
      -o jsonpath='{.status.succeeded}/{.status.failed}')"
    case "$status" in
      1/*) kubectl --context "$KUBE_CONTEXT" -n tailwind-internal logs "job/$name" --tail=100; return 0 ;;
      */[1-9]*)
        kubectl --context "$KUBE_CONTEXT" -n tailwind-internal logs "job/$name" --tail=100 >&2 || true
        echo "Job 실패: $name" >&2; return 1 ;;
    esac
    sleep 5
  done
  echo "Job 대기 시간 초과: $name" >&2
  return 1
)

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
  portal_wait_job "$check_name"
)
```

검사 명령은 DB를 읽기만 하며, 함수는 검사 Job을 클러스터에 생성합니다. 함수가 실패하면 `kubectl --context "$KUBE_CONTEXT" -n tailwind-internal describe job <이름>`으로 Pod 상태를 확인하고 다음 단계로 넘어가지 않습니다.

#### 기존 DB 갱신 전 쓰기 중지와 사전 검사

**신규 DB는 이 절을 건너뜁니다.** 업무 테이블이 없으므로 `pre-migration` 검사를 실행하지 않습니다.
기존 환경은 DB에 쓰는 worker·Airflow 작업을 중지하고 진행 중인 요청을 마친 뒤 API를 중지합니다. 중지한 작업과 API replica 수는 쓰기 재개 때 복원할 입력입니다.

```bash
PORTAL_API_REPLICAS=$(kubectl --context "$KUBE_CONTEXT" -n tailwind-internal \
  get deployment api -o jsonpath='{.spec.replicas}')
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal scale deployment/api --replicas=0
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/api --timeout=5m
```

API와 관련 쓰기가 모두 중지됐는지 확인한 뒤 DB 백업·복구 가능 여부·migration ledger·대상 테이블 row 수를 확인합니다. 사전 검사가 실패하면 migration을 실행하지 않습니다.

```bash
read -r -p '사전 검사 Job의 고유 이름: ' PORTAL_PRECHECK_JOB
portal_permission_check "$PORTAL_PRECHECK_JOB" pre-migration
```

#### Migration Job 실행

```bash
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal get job portal-migrate --ignore-not-found
```

최초 설치라면 Job이 없습니다. 이전 완료 Job이 있고 새 migration을 수행할 때는 완료 상태와 백업을 확인한 뒤 해당 Job만 삭제하고 아래 블록으로 재생성합니다. DB·PVC는 삭제하지 않습니다.
진행 중이거나 실패한 Job이면 로그·DB 원인부터 확인하고 중복 실행하지 않습니다.

```bash
kubectl --context "$KUBE_CONTEXT" apply -k deploy/portal/k8s/overlays/prod/migrate
portal_wait_job portal-migrate
```

`portal-migrate`는 자동 재시도하지 않습니다(`backoffLimit: 0`). 실패하면 앱 배포를 진행하지 않고 `describe job`·Job Pod 로그로 DB 연결과 migration 오류를 확인합니다.

#### 사후 검사

신규 설치와 기존 DB 갱신 모두 다음 검사를 통과해야 앱을 시작합니다.

```bash
read -r -p '사후 검사 Job의 고유 이름: ' PORTAL_POSTCHECK_JOB
portal_permission_check "$PORTAL_POSTCHECK_JOB" post-migration
```

실패하면 API와 쓰기 작업을 시작하지 않습니다. 신규 설치는 오류를 해결한 뒤 다시 검사하고, 기존 DB는 백업·변경분을 확인해 준비한 복구 절차를 따릅니다.

### 4. 앱 적용

사후 검사를 통과한 상태에서 Portal 리소스를 적용합니다. 기존 환경은 위에서 기록한 replica 수를 복원하고 신규 설치는 overlay의 replica 수로 시작합니다.

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

**실패 확인:** PVC가 Pending이면 StorageClass/PV·노드 affinity를 먼저 확인합니다. rollout이 끝나지 않으면 `get events`와 Pod 로그를 확인합니다.

### 5. 공용 Traefik에 Portal 연결

Portal overlay의 `traefik-rbac.yaml`이 `etch-sso/traefik` ServiceAccount에 Portal namespace의 라우팅 권한을 부여합니다.

```bash
make ingress-connect APP=portal KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" rollout status deployment/traefik -n etch-sso --timeout=3m
kubectl --context "$KUBE_CONTEXT" -n etch-sso get deployment traefik \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].args}{"\n"}'
```

이 명령은 `portal-traefik` Role·RoleBinding과 공용 ServiceAccount 연결을 확인하고 감시 목록에 `tailwind-internal`만 추가합니다.
기존 감시 목록과 replica·nodeSelector·affinity·VIP annotation은 보존하며 RBAC를 생성·삭제하거나 다른 앱을 재배포하지 않습니다. 이미 연결됐거나 전체 namespace를 감시하면 변경하지 않습니다.

**기대 결과:** Traefik args의 감시 namespace에 `tailwind-internal`이 포함됩니다.
**실패 확인:** controller·권한이 없거나 실행 중 동시 변경이 감지되면 실패합니다. 원인을 확인한 뒤 같은 명령으로 다시 검사합니다. Traefik 재기동 중 개별 연결은 재시도가 필요할 수 있습니다.

### 6. 접속 검증

[접속 검증](../../shared/docs/operations/02-deploy.md#접속기능-검증)에 따라 API health, Keycloak login/callback/logout, MinIO 시험 파일 업로드·다운로드를 확인해야 배포 완료입니다.
시험 계정으로 신원 claim, 필요한 소속·그룹과 앱 접근 판정을 확인합니다. 기존 환경은 검증이 끝난 뒤 중지했던 worker·Airflow 작업을 재개합니다.

**다음 단계:** [최초 운영자 권한](02-access.md). 이후 설정만 바꾸는 경우에는 [설정 변경 반영](03-operations.md#설정-변경-반영)을 따릅니다.
