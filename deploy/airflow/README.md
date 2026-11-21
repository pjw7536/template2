# Airflow 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

Airflow를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 업무 DAG를 실행하는 Airflow 3.3.2. Worker 한 대에서 LocalExecutor와 PostgreSQL 16을 실행 |
| namespace | `airflow` |
| 실행 Worker | `khinfow01`. DB·로그·DAG·ODBC는 `/appdata/airflow/{postgres,logs,dags,odbc}`(없으면 `airflow-up`이 생성) |
| 공개 주소 | `https://airflow.etch.samsungds.net` (Keycloak 로그인, client `airflow`) |
| 배포 명령 | `make ops-deploy APP=airflow` = 준비 검사 → `airflow-check` → `airflow-image` → `airflow-keycloak-client` → `airflow-up` → `airflow-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, 모든 Pod Ready, PVC Bound, `smoke 통과: airflow` |
| 이미지 | `store.etch.samsungds.net/airflow:3.3.2-<소스 해시>`. `airflow-image`가 이 checkout에서 빌드해 push |
| 먼저 필요한 것 | [공용 Traefik(ingress)](../shared/ingress/README.md)·[Keycloak](../keycloak/README.md)·[Registry](../registry/README.md) 배포. 공용 TLS(`airflow.etch.samsungds.net`)·빌드 도구·chart 파일·사내 CA 묶음은 준비 검사가 확인하고, 필요한 파일이 있으면 자동으로 준비 |

## 구성

- 실행: scheduler·API server·DAG processor·triggerer와 내부 PostgreSQL이 `NODE_NAME` Worker 한 대에 묶입니다. 단일 Worker 구성이므로 해당 Worker나 디스크에 장애가 나면 Airflow가 중단됩니다.
- 이미지: 플러그인·Python 패키지·ODBC 드라이버를 넣은 이미지를 관리 호스트에서 빌드해 [Registry](../registry/README.md)로 push합니다. chart는 고정 버전(1.22.0) 파일을 사용합니다. 파일이 없으면 `ops-deploy`의 준비 검사가 사내 미러에서 받으며, `airflow-check`·`airflow-up`은 chart를 내려받지 않습니다.
- DAG: 이미지에는 DAG가 없습니다. Worker의 `DAGS_HOST_PATH`를 `airflow-dags` PVC로 연결해 `/opt/airflow/dags`에서 읽기 전용으로 읽으며, 이 폴더에 넣은 파일만 Airflow에 나타납니다. 관리 호스트에서 `make airflow-dags-sync`로 checkout의 `apps/airflow/dags`를 이 폴더에 맞추며(같은 이름은 덮어쓰고 폴더에만 있는 파일은 남김), 재배포는 필요 없습니다. 노드에 접속하지 않습니다.
- 로그인: [Keycloak](../keycloak/README.md) `etch` realm의 전용 client `airflow`를 사용합니다. 로그인한 사용자는 기본 Viewer이며 `airflow` client 역할 User·Admin으로 권한을 올립니다.
- 접속: 공용 Traefik의 HTTPS entrypoint로 들어옵니다. 인증서는 `etch-sso/traefik-tls`에서 관리하므로 앱별 TLS Secret이 없고, `airflow` namespace 감시는 `airflow-up`이 추가합니다.
- 저장: DB·로그·DAG는 지정 Worker의 local PV(`Retain`)입니다. ODBC 설정 폴더는 `/usr/local/odbc`에 읽기 전용으로 마운트합니다.
- 연동: Airflow → Portal API 호출은 trigger token, Portal → Airflow 호출은 Airflow 계정의 JWT를 사용합니다. Task 실패 알림은 메신저·메일로 보냅니다.
- 기존 DB를 재사용할 때는 DB 비밀번호·Fernet 키를 유지합니다.

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사전 준비

완료 여부를 확인하고 미완료면 같은 행의 준비 작업을 수행합니다. `자동`이라고 적은 준비는 `make ops-deploy`의 준비 검사가 실행하므로 따로 실행하지 않습니다.

| 준비 작업 | 완료 확인 |
| --- | --- |
| 실행 Worker `khinfow01`이 `Ready`이고 cordon 상태가 아님 | `kubectl --context "<context>" get node khinfow01` |
| `khinfow01`의 containerd와 관리 호스트가 사내 이미지 저장소 인증서를 신뢰(노드 설정, [방법](../registry/docs/01-operations.md#노드와-관리-호스트의-ca-신뢰)) | 관리 호스트는 [CA 신뢰 확인](../registry/docs/01-operations.md#노드와-관리-호스트의-ca-신뢰), `khinfow01`은 [노드 명령 실행](../shared/docs/infrastructure/access.md#노드-명령-실행)으로 [시험 이미지 pull](../registry/docs/01-operations.md#수동-pushpull-시험) |
| chart 파일 `deploy/airflow/helm/vendor/airflow-1.22.0.tgz`. 자동: 없으면 사내 미러에서 받음. 미러에서 받지 못하면 [파일 반입](../shared/docs/infrastructure/access.md#파일-반입)으로 둠([방법](docs/02-artifacts.md#1-공식-chart-준비)) | `make ops-preflight APP=airflow KUBE_CONTEXT="<context>"`의 `chart` 줄이 `[통과]` 또는 `[자동 준비]` |
| 사내 Root·Issuing CA 파일을 `deploy/shared/certs/ca/`에 배치([인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급)). 자동: CA 묶음 생성 | `make ops-preflight APP=airflow KUBE_CONTEXT="<context>"`의 `사내 CA 묶음` 줄이 `[통과]` 또는 `[자동 준비]` |
| `airflow.etch.samsungds.net`을 SAN에 가진 `fullchain.crt`·`private.key`를 `deploy/shared/certs/etch.samsungds.net/`에 배치([인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급)). 자동: 공용 TLS 등록 | `make ops-preflight APP=airflow KUBE_CONTEXT="<context>"`의 `공용 TLS airflow.etch.samsungds.net` 줄이 `[통과]` 또는 `[자동 준비]` |
| 이미지 빌드 도구(nerdctl·BuildKit). 자동: 없으면 설치. 비밀번호 없는 sudo가 필요([관리 호스트 sudo](../shared/docs/infrastructure/access.md#관리-호스트-sudo)) | `make build-tools-check` |
| 관리 호스트에서 Keycloak 공개 주소 `sso.etch.samsungds.net`의 이름 조회. `airflow-keycloak-client`가 이 주소의 관리 API를 호출 | `getent hosts sso.etch.samsungds.net`. 출력이 없으면 [DNS](../shared/docs/infrastructure/access.md#dns) |
| DNS `airflow.etch.samsungds.net` → APP VIP. 없어도 배포는 진행하며 smoke가 `DNS 미등록`으로 표시 | `getent hosts airflow.etch.samsungds.net`. 출력이 없으면 [DNS](../shared/docs/infrastructure/access.md#dns) |
| ODBC를 쓰면 `khinfow01`의 `/appdata/airflow/odbc`에 실제 드라이버 파일 배치([방법](odbc/README.md#worker에-반영)) | [노드 명령 실행](../shared/docs/infrastructure/access.md#노드-명령-실행)의 `python3 deploy/shared/scripts/node_exec.py khinfow01 --context "<context>" --command 'sudo -n ls -lnR /appdata/airflow/odbc'`. 기준은 [Worker에 반영](odbc/README.md#worker에-반영) |

`airflow-up`은 DAG 폴더를 만들기만 하고 안의 파일을 넣거나 바꾸지 않습니다.

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `AIRFLOW_ENV` | Airflow env 경로 | `deploy/airflow/env/k8s.env`. 외부 경로면 모든 명령에 같은 값 |
| `AIRFLOW_OIDC_CA_FILE` | ConfigMap `airflow-oidc-ca`가 없을 때 쓸 CA 묶음 | `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem` |
| `KEYCLOAK_ENV` | client 등록에 쓰는 Keycloak 관리자 계정의 출처 | `deploy/keycloak/env/prod.env` |
| `REGISTRY_PUSH_ENV` | `airflow-image`가 로그인에 쓰는 사내 이미지 저장소 push 계정 파일 | `deploy/registry/env/push-initial.env` |

env 파일의 키와 입력 파일은 [환경설정](docs/01-prepare.md#환경설정), OIDC 키는 [OIDC env 입력](docs/03-deploy.md#oidc-env-입력), 그 밖의 선택 입력(`AIRFLOW_TLS_SOURCE`, `AIRFLOW_CHART_FILE`)은 [선택 입력](docs/03-deploy.md#선택-입력)에 있습니다.
저장소의 기본 env와 다른 값이 필요하면 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일) 절의 방법으로 저장소 밖 env를 만들어 `AIRFLOW_ENV=<경로>`로 지정합니다.

## A. 최초 설치

1. [조회] 노드 확인
   ```bash
   kubectl --context "<context>" get node khinfow01
   ```
   성공: `Ready`.
2. [변경] 배포. 준비 검사(chart 받기·CA 묶음 생성·빌드 도구 설치·공용 TLS 등록을 자동 실행) → 검사 → 이미지 빌드·push → Keycloak client 등록 → namespace·OIDC CA ConfigMap·Worker 폴더 준비와 DB migration을 포함한 Helm 배포 → smoke → 대조 순서로 진행합니다. 최초 설치는 새 DB에 migration을 실행하므로 [변경]입니다. 첫 빌드는 의존성 설치로 오래 걸립니다.
   ```bash
   make ops-deploy APP=airflow KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.
   실패하면 JSON의 `failedStep`에 맞는 조치를 한 번 수행하고 같은 명령을 다시 실행합니다. 오류 문구별 조치는 [문제 해결과 멈춤 조건](#문제-해결과-멈춤-조건)에 있습니다.
   - `preflight`: `blocked`의 항목마다 `reference`가 가리키는 [접근 경로](../shared/docs/infrastructure/access.md) 절로 해결합니다. `chart`는 [chart 준비](docs/02-artifacts.md#1-공식-chart-준비), `사내 CA 묶음`과 `공용 TLS airflow.etch.samsungds.net`은 [인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급), `이미지 빌드 도구`는 [이미지 빌드 도구](../README.md#이미지-빌드-도구), `먼저 필요한 앱 <이름>`은 그 앱 가이드의 A를 따릅니다.
   - `airflow-check`: 출력의 `오류:` 줄을 문제 해결 표에서 찾습니다.
   - `airflow-image`: `이미지 빌더 nerdctl 실행 파일을 찾을 수 없습니다`나 `BuildKit`이 들어간 오류면 [이미지 빌드 도구](../README.md#이미지-빌드-도구), `registry에 연결할 수 없습니다`면 [Registry](../registry/README.md) 배포와 관리 호스트의 DNS·CA 신뢰를 확인합니다. 패키지 설치 오류면 사내 미러 문제이므로 오류 마지막 20줄과 함께 보고합니다.
   - `airflow-keycloak-client`: 관리 호스트가 Keycloak 공개 주소 `sso.etch.samsungds.net`을 DNS로 찾지 못하면 실패합니다. `getent hosts sso.etch.samsungds.net`에 출력이 없으면 [DNS](../shared/docs/infrastructure/access.md#dns) 절로 등록합니다. 그 밖의 원인은 문제 해결 표의 `Airflow client 등록 실패` 행을 따릅니다.
   - `airflow-up`: `공용 TLS 마운트가 없습니다`면 [공용 Traefik 검사·갱신](../README.md#공용-traefik-검사갱신)의 `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`를 실행합니다. migration·관리자 Job 실패는 멈춤 조건입니다.
   - `airflow-smoke`: `DNS 미등록`만 표시되고 `smoke 통과: airflow`로 끝나면 성공입니다. DNS 등록은 JSON의 `pending`에 남으며 [DNS](../shared/docs/infrastructure/access.md#dns) 절로 수행합니다.
3. [변경] DAG 반입. 최초 설치 직후의 DAG 폴더는 비어 있어 Airflow에 DAG가 없습니다. checkout의 `apps/airflow/dags`를 폴더에 넣습니다.
   ```bash
   make airflow-dags-sync KUBE_CONTEXT="<context>"
   ```
   성공: 마지막 줄이 `DAG 폴더 동기화 완료: …`이고, [DAG 목록 확인과 활성화](docs/04-operations.md#dag-목록-확인과-활성화)의 [조회]에서 넣은 DAG가 보이고 import 오류가 없습니다.
4. [조회] [C. 배포 후 확인](#c-배포-후-확인)

## B. 업데이트

먼저 이번 배포가 이미지를 바꾸는지 확인합니다. 클러스터를 바꾸지 않습니다.

[검사]
```bash
make airflow-check KUBE_CONTEXT="<context>"
```

성공: `설정·차트·기존 리소스·TLS·배치 검사 통과`와 `이미지 변경:` 줄이 출력됩니다.

| 출력의 `이미지 변경:` 줄 | 다음 행동 |
| --- | --- |
| `이미지 변경: 없음` | [변경] 아래 표에서 해당하는 [변경] 행을 바로 실행 |
| `이미지 변경: 있음(<현재> → <새 이미지>)` | [승인] 실행 중 작업이 중단되고 운영 중인 DB에 되돌릴 수 없는 migration이 실행됩니다. [배포 전 준비](docs/04-operations.md#이미지-업데이트)의 DAG 일시정지와 DB 백업을 마친 뒤 명령·대상·영향을 보여 주고 승인받아 실행 |
| `이미지 변경: 최초 설치(<새 이미지>)` | [변경] 실행 중인 Airflow가 없으므로 [A. 최초 설치](#a-최초-설치)를 따름 |

| 변경 | 실행 |
| --- | --- |
| DAG 파일만 | [검사] `make airflow-dags-check KUBE_CONTEXT="<context>"`로 바뀔 파일을 본 뒤 [변경] `make airflow-dags-sync KUBE_CONTEXT="<context>"`. 같은 이름은 덮어쓰고 폴더에만 있는 파일은 남김. 재배포 없음. 덮어쓸 DAG가 실행 중이면 먼저 일시정지([방법](docs/04-operations.md#dag-파일-추가수정삭제)) |
| 이미지 소스(`apps/airflow/image`·`apps/airflow/plugins`의 플러그인·패키지·ODBC, `build.env`) | [승인] tag가 자동으로 바뀌어 실행 중 작업이 중단되고 운영 중인 DB에 migration이 실행됩니다. [배포 전 준비](docs/04-operations.md#이미지-업데이트)를 마치고 승인받은 뒤 `make ops-deploy APP=airflow KUBE_CONTEXT="<context>"` |
| env(알림·OIDC·runtime 값) | [변경] `make ops-deploy APP=airflow KUBE_CONTEXT="<context>"`. Pod는 배포 마지막에 재시작됨. 저장소 밖 env는 같은 명령에 `AIRFLOW_ENV=<경로>`를 붙임 |
| Keycloak 사용자 표시 이름 | [변경] `make ops-deploy APP=airflow KUBE_CONTEXT="<context>"`. 배포 성공 뒤 다시 로그인해 [사용자 메뉴와 FAB Users](docs/03-deploy.md#로그인과-앱-간-호출-확인)를 확인 |
| 인증서 | [변경] [공용 TLS 등록](../README.md#공용-tls-등록)의 명령으로 `airflow.etch.samsungds.net`을 다시 등록 |
| 사내 CA 교체 | [변경] [사내 CA 묶음](../README.md#사내-ca-묶음)을 다시 만들고 [OIDC CA ConfigMap](docs/03-deploy.md#oidc-ca-configmap)을 갱신한 뒤 env 행의 배포를 실행 |
| DB 비밀번호·Fernet 키 불일치 | [조회] `make airflow-check KUBE_CONTEXT="<context>"`의 오류로 다른 값을 확인하고 [Secret 복원](docs/04-operations.md#2-secret-복원)의 조건을 대조. DB를 만들 때의 원래 값이 든 env가 없으면 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일) 절로 준비. 새 값을 만들지 않음 |

`ops-deploy`를 실행한 행의 성공 확인은 A-2와 같습니다. JSON의 `failedStep`이 `null`, `driftResultCode`가 `0`이어야 합니다.

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" -n airflow get pods,pvc,jobs
make airflow-smoke KUBE_CONTEXT="<context>"
```

성공: 모든 Pod Ready, PVC(`airflow-dags` 포함) Bound, `smoke 통과: airflow`. host가 DNS에 없으면 `DNS 미등록. APP VIP 직접 접속: …` 줄과 `smoke 통과: airflow (DNS 미등록 host 1개)`로 끝나며 이것도 통과입니다. 남은 DNS 등록은 [DNS](../shared/docs/infrastructure/access.md#dns) 절로 수행합니다.

[조회] 로그인과 앱 간 호출은 [화면 기능 확인](../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 [확인 항목](docs/03-deploy.md#로그인과-앱-간-호출-확인)을 검증합니다. ODBC를 사용하면 검증용 DAG에서 연결을 확인합니다. 업무 DAG 활성화([명령](docs/04-operations.md#dag-목록-확인과-활성화))와 역할 부여([방법](docs/03-deploy.md#client-등록))는 요청에 포함된 경우 진행합니다.

## 문제 해결과 멈춤 조건

실패하면 로그를 조회합니다. 모두 [조회]입니다.

```bash
kubectl --context "<context>" -n airflow logs deployment/airflow-scheduler --tail=100
kubectl --context "<context>" -n airflow logs deployment/airflow-api-server --tail=100
kubectl --context "<context>" -n airflow logs deployment/airflow-dag-processor --tail=100
kubectl --context "<context>" -n airflow logs statefulset/airflow-postgres --tail=100
```

Job 로그 조회와 그 밖의 증상은 [실패 단계 확인](docs/04-operations.md#5-실패-단계-확인), 공통 증상은 [장애 조회](../README.md#장애-조회)에 있습니다.

| 증상 | 원인과 조치 |
| --- | --- |
| `실제 값으로 교체하세요: <키>`, `필수 설정 누락: <키>` | env에 실제 값이 없습니다. [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일) 절로 그 키를 채운 env를 준비하고 `AIRFLOW_ENV=<경로>`로 지정. 키의 뜻은 [환경설정](docs/01-prepare.md#환경설정) |
| `Helm chart 준비 필요`, `Helm chart SHA-256 불일치` | [변경] `make airflow-fetch-chart`. 다시 실패하면 [chart 준비](docs/02-artifacts.md#1-공식-chart-준비). 다른 버전의 chart로 바꾸지 않음 |
| `OIDC CA ConfigMap airflow-oidc-ca이 없고 CA 묶음 파일도 없습니다` | [변경] [사내 CA 묶음](../README.md#사내-ca-묶음)의 `make ca-bundle CA_HOST=sso.etch.samsungds.net` |
| `공용 TLS 마운트가 없습니다` | [변경] `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"` 뒤 다시 실행 |
| `registry에 연결할 수 없습니다` | [조회] `make registry-smoke KUBE_CONTEXT="<context>"`로 Registry를 확인. 정상이면 관리 호스트의 [CA 신뢰](../registry/docs/01-operations.md#노드와-관리-호스트의-ca-신뢰)와 [DNS](../shared/docs/infrastructure/access.md#dns) |
| `Airflow client 등록 실패` | [조회] `getent hosts sso.etch.samsungds.net`에 출력이 없으면 [DNS](../shared/docs/infrastructure/access.md#dns) 절로 등록. `make keycloak-smoke KUBE_CONTEXT="<context>"`가 실패하면 [Keycloak 가이드](../keycloak/README.md). 둘 다 정상이면 관리자 계정이나 기존 client secret이 env와 다른 것이므로 [client 등록](docs/03-deploy.md#client-등록)의 방법으로 대조 |
| Pod `ImagePullBackOff` | 노드가 사내 이미지 저장소 인증서를 신뢰하지 않거나 이미지가 저장소에 없음. [노드 명령 실행](../shared/docs/infrastructure/access.md#노드-명령-실행)으로 [노드의 CA 신뢰](../registry/docs/01-operations.md#노드와-관리-호스트의-ca-신뢰)를 확인하고, 이미지가 없으면 [변경] `make airflow-image KUBE_CONTEXT="<context>"` |
| ODBC 마운트 실패 | `khinfow01`의 `/appdata/airflow/odbc`가 없거나 읽을 수 없음. [Worker에 반영](odbc/README.md#worker에-반영) |
| Pod는 Ready인데 smoke가 `DNS 조회 실패, APP VIP 직접 접속도 실패` | 서비스가 Ingress를 거쳐 응답하지 않음. [Service 직접 확인](docs/03-deploy.md#접속과-연동-확인)으로 앱과 진입 경로를 나눠 확인 |

다음이면 멈추고 보고합니다.

- `기존 POSTGRES_PASSWORD과 다릅니다` 또는 `기존 AIRFLOW_FERNET_KEY과 다릅니다`: env가 기존 DB의 값과 다릅니다. 새 값을 만들거나 Secret을 지우고 다시 만들지 않습니다. `python3 deploy/airflow/scripts/manage.py init-secrets`를 실행하지 않습니다.
- `기존 DB PVC가 있으나 airflow-postgres Secret이 없습니다` 또는 `기존 Airflow 설치의 Fernet Secret이 없습니다`: [Secret 복원](docs/04-operations.md#2-secret-복원)은 [승인] 단계입니다. env의 값이 DB를 만들 때의 원래 값인지 확인할 수 없으면 실행하지 않습니다. PVC·Secret을 지워 새 설치로 만들지 않습니다.
- `airflow-up` 중 migration·관리자 Job 실패: [Job 로그](docs/04-operations.md#5-실패-단계-확인)를 조회해 함께 보고합니다. DB·PVC를 삭제하거나 `helm rollback`·`helm uninstall`로 되돌리지 않습니다.
- 기존 Keycloak client `airflow`의 secret이 env와 다른 경우: client secret을 회전하거나 client를 지우지 않습니다.
- PVC가 `Pending`이거나 PV가 `Released`인 경우: PV·PVC·Worker 데이터 폴더를 지우거나 다시 만들지 않습니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [서버 준비와 환경설정](docs/01-prepare.md) | 필요 도구, 실행 Worker 선택, Worker 폴더 직접 준비, 입력 파일과 env 키, 최초 비밀값 생성, 접속 방식, 실패 알림 입력 |
| [차트·이미지·ODBC 준비](docs/02-artifacts.md) | chart 반입, 이미지 빌드·push와 빌드 옵션, 빌드 도구가 설치하는 내용, 두 단계 빌드, registry 없는 이미지 전달, ODBC 마운트 |
| [인증·검사·직접 배포](docs/03-deploy.md) | OIDC env·CA ConfigMap·client 등록·역할 부여, 검사 범위, 렌더 미리 보기, `airflow-up` 동작과 선택 입력, 접속·연동 확인, 직접 deploy와 Helm override |
| [백업·이전·업데이트와 문제 해결](docs/04-operations.md) | DB·설정 백업, Secret 복원, 기존 DB 이전, DAG 공유 폴더 전환·관리, DAG 활성화, 이미지 업데이트, 2.x 업그레이드, 증상별 조치, 부하 테스트 |
| [ODBC 파일 안내](odbc/README.md) | ODBC 설정 파일의 배치 구조와 Worker 반영 |
| [Keycloak client 등록 도구](k8s/jobs/keycloak-client/README.md) | `setup_client.py`의 입력과 동작 범위 |
