# Portal 설치 입력과 배포 동작

[Portal 가이드](../README.md)

설치·업데이트 절차는 [Portal 가이드](../README.md)에 있습니다. 이 문서는 env 입력의 의미, Keycloak client 등록 결과, 배포 도구가 단계마다 하는 일과 migration 준비·실패 대응입니다.

- [환경설정](#환경설정)
- [Keycloak client 등록](#keycloak-client-등록)
- [배포 단계와 도구 동작](#배포-단계와-도구-동작)
- [Migration](#migration)
- [공용 Traefik 연결](#공용-traefik-연결)

## 환경설정

API·Web 운영 입력을 작성합니다. 운영 입력은 `deploy/portal/env/prod/`가 소유하며 Git으로 전달됩니다. 작성과 검사는 클러스터를 변경하지 않고, Secret `api-env`·`web-env` 등록은 `portal-up`이 합니다.

### 1. env 파일 작성

| 파일 | 넣는 내용 | 주의할 점 |
| --- | --- | --- |
| `env/prod/api.env` | Portal 서버, DB·로그인·MinIO·업무 연동 설정과 비밀번호·토큰·인증 헤더 | API Secret `api-env`의 유일한 입력 |
| `env/prod/web.env` | 브라우저에서 사용할 Portal·API·파일 주소와 화면 링크 | 브라우저에 공개되므로 비밀번호·토큰을 입력하지 않음 |
| `env/prod/build.env` | `make portal-image`가 쓰는 사내 미러의 base image·패키지 저장소 | 각 Dockerfile이 선언한 ARG에만 build arg로 전달. 비밀번호·토큰을 넣지 않음 |

API는 Django 업무 기능이 함께 실행되는 하나의 서버이므로 Assistant·Emails·Drone 등도 `api.env`의 기능별 구역으로 관리합니다.
Airflow 서버 자체의 설정은 `deploy/airflow/env/`, API에서 Airflow에 연결하는 설정은 `api.env`에 둡니다.

| 환경 폴더 | 사용처 |
| --- | --- |
| `env/prod/` | 사내 Kubernetes 운영 Portal |
| `env/test/` | API 자동 테스트 |

환경끼리 자동 상속하지 않습니다. 기본 운영 입력은 `env/prod/`입니다. 관리 호스트의 외부 env를 사용하면 `PROD_API_ENV_FILE`·`PROD_WEB_ENV_FILE`에 실제 경로를 지정하고 검사·배포·대조의 모든 명령에 같은 경로를 전달합니다.

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

신규 설치용 Django 서명 키는 기본 API env에 있습니다. 기존 Portal 이전 시 운영 서명 키를 유지합니다. 외부 DB의 `DJANGO_DB_HOST`·`DJANGO_DB_NAME`·`DJANGO_DB_USER`·`DJANGO_DB_PASSWORD`는 실제 접속 정보를 입력합니다. DB·계정과 `pg_trgm` extension은 DB 담당자가 준비하며 Keycloak DB와 별개입니다.

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

[검사] `portal-check`와 `portal-up`이 같은 검사를 먼저 실행합니다. 파일만 따로 확인할 때 씁니다.

```bash
make env-check APP=portal PROFILE=prod COMPONENT=api
make env-check APP=portal PROFILE=prod COMPONENT=web
make env-check APP=portal PROFILE=prod COMPONENT=client
```

성공: 세 검사가 통과합니다. 필수값이 비어 있거나 임시값이면 실패합니다.
검사 통과는 필수 입력 확인이며 DB 접속이나 로그인 성공을 보장하지 않습니다. Airflow·RAG 등 선택 업무 연동은 필수로 검사하지 않으므로 사용할 때 endpoint와 계정을 별도로 확인합니다.

## Keycloak client 등록

Portal 전용 client·token mapper·앱 역할을 Keycloak에 등록합니다. 사내 IdP·User Profile·수신 mapper는 변경하지 않습니다. `make ops-deploy APP=portal`의 두 번째 단계(`keycloak-portal-client-setup`)가 수행하며 Keycloak의 [설정 완료 확인](../../keycloak/docs/02-configure.md#설정-완료-확인)이 끝나 있어야 합니다. client 등록만으로 Portal API가 배포되지는 않습니다.

### 입력

등록 입력은 Portal `api.env`의 [로그인 입력](#2-서로-맞춰야-하는-값) 중 `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_ISSUER`, `OIDC_REDIRECT_URI`, `FRONTEND_BASE_URL`만 사용하며 Keycloak env는 읽지 않습니다.

### 실행과 확인

[변경] 등록만 다시 실행할 때 씁니다. `<context>`는 Keycloak이 설치된 context입니다.

```bash
make keycloak-portal-client-setup KUBE_CONTEXT="<context>"
```

명령은 입력 검사 → 관리 ConfigMap·`portal-keycloak-client` Secret 준비 → Job 실행 순서로 진행하고 완료를 기다립니다.

[조회]

```bash
kubectl --context "<context>" -n etch-sso logs job/portal-keycloak-client
kubectl --context "<context>" -n etch-sso describe job portal-keycloak-client
```

성공: 로그 끝에 `portal-members 표준 그룹 준비 완료`가 있습니다. issuer가 Keycloak 공개 URL의 `etch` realm과 다르면 Job이 중단됩니다.

### 등록 결과

| 항목 | 내용 |
| --- | --- |
| 신원·소속 claim | 사내 claim 16개와 소속 2개를 ID Token·Access Token·UserInfo에 발급. [사용자 필드와 claim](../../keycloak/docs/02-configure.md#사용자-필드와-claim) |
| `groups` | `sdwt-groups` mapper가 SDWT 그룹 전체 경로 배열을 발급 |
| 앱 역할 | client 역할과 `resource_access.<client-id>.roles` mapper |
| 기본 그룹 | `portal-members` 그룹과 `portal-all-apps` 역할 연결 |

사용자에게 역할을 자동 부여하지 않습니다. 운영자가 조직 정책에 따라 그룹 구성원을 지정하고 제한 사용자에게는 개별 앱 역할을 부여합니다([최초 권한 설정](02-access.md)).
Portal은 발급된 client 역할로 앱 접근을 판단하며 `deptid`나 그룹 이름으로 앱 접근을 추정하지 않습니다.

SDWT CSV가 준비되면 [SDWT 공통 scope 연결](../../keycloak/docs/02-configure.md#sdwt-공통-scope-연결)로 `sdwt-groups` mapper를 공통 scope로 옮기고 Access Token 수명을 300초로 설정합니다.

## 배포 단계와 도구 동작

`make ops-deploy APP=portal KUBE_CONTEXT="<context>"`는 아래 타깃을 순서대로 실행하고 [배포 상태 대조](../../shared/docs/operations/04-drift.md)까지 수행합니다. 관리 호스트에는 Bash·Make·kubectl·Python 3과 대상 클러스터의 namespace·Secret·Job·앱 리소스 적용 권한이 있는 kubeconfig가 필요합니다.

| 순서 | 타깃 | 하는 일 |
| --- | --- | --- |
| 1 | `portal-image` | API·Web 이미지 중 사내 이미지 저장소에 없는 tag만 이 checkout에서 빌드해 push |
| 2 | `keycloak-portal-client-setup` | [Keycloak client 등록](#keycloak-client-등록) Job 실행 |
| 3 | `portal-check` | env(api·client·web) 검사, overlay 이미지의 자리표시자와 앱·migration의 API 이미지 일치, 노드 조회, 이전 `portal-migrate` Job 상태 확인. 클러스터를 변경하지 않고 `migration: 실행 예정` 또는 `migration: API 이미지가 같아 생략`을 출력 |
| 4 | `portal-up` | 같은 검사 → namespace 적용 → Secret `api-env`·`web-env` 등록 → 필요하면 [migration](#migration) → 렌더한 overlay 적용 → 기존 설치는 Deployment 재시작 → 세 Deployment rollout 대기(각 10분) → [공용 Traefik 연결](#공용-traefik-연결) → 배포 기록 |
| 5 | `portal-smoke` | 워크로드 Ready와 `/api/v1/health/`의 HTTPS 응답을 조회 전용으로 확인 |

[변경] 한 단계만 다시 실행할 때는 같은 입력을 붙여 타깃을 직접 실행합니다.

```bash
make portal-up KUBE_CONTEXT="<context>"
```

성공: `Portal 배포 완료. 로그인·파일 송수신은 사용자가 확인합니다.`

**이미지 tag:** overlay의 `newTag: auto`를 배포 도구가 실제 tag로 바꿉니다. tag는 각 소스 폴더(`apps/portal/api`, `apps/portal/web`)와 [build.env](../env/prod/build.env) 내용으로 정해지므로 소스가 바뀌면 자동으로 새 tag가 됩니다. `PORTAL_IMAGE_TAG=<tag>`로 직접 지정할 수 있고, 이 경우 이미지·검사·배포·대조 명령에 같은 값을 붙입니다.
migration·검사 Job과 대조(`make drift-check`)도 같은 tag로 렌더합니다. `kubectl apply -k`로 overlay를 직접 적용하면 tag가 `auto`로 남으므로 사용하지 않습니다.

[조회] 적용될 리소스와 tag는 아래 명령으로 봅니다. 클러스터를 변경하지 않으며 출력은 확인용입니다.

```bash
python3 deploy/portal/scripts/up.py --context "<context>" --render app
```

**Secret과 재시작:** Secret 변경은 Pod에 자동 반영되지 않으므로 `portal-up`은 기존 설치를 배포마다 다시 시작합니다. API 이미지가 같으면 migration 없이 Secret 재등록과 세 Deployment 재시작만 합니다.

## Migration

`portal-up`은 아래 중 하나일 때만 migration을 실행합니다.

- 처음 설치(API Deployment가 없음)
- 실제 API 이미지와 overlay로 정한 API 이미지가 다름
- 이전 실행이 API를 멈춘 채 끝남
- `PORTAL_MIGRATE=1`을 붙임(이미지가 같아도 실행)

실행 순서와 Job입니다.

| 순서 | 동작 | 내용 |
| --- | --- | --- |
| 1 | API 중지 | 실행 중인 API가 있으면 replica 수를 Deployment annotation `deploy.etch/replicas-before-migration`에 기록하고 0으로 줄인 뒤 API Pod가 모두 사라질 때까지 대기 |
| 2 | 사전 검사 Job `portal-precheck-<시각>` | 기존 설치에서만 실행. 신규 DB는 업무 테이블이 없어 생략 |
| 3 | 이전 Job 정리 | 완료된 이전 `portal-migrate` Job만 삭제. 실패한 Job은 `PORTAL_RETRY_MIGRATE=1`일 때만 삭제. DB·PVC는 삭제하지 않음 |
| 4 | Job `portal-migrate` | `manage.py migrate --noinput`. 자동 재시도 없음(`backoffLimit: 0`) |
| 5 | 사후 검사 Job `portal-postcheck-<시각>` | 신규 설치와 기존 DB 갱신 모두 통과해야 앱을 적용 |
| 6 | 앱 적용과 복원 | overlay 적용 뒤 API를 기록한 replica 수로 되돌리고 annotation을 지움 |

검사 Job은 migration overlay와 같은 이미지와 Secret으로 `manage.py check_access_permission_integrity --phase pre-migration|post-migration`을 실행합니다. 각 Job은 최대 15분 동안 결과를 기다리고, 끝난 검사 Job은 1시간 뒤 자동으로 삭제됩니다(`ttlSecondsAfterFinished`). Job이 실패하면 로그 끝 30줄이 배포 오류 출력에 함께 나옵니다. `portal-migrate` Job은 다음 migration까지 남습니다.
migration을 실행해야 하는데 진행 중인 `portal-migrate` Job이 있으면 `portal-check`와 `portal-up`이 중단합니다. 검사·migration Job은 `portal-up`이 `scripts/migration-job.sh`로 만듭니다.

### 기존 DB 갱신 전 준비

API 이미지가 바뀌는 업데이트 전에 수행합니다. API 중지와 복원은 `portal-up`이 하지만 아래는 도구가 하지 않습니다.

1. 적용할 migration의 SQL·데이터 변경과 관련 작업의 호환성을 검토합니다.
2. DB에 쓰는 worker·Airflow 작업을 중지하고 진행 중인 요청을 마칩니다. 중지한 작업은 쓰기 재개 때 복원할 입력입니다.
3. DB 백업·복구 가능 여부·migration ledger·대상 테이블 row 수를 확인합니다.
4. 배포와 [접속·기능 검증](../../shared/docs/operations/02-deploy.md#접속기능-검증)이 끝난 뒤 중지했던 worker·Airflow 작업을 재개합니다. 그 전에는 쓰기 작업을 재개하지 않습니다.

신규 DB는 `pg_trgm` extension을 준비한 뒤 배포합니다.

### 실패했을 때

[조회]

```bash
kubectl --context "<context>" -n tailwind-internal get jobs
kubectl --context "<context>" -n tailwind-internal describe job portal-migrate
kubectl --context "<context>" -n tailwind-internal logs job/portal-migrate --tail=100
```

- `migration 전 단계 실패`: API 중지·사전 검사·이전 Job 정리에서 멈춘 경우입니다. migration을 시작하지 않았으므로 DB는 그대로이고 `portal-up`이 API를 원래 replica 수로 되돌립니다. 원인을 해결한 뒤 `PORTAL_RETRY_MIGRATE` 없이 같은 명령을 다시 실행합니다. 이전 migration이 실패한 뒤의 재시도에서 멈추면 DB 상태를 알 수 없으므로 API를 되돌리지 않고 아래 `migration 단계 실패`로 처리합니다.
- `migration 단계 실패`: migration이나 사후 검사가 실패한 경우이며 앱을 적용하지 않습니다. 오류 문구에 `API는 중지 상태입니다`가 있으면 API는 0인 채로 남아 있습니다.
- 신규 설치는 오류를 해결한 뒤 다시 실행합니다. 기존 DB는 백업·변경분을 확인해 준비한 복구 절차를 따릅니다.
- [승인] 원인을 해결한 뒤 `PORTAL_RETRY_MIGRATE=1`을 붙여 다시 실행합니다. 실패한 Job을 지우고 migration을 이어서 진행하며 API를 원래 replica 수로 복원합니다. Job을 직접 지우지 않습니다.

```bash
make ops-deploy APP=portal KUBE_CONTEXT="<context>" PORTAL_RETRY_MIGRATE=1
```

## 공용 Traefik 연결

`portal-up`의 마지막 단계입니다. Portal overlay의 `traefik-rbac.yaml`이 `etch-sso/traefik` ServiceAccount에 Portal namespace의 라우팅 권한을 부여하고, 연결 단계가 `portal-traefik` Role·RoleBinding과 공용 ServiceAccount 연결을 확인한 뒤 감시 목록에 `tailwind-internal`만 추가합니다.
기존 감시 목록과 replica·nodeSelector·affinity·VIP annotation은 보존하며 RBAC를 생성·삭제하거나 다른 앱을 재배포하지 않습니다. 이미 연결됐거나 전체 namespace를 감시하면 변경하지 않습니다.

[조회]

```bash
kubectl --context "<context>" -n etch-sso get deployment traefik \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].args}{"\n"}'
```

성공: Traefik args의 감시 namespace에 `tailwind-internal`이 포함됩니다.

[변경] controller·권한이 없거나 실행 중 동시 변경이 감지되면 연결이 실패합니다. 원인을 확인한 뒤 연결만 다시 실행합니다. Traefik 재기동 중 개별 연결은 재시도가 필요할 수 있습니다.

```bash
make ingress-connect APP=portal KUBE_CONTEXT="<context>"
```
