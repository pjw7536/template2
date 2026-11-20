# Airflow 인증·검사·직접 배포

[Airflow 가이드](../README.md)

설치·업데이트 절차는 [Airflow 가이드](../README.md)에 있습니다. 이 문서는 Keycloak 로그인 입력과 사람이 하는 확인, 검사·배포 도구의 동작 범위, 도구를 직접 실행하는 방법입니다.

- [Keycloak 로그인](#keycloak-로그인)
- [배포 도구 상세](#배포-도구-상세)

## Keycloak 로그인

기존 Keycloak realm(`etch`)에 Airflow 전용 비공개 클라이언트(confidential client)를 등록해 사용합니다. 이미지는 SSO 코드를 포함한 Airflow 3.3.2 이미지입니다.

로그인한 사용자는 기본적으로 Viewer입니다. 추가 권한이 필요한 운영자에게만 Keycloak의 `airflow` client 역할 User 또는 Admin을 부여합니다.
조직별 그룹은 사용하지 않으며 역할을 제거하면 다음 로그인부터 Viewer로 돌아갑니다. 기존 세션 이관과 통합 로그아웃은 지원 범위가 아닙니다.

### OIDC env 입력

`deploy/airflow/env/k8s.env`에 아래 값을 둡니다. 기존 DB·Fernet 키·관리자 API 계정은 유지하며 비밀값은 문서에 복사하지 않습니다.

| 키 | 입력 |
| --- | --- |
| `AIRFLOW_AUTH_MODE` | `keycloak` |
| `AIRFLOW_OIDC_ISSUER` | `https://sso.etch.samsungds.net/realms/etch` |
| `AIRFLOW_OIDC_CLIENT_ID` | `airflow` |
| `AIRFLOW_OIDC_CLIENT_SECRET` | 신규 client는 기본 env에 준비된 값, 기존 client는 기존 secret |
| `AIRFLOW_OIDC_BACKCHANNEL_BASE_URL` | Pod 접근용 realm URL, 비우면 issuer 사용 |
| `AIRFLOW_OIDC_CA_CONFIGMAP` | 사내 CA를 쓰면 `airflow-oidc-ca`(현재 선언), 공인 CA면 빈 값 |
| `AIRFLOW_OIDC_CA_BUNDLE` | CA 사용 시 `/etc/airflow/oidc-ca/ca.crt`, 아니면 빈 값 |
| `AIRFLOW_OIDC_ALLOW_HTTP` | 서버는 `false` |

브라우저 callback은 `${AIRFLOW_WEBSERVER_BASE_URL}/auth/oauth-authorized/keycloak` 하나이며 운영값은
`https://airflow.etch.samsungds.net/auth/oauth-authorized/keycloak`입니다.
CA 두 값은 함께 지정하거나 함께 비웁니다. HTTPS 인증서 검증 생략은 지원하지 않습니다.

### OIDC CA ConfigMap

`AIRFLOW_OIDC_CA_CONFIGMAP`을 지정한 경우에만 필요합니다. `airflow-up`은 ConfigMap이 없으면 CA 묶음 파일(`AIRFLOW_OIDC_CA_FILE`, 기본 `deploy/shared/certs/<issuer host>/keycloak-ca-bundle.pem`)로 namespace와 ConfigMap을 만듭니다. 기존 ConfigMap은 바꾸지 않습니다.
CA 묶음은 Keycloak 인증서의 루트·중간 CA를 포함한 PEM이며 [사내 CA 묶음](../../README.md#사내-ca-묶음)의 `make ca-bundle CA_HOST=sso.etch.samsungds.net`이 `deploy/shared/certs/ca/`의 사내 CA로 만듭니다.
ConfigMap과 CA 파일이 모두 없으면 사전 검사가 중단합니다.
ConfigMap의 `ca.crt` 키가 Pod의 `/etc/airflow/oidc-ca/ca.crt`로 읽기 전용 마운트됩니다.

[변경] CA를 교체하거나 [직접 deploy](#직접-deploy와-helm-override) 전에 ConfigMap을 미리 만들 때만 아래 명령을 씁니다.

```bash
openssl crl2pkcs7 -nocrl -certfile <Keycloak CA 묶음 PEM 절대 경로> | openssl pkcs7 -print_certs -noout
kubectl --context "<context>" get namespace airflow ||
  kubectl --context "<context>" create namespace airflow
kubectl --context "<context>" -n airflow create configmap airflow-oidc-ca \
  --from-file=ca.crt=<Keycloak CA 묶음 PEM 절대 경로> --dry-run=client -o yaml |
  kubectl --context "<context>" apply -f -
kubectl --context "<context>" -n airflow get configmap airflow-oidc-ca
```

성공: 루트·중간 CA가 출력되고 ConfigMap이 `created`·`configured`·`unchanged` 후 조회됩니다.
CA를 갱신한 뒤 [가이드 B](../README.md#b-업데이트)의 env 변경과 같은 배포를 다시 실행해 Pod를 재시작합니다.

### client 등록

`airflow` client는 기존 `portal` client와 별도로 관리합니다. `make airflow-keycloak-client`(`make ops-deploy APP=airflow`의 한 단계)가 client를 만들므로 관리자 화면에서 미리 만들 필요는 없습니다.

- 신규 client는 `deploy/airflow/env/k8s.env`에 준비된 `AIRFLOW_OIDC_CLIENT_SECRET`으로 등록합니다.
- [사람] 이미 client가 있으면 Keycloak 관리자 화면의 realm → Clients → airflow → Credentials에서 기존 Client secret을 확인해 env에 입력하며 재생성하지 않습니다.
- 기본 입력은 `deploy/airflow/env/k8s.env`이며 다른 파일은 `AIRFLOW_ENV=/절대경로/k8s.env`로 등록·검사·배포에 같게 전달합니다.

성공: `Airflow client·역할·mapper 등록 완료`.
등록기는 master realm의 admin-cli로 인증한 뒤 대상 realm의 전용 client만 관리합니다. Authorization Code + PKCE S256, RS256 ID Token,
profile·email scope, Viewer·User·Admin client 역할과 역할 mapper를 설정합니다. 기존 client secret이 env와 다르면 중단하며 회전하지 않습니다.
사용자 역할·다른 앱 client는 유지하고 운영 사용자에게 권한을 자동 부여하지 않습니다.

등록 명령은 `KEYCLOAK_ENV`(기본 `deploy/keycloak/env/prod.env`)의 공개 주소와 관리자 계정을 자동으로 사용합니다. 실행 입력의 의미는 다음과 같습니다.

| 실행 입력 | 현재 선언 | 확인 범위 |
| --- | --- | --- |
| `KEYCLOAK_ADMIN_URL` | `https://sso.etch.samsungds.net` | `/realms/etch`·`/admin`을 붙이지 않음. 명시적 localhost port-forward 주소도 허용 |
| `KEYCLOAK_ADMIN_USERNAME` | `etch-admin` | 초기 관리자 선언. 서버에서 바꿨다면 실제 관리자 계정 사용 |
| `KEYCLOAK_ADMIN_PASSWORD` | 세 값을 모두 지정하지 않으면 `KEYCLOAK_ENV`의 `bootstrap-admin-password` | Airflow 관리자 비밀번호·OIDC client secret과 구분 |
| `KEYCLOAK_ADMIN_CA_BUNDLE` | 필요할 때만 | 관리 호스트의 CA 파일 경로. Airflow Pod 내부 CA 경로와 구분 |

[사람] 다른 관리자 계정을 쓸 때만 아래처럼 주소·계정·비밀번호를 모두 직접 지정합니다. 하나라도 지정하면 `KEYCLOAK_ENV`의 값은 쓰지 않습니다.

```bash
export KEYCLOAK_ADMIN_URL=https://sso.etch.samsungds.net
export KEYCLOAK_ADMIN_USERNAME=etch-admin
read -r -s -p 'Keycloak 관리자 비밀번호: ' KEYCLOAK_ADMIN_PASSWORD; echo; export KEYCLOAK_ADMIN_PASSWORD
# 실행 호스트에 사내 CA가 필요하면 KEYCLOAK_ADMIN_CA_BUNDLE에 실제 파일 경로를 export합니다.
make airflow-keycloak-client
unset KEYCLOAK_ADMIN_PASSWORD
```

[사람] 관리자 UI에서 필요한 사용자에게 `airflow`의 `Admin` 또는 `User`를 부여합니다. 조회 사용자는 별도 할당이 필요 없으며 `portal` client의 역할은 Airflow 권한이 아닙니다.

### 로그인과 앱 간 호출 확인

배포를 마친 뒤 Airflow 로그인 화면의 Keycloak 버튼으로 확인합니다.

- 기본 사용자는 DAG 조회만 되고 관리 작업은 거부됩니다. 관리자는 관리 화면에 접근합니다.
- User·Admin 역할 제거 후 새 로그인에서 Viewer로 돌아갑니다.
- 잘못된 토큰·다른 issuer·만료 토큰은 Viewer로 처리되지 않고 로그인에 실패합니다.
- Portal → Airflow 호출은 DB 계정으로 `/auth/token`에서 JWT를 받아 API v2에 Bearer로 전달합니다. Airflow → Portal 호출은 trigger token을 사용합니다. 두 방향을 따로 검증합니다.

문제가 있으면 `AIRFLOW_AUTH_MODE=db`로 명시적으로 바꿔 재배포할 수 있으며 DB·Fernet 키·기존 API 계정을 초기화하지 않습니다.
로컬 성공을 서버 SSO 적용 완료로 간주하지 않습니다.

**남은 확인:** Portal API가 쓰는 관리자 계정을 최소 권한 전용 계정으로 바꾸는 일은 별도로 결정합니다.

## 배포 도구 상세

기본 입력은 `deploy/airflow/env/k8s.env`, namespace는 `airflow`입니다.
namespace를 바꾸면 kubectl의 `-n airflow`를, env를 바꾸면 Python `--env`·Makefile `AIRFLOW_ENV`를 같은 값으로 바꿉니다.

최초 설치는 새 DB로 진행하며 Worker의 DB 디렉터리가 기존 PostgreSQL 데이터 경로가 아닌지 확인합니다.
Airflow PVC·Secret이 남아 있다면 새 설치로 간주하지 말고 연결된 저장소부터 확인합니다. 기존 리소스나 데이터는 자동 삭제하지 않습니다.

### 검사 범위

모두 [검사]이며 클러스터를 변경하지 않고 chart를 자동 다운로드하지 않습니다.

| 명령 | 범위 | 성공 문구 |
| --- | --- | --- |
| `make server-check APP=airflow PROFILE=prod` | 저장소 env 구조와 고정 chart의 렌더. 클러스터에 연결하지 않음 | `Airflow Helm·PostgreSQL 원본 검사 통과` |
| `python3 deploy/airflow/scripts/manage.py check --env deploy/airflow/env/k8s.env --pause-new-dags` | 실제 입력의 자리표시자·비밀값 길이·URL·Fernet 키 형식. 클러스터에 연결하지 않음 | `Airflow Helm·PostgreSQL 원본 검사 통과` |
| `make airflow-check KUBE_CONTEXT="<context>"` | 아래 클러스터 사전 검사 | `설정·차트·기존 리소스·TLS·배치 검사 통과` |

오류에 표시된 env 키는 [환경설정](01-prepare.md#환경설정)에서 보완합니다. `airflow-check`의 확인 항목은 다음과 같습니다.

- 클러스터 버전, 대상 노드의 Ready·cordon 상태
- Helm override까지 반영한 각 Pod의 nodeSelector·toleration과 노드 taint. 기본 설정은 control-plane/master `NoSchedule` taint를 허용하며 내부 PostgreSQL은 자체 원본의 toleration을 따로 검사합니다.
- 기존 `airflow-postgres`·`airflow-fernet` Secret과 env의 일치, 기존 설치 흔적이 있는데 Secret이 없는 경우
- image pull·ODBC Secret, OIDC CA ConfigMap(없으면 CA 묶음 파일), IngressClass
- Ingress를 쓸 때 `etch-sso/traefik`과 공용 TLS 인증서의 도메인·만료·개인키 일치

운영 URL `https://airflow.etch.samsungds.net`은 앱별 TLS Secret이 필요 없습니다. 업무 도메인 인증서를
[공용 TLS 등록](../../README.md#공용-tls-등록)으로 먼저 등록합니다. 등록 도구가 Traefik을 다시 시작하므로 별도 반영은 필요 없고, check가 `공용 TLS 마운트가 없습니다`로 멈출 때만 `make ingress-up`을 실행합니다.

Secret 불일치·누락은 [Secret 복원](04-operations.md#2-secret-복원)을 따릅니다.
검사 통과 후에도 실제 디스크 권한, 이미지 다운로드, 외부 DB 접속, Portal 연동은 따로 확인합니다.

### 배포 내용 미리 보기

[검사] 클러스터를 바꾸지 않고 로컬 `deploy/airflow/rendered`에 결과를 씁니다.

```bash
python3 deploy/airflow/scripts/manage.py render \
  --env deploy/airflow/env/k8s.env --pause-new-dags \
  --output deploy/airflow/rendered
```

성공: `렌더 완료: Secret 값은 출력 파일에 포함하지 않았습니다.`

| 출력 | 검토할 내용 |
| --- | --- |
| `storage.json` | Worker hostname, DB·로그·DAG 경로와 용량, Retain 정책 |
| `postgres.json` | 내부 DB 이미지·권한·Service, external 모드에서는 빈 목록 |
| `values.json` | 이미지 태그·노드·ODBC·OIDC CA·URL·신규 DAG 일시정지 설정 |
| `airflow.yaml` | Airflow workload·Ingress·migration 및 관리자 Job |

Secret 값은 출력에 포함하지 않습니다. **`airflow.yaml`을 직접 kubectl apply하지 않습니다.** 실제 배포는 Helm hook으로 DB migration과 관리자 생성 순서를 지킵니다.
`--pause-new-dags`는 make 배포와 같은 신규 DAG 정책으로 검토하는 옵션입니다.

### `airflow-up` 동작

진행 순서는 namespace·OIDC CA ConfigMap·Worker 폴더·DAG 초기 파일 준비 → 공용 Traefik 감시 권한·namespace 추가 → Secret → local PV/PVC → 내부 PostgreSQL → Helm migration·관리자 생성 → Airflow 재시작·rollout입니다.
외부 DB 모드는 내부 PostgreSQL 적용과 대기를 생략합니다. Keycloak과 Keycloak DB는 재배포하지 않습니다.
공용 Traefik은 최신 감시 namespace 목록에 Airflow를 추가하는 패치만 적용하며, 동시 변경으로 거부되면 기존 앱 연결을 확인한 뒤 검사·배포를 다시 실행합니다.

- 기존 DB/PVC는 삭제하지 않습니다. 기존 Secret과 DB 비밀번호·Fernet 키가 다르면 중단합니다.
- 관리자 계정은 없을 때만 생성하며 env의 관리자 비밀번호를 바꿔도 기존 계정의 비밀번호·역할은 바뀌지 않습니다.
- runtime Secret 변경은 배포 마지막의 Pod 재시작으로 반영합니다.
- **신규 DAG는 일시정지로 생성하고 기존 DB의 DAG 활성 상태는 유지합니다.** 기존 scheduler가 있다면 전환 전에 작업을 정리하고 중지합니다.

성공: migration·관리자 hook과 scheduler·API server·DAG processor·triggerer rollout이 끝나고 `Airflow 기동 완료`와 URL이 출력됩니다.


### 선택 입력

| 선택 입력 | 사용하는 경우 |
| --- | --- |
| `AIRFLOW_ENV=/절대경로/k8s.env` | 다른 env 전달 |
| `AIRFLOW_TLS_SOURCE=<namespace>/<secret>` | 기존 인증서를 공용 Traefik 저장소에 등록 |
| `AIRFLOW_CHART_FILE=/절대경로/airflow-1.22.0.tgz` | 별도 위치의 chart. Make 변수가 아니라 환경변수로 전달([chart 준비](02-artifacts.md#1-공식-chart-준비)) |

다른 namespace의 기존 인증서를 공용 저장소로 가져올 때만 `AIRFLOW_TLS_SOURCE=<namespace>/<secret>`을 check와 up에 함께 전달합니다.
check는 원본을 검사만 하고, up은 공용 저장소에 등록하며 Airflow namespace에 복제하지 않습니다.

### 접속과 연동 확인

[조회] 리소스 상태를 확인합니다.

```bash
kubectl --context "<context>" -n airflow get pods,pvc -o wide
kubectl --context "<context>" -n airflow get ingress
```

[사람] 브라우저 접속과 업무 연동은 사람이 확인합니다. Ingress 없이 앱 접속만 분리해 볼 때는 port-forward를 씁니다. 터미널을 점유하는 명령이므로 운영 agent는 실행하지 않습니다.

```bash
kubectl --context "<context>" -n airflow port-forward svc/airflow-api-server 8080:8080
```

port-forward는 터미널을 점유하며 Ctrl+C로 종료합니다. 같은 컴퓨터의 브라우저에서 `http://localhost:8080`에 접속하고,
원격 서버에서 실행했다면 [사람]이 PC에서 SSH 터널을 연결합니다.

```bash
ssh -N -L 8080:127.0.0.1:8080 <port-forward 실행 서버 user@host>
```

HTTPS는 `AIRFLOW_WEBSERVER_BASE_URL`로도 접속합니다. DNS는 Ingress 진입 주소를 가리키며 루트 경로(`/`)를 앱에 그대로 전달합니다.

1. Keycloak 또는 관리자 계정으로 로그인합니다([로그인 확인](#로그인과-앱-간-호출-확인)).
2. DAG가 보이고 import 오류가 없는지 확인합니다.
3. 기존 Connection·Variable 복호화와 ODBC 설정을 확인합니다.
4. Airflow → Portal API 주소와 trigger token을 양쪽에서 맞추고 시험 작업으로 확인합니다.
5. Portal → Airflow 호출을 쓴다면 아래 Portal 설정을 확인합니다.
6. 기존 scheduler의 중복 실행이 없는지 확인한 뒤 필요한 DAG만 활성화합니다.

| Portal 설정 | 의미 |
| --- | --- |
| `AIRFLOW_BASE_URL` | 내부 호출 주소. 기본 namespace: `http://airflow-api-server.airflow.svc.cluster.local:8080` |
| `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD` | 실제 Airflow 계정과 일치 |
| `AIRFLOW_PUBLIC_BASE_URL` | 브라우저에서 접근하는 Airflow 공개 URL |

위 변수는 Portal 설정이며 Airflow k8s.env에 추가하지 않습니다. Pod Ready와 실제 업무 성공은 별도 확인이며 실패 시 [문제 해결](04-operations.md#5-실패-단계-확인)을 사용합니다.

### 직접 deploy와 Helm override

별도 Ingress controller나 환경별 Helm override가 필요한 경우에만 사용합니다. 이 경로는 공용 Traefik 연결, 인증서 등록, OIDC CA ConfigMap·Worker 폴더·DAG 초기 파일 준비를 하지 않으므로
controller·라우팅·TLS Secret·imagePullSecret·ODBC Secret, [OIDC CA ConfigMap](#oidc-ca-configmap), [Worker 폴더](01-prepare.md#worker-폴더-직접-준비)를 먼저 준비합니다.

[승인] DB migration을 실행하고 Airflow를 재시작합니다.

```bash
python3 deploy/airflow/scripts/manage.py deploy \
  --env deploy/airflow/env/k8s.env --context "<context>" \
  --pause-new-dags
```

`--pause-new-dags`를 생략하면 `helm/values.yaml` 기본값에 따라 **신규 DAG가 활성 상태로 생성**됩니다. 기존 DAG의 일시정지 상태는 어느 경로에서도 유지합니다.
비밀값 없는 override는 `check`, `render`, `deploy`에 같은 `--values /절대경로/values.yaml`을 전달합니다. Makefile의 airflow-check/up은 override를 전달하지 않습니다.
override는 생성 values 뒤에 적용되어 노드·DAG 정책도 덮어쓸 수 있으므로 렌더 결과를 확인합니다.
재시작·준비 대기는 최종 렌더에 있는 Deployment·StatefulSet·DaemonSet만 대상으로 합니다(예: `triggerer.enabled: false`이면 triggerer 제외).

자원 기본값의 원본은 `helm/values.yaml`과 `k8s/postgres/stack.json`입니다. parallelism=32, DAG별 task=16·run=16, API server worker=4이며
초기화 Job은 default_pool slots를 -1로 설정합니다. CPU·메모리 제한은 실제 작업량과 서버 사양에 맞춰 조정합니다.
