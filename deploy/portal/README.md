# Portal 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

Portal(API·Web·edge-nginx)을 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 업무 Portal의 API(Django)·Web·reverse proxy를 사내 Kubernetes에 배포 |
| namespace | `tailwind-internal` (Deployment `api`, `web`, `edge-nginx`) |
| 공개 주소 | `https://etch.samsungds.net`, health `/api/v1/health/` |
| 배포 명령 | `make ops-deploy APP=portal` = 준비 검사 → `portal-check` → `portal-image` → `keycloak-portal-client-setup` → `portal-up` → `portal-smoke` → 대조 |
| 이미지 | 사내 Zot의 `portal-api`·`portal-web`. tag는 `apps/portal/api`·`web` 소스 해시. `portal-image`가 이 checkout에서 빌드해 push |
| `portal-up`이 하는 일 | namespace·Secret(`api-env`, `web-env`) 등록 → 필요하면 migration → 앱 적용 → 공용 Traefik 연결 → 배포 기록 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, 세 Deployment Ready |
| 먼저 필요한 것 | 공용 Traefik(ingress), Keycloak 설정 완료, MinIO, Registry, 외부 PostgreSQL(`pg_trgm`), 업무 도메인 공용 TLS, 빌드 도구 |

## 구성

- 접속: DNS → APP VIP 443 → 공용 Traefik → Ingress `portal` → `edge-nginx`. edge-nginx가 같은 origin의 `/api/`·`/auth/`를 API로 전달합니다. `tailwind-internal` namespace 감시는 `portal-up`이 공용 Traefik에 연결하고, 인증서는 공용 `etch-sso/traefik-tls`로 관리합니다.
- DB: Portal 전용 외부 PostgreSQL의 DB·계정과 `pg_trgm` extension을 씁니다. Keycloak DB와 별개이며 이 배포는 DB를 만들지 않습니다.
- 로그인: [Keycloak](../keycloak/README.md)의 `etch` realm에 Portal 전용 client를 둡니다. client·token mapper·앱 역할은 `keycloak-portal-client-setup` 단계가 API env로 등록합니다([등록 결과](docs/01-install.md#keycloak-client-등록)).
- 파일 저장소: [공용 MinIO](../minio/README.md)가 설치·credential·Ingress·PVC를 소유하고 Portal overlay는 MinIO 리소스를 만들지 않습니다.
- 이미지: [Registry](../registry/README.md)에 올린 API·Web 이미지를 씁니다. overlay의 tag `auto`를 배포 도구가 소스 내용으로 정한 tag로 바꾸고, migration Job도 같은 API 이미지를 씁니다.
- 업무 파일: API의 `/data/<domain>` 볼륨은 기본 `emptyDir`입니다. 영속 데이터가 필요한 경로는 [운영 overlay](k8s/overlays/prod/README.md#원본과-입력)에서 실제 PVC로 교체합니다.

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사전 준비

완료 여부를 확인하고 미완료면 준비 작업을 수행합니다. 빌드 도구 설치와 공용 TLS 등록은 필요한 파일이 있으면 `make ops-deploy`의 준비 검사가 자동으로 실행합니다.
이 문서의 `PROD_API_ENV_FILE=<API env 경로>`는 DB 접속값을 넣은 저장소 밖 API env 사본의 경로입니다([입력](#입력)).

| 준비 작업 | 완료 확인 |
| --- | --- |
| 외부 PostgreSQL에 Portal용 DB·계정·`pg_trgm` extension 준비 | [외부 DB](../shared/docs/infrastructure/access.md#외부-db) |
| API env 사본에 DB 접속값 입력. 저장소 기본 `api.env`는 `DJANGO_DB_HOST`·`DJANGO_DB_NAME`·`DJANGO_DB_USER`·`DJANGO_DB_PASSWORD`가 비어 있으므로 저장소 밖 사본에 넣습니다([방법](docs/01-install.md#1-env-파일-작성)) | `make portal-check KUBE_CONTEXT="<context>" PROD_API_ENV_FILE=<API env 경로>`가 `Portal 입력·이미지·기존 Job 검사 통과`를 출력 |
| [공용 Traefik(ingress)](../shared/ingress/README.md)·[Keycloak](../keycloak/README.md)·[MinIO](../minio/README.md)·[Registry](../registry/README.md) 배포 | `make ops-preflight APP=portal KUBE_CONTEXT="<context>" PROD_API_ENV_FILE=<API env 경로>`의 `먼저 필요한 앱` 네 줄이 `[통과]` |
| Keycloak `etch` realm 설정 완료([Keycloak 가이드](../keycloak/README.md)의 A) | `make keycloak-smoke KUBE_CONTEXT="<context>"`의 마지막 줄이 `smoke 통과: keycloak` |
| MinIO에 Portal 접근 키·bucket 정책 등록, 같은 값이 API env의 `MINIO_ACCESS_KEY`·`MINIO_SECRET_KEY`에 있음 | [앱 접근 키와 bucket 정책 등록](../minio/docs/01-configuration.md#앱-접근-키와-bucket-정책-등록) |
| `etch.samsungds.net`을 SAN에 가진 `fullchain.crt`·`private.key`를 `deploy/shared/certs/<사이트>/`에 배치(현재 사이트 폴더 `etch.samsungds.net`). 공용 TLS 등록은 배포할 때 자동으로 합니다 | `make ops-preflight APP=portal KUBE_CONTEXT="<context>" PROD_API_ENV_FILE=<API env 경로>`의 `공용 TLS etch.samsungds.net` 줄이 `[통과]` 또는 `[자동 준비]` |
| 이미지 빌드 도구(nerdctl·BuildKit). 없으면 배포할 때 자동으로 설치합니다([이미지 빌드 도구](../README.md#이미지-빌드-도구)) | `make build-tools-check`가 `빌드 도구 준비 완료`를 출력 |
| DNS `etch.samsungds.net` → APP VIP 등록([DNS](../shared/docs/infrastructure/access.md#dns)). 없어도 배포는 진행합니다 | `getent hosts etch.samsungds.net` |

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `PROD_API_ENV_FILE` | API env(Secret `api-env`, Keycloak client 등록 입력) | `deploy/portal/env/prod/api.env`(DB 접속값이 비어 있음). DB 접속값을 넣은 저장소 밖 사본의 경로를 검사·배포·대조·진단의 모든 명령에 같게 붙임([운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)) |
| `PROD_WEB_ENV_FILE` | Web env(Secret `web-env`, 브라우저에 공개되므로 비밀값 없음) | `deploy/portal/env/prod/web.env`. 다른 값이 필요할 때만 저장소 밖 사본의 경로를 같은 방식으로 붙임 |
| `REGISTRY_PUSH_ENV` | `portal-image`가 쓰는 Registry push 계정 파일 | `deploy/registry/env/push-initial.env` |
| `PORTAL_MIGRATE` | `1`이면 API 이미지가 같아도 migration 실행 | 비움 |
| `PORTAL_RETRY_MIGRATE` | `1`이면 실패한 이전 `portal-migrate` Job을 지우고 migration을 다시 실행 | 비움. 실패 원인을 해결한 뒤에만 사용 |
| `PORTAL_IMAGE_TAG` | API·Web 이미지 tag를 직접 지정 | 비움(소스 내용으로 자동 결정). 지정하면 이미지·배포·대조 명령에 같은 값을 붙임 |

env 파일입니다. 키의 의미와 서로 맞춰야 하는 값은 [환경설정](docs/01-install.md#환경설정)에 있습니다.

| 파일 | 내용 |
| --- | --- |
| `env/prod/api.env` | Portal 서버, DB·로그인·MinIO·업무 연동 설정과 비밀번호·토큰. Secret `api-env`와 Keycloak client 등록의 유일한 입력 |
| `env/prod/web.env` | 브라우저가 쓰는 Portal·API·파일 주소와 화면 링크. 비밀값을 넣지 않음 |
| `env/prod/build.env` | 이미지 빌드에 쓰는 사내 미러의 base image·패키지 저장소. 내용이 바뀌면 이미지 tag도 바뀜 |

## A. 최초 설치

1. [변경] 배포. 준비 검사(빌드 도구 설치·공용 TLS 등록 포함) → env·이미지·이전 Job 검사 → 이미지 빌드·push → Keycloak client 등록 → Secret 등록·DB 스키마 migration·앱 적용·공용 Traefik 연결 → smoke → 대조를 순서대로 수행합니다.
   ```bash
   make ops-deploy APP=portal KUBE_CONTEXT="<context>" PROD_API_ENV_FILE=<API env 경로>
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. 출력에 `Portal 배포 완료`가 있습니다.
   DNS가 아직 없으면 smoke가 APP VIP로 확인해 `smoke 통과: portal (DNS 미등록 host 1개)`로 끝나고 JSON의 `pending`에 DNS 등록이 남습니다. [DNS](../shared/docs/infrastructure/access.md#dns) 절로 등록합니다.
   연결한 DB에 이미 운영 데이터가 있으면 migration은 되돌릴 수 없는 변경이므로 이 단계는 [승인]입니다([기준](../README.md#단계-표시)). 새로 만든 빈 DB면 [변경]입니다.
   실패하면 JSON의 `failedStep`에 따라 조치한 뒤 같은 명령을 다시 실행합니다.
   - `preflight`: `blocked`의 `item`을 봅니다. `앱 검사`면 `make portal-check KUBE_CONTEXT="<context>" PROD_API_ENV_FILE=<API env 경로>`를 직접 실행해 `오류:` 줄을 확인합니다. `누락된 필수 설정: DJANGO_DB_NAME`처럼 DB 키가 나오면 `PROD_API_ENV_FILE`을 붙이지 않았거나 사본에 DB 접속값이 없는 것입니다. `먼저 필요한 앱 <이름>`이면 그 앱의 가이드로 먼저 배포합니다. `공용 TLS etch.samsungds.net`이면 [인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급), `이미지 빌드 도구`면 [관리 호스트 sudo](../shared/docs/infrastructure/access.md#관리-호스트-sudo) 절로 준비합니다.
   - `portal-image`: `이미지 빌드 도구(nerdctl·buildctl)가 없습니다`면 [이미지 빌드 도구](../README.md#이미지-빌드-도구), `registry에 연결할 수 없습니다`면 [Registry](../registry/README.md) 배포·DNS·CA를 확인합니다. npm·pip·apt 오류면 사내 미러 문제이므로 아래 멈춤 조건을 따릅니다.
   - `keycloak-portal-client-setup`: `kubectl --context "<context>" -n etch-sso logs job/portal-keycloak-client --tail=20`으로 원인을 확인합니다. 성공하면 로그 끝에 `portal-members 표준 그룹 준비 완료`가 있습니다.
   - `portal-check`·`portal-up`·`portal-smoke`: [문제 해결과 멈춤 조건](#문제-해결과-멈춤-조건)의 표에서 같은 오류 문구를 찾습니다.
2. [조회] [C. 배포 후 확인](#c-배포-후-확인)

## B. 업데이트

`portal-image`는 소스가 바뀐 이미지만 새 tag로 빌드하고, `portal-up`은 실제 API 이미지와 새 tag를 비교해 migration 실행 여부를 스스로 정합니다.

- API 이미지가 같으면(env·manifest만 변경) migration을 생략하고 Secret 재등록과 세 Deployment 재시작만 합니다.
- API 이미지가 바뀌면 API를 0으로 줄임 → 사전 검사 Job → 완료된 이전 `portal-migrate` Job 삭제 → migration → 사후 검사 → 앱 적용 → 원래 replica 수로 복원 순서로 진행합니다.

먼저 이번 배포가 API를 멈추는지 확인합니다. 클러스터를 바꾸지 않습니다.

[검사]
```bash
make portal-check KUBE_CONTEXT="<context>" PROD_API_ENV_FILE=<API env 경로>
```

성공: `Portal 입력·이미지·기존 Job 검사 통과`와 `migration:` 줄. `migration:` 줄에 따라 아래 표의 행을 실행합니다.

| 출력의 `migration:` 줄 | 다음 행동 |
| --- | --- |
| `migration: API 이미지가 같아 생략` | [변경] 아래 표에서 해당하는 행을 바로 실행 |
| `migration: 실행 예정(API <n>개를 중지한 뒤 실행하고 복원)` | [승인] API 중단과 되돌릴 수 없는 스키마 변경을 보여 주고 [기존 DB 갱신 전 준비](docs/01-install.md#기존-db-갱신-전-준비)를 마친 뒤 승인받아 아래 표의 `apps/portal/api` 소스 행을 실행 |
| `migration: 실행 예정` | [변경] 실행 중인 API가 없는 경우입니다. 아래 표에서 해당하는 행을 바로 실행 |

| 변경 | 실행 |
| --- | --- |
| API env·Web env·manifest | [변경] `make ops-deploy APP=portal KUBE_CONTEXT="<context>" PROD_API_ENV_FILE=<API env 경로>`. 확인할 동작은 [설정 변경 반영](docs/03-operations.md#설정-변경-반영) |
| `apps/portal/api` 소스 | [승인] API tag가 바뀌어 migration이 실행됩니다. [기존 DB 갱신 전 준비](docs/01-install.md#기존-db-갱신-전-준비)로 DB 백업과 쓰기 작업 상태를 확인하고, API 중단과 스키마 변경을 보여 준 뒤 `make ops-deploy APP=portal KUBE_CONTEXT="<context>" PROD_API_ENV_FILE=<API env 경로>` |
| `apps/portal/web` 소스만 | [변경] Web 이미지만 새로 빌드되고 migration은 없습니다. `make ops-deploy APP=portal KUBE_CONTEXT="<context>" PROD_API_ENV_FILE=<API env 경로>` |
| DB·Keycloak·MinIO 계정 비밀번호 | [승인] 연결 영향과 교체 순서를 보여 준 뒤 실제 서비스 계정을 먼저 바꾸고 API env 사본을 맞춰 배포. [함께 바뀌는 대상](docs/03-operations.md#설정-변경-반영) |

`make ops-deploy`의 성공 기준은 A-1과 같고, 실행 뒤 [C. 배포 후 확인](#c-배포-후-확인)을 수행합니다.

## C. 배포 후 확인

1. [조회] 워크로드와 공개 주소를 확인합니다.
   ```bash
   kubectl --context "<context>" -n tailwind-internal get deployment,pods,jobs,pvc
   kubectl --context "<context>" -n tailwind-internal get ingress
   make portal-smoke KUBE_CONTEXT="<context>"
   ```
   성공: 세 Deployment READY, `portal-migrate` Complete, 마지막 줄이 `smoke 통과: portal`. 뒤에 `(DNS 미등록 host 1개)`가 붙어도 통과이며 DNS 등록만 남은 것입니다.
2. [변경] 최초 설치면 최초 운영자 계정에 [최초 운영자 권한](docs/02-access.md#keycloak-권한과-새-db-시작)을 부여합니다. 최초 운영자의 Keycloak username은 요청에 주어지는 입력입니다. 요청에 없으면 이 단계는 수행하지 않고 보고의 남은 일에 `Portal 최초 운영자 지정`을 적습니다.
3. [조회] 화면 기능을 확인합니다. [화면 기능 확인](../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 [로그인 callback → API → 로그아웃, 시험 파일 업로드·다운로드](../shared/docs/operations/02-deploy.md#접속기능-검증) 시나리오를 확인합니다.

## 문제 해결과 멈춤 조건

Pod·event·로그 조회는 [장애 조회](../README.md#장애-조회)의 명령을 namespace `tailwind-internal`로 실행합니다. Job 로그는 아래로 봅니다. 모두 [조회]입니다.

```bash
kubectl --context "<context>" -n etch-sso logs job/portal-keycloak-client --tail=20
kubectl --context "<context>" -n tailwind-internal logs job/portal-migrate --tail=100
```

| 증상 | 원인과 조치 |
| --- | --- |
| `누락된 필수 설정: <키>`, `실제 값으로 교체할 설정: <키>` | API env·Web env에 그 키의 값이 없음. [환경설정](docs/01-install.md#환경설정) 기준으로 값을 확인해 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)의 사본에 넣고 `PROD_API_ENV_FILE=<API env 경로>`(Web은 `PROD_WEB_ENV_FILE`)를 붙여 다시 실행 |
| `DJANGO_ALLOWED_HOSTS에 운영 health probe의 Host인 localhost를 추가하세요.` | API env 사본의 `DJANGO_ALLOWED_HOSTS`에 `localhost`를 더해 다시 실행([health 검사](docs/03-operations.md#health-검사)) |
| `이전 portal-migrate Job이 진행 중입니다` | 끝날 때까지 기다린 뒤 같은 명령 재실행. Job을 지우지 않음 |
| `migration 전 단계 실패` | API 중지·사전 검사 Job·이전 Job 정리에서 멈춤. DB는 그대로이고 API는 원래 replica 수로 복원됨. `kubectl --context "<context>" -n tailwind-internal get pods`로 API Pod가 Running인지 확인하고, 오류 문구의 원인을 해결한 뒤 같은 명령을 한 번 재실행(`PORTAL_RETRY_MIGRATE` 불필요) |
| `Job 실패: portal-keycloak-client` | 위 Job 로그로 원인 확인. `Portal issuer가 대상 Keycloak realm과 다릅니다.`면 API env 사본의 `OIDC_ISSUER`를 Keycloak 공개 URL + `/realms/etch`로 맞춤([서로 맞춰야 하는 값](docs/01-install.md#2-서로-맞춰야-하는-값)) |
| rollout 시간 초과 | event와 Pod 로그. API·edge-nginx의 probe는 [health 검사](docs/03-operations.md#health-검사). 원인을 해결하지 못하면 보고 |
| smoke 404 / 503 | Portal Ingress와 Traefik의 `tailwind-internal` 감시, Pod·Service endpoint를 조회. 감시 범위 문제면 [변경] `make ingress-connect APP=portal KUBE_CONTEXT="<context>"`([연결만 복구](docs/01-install.md#공용-traefik-연결)). 그 밖에는 B의 `make portal-check`를 실행해 `migration: API 이미지가 같아 생략`이면 [변경] `make ops-deploy APP=portal KUBE_CONTEXT="<context>" PROD_API_ENV_FILE=<API env 경로>`를 다시 실행(migration 없이 Secret 재등록과 재시작만 함). `migration: 실행 예정(API <n>개를 중지한 뒤 실행하고 복원)`이면 B의 [승인] 조건을 따름 |
| 로그인 반복·callback 실패 | API env의 issuer·redirect URI·client secret과 Keycloak client를 대조([서로 맞춰야 하는 값](docs/01-install.md#2-서로-맞춰야-하는-값)). 다르면 API env 사본을 맞춰 B의 `API env` 행으로 반영 |

다음이면 멈추고 보고합니다.

- `migration 단계 실패` 또는 `이전 portal-migrate Job이 실패 상태입니다`가 나온 경우. `portal-migrate` Job을 직접 지우거나 API replica 수를 손으로 바꾸지 않습니다. `kubectl --context "<context>" -n tailwind-internal logs job/portal-migrate --tail=100`의 원인을 보고하고, 메시지에 `API는 중지 상태입니다`가 있으면 그 사실과 이전 replica 수도 함께 보고합니다. 이전 replica 수는 Deployment에 기록돼 있어 재실행이 복원합니다. 원인이 해결된 뒤에만 [승인] `make ops-deploy APP=portal KUBE_CONTEXT="<context>" PROD_API_ENV_FILE=<API env 경로> PORTAL_RETRY_MIGRATE=1`로 다시 실행합니다.
- `migration 전 단계 실패`가 한 번 재실행한 뒤에도 반복되는 경우. `PORTAL_RETRY_MIGRATE=1`이나 `PORTAL_MIGRATE=1`을 붙이지 않습니다.
- `prod와 prod/migrate의 images에서 portal-api 버전을 일치시키세요`가 나온 경우. 앱 overlay와 migration overlay의 API 이미지가 다른 저장소 원본 문제이므로 overlay 파일을 고치지 않습니다.
- 이미지 빌드가 npm·pip·apt 사내 미러 오류로 실패한 경우. `build.env`나 Dockerfile을 고치지 않고 오류 마지막 20줄을 보고합니다.
- PVC가 Pending인 경우. PV·PVC를 지우거나 다시 만들지 않고 StorageClass/PV·노드 affinity를 조회해 보고합니다.
- DB·PVC·namespace 삭제가 필요해 보이는 경우. 실행하지 않습니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [설치 입력과 배포 동작](docs/01-install.md) | API env 사본 준비와 서로 맞춰야 하는 값, 입력 검사, Keycloak client 등록 입력·결과, 배포 단계별 동작, migration 준비·실패 대응, 공용 Traefik 연결 |
| [최초 권한 설정](docs/02-access.md) | 최초 운영자·앱 역할·데이터 권한, 비상 Django 관리자 계정 |
| [설정 변경과 운영 확인](docs/03-operations.md) | env 변경 반영과 확인할 동작, 함께 바뀌는 외부 대상, health 검사 |
| [운영 overlay](k8s/overlays/prod/README.md) | 이미지·Ingress·Traefik 권한·migration 입력과 업무 파일 볼륨 |
| [Keycloak client 등록 Job](k8s/jobs/keycloak-client/README.md) | 등록 Job의 원본 파일과 역할 |
