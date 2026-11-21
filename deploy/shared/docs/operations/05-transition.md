# 전환 런북: 배포된 서버에 새 배포 구조 적용

[공통 안내](../README.md) · 이전: [배포 상태 대조](04-drift.md) · [배포 가이드](../../../README.md)

이미 앱이 배포된 서버가 새 checkout을 받은 뒤 **한 번** 수행하는 순서입니다. 아직 아무 앱도 배포하지 않은 서버는 이 문서가 필요 없고 [앱 설치 순서](../../../README.md#앱-설치-순서)대로 설치합니다.
명령은 관리 호스트의 저장소 루트에서 실행합니다. 단계 표시와 공통 규칙은 [배포 가이드](../../../README.md#문서-읽는-법)를 따릅니다.

이 문서는 임시 문서입니다. 아래 `적용 여부 확인`이 모든 서버에서 `적용됨`이면 항목을 지웁니다.

## 적용 여부 확인

[조회] 배포 기록이 있는 앱을 조회합니다.

```bash
kubectl --context "<context>" get configmaps -A -l deploy-record -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name
```

| 작업 | 실행 조건 |
| --- | --- |
| [1. 공용 Traefik 인수](#1-공용-traefik-인수) | 기존 Traefik이 있고 `deploy-record-ingress`가 없는 경우 |
| [2. 배포된 앱의 기록 갱신](#2-배포된-앱의-기록-갱신) | 기존 앱에서 대조가 배포 기록 또는 리소스 차이를 보고하는 경우 |
| [3. Portal env 값 반영](#3-portal-env-값-반영) | Portal이 설치돼 있고 Airflow 호출에 필요한 host 또는 계정 입력을 확인해야 하는 경우 |
| [4. 초기 계정 값 확인](#4-초기-계정-값-확인) | 기존 설치의 실제 계정과 연결에 쓰는 env 또는 계정 파일이 맞는지 확인해야 하는 경우 |
| [5. Airflow 이미지에서 DAG 분리](#5-airflow-이미지에서-dag-분리) | 기존 Airflow 설치에 새 이미지나 DAG 폴더를 적용할 경우 |
| [6. Keycloak과 IAM 설정 확인](#6-keycloak과-iam-설정-확인) | 기존 realm·Headlamp client 또는 IAM 설정을 배포 정의와 맞출 경우 |

`deploy-record-ingress`는 공용 Traefik 인수 여부를 확인하는 데 사용합니다. 다른 작업은 해당 앱의 배포 기록과 실제 상태로 확인합니다. 적용할 항목이 있으면 시작 전 검사 후 해당 절의 순서대로 진행합니다. Airflow 갱신이 필요하면 [DAG 분리 절차](#5-airflow-이미지에서-dag-분리)에서 기존 DAG 위치를 먼저 확인합니다.

## 0. 시작 전 검사

1. [검사] 새 checkout의 배포 정의를 클러스터 없이 검사합니다.
   ```bash
   make server-check APP=all
   ```
   성공: 앱마다 `서버 원본 검사 통과: <app>`. 실패하면 저장소 문제이므로 멈추고 실패한 앱과 오류 마지막 줄을 보고합니다. 클러스터는 아직 바뀌지 않았습니다.
2. [조회] 어떤 앱이 배포돼 있는지 확인하고 기록해 둡니다.
   ```bash
   make drift-check KUBE_CONTEXT="<context>" DRIFT_JSON=1 DRIFT_SKIP_MANIFEST=1
   ```
   `apps[]`에서 `namespace`가 있고 `findings`에 `query` 오류나 `대상 워크로드 없음`이 없는 앱을 확인합니다. `resultCode`가 1·2이면 `findings`를 보고 배포 기록 차이와 조회 실패를 확인합니다.
3. [조회] 공용 Traefik을 인수할 경우 현재 감시 namespace와 배치를 확인합니다. 1단계 뒤에 같은지 비교합니다.
   ```bash
   kubectl --context "<context>" -n etch-sso get deployment traefik -o jsonpath='{.spec.replicas}{"\n"}{.spec.template.spec.containers[0].args}{"\n"}{.metadata.annotations.deploy\.tailwind\.local/vip-backends}{"\n"}'
   ```

저장소 밖 env로 배포한 앱은 이 문서의 모든 `make` 명령에 같은 env 변수(예: `AIRFLOW_ENV=<경로>`)를 붙입니다. 변수 이름은 각 앱 가이드의 `입력` 표에 있습니다.

## 1. 공용 Traefik 인수

Traefik이 이미 있으면 같은 리소스를 `ingress` 앱의 이름으로 다시 적용하고 배포 기록을 만듭니다. 감시 namespace와 VIP 배치는 보존됩니다.

1. [검사] 변경 없이 검사합니다.
   ```bash
   make ingress-check KUBE_CONTEXT="<context>"
   ```
   성공: `공용 Ingress 원본·배치 검사 통과. 클러스터를 변경하지 않았습니다.`
2. [변경] 적용하고 기록합니다. Pod template이 같으면 Traefik은 다시 시작되지 않습니다.
   ```bash
   make ops-deploy APP=ingress KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.
3. [조회] 0-3의 명령을 다시 실행해 replica 수, `--providers.kubernetesingress.namespaces=` 값, VIP 기록이 전과 같은지 확인합니다. 다르면 멈추고 전후 값을 보고합니다. 손으로 고치지 않습니다.
4. [조회] 공개 주소가 그대로 응답하는지 확인합니다. 배포된 앱마다 실행합니다.
   ```bash
   make <app>-smoke KUBE_CONTEXT="<context>"
   ```

## 2. 배포된 앱의 기록 갱신

0-2에서 배포된 것으로 확인한 앱에 대해 [앱 설치 순서](../../../README.md#앱-설치-순서) 표의 순서로 수행합니다.

1. [조회] 리소스까지 대조합니다.
   ```bash
   make drift-check APP=<app> KUBE_CONTEXT="<context>"
   ```
2. 결과에 따라 하나를 수행합니다.

   | `manifest` 줄 | 뜻 | 할 일 |
   | --- | --- | --- |
   | `리소스 n/n개 일치`이고 기록만 이전 내용을 가리킴 | 클러스터 리소스가 현재 정의와 같음 | [변경] 실제 배포에 사용한 env로 기록을 갱신합니다 |
   | `DRIFT manifest …` 또는 `DRIFT input …` 줄이 있음 | 리소스 또는 배포 입력이 다름 | [대조 결과 해석](04-drift.md#결과-해석과-조치)에서 차이의 원인을 확인합니다. 갱신이 필요하면 그 앱 가이드의 `B. 업데이트`를 따릅니다 |
   | `UNKNOWN manifest 현재 코드 렌더 실패` | 입력이나 chart가 없음 | `make ops-preflight APP=<app> KUBE_CONTEXT="<context>"`로 원인을 확인합니다 |

   기록만 갱신하는 명령입니다.
   ```bash
   make deploy-record APP=<app> KUBE_CONTEXT="<context>"
   ```
   성공: `배포 기록 저장: <namespace>/deploy-record-<app> commit=…`.
3. [조회] 다시 대조해 `resultCode` 0을 확인합니다.
   ```bash
   make drift-check APP=<app> KUBE_CONTEXT="<context>" DRIFT_JSON=1
   ```

## 3. Portal env 값 반영

Portal이 배포돼 있을 때만 수행합니다.

1. [검사] Portal API env에 Airflow가 호출하는 클러스터 내부 host가 허용돼 있는지 확인합니다. 저장소 밖 env를 쓰면 그 경로를, 아니면 `deploy/portal/env/prod/api.env`를 넣습니다.
   ```bash
   grep -c '^DJANGO_ALLOWED_HOSTS=.*api\.tailwind-internal\.svc\.cluster\.local' "<Portal API env 경로>"
   ```
   `1`이면 반영돼 있습니다. `0`이면 [운영 입력 파일](../infrastructure/access.md#운영-입력-파일)의 방법으로 그 파일의 `DJANGO_ALLOWED_HOSTS` 값 끝에 `,api.tailwind-internal.svc.cluster.local`을 더합니다.
2. [검사] Portal이 쓰는 Airflow 계정 비밀번호가 Airflow 관리자 비밀번호와 같은지 값 없이 비교합니다.
   ```bash
   bash -c 'portal=$(sed -n "s/^AIRFLOW_PASSWORD=//p" "$1"); airflow=$(sed -n "s/^AIRFLOW_ADMIN_PASSWORD=//p" "$2"); [[ -n "$portal" && "$portal" == "$airflow" ]] && echo 일치 || echo 불일치' _ "<Portal API env 경로>" "<Airflow env 경로>"
   ```
   `불일치`면 Portal API env의 `AIRFLOW_PASSWORD`를 Airflow env의 `AIRFLOW_ADMIN_PASSWORD` 값으로 맞춥니다. Airflow 쪽 값은 바꾸지 않습니다.
3. [변경] 1·2에서 값을 고쳤거나 저장소 기본 env를 쓰고 있으면 Portal에 반영합니다. API 이미지가 같으면 migration은 실행되지 않고 Pod만 다시 시작됩니다.
   ```bash
   make ops-deploy APP=portal KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.

## 4. 초기 계정 값 확인

설치 시 계정 파일 또는 env로 만든 실제 계정은 이미 배포된 앱에 남습니다. 각 앱에 적용한 env·계정 파일을 기준으로 아래를 확인합니다.

1. FTP가 배포돼 있으면 [검사] 계정 파일과 기존 Secret을 비교합니다.
   ```bash
   make ftp-check KUBE_CONTEXT="<context>"
   ```
   통과하면 할 일이 없습니다. `기존 FTP Secret과 계정 파일이 다릅니다`면 서버는 이전 계정으로 동작 중입니다. 새 계정으로 바꾸는 것은 접속 중인 클라이언트에 영향을 주므로 [승인]이며 [계정 변경](../../../ftp/docs/02-operations.md#5-계정-변경)을 따릅니다. 승인받지 못하면 이전 계정을 그대로 두고 그 사실을 보고합니다. 이 경우 이후의 FTP 명령은 이전 계정 파일을 `FTP_CREDENTIAL_FILE=<경로>`로 지정해야 통과합니다.
2. Monitoring이 배포돼 있으면 할 일이 없습니다. Grafana 관리자 Secret이 이미 있으면 계정 파일을 읽지 않습니다. 실제 로그인 비밀번호를 새 값으로 맞추라는 요청이 있을 때만 [Monitoring 가이드](../../../monitoring/README.md#b-업데이트)의 `Grafana 비밀번호` 행을 따릅니다.
3. Airflow가 배포돼 있으면 관리자 계정의 실제 비밀번호를 env 값으로 맞춥니다. Airflow는 관리자 계정이 이미 있으면 env의 비밀번호를 반영하지 않는데, Portal은 env의 새 값으로 Airflow를 호출하기 때문입니다.
   1. [변경] Airflow를 다시 배포해 Secret `airflow-admin`에 새 값을 넣습니다. 배포 마지막에 Airflow Pod가 다시 시작되므로 실행 중인 DAG run이 없을 때 실행합니다([Airflow 가이드](../../../airflow/README.md#b-업데이트)의 env 변경 행).
      ```bash
      make ops-deploy APP=airflow KUBE_CONTEXT="<context>"
      ```
      성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.
   2. [변경] 관리자 계정의 비밀번호를 Secret의 값으로 바꿉니다. 값은 화면에 출력되지 않습니다.
      ```bash
      kubectl --context "<context>" -n airflow exec deployment/airflow-scheduler -- airflow users reset-password \
        --username "$(kubectl --context "<context>" -n airflow get secret airflow-admin -o jsonpath='{.data.username}' | base64 -d)" \
        --password "$(kubectl --context "<context>" -n airflow get secret airflow-admin -o jsonpath='{.data.password}' | base64 -d)"
      ```
      성공: 종료 코드 0과 비밀번호를 바꿨다는 출력. 실패하면 출력의 오류 줄과 함께 보고하고, Portal의 Airflow 연동은 확인 전까지 정상으로 보고하지 않습니다.
   3. [조회] Portal이 배포돼 있으면 위 두 단계와 [3. Portal env 값 반영](#3-portal-env-값-반영)을 마친 뒤 Portal의 Airflow 연동을 [화면 기능 확인](../infrastructure/access.md#화면-기능-확인) 절의 방법으로 확인합니다.

## 5. Airflow 이미지에서 DAG 분리

Airflow가 배포된 경우에 수행합니다.

1. [검사] 현재 checkout이 이미지를 바꾸는지와 DAG 폴더 사용 여부를 확인합니다. 클러스터를 바꾸지 않습니다.
   ```bash
   make airflow-check KUBE_CONTEXT="<context>"
   kubectl --context "<context>" -n airflow get pvc airflow-dags --ignore-not-found
   ```

   | 결과 | 판단 |
   | --- | --- |
   | `이미지 변경: 없음` | `적용됨`. 이 절을 건너뜁니다 |
   | `이미지 변경: 최초 설치(…)` | Airflow가 배포돼 있지 않습니다. 이 절을 건너뛰고 [Airflow 가이드](../../../airflow/README.md#a-최초-설치)로 설치합니다 |
   | `이미지 변경: 있음(…)`이고 `airflow-dags`가 `Bound` | DAG 폴더를 이미 쓰는 설치입니다. 폴더의 파일을 그대로 쓰므로 3번으로 갑니다 |
   | `이미지 변경: 있음(…)`이고 `airflow-dags` 줄이 없음 | 이미지의 DAG로 실행 중입니다. 2번부터 수행합니다 |
   | `오류: DAGS_HOST_PATH가 필요합니다` | 저장소 밖 env에 DAG 폴더 경로가 없습니다. [운영 입력 파일](../infrastructure/access.md#운영-입력-파일)의 방법으로 `DAGS_HOST_PATH=/appdata/airflow/dags`와 `DAGS_STORAGE_SIZE=1Gi`를 넣고 이 단계를 다시 실행합니다 |

2. [변경] 실행 중인 DAG 파일을 DAG 폴더로 옮깁니다. 새 이미지에는 DAG가 없으므로 배포보다 먼저 합니다. [공유 폴더 전환](../../../airflow/docs/04-operations.md#공유-폴더-전환)의 1~2번을 수행합니다.
   성공: 그 절 2번의 목록에 기존 DAG 파일이 보입니다.
3. [승인] 새 이미지로 배포합니다. 이미지가 바뀌어 실행 중 작업이 중단되므로 [Airflow 가이드 B](../../../airflow/README.md#b-업데이트)의 `이미지 변경: 있음` 행을 따릅니다.
   ```bash
   make ops-deploy APP=airflow KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.
4. [조회] DAG가 그대로 보이는지 확인합니다.
   ```bash
   kubectl --context "<context>" -n airflow get pods,pvc
   kubectl --context "<context>" -n airflow exec deployment/airflow-scheduler -- airflow dags list
   kubectl --context "<context>" -n airflow exec deployment/airflow-scheduler -- airflow dags list-import-errors
   ```
   성공: 모든 Pod가 Ready, `airflow-dags`가 `Bound`, 배포 전과 같은 DAG가 목록에 있고 import 오류가 없습니다. 빠진 DAG는 `make airflow-dags-sync KUBE_CONTEXT="<context>"`([방법](../../../airflow/docs/04-operations.md#dag-파일-추가수정삭제))로 넣습니다.

DAG·테스트만 바뀐 커밋은 이미지 tag가 같으므로 `make airflow-check`가 `이미지 변경: 없음`을 출력하고, DAG는 `make airflow-dags-sync`로만 반영합니다.

## 6. Keycloak과 IAM 설정 확인

1. [조회] 관리 호스트에서 배포에 사용한 env로 Keycloak의 username 정책과 원소속 부서 프로필을 확인합니다.
   ```bash
   python3 deploy/keycloak/scripts/admin_env.py --env "<Keycloak env 경로>" -- python3 -c '
   import sys
   sys.path.insert(0, "deploy/keycloak/scripts")
   from init_sdwt import Admin
   api = Admin("etch")
   print("registrationEmailAsUsername:", api.call("GET")["registrationEmailAsUsername"])
   profile = api.call("GET", "users/profile")
   print("original_deptname:", any(field["name"] == "original_deptname" for field in profile["attributes"]))
   '
   ```
   기대 결과는 `registrationEmailAsUsername: False`와 `original_deptname: True`입니다. 차이가 있으면 [변경] [Keycloak 업데이트](../../../keycloak/README.md#b-업데이트)를 실행한 뒤 위 조회를 반복합니다.
2. Headlamp가 설치된 환경은 [조회] [기존 client 대조](../../../headlamp/docs/02-authentication.md#2-기존-client-대조)로 redirect·PKCE·그룹 mapper를 확인합니다. 차이나 승인된 신규 관리자가 있으면 [변경] [Headlamp 업데이트](../../../headlamp/README.md#b-업데이트)를 수행한 뒤 [배포 후 확인](../../../headlamp/README.md#c-배포-후-확인)을 실행합니다.
3. [조회] 이전 IAM 설정만 반영했으면 `kubectl --context "<context>" -n iam get deployment,pvc,ingress`로 웹·API·SQLite PVC의 존재 여부를 확인합니다. 기존의 저장소 밖 IAM env에 `IAM_STORAGE_NODE`와 `IAM_DATA_HOST_PATH`가 없으면 [IAM 입력](../../../iam/README.md#입력)의 키를 추가합니다. [변경] 워크로드가 없으면 [IAM 최초 설치](../../../iam/README.md#a-최초-설치), 이미 있으면 [IAM 업데이트](../../../iam/README.md#b-업데이트)를 시행합니다. 공개 주소는 [서비스 접속 주소](../infrastructure/services.md#서비스-접속-주소)와 대조하고 [배포 후 확인](../../../iam/README.md#c-배포-후-확인)을 반복합니다.

## 완료 확인

[조회] 변경한 워크로드의 리소스와 배포 기록을 대조합니다. IAM 설정의 완료 기준은 [IAM 가이드](../../../iam/README.md#c-배포-후-확인)를 따릅니다.

```bash
make drift-check APP=<app> KUBE_CONTEXT="<context>" DRIFT_JSON=1
```

`resultCode`가 0이면 해당 항목의 확인 결과를 [운영 기록](01-checkout.md#운영-기록)에 남깁니다.

## 실패했을 때

- 0단계에서 실패하면 클러스터는 바뀌지 않았습니다. 실패한 검사와 오류 마지막 줄을 보고합니다.
- 1단계의 `ops-deploy`가 실패하면 `failedStep`과 [ingress 가이드](../../ingress/README.md#문제-해결과-멈춤-조건)의 표를 봅니다. Traefik을 지우거나 `kubectl apply -k`로 다시 만들지 않습니다.
- 2·3·4단계에서 한 앱이 실패하면 그 앱만 멈추고 다음 앱을 계속합니다. 앱 가이드의 `문제 해결과 멈춤 조건`을 따릅니다.
- 5단계의 배포 뒤 DAG 목록이 비어 있으면 DAG 폴더가 비어 있는 것입니다. Airflow를 되돌리지 않고 `make airflow-dags-sync KUBE_CONTEXT="<context>"`로 저장소의 DAG를 넣습니다. 저장소에 없던 서버 전용 DAG는 5-2번에서 만든 백업 tar로 [공유 폴더 전환](../../../airflow/docs/04-operations.md#공유-폴더-전환)의 2번을 다시 합니다.
- checkout을 이전 commit으로 되돌리지 않습니다. 저장소 수정이 필요하면 원인과 필요한 수정을 보고합니다.
