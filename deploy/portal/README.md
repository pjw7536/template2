# Portal 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

Portal(API·Web·edge-nginx)을 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인]·[사람])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 업무 Portal의 API(Django)·Web·reverse proxy를 사내 Kubernetes에 배포 |
| namespace | `tailwind-internal` (Deployment `api`, `web`, `edge-nginx`) |
| 공개 주소 | `https://etch.samsungds.net`, health `/api/v1/health/` |
| 배포 명령 | `make ops-deploy APP=portal` = `portal-image` → `keycloak-portal-client-setup` → `portal-check` → `portal-up` → `portal-smoke` → 대조 |
| 이미지 | `store.etch.samsungds.net/tailwind/api`·`web`, tag는 `apps/portal/api`·`web` 소스 해시. `portal-image`가 이 checkout에서 빌드해 push |
| `portal-up`이 하는 일 | namespace·Secret(`api-env`, `web-env`) 등록 → 필요하면 migration → 앱 적용 → 공용 Traefik 연결 → 배포 기록 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, 세 Deployment Ready |
| 먼저 필요한 것 | Keycloak 설정 완료, MinIO, Registry, 외부 PostgreSQL(`pg_trgm`), 업무 도메인 공용 TLS, 빌드 도구 |

## 구성

- 접속: DNS → APP VIP 443 → 공용 Traefik → Ingress `portal` → `edge-nginx`. edge-nginx가 같은 origin의 `/api/`·`/auth/`를 API로 전달합니다. `tailwind-internal` namespace 감시는 `portal-up`이 공용 Traefik에 연결하고, 인증서는 공용 `etch-sso/traefik-tls`로 관리합니다.
- DB: Portal 전용 외부 PostgreSQL의 DB·계정과 `pg_trgm` extension을 씁니다. Keycloak DB와 별개이며 이 배포는 DB를 만들지 않습니다.
- 로그인: [Keycloak](../keycloak/README.md)의 `etch` realm에 Portal 전용 client를 둡니다. client·token mapper·앱 역할은 `keycloak-portal-client-setup` 단계가 `api.env`로 등록합니다([등록 결과](docs/01-install.md#keycloak-client-등록)).
- 파일 저장소: [공용 MinIO](../minio/README.md)가 설치·credential·Ingress·PVC를 소유하고 Portal overlay는 MinIO 리소스를 만들지 않습니다.
- 이미지: [Registry](../registry/README.md)에 올린 API·Web 이미지를 씁니다. overlay의 tag `auto`를 배포 도구가 소스 내용으로 정한 tag로 바꾸고, migration Job도 같은 API 이미지를 씁니다.
- 업무 파일: API의 `/data/<domain>` 볼륨은 기본 `emptyDir`입니다. 영속 데이터가 필요한 경로는 [운영 overlay](k8s/overlays/prod/README.md#원본과-입력)에서 실제 PVC로 교체합니다.

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사람이 하는 일

클러스터 밖 작업입니다. 오른쪽 명령으로 완료 여부를 먼저 확인하고, 미완료일 때만 요청합니다.

| 일 | 완료 확인 |
| --- | --- |
| 외부 PostgreSQL DB·계정·`pg_trgm` 준비와 접속값을 `api.env`에 반영([방법](docs/01-install.md#환경설정)) | A-1의 `portal-check`가 env를 통과. 실제 접속은 migration Job 결과로 확인 |
| MinIO의 Portal 접근 키·bucket 정책 등록 | 사용자 보고 |
| 인증서 파일 배치, DNS `etch.samsungds.net` → APP VIP | `ls -l deploy/shared/certs/etch.samsungds.net/fullchain.crt`, `getent hosts etch.samsungds.net` |
| 최초 운영자 `portal-admin` 지정·그룹 가입(Keycloak, [방법](docs/02-access.md#keycloak-권한과-새-db-시작)) | 사용자 보고 |
| 선택: 브라우저 로그인·callback·logout·파일 업로드·다운로드 확인([시나리오](../shared/docs/operations/02-deploy.md#접속기능-검증)) | 사용자 보고 |

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `PROD_API_ENV_FILE` | API env(Secret `api-env`, Keycloak client 등록 입력) | `deploy/portal/env/prod/api.env` |
| `PROD_WEB_ENV_FILE` | Web env(Secret `web-env`, 브라우저에 공개되므로 비밀값 없음) | `deploy/portal/env/prod/web.env` |
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

1. [검사] [이미지 빌드 도구](../README.md#이미지-빌드-도구)를 준비하고 사전 검사를 합니다. env·이전 migration Job을 확인합니다.
   ```bash
   make portal-check KUBE_CONTEXT="<context>"
   ```
   성공: `Portal 입력·이미지·기존 Job 검사 통과`.
2. [변경] 공용 TLS 등록: `etch.samsungds.net`을 [공용 TLS 등록](../README.md#공용-tls-등록)합니다.
3. [변경] 배포. 이미지 빌드·push, Keycloak client 등록, DB 스키마 migration을 포함합니다.
   ```bash
   make ops-deploy APP=portal KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.
   - `portal-image` 실패: `nerdctl·buildctl`이 없으면 [이미지 빌드 도구](../README.md#이미지-빌드-도구), `registry에 연결할 수 없습니다`면 [Registry](../registry/README.md) 배포·DNS·CA를 확인합니다. npm·pip·apt 오류면 사내 미러 문제이므로 오류 마지막 20줄과 함께 보고합니다.
   - `keycloak-portal-client-setup` 실패: `kubectl --context "<context>" -n etch-sso logs job/portal-keycloak-client --tail=20`으로 원인을 확인합니다. 성공하면 로그 끝에 `portal-members 표준 그룹 준비 완료`가 있습니다.
4. [조회] [C. 배포 후 확인](#c-배포-후-확인)
5. [사람] 최초 운영자 권한과 브라우저 기능 확인: [사람이 하는 일](#사람이-하는-일)의 마지막 두 행입니다.

## B. 업데이트

`portal-image`는 소스가 바뀐 이미지만 새 tag로 빌드하고, `portal-up`은 실제 API 이미지와 새 tag를 비교해 스스로 판단합니다.

먼저 이번 배포가 API를 멈추는지 확인합니다. 클러스터를 바꾸지 않습니다.

[검사]
```bash
make portal-check KUBE_CONTEXT="<context>"
```

| 출력의 `migration:` 줄 | 다음 행동 |
| --- | --- |
| `migration: API 이미지가 같아 생략` | 아래 표에서 [변경] 행을 바로 실행 |
| `migration: 실행 예정(API <n>개를 중지한 뒤 실행하고 복원)` | [승인] 대상입니다. API 중단과 되돌릴 수 없는 스키마 변경을 알리고 DB 백업 여부를 확인받은 뒤 실행 |
| `migration: 실행 예정` | 실행 중인 API가 없는 경우입니다. 바로 실행 |

| 상황 | `portal-up`의 동작 |
| --- | --- |
| API 이미지가 같음(env·manifest만 변경) | migration 생략, Secret 재등록, 세 Deployment 재시작 |
| API 이미지가 바뀜 | API를 0으로 줄임 → 사전 검사 Job → 완료된 이전 `portal-migrate` Job 삭제 → migration → 사후 검사 → 앱 적용 → 원래 replica 수로 복원 |

| 변경 | 실행 |
| --- | --- |
| `api.env`·`web.env`·manifest | [변경] `make ops-deploy APP=portal KUBE_CONTEXT="<context>"`. 확인할 동작은 [설정 변경 반영](docs/03-operations.md#설정-변경-반영) |
| `apps/portal/api` 소스 | API tag가 바뀝니다. [승인] migration 동안 API가 중단되고 스키마 변경은 되돌릴 수 없습니다. DB 백업 여부를 함께 확인한 뒤 `make ops-deploy APP=portal KUBE_CONTEXT="<context>"`. 사람이 먼저 할 준비는 [Migration](docs/01-install.md#migration) |
| `apps/portal/web` 소스만 | Web 이미지만 새로 빌드되고 migration은 없습니다. [변경] `make ops-deploy APP=portal KUBE_CONTEXT="<context>"` |
| DB·Keycloak·MinIO 계정 비밀번호 | 멈추고 사람에게 묻기(실제 서비스 계정 먼저 변경) |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" -n tailwind-internal get deployment,pods,jobs,pvc
kubectl --context "<context>" -n tailwind-internal get ingress
make portal-smoke KUBE_CONTEXT="<context>"
```

성공: 세 Deployment READY, `portal-migrate` Complete, `smoke 통과: portal`.

## 문제 해결과 멈춤 조건

Pod·event·로그 조회는 [장애 조회](../README.md#장애-조회)의 명령을 namespace `tailwind-internal`로 실행합니다. Job 로그는 아래로 봅니다. 모두 [조회]입니다.

```bash
kubectl --context "<context>" -n etch-sso logs job/portal-keycloak-client --tail=20
kubectl --context "<context>" -n tailwind-internal logs job/portal-migrate --tail=100
```

| 증상 | 원인과 조치 |
| --- | --- |
| `portal-check`의 env 오류 | 필수값이 비었거나 임시값. `DJANGO_ALLOWED_HOSTS`에 `localhost`가 없어도 중단. [환경설정](docs/01-install.md#환경설정)을 보고 사람에게 수정 요청 |
| `prod와 prod/migrate의 images에서 portal-api 버전을 일치시키세요` | 앱 overlay와 migration overlay의 API 이미지가 다름. 저장소 원본 문제이므로 보고 |
| `이전 portal-migrate Job이 진행 중` | 끝날 때까지 기다린 뒤 같은 명령 재실행 |
| `migration 전 단계 실패` | API 중지·사전 검사 Job·이전 Job 정리에서 멈춤. DB는 그대로이고 API는 원래 replica 수로 복원됨. 원인을 해결하고 같은 명령 재실행(`PORTAL_RETRY_MIGRATE` 불필요) |
| `migration 단계 실패`, `이전 portal-migrate Job이 실패 상태` | 위 Job 로그로 DB 연결·migration 오류 확인. 아래 멈춤 조건을 따름 |
| PVC Pending | StorageClass/PV·노드 affinity. 보고 |
| rollout 시간 초과 | event와 Pod 로그. API·edge-nginx의 probe는 [health 검사](docs/03-operations.md#health-검사) |
| smoke 404 / 503 | Portal Ingress와 Traefik의 `tailwind-internal` 감시 / Pod·Service endpoint. [변경] `make portal-up KUBE_CONTEXT="<context>"` 재실행 |
| 로그인 반복·callback 실패 | `api.env`의 issuer·redirect URI·client secret과 Keycloak client([서로 맞춰야 하는 값](docs/01-install.md#2-서로-맞춰야-하는-값)). 보고 |

멈추고 사람에게 묻는 조건입니다.

- migrate 이미지와 앱 이미지 불일치, 이미지 빌드의 사내 미러 오류
- `portal-check`의 env 오류, Keycloak client Job 실패(issuer 불일치 등)
- `이전 portal-migrate Job이 진행 중`이라는 오류. 끝날 때까지 기다립니다.
- `migration 전 단계 실패`라는 오류. DB는 바뀌지 않았고 API는 복원돼 있습니다. `kubectl --context "<context>" -n tailwind-internal get pods`로 API Pod가 Running인지 확인하고 오류 문구와 함께 보고합니다.
- `migration 단계 실패` 또는 `이전 portal-migrate Job이 실패 상태`라는 오류. `kubectl --context "<context>" -n tailwind-internal logs job/portal-migrate --tail=100`으로 원인을 보고합니다. 메시지에 `API는 중지 상태입니다`가 있으면 그 사실과 이전 replica 수도 함께 보고합니다. 이전 replica 수는 Deployment에 기록돼 있어 재실행이 복원합니다.
- [승인] 원인이 해결됐다는 확인을 받은 뒤에만 `make ops-deploy APP=portal KUBE_CONTEXT="<context>" PORTAL_RETRY_MIGRATE=1`로 다시 실행합니다. 직접 Job을 지우지 않습니다.
- PVC Pending, rollout 시간 초과
- DB·PVC·namespace 삭제가 필요해 보이는 경우. 실행하지 않습니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [설치 입력과 배포 동작](docs/01-install.md) | env 파일 작성과 서로 맞춰야 하는 값, 입력 검사, Keycloak client 등록 입력·결과, 배포 단계별 동작, migration 준비·실패 대응, 공용 Traefik 연결 |
| [최초 권한 설정](docs/02-access.md) | 최초 운영자·앱 역할·데이터 권한, 비상 Django 관리자 계정 |
| [설정 변경과 운영 확인](docs/03-operations.md) | env 변경 반영과 확인할 동작, 함께 바뀌는 외부 대상, health 검사 |
| [운영 overlay](k8s/overlays/prod/README.md) | 이미지·Ingress·Traefik 권한·migration 입력과 업무 파일 볼륨 |
| [Keycloak client 등록 Job](k8s/jobs/keycloak-client/README.md) | 등록 Job의 원본 파일과 역할 |
