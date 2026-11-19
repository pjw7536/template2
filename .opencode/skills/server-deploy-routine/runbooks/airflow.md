# Airflow 배포 런북

공통 규칙은 [00-common.md](00-common.md)를 먼저 따릅니다. 명령은 관리 호스트 저장소 루트에서 실행합니다.
원본 문서: [README](../../../../deploy/airflow/README.md) · [준비](../../../../deploy/airflow/docs/01-prepare.md) · [이미지·chart](../../../../deploy/airflow/docs/02-artifacts.md) · [배포](../../../../deploy/airflow/docs/03-deploy.md) · [운영](../../../../deploy/airflow/docs/04-operations.md). 이 런북과 다르면 원본이 우선입니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| namespace | `airflow` |
| 실행 Worker | `khinfow01`. DB·로그·DAG·ODBC는 `/appdata/airflow/{postgres,logs,dags,odbc}` |
| 공개 주소 | `https://airflow.etch.samsungds.net` (Keycloak 로그인, client `airflow`) |
| 배포 명령 | `make airflow-check` → `make airflow-up` (성공 시 배포 기록 자동) |
| 완료 기준 | `Airflow 기동 완료. Airflow URL: https://airflow.etch.samsungds.net`, scheduler·api-server·dag-processor·triggerer·`airflow-postgres-0` Ready, PVC Bound, 사람이 로그인·DAG import 오류 없음 확인 |
| 먼저 필요한 것 | Keycloak 운영, 공용 TLS(`airflow.etch.samsungds.net`), khinfow01 이미지·폴더·DAG·ODBC, chart 파일 |

이미지는 관리 호스트가 아니라 `khinfow01`에서 빌드합니다. 빌드는 [사람]이 [이미지 준비](../../../../deploy/airflow/docs/02-artifacts.md#2-dag-포함-이미지-준비)로 합니다.

## 사람이 해야 하는 일

- [사람] khinfow01 sudo 작업: `/appdata/airflow/postgres`(999:999 0700), `logs`(50000:0 0770), `dags`(root:root 0755), `odbc`(50000:0 0750) 폴더, ODBC 파일 배치
- [사람] khinfow01에서 이미지 빌드와 `k8s.io` containerd 등록(`airflow:<AIRFLOW_IMAGE_TAG>`). 빌드 host에도 배포와 같은 실제 값의 `k8s.env`가 필요함([두 단계 이미지 빌드](../../../../deploy/airflow/docs/02-artifacts.md#두-단계-이미지-빌드))
- [사람] DAG 공유 폴더 `/appdata/airflow/dags`에 DAG 파일과 준비 표식 `.airflow-dags-initialized` 배치([공유 폴더 전환](../../../../deploy/airflow/docs/04-operations.md#공유-폴더-전환))
- [사람] env 실제 값 입력. 저장소 env에 `AIRFLOW_ADMIN_PASSWORD`, `AIRFLOW_OIDC_CLIENT_SECRET` 자리표시자가 남아 있으면 배포할 수 없음
- [사람] Keycloak 관리자 비밀번호 입력이 필요한 client 등록, 사용자 역할 부여
- [사람] DNS, 인증서 파일, DAG 활성화(신규 DAG는 일시정지로 생성됨), 브라우저 로그인 확인
- [사람] 업데이트 전 DAG 일시정지·실행 중 작업 완료·DB 백업

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `AIRFLOW_ENV` | Airflow env 경로 | `deploy/airflow/env/k8s.env`. 외부 경로면 check·up·drift-check에 같은 값 |
| `AIRFLOW_TLS_SOURCE` | 다른 namespace의 기존 인증서를 공용 TLS로 가져올 때만 `<namespace>/<secret>` | 비움 |
| chart | `deploy/airflow/helm/vendor/airflow-1.22.0.tgz` | 없으면 A-2로 준비 |
| OIDC CA | ConfigMap `airflow/airflow-oidc-ca`(키 `ca.crt`) | CA 파일은 `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem` |

## A. 최초 설치

1. [사람] 위 [사람이 해야 하는 일](#사람이-해야-하는-일)의 폴더·이미지·DAG·ODBC·env·DNS·인증서가 끝났는지 사용자에게 확인합니다.
2. [변경] chart 준비(로컬 파일). 파일이 이미 있으면 생략합니다.
   ```bash
   ls -l deploy/airflow/helm/vendor/airflow-1.22.0.tgz || python3 deploy/airflow/scripts/manage.py fetch-chart
   ```
   성공: 파일이 있거나 `사내 Helm 미러 chart 다운로드·SHA-256 검사 완료`. SHA-256 불일치면 멈춥니다.
3. [조회] 노드 확인
   ```bash
   kubectl --context kubernetes-admin@kubernetes get node khinfow01 -o wide
   ```
   성공: `Ready`.
4. [검사] 원본·실제 env 검사
   ```bash
   make server-check APP=airflow PROFILE=prod
   python3 deploy/airflow/scripts/manage.py check --env deploy/airflow/env/k8s.env --pause-new-dags
   ```
   성공: 두 번째 출력에 `(실제 설정; 클러스터 적용 없음)`. `실제 값으로 교체하세요: <키>`면 [사람]에게 env 입력을 요청하고 멈춥니다.
5. [변경] OIDC CA ConfigMap 준비(승인 필요). CA 파일이 없으면 [Headlamp 런북](headlamp.md) A-6의 CA 묶음 생성을 먼저 합니다.
   ```bash
   kubectl --context kubernetes-admin@kubernetes get namespace airflow || kubectl --context kubernetes-admin@kubernetes create namespace airflow
   kubectl --context kubernetes-admin@kubernetes -n airflow create configmap airflow-oidc-ca --from-file=ca.crt=deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem --dry-run=client -o yaml | kubectl --context kubernetes-admin@kubernetes apply -f -
   ```
6. [변경] 공용 TLS 등록: `airflow.etch.samsungds.net` host로 [공통 TLS 등록](00-common.md#공용-tls-등록)을 합니다. 이미 등록돼 있으면 생략합니다.
7. [사람] Keycloak client 등록: 관리자 비밀번호 입력이 필요하므로 사용자가 [client 등록](../../../../deploy/airflow/docs/03-deploy.md#3-client-등록)의 `make airflow-keycloak-client` 블록을 실행하도록 요청합니다. 기존 client secret과 env가 다르다는 오류면 멈춥니다.
8. [검사] 클러스터 사전 검사
   ```bash
   make airflow-check KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   성공: `설정·차트·기존 리소스·TLS·배치 검사 통과. 클러스터를 변경하지 않았습니다.` `공용 TLS 마운트가 없습니다`면 사용자 승인 후 [공통 Traefik 갱신](00-common.md#공용-traefik-검사갱신)의 `ingress-up`을 하고 다시 검사합니다.
9. [변경] 배포(승인 필요). DB migration이 실행되며 되돌릴 수 없습니다.
   ```bash
   make airflow-up KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   성공: `Airflow 기동 완료. Airflow URL: https://airflow.etch.samsungds.net`과 `배포 기록 저장: airflow/deploy-record-airflow`.
10. [조회] [C. 배포 후 확인](#c-배포-후-확인)을 실행합니다.
11. [사람] 브라우저 로그인, DAG import 오류, Connection·Variable 복호화, Portal 연동 확인을 요청합니다. DAG 활성화는 사용자가 결정합니다.

## B. 업데이트

먼저 [사람]에게 DAG 일시정지·실행 중 작업 완료·DB 백업([DB 백업](../../../../deploy/airflow/docs/04-operations.md#1-db와-설정-백업))을 확인받습니다.

| 변경 | 실행 |
| --- | --- |
| DAG 파일만(공유 폴더 사용 중) | 재배포 없음. [사람]이 khinfow01의 `/appdata/airflow/dags`에 반영 |
| 이미지 태그(플러그인·패키지·ODBC) | [사람] khinfow01 빌드·등록 → A-8 → A-9 → C |
| env(알림·OIDC·runtime 값) | A-4 → A-8 → A-9 → C. Pod는 배포 마지막에 재시작됨 |
| OIDC CA | A-5 → A-9 |
| 인증서 | A-6 |
| DB 비밀번호·Fernet 키 | 멈추고 사람에게 묻기. 바꾸면 안 되며 기존 Secret과 다르면 배포가 중단됨 |

외부 env를 쓰면 모든 단계에 같은 경로를 붙입니다.

```bash
make airflow-check KUBE_CONTEXT=kubernetes-admin@kubernetes AIRFLOW_ENV=<env 절대 경로>
make airflow-up KUBE_CONTEXT=kubernetes-admin@kubernetes AIRFLOW_ENV=<env 절대 경로>
```

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n airflow get pods,pvc,jobs -o wide
kubectl --context kubernetes-admin@kubernetes -n airflow get ingress
kubectl --context kubernetes-admin@kubernetes -n airflow get events --sort-by=.lastTimestamp
make drift-check APP=airflow KUBE_CONTEXT=kubernetes-admin@kubernetes
```

성공: 모든 Pod Ready, PVC(`airflow-dags` 포함) Bound, drift-check 종료 코드 `0`.

실패하면 로그를 조회합니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n airflow logs deployment/airflow-scheduler --tail=100
kubectl --context kubernetes-admin@kubernetes -n airflow logs deployment/airflow-api-server --tail=100
kubectl --context kubernetes-admin@kubernetes -n airflow logs deployment/airflow-dag-processor --tail=100
kubectl --context kubernetes-admin@kubernetes -n airflow logs statefulset/airflow-postgres --tail=100
```

## 멈추고 사람에게 묻는 조건

- 검사에서 `실제 값으로 교체하세요`, Secret 불일치·누락, OIDC CA ConfigMap 없음, chart SHA-256 불일치
- `airflow-up` 중 migration·관리자 Job 실패, Traefik 패치가 동시 변경으로 거부됨
- Pod가 Pending·ImagePullBackOff(이미지가 khinfow01 `k8s.io`에 없음)·ODBC 마운트 실패
- `/appdata/airflow/dags`에 준비 표식이 없어 scheduler·dag-processor init이 실패
- 기존 Airflow PVC·Secret이 남아 있는데 최초 설치로 진행하려는 경우
- `python3 deploy/airflow/scripts/manage.py init-secrets`, `manage.py deploy`, `helm uninstall`, Secret 재생성이 필요해 보이는 경우. 실행하지 않습니다.
