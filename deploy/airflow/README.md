# Airflow 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

Airflow를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인]·[사람])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 업무 DAG를 실행하는 Airflow 3.3.2. Worker 한 대에서 LocalExecutor와 PostgreSQL 16을 실행 |
| namespace | `airflow` |
| 실행 Worker | `khinfow01`. DB·로그·DAG·ODBC는 `/appdata/airflow/{postgres,logs,dags,odbc}`(없으면 `airflow-up`이 생성) |
| 공개 주소 | `https://airflow.etch.samsungds.net` (Keycloak 로그인, client `airflow`) |
| 배포 명령 | `make ops-deploy APP=airflow` = `airflow-image` → `airflow-keycloak-client` → `airflow-check` → `airflow-up` → `airflow-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, 모든 Pod Ready, PVC Bound |
| 이미지 | `store.etch.samsungds.net/airflow:3.3.2-<소스 해시>`. `airflow-image`가 이 checkout에서 빌드해 push |
| 먼저 필요한 것 | Keycloak·Registry 운영, 공용 TLS(`airflow.etch.samsungds.net`), 빌드 도구, chart 파일, 사내 CA 묶음 |

## 구성

- 실행: scheduler·API server·DAG processor·triggerer와 내부 PostgreSQL이 `NODE_NAME` Worker 한 대에 묶입니다. 단일 Worker 구성이므로 해당 Worker나 디스크에 장애가 나면 Airflow가 중단됩니다.
- 이미지: 플러그인·Python 패키지·ODBC 드라이버·DAG를 넣은 이미지를 관리 호스트에서 빌드해 [Registry](../registry/README.md)로 push합니다. chart는 고정 버전(1.22.0) 파일을 사용하며 배포 중 자동으로 내려받지 않습니다.
- DAG: Worker의 `DAGS_HOST_PATH`를 `airflow-dags` PVC로 공유해 `/opt/airflow/dags`에서 읽습니다. 경로를 비우면 이미지의 DAG를 읽습니다.
- 로그인: [Keycloak](../keycloak/README.md) `etch` realm의 전용 client `airflow`를 사용합니다. 로그인한 사용자는 기본 Viewer이며 `airflow` client 역할 User·Admin으로 권한을 올립니다.
- 접속: 공용 Traefik의 HTTPS entrypoint로 들어옵니다. 인증서는 `etch-sso/traefik-tls`에서 관리하므로 앱별 TLS Secret이 없고, `airflow` namespace 감시는 `airflow-up`이 추가합니다.
- 저장: DB·로그·DAG는 지정 Worker의 local PV(`Retain`)입니다. ODBC 설정 폴더는 `/usr/local/odbc`에 읽기 전용으로 마운트합니다.
- 연동: Airflow → Portal API 호출은 trigger token, Portal → Airflow 호출은 Airflow 계정의 JWT를 사용합니다. Task 실패 알림은 메신저·메일로 보냅니다.
- 기존 DB를 재사용할 때는 DB 비밀번호·Fernet 키를 유지합니다.

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사람이 하는 일

클러스터 밖 작업입니다. 오른쪽 명령으로 완료 여부를 먼저 확인하고, 미완료일 때만 요청합니다.

| 일 | 완료 확인 |
| --- | --- |
| `khinfow01`의 containerd가 사내 이미지 저장소 인증서를 신뢰(노드 설정, [방법](../registry/docs/01-operations.md#노드와-관리-호스트의-ca-신뢰)) | 배포 뒤 Pod가 `ImagePullBackOff` 없이 뜨는지로 확인 |
| 사내 미러에서 chart를 받을 수 없을 때 chart 파일 반입([방법](docs/02-artifacts.md#1-공식-chart-준비)) | `ls -l deploy/airflow/helm/vendor/airflow-1.22.0.tgz` |
| 사내 Root·Issuing CA 파일을 `deploy/shared/certs/ca/`에 배치 | `make ca-bundle CA_HOST=sso.etch.samsungds.net` |
| 인증서 파일 배치, DNS `airflow.etch.samsungds.net` → APP VIP | `ls -l deploy/shared/certs/etch.samsungds.net/fullchain.crt`, `getent hosts airflow.etch.samsungds.net` |
| ODBC를 쓰면 `khinfow01`의 `/appdata/airflow/odbc`에 실제 드라이버 파일 배치([방법](odbc/README.md#worker에-반영)) | ODBC를 쓰는 DAG 실행 결과로 확인 |
| 선택: DAG 활성화(신규 DAG는 일시정지로 생성됨), 브라우저 로그인, 사용자 역할 부여([방법](docs/03-deploy.md#로그인과-앱-간-호출-확인)) | 사용자 보고 |

DAG 공유 폴더가 비어 있으면 `airflow-up`이 이미지에 들어 있는 DAG와 준비 표식을 복사합니다. 파일이 이미 있으면 바꾸지 않습니다.

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `AIRFLOW_ENV` | Airflow env 경로 | `deploy/airflow/env/k8s.env`. 외부 경로면 모든 명령에 같은 값 |
| `AIRFLOW_OIDC_CA_FILE` | ConfigMap `airflow-oidc-ca`가 없을 때 쓸 CA 묶음 | `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem` |
| `KEYCLOAK_ENV` | client 등록에 쓰는 Keycloak 관리자 계정의 출처 | `deploy/keycloak/env/prod.env` |

env 파일의 키와 입력 파일은 [환경설정](docs/01-prepare.md#환경설정), OIDC 키는 [OIDC env 입력](docs/03-deploy.md#oidc-env-입력), 그 밖의 선택 입력(`AIRFLOW_TLS_SOURCE`, `AIRFLOW_CHART_FILE`)은 [선택 입력](docs/03-deploy.md#선택-입력)에 있습니다.

## A. 최초 설치

1. [검사] 위 표의 확인 명령으로 chart·CA 묶음·인증서 파일을 확인하고, [이미지 빌드 도구](../README.md#이미지-빌드-도구)를 준비합니다. chart가 없으면 [변경] `make airflow-fetch-chart`를 실행하고, 받지 못하면 멈추고 반입을 요청합니다.
2. [조회] 노드 확인
   ```bash
   kubectl --context "<context>" get node khinfow01
   ```
   성공: `Ready`.
3. [변경] 공용 TLS 등록: `airflow.etch.samsungds.net`을 사이트 폴더 `etch.samsungds.net`으로 [공용 TLS 등록](../README.md#공용-tls-등록)합니다.
4. [변경] 배포. 이미지 빌드·push, Keycloak client 등록, namespace·OIDC CA ConfigMap·Worker 폴더·DAG 초기 파일 준비, DB migration을 포함한 Helm 배포를 수행합니다. migration은 되돌릴 수 없습니다. 첫 빌드는 의존성 설치로 오래 걸립니다.
   ```bash
   make ops-deploy APP=airflow KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.
   - `airflow-image` 실패: `nerdctl·buildctl`이 없으면 [이미지 빌드 도구](../README.md#이미지-빌드-도구), `registry에 연결할 수 없습니다`면 [Registry](../registry/README.md) 배포·DNS·CA를 확인합니다. 패키지 설치 오류면 사내 미러 문제이므로 오류 마지막 20줄과 함께 보고합니다.
   - `airflow-keycloak-client` 실패: Keycloak 공개 주소의 DNS·CA 문제이거나 기존 client secret이 env와 다른 경우입니다. DNS 미등록이면 등록을 요청하고 멈춥니다.
   - `공용 TLS 마운트가 없습니다`: [공용 Traefik 갱신](../README.md#공용-traefik-검사갱신)의 `ingress-up` 뒤 다시 실행합니다.
5. [조회] [C. 배포 후 확인](#c-배포-후-확인)

## B. 업데이트

먼저 이번 배포가 이미지를 바꾸는지 확인합니다. 클러스터를 바꾸지 않습니다.

[검사]
```bash
make airflow-check KUBE_CONTEXT="<context>"
```

| 출력의 `이미지 변경:` 줄 | 다음 행동 |
| --- | --- |
| `이미지 변경: 없음` | 아래 표에서 [변경] 행을 바로 실행 |
| `이미지 변경: 있음(<현재> → <새 이미지>)` | [승인] 대상입니다. 실행 중 작업 중단과 되돌릴 수 없는 DB migration을 알리고 DB 백업 여부를 확인받은 뒤 실행 |

| 변경 | 실행 |
| --- | --- |
| DAG 파일만(공유 폴더 사용 중) | 재배포 없음. [사람]이 `khinfow01`의 `/appdata/airflow/dags`에 반영([방법](docs/04-operations.md#dag-파일-추가수정삭제)) |
| `apps/airflow` 소스(플러그인·패키지·ODBC, `dags` 제외) | tag가 자동으로 바뀝니다. [승인] 실행 중 작업이 중단되고 DB migration이 실행되므로 승인 후 `make ops-deploy APP=airflow KUBE_CONTEXT="<context>"`. [사전 준비](docs/04-operations.md#이미지-업데이트) |
| env(알림·OIDC·runtime 값) | [변경] `make ops-deploy APP=airflow KUBE_CONTEXT="<context>"`. Pod는 배포 마지막에 재시작됨 |
| 인증서 | A-3 |
| DB 비밀번호·Fernet 키 | 멈추고 사람에게 묻기. 바꾸면 안 되며 기존 Secret과 다르면 배포가 중단됨 |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" -n airflow get pods,pvc,jobs
make airflow-smoke KUBE_CONTEXT="<context>"
```

성공: 모든 Pod Ready, PVC(`airflow-dags` 포함) Bound, `smoke 통과: airflow`.

## 문제 해결과 멈춤 조건

실패하면 로그를 조회합니다. 모두 [조회]입니다.

```bash
kubectl --context "<context>" -n airflow logs deployment/airflow-scheduler --tail=100
kubectl --context "<context>" -n airflow logs deployment/airflow-api-server --tail=100
kubectl --context "<context>" -n airflow logs deployment/airflow-dag-processor --tail=100
kubectl --context "<context>" -n airflow logs statefulset/airflow-postgres --tail=100
```

증상별 확인 항목과 Job 로그 조회는 [실패 단계 확인](docs/04-operations.md#5-실패-단계-확인), 공통 증상은 [장애 조회](../README.md#장애-조회)에 있습니다.

멈추고 사람에게 묻는 조건입니다.

- 검사에서 `실제 값으로 교체하세요`, Secret 불일치, chart SHA-256 불일치
- `airflow-up` 중 migration·관리자 Job 실패
- Pod가 Pending·ImagePullBackOff(노드가 사내 이미지 저장소를 신뢰하지 않음)·ODBC 마운트 실패
- 기존 Airflow PVC·Secret이 남아 있는데 Fernet·DB Secret이 없다는 오류
- `python3 deploy/airflow/scripts/manage.py init-secrets`, `helm uninstall`, Secret 재생성이 필요해 보이는 경우. 실행하지 않습니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [서버 준비와 환경설정](docs/01-prepare.md) | 필요 도구, 실행 Worker 선택, Worker 폴더 직접 준비, 입력 파일과 env 키, 최초 비밀값 생성, 접속 방식, 실패 알림 입력 |
| [차트·이미지·ODBC 준비](docs/02-artifacts.md) | chart 반입, 이미지 빌드·push와 빌드 옵션, containerd 빌드 도구 수동 설치, 두 단계 빌드, registry 없는 이미지 전달, ODBC 마운트 |
| [인증·검사·직접 배포](docs/03-deploy.md) | OIDC env·CA ConfigMap·client 등록·역할 부여, 검사 범위, 렌더 미리 보기, `airflow-up` 동작과 선택 입력, 접속·연동 확인, 직접 deploy와 Helm override |
| [백업·이전·업데이트와 문제 해결](docs/04-operations.md) | DB·설정 백업, Secret 복원, 기존 DB 이전, DAG 공유 폴더 전환·관리, 이미지 업데이트, 2.x 업그레이드, 증상별 조치, 부하 테스트 |
| [ODBC 파일 안내](odbc/README.md) | ODBC 설정 파일의 배치 구조와 Worker 반영 |
| [Keycloak client 등록 도구](k8s/jobs/keycloak-client/README.md) | `setup_client.py`의 입력과 동작 범위 |
