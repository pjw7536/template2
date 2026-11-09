# Airflow 인증·배포·검증

[앱 안내](../README.md)

- [Keycloak 로그인](#keycloak-로그인)
- [배포와 검증](#배포와-검증)

## Keycloak 로그인

기존 Keycloak realm에 Airflow 전용 비공개 클라이언트(confidential client)를 등록하는 안내입니다.
로그인한 사용자는 기본적으로 Viewer가 됩니다.

추가 권한이 필요한 운영자에게만 Keycloak 사용자 화면에서 `airflow` client의 User 또는 Admin을 부여합니다.
조직별 그룹은 사용하지 않습니다. 역할을 제거하면 다음 로그인부터 Viewer로 돌아갑니다.
기존 세션 이관과 통합 로그아웃은 이 작업에 포함되지 않습니다.

### 1. 실제 env와 이미지 준비

SSO 코드를 포함한 Airflow 3.3.2 이미지를 새 고유 태그로 빌드합니다.
Git에서 관리하는 `deploy/airflow/env/k8s.env`를 사용하고 아래 값을 입력합니다. 실제 비밀값은 이 문서에 복사하지 않습니다.
기존 DB·Fernet 키·관리자 API 계정은 유지합니다.

| 키 | 입력 |
| --- | --- |
| `AIRFLOW_AUTH_MODE` | `keycloak` |
| `AIRFLOW_OIDC_ISSUER` | 기존 realm의 공개 HTTPS issuer, 끝은 `/realms/<realm>` |
| `AIRFLOW_OIDC_CLIENT_ID` | `airflow` |
| `AIRFLOW_OIDC_CLIENT_SECRET` | 신규 client용 강한 비밀값. 기존 client가 있으면 기존 secret |
| `AIRFLOW_OIDC_BACKCHANNEL_BASE_URL` | Pod 접근용 realm URL, 비우면 issuer 사용 |
| `AIRFLOW_OIDC_CA_CONFIGMAP` | 사내 CA가 필요하면 Airflow namespace의 ConfigMap 이름 |
| `AIRFLOW_OIDC_CA_BUNDLE` | CA 사용 시 `/etc/airflow/oidc-ca/ca.crt`, 아니면 빈 값 |
| `AIRFLOW_OIDC_ALLOW_HTTP` | 서버는 `false` |

CA ConfigMap은 `ca.crt` 키에 필요한 신뢰 루트·중간 CA를 포함한 bundle을 넣습니다.
CA 설정을 쓰면 TLS 인증서 검증에 해당 bundle을 사용합니다. HTTPS 검증 생략은 지원하지 않습니다.
브라우저 callback은 `${AIRFLOW_WEBSERVER_BASE_URL}/auth/oauth-authorized/keycloak` 하나만 등록합니다.
운영 Airflow 공개 URL은 `https://etch.samsungds.net/airflow`이며, callback은
`https://etch.samsungds.net/airflow/auth/oauth-authorized/keycloak`입니다.
현재 realm issuer는 `https://etch-sso.samsungds.net/realms/etch`입니다.
업무 도메인 인증서는 `etch-sso/traefik-tls`에서 관리하며
[배포 절차](#배포와-검증)에 따라 공용 저장소에 등록합니다.

### 2. client 등록

`AIRFLOW_AUTH_MODE=keycloak`에서는 기존 realm에 전용 `airflow` client가 필요합니다.
아래 등록 명령이 client를 생성하므로 관리자 화면에서 미리 만들 필요는 없습니다.
기존 `portal` client와 별도로 관리합니다.

**신규 client를 등록할 때만** CP1에서 비밀값을 생성합니다.

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

출력값을 사용하는 env 파일의 `AIRFLOW_OIDC_CLIENT_SECRET=`에 따옴표 없이 입력합니다.
`manage.py init-secrets`는 이 값을 생성하지 않습니다.
이미 `airflow` client가 있으면 Keycloak 관리자 화면에서 대상 realm → Clients → airflow → Credentials의
기존 Client secret을 확인해 env에 입력합니다. 기존 client의 secret은 재생성하지 않습니다.

저장소 루트에서 실행합니다. Python 표준 라이브러리와 기존 Keycloak 관리자 계정이 필요합니다.
관리자 API URL은 HTTPS 주소 또는 명시적으로 준비한 localhost port-forward 주소입니다.
base URL에는 `/realms/etch`나 `/admin`을 붙이지 않습니다.
아래 환경변수는 실행 프로세스 입력이며 Git 추적 파일에 보관하지 않습니다.

```bash
read -r -p 'Keycloak 관리자 API base URL: ' KEYCLOAK_ADMIN_URL
read -r -p 'Keycloak 관리자 계정: ' KEYCLOAK_ADMIN_USERNAME
read -r -s -p 'Keycloak 관리자 비밀번호: ' KEYCLOAK_ADMIN_PASSWORD
export KEYCLOAK_ADMIN_URL KEYCLOAK_ADMIN_USERNAME KEYCLOAK_ADMIN_PASSWORD
# 실행 호스트에 사내 CA가 필요하면 KEYCLOAK_ADMIN_CA_BUNDLE에 실제 파일 경로를 export합니다.
make airflow-keycloak-client
unset KEYCLOAK_ADMIN_PASSWORD
```

기본 입력은 `deploy/airflow/env/k8s.env`입니다.
다른 파일을 사용하면 등록 명령에 `AIRFLOW_ENV=/절대경로/k8s.env`를 전달하고 검사·배포에도 같은 파일을 사용합니다.

등록기는 master realm의 admin-cli로 관리자 인증한 뒤 대상 realm의 전용 client만 관리합니다.
Authorization Code + PKCE S256, RS256 ID Token, profile·email scope와 전용 client 역할 mapper를 설정합니다.
신규·기존 realm 모두 같은 명령을 사용합니다. 기존 client secret이 env와 다르면 중단하며 회전하지 않습니다.
사용자 역할·기존 realm·타 앱 client는 유지하고 운영 사용자에게 권한을 자동 부여하지 않습니다.

관리자 UI에서 필요한 사용자에게 `airflow`의 `Admin` 또는 `User`를 직접 부여합니다.
조회 사용자는 별도 할당이 필요 없습니다. `portal` client의 역할은 Airflow 자체 권한이 아닙니다.

### 3. 검사·배포·검증

기존 [배포 흐름](#배포와-검증)에 같은 운영 env를 전달합니다.

```bash
python3 deploy/airflow/scripts/manage.py check --env /절대경로/k8s.env --pause-new-dags
make airflow-check AIRFLOW_ENV=/절대경로/k8s.env KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
make airflow-up AIRFLOW_ENV=/절대경로/k8s.env KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
```

Airflow 로그인 화면의 Keycloak 버튼으로 로그인합니다. 기본 사용자의 DAG 조회·관리 작업 거부,
관리자의 관리 화면 접근, User·Admin 제거 후 새 로그인에서 Viewer 복귀를 확인합니다.
잘못된 토큰·다른 issuer·만료 토큰은 기본 Viewer로 처리하지 않고 로그인에 실패해야 합니다.

웹 로그인과 앱 간 호출은 각각 확인합니다.

- 웹 로그인은 Keycloak SSO를 사용합니다.
- Portal → Airflow 호출은 DB 계정으로 `/auth/token`에서 JWT를 발급받아 API v2에 Bearer 인증으로 전달합니다.
- Airflow → Portal 호출은 기존 trigger token을 유지합니다.

양방향 호출을 따로 검증합니다. 현재 Portal API가 쓰는 관리자 계정을 최소 권한의 전용 계정으로 바꾸는 일은 후속 작업입니다.

문제 시 `AIRFLOW_AUTH_MODE=db`로 명시적으로 되돌려 재배포할 수 있습니다.
DB·Fernet 키·기존 API 계정을 초기화하지 않습니다. 서버 env·client를 준비하지 않은 로컬 성공을
서버 SSO 적용 완료로 간주하지 않습니다.

## 배포와 검증

서버·env·chart·이미지·ODBC를 준비한 뒤 저장소 루트의 Bash에서 실행합니다.
기본 입력은 `deploy/airflow/env/k8s.env`, namespace는 `airflow`입니다.
현재 최초 설치는 새 DB로 진행합니다. DB 복원 단계는 수행하지 않으며,
선택한 Worker의 DB 디렉터리가 기존 PostgreSQL 데이터 경로가 아닌지 확인합니다.
이미 Airflow PVC·Secret이 남아 있다면 새 설치로 간주하지 말고 연결된 저장소부터 확인합니다.
이 안내는 기존 리소스나 데이터를 자동 삭제하지 않습니다.

다른 설정을 쓴다면 아래 두 항목을 맞춥니다.

- namespace를 바꾼 경우: kubectl 명령의 `-n airflow`도 같은 이름으로 바꿉니다.
- env 파일을 바꾼 경우: Python에는 `--env`, Makefile에는 `AIRFLOW_ENV`로 같은 파일을 전달합니다.

### 실행 순서와 영향

| 단계 | 실행 목적 | 변경 대상 | 완료 기준 |
| --- | --- | --- | --- |
| 0 | 대상 context 선택 | 셸 변수 | 의도한 클러스터의 노드 조회 |
| 1 | 설정·chart 검사 | 없음 | 정적 검사 통과 |
| 2 | manifest 검토 | 로컬 rendered 파일 | 노드·이미지·디스크·Ingress가 의도와 일치 |
| 3 | 클러스터 사전 검사 | 없음 | 버전·노드·기존 비밀값 검사 통과, Ingress 사용 시 Traefik·TLS 확인 |
| 4 | 실제 배포 | Airflow·DB·스토리지·Secret, 필요한 공용 라우팅 | Helm hook·Pod rollout 완료 |
| 5 | 접속·업무 연동 확인 | 시험 작업과 선택한 DAG 상태 | 로그인·DAG 로딩·Portal 호출 확인 |

최초 설치는 순서대로 진행합니다. 재배포는 [백업·업데이트](04-operations.md)를 먼저 확인합니다.
검사 실패 시 다음 단계로 넘어가지 말고 원인을 고친 뒤 해당 검사를 다시 실행합니다.

### 0. 대상 context 선택

```bash
kubectl config get-contexts
read -r -p '배포할 Kubernetes context: ' AIRFLOW_KUBE_CONTEXT
kubectl --context "$AIRFLOW_KUBE_CONTEXT" get nodes -L kubernetes.io/hostname
kubectl --context "$AIRFLOW_KUBE_CONTEXT" get node khinfow01 -o wide
```

현재 기본 context에 의존하지 않도록 이후 명령에도 context를 명시합니다.
새 터미널을 열면 이 단계를 다시 수행합니다.
Airflow 배포 대상은 [서버 목록](../../shared/docs/infrastructure/servers.md#서버-목록)의 `khinfow01`입니다.
클러스터 Worker 추가는 사용자 확인이며, 위 조회로 선택한 context의 노드명·InternalIP·Ready를 대조합니다.
Airflow의 실제 배포 적용은 별도 확인이 필요합니다.

### 1. 설정과 차트 검사

```bash
make server-check APP=airflow PROFILE=prod
python3 deploy/airflow/scripts/manage.py check \
  --env deploy/airflow/env/k8s.env --pause-new-dags
```

첫 명령은 저장소 env 구조와 고정 chart의 렌더를 검사합니다.
두 번째는 실제 입력으로 예시값·비밀값 길이·URL·Fernet 키 형식까지 검사합니다.
둘 다 클러스터에 연결하지 않으며 차트를 자동 다운로드하지 않습니다.
완료 기준: 각각 원본 검사 통과 메시지가 나와야 합니다.

### 2. 배포 내용 미리 보기

```bash
python3 deploy/airflow/scripts/manage.py render \
  --env deploy/airflow/env/k8s.env --pause-new-dags \
  --output deploy/airflow/rendered
```

| 출력 | 검토할 내용 |
| --- | --- |
| `storage.json` | Worker hostname, DB·로그 경로와 용량, Retain 정책 |
| `postgres.json` | 내부 DB 이미지·권한·Service, external 모드에서는 빈 리소스 목록 |
| `values.json` | 이미지 태그·노드·ODBC·URL·신규 DAG 일시정지 설정 |
| `airflow.yaml` | Airflow workload·Ingress·migration 및 관리자 Job |

Secret 값은 출력에 포함하지 않습니다. **`airflow.yaml`을 직접 kubectl apply하지 않습니다.**
실제 배포는 Helm hook을 통해 DB migration과 관리자 생성 순서를 지켜야 합니다.
`--pause-new-dags`는 기본 make 배포와 동일한 신규 DAG 정책으로 검토하기 위한 옵션입니다.

### 3. 클러스터 사전 검사

```bash
make airflow-check KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
```

이 단계에서 확인하는 항목은 다음과 같습니다.

- 클러스터 버전과 대상 노드의 Ready·cordon 상태
- 최종 Pod 설정이 해당 노드의 taint를 허용하는지 여부
- 기존 DB 비밀번호·Fernet 키와 env의 일치 여부
- 설정에서 참조하는 image pull·ODBC Secret, OIDC CA ConfigMap, IngressClass
- Ingress를 쓸 때 `etch-sso/traefik`과 TLS 인증서의 도메인·만료

필요한 입력이 빠지면 공용 리소스를 적용하기 전에 중단합니다.
검사를 통과한 뒤에도 실제 디스크 권한, 이미지 다운로드, 외부 DB 접속, Portal 연동은 따로 확인합니다.

운영 URL은 `https://etch.samsungds.net/airflow`이며 앱별 TLS Secret 입력은 필요 없습니다.
업무 도메인 인증서를 [공용 Traefik](../../shared/docs/certificates/apply.md#2-2-kubernetes-tls-secret에-등록-또는-갱신)에 먼저 등록하고
`make ingress-up`으로 공용 인증서 마운트를 반영합니다.

```bash
make airflow-check KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
```

이전 설치의 인증서를 가져올 때는 `AIRFLOW_TLS_SOURCE=namespace/secret`도 사용할 수 있습니다.
check는 원본을 검사하고 적용하지 않습니다. up에 같은 인자를 전달하면 공용 저장소에 등록하며
Airflow namespace에 복제하지 않습니다. 이미 등록했다면 TLS source가 필요 없습니다.

### 4. 실제 배포

```bash
make airflow-up KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
```

3단계에서 TLS source를 지정했다면 위 명령 대신 다음 명령을 사용합니다.

```bash
make airflow-up KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT" AIRFLOW_TLS_SOURCE=headlamp/headlamp-tls
```

Ingress 사용 시 namespace·TLS·공용 Traefik의 감시 권한을 준비한 뒤 Airflow를 배포합니다.
Keycloak과 Keycloak DB는 재배포하지 않습니다. 공용 Traefik의 설정 변경과 rollout은 발생할 수 있습니다.
이후 namespace → Secret → local PV/PVC → 내부 PostgreSQL 준비 → Helm migration·관리자 생성 → Airflow rollout 순서로 진행합니다.
외부 DB 모드에서는 내부 PostgreSQL 적용과 대기를 생략합니다.

기존 DB/PVC는 삭제하지 않습니다. 기존 Secret과 DB 비밀번호·Fernet 키가 다르면 중단합니다.
기존 PVC가 있는데 DB Secret만 없다면 실제 DB 비밀번호로 Secret을 먼저 복원해야 합니다.
관리자 계정은 없을 때만 생성하며, env의 관리자 비밀번호를 바꾸어도 기존 계정의 비밀번호·역할은 바뀌지 않습니다.
다른 runtime Secret 변경은 배포 마지막 Pod 재시작으로 반영합니다.

**신규 DAG는 일시정지로 생성하고 기존 DB의 DAG 활성 상태는 유지합니다.**
기존 scheduler가 있다면 전환 전에 작업을 정리하고 중지해야 합니다.
완료 기준: migration·관리자 hook과 scheduler·API server·DAG processor·triggerer rollout이 끝나야 합니다.

### 5. 접속과 연동 확인

```bash
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get pods,pvc -o wide
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get ingress
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow port-forward svc/airflow-api-server 8080:8080
```

port-forward는 터미널을 점유하며 Ctrl+C로 종료합니다. 같은 컴퓨터의 브라우저에서
`http://localhost:8080/airflow`에 접속합니다. 원격 서버에서 실행했다면 PC에서 별도 SSH 터널을 연결합니다.

```bash
read -r -p 'port-forward 실행 서버 user@host: ' AIRFLOW_SSH_TARGET
ssh -N -L 8080:127.0.0.1:8080 "$AIRFLOW_SSH_TARGET"
```

HTTPS를 사용하면 `AIRFLOW_WEBSERVER_BASE_URL`의 주소로도 접속합니다.
DNS는 실제 Ingress 진입 주소를 가리켜야 하며 `/airflow` 경로를 rewrite하지 않습니다.

1. 최초 관리자 또는 기존 계정으로 로그인합니다.
2. DAG가 보이고 import 오류가 없는지 확인합니다.
3. 기존 Connection·Variable 복호화와 ODBC 설정을 확인합니다.
4. Airflow → Portal API 주소와 trigger token을 양쪽에서 맞추고 시험 작업으로 확인합니다.
5. Portal → Airflow 호출도 쓴다면 아래 Portal 소유 설정을 확인합니다.
6. 기존 scheduler의 중복 실행이 없는지 확인한 뒤 필요한 DAG만 활성화합니다.

| Portal 설정 | 의미 |
| --- | --- |
| `AIRFLOW_BASE_URL` | 내부 호출 주소. 기본 namespace 예: `http://airflow-api-server.airflow.svc.cluster.local:8080/airflow` |
| `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD` | 실제 Airflow 계정과 일치 |
| `AIRFLOW_PUBLIC_BASE_URL` | 브라우저에서 접근하는 Airflow 공개 URL |

위 변수는 Portal 설정이며 Airflow k8s.env에 추가하지 않습니다. namespace를 바꾸면 내부 DNS도 수정합니다.
Pod Ready와 실제 업무 성공은 별도 확인입니다. 실패 시 [문제 해결](04-operations.md#4-실패-단계-확인)을 사용합니다.

### 6. 고급: 직접 deploy와 Helm override

기본 운영 흐름은 위 Makefile 명령입니다. 별도 Ingress controller나 환경별 Helm override가 필요한 경우에만
직접 명령을 사용합니다. 이 경로는 공용 Traefik 연결이나 인증서 등록을 하지 않으므로
controller·라우팅·TLS Secret·imagePullSecret·ODBC Secret을 먼저 준비해야 합니다.

```bash
python3 deploy/airflow/scripts/manage.py deploy \
  --env deploy/airflow/env/k8s.env --context "$AIRFLOW_KUBE_CONTEXT" \
  --pause-new-dags
```

`--pause-new-dags`를 생략하면 저장소 `helm/values.yaml` 기본값에 따라 **신규 DAG가 활성 상태로 생성**됩니다.
기존 DAG의 일시정지 상태는 어느 경로에서도 유지합니다.

환경별 비밀값 없는 override가 필요하면 `check`, `render`, `deploy` 모두 동일한
`--values /절대경로/values.yaml`을 전달합니다. Makefile의 airflow-check/up에는 이 override 전달 기능이 없습니다.
override는 생성 values 뒤에 적용되므로 노드·DAG 정책까지 덮어쓸 수 있습니다. 렌더 결과를 반드시 확인합니다.
배포 후 재시작·준비 대기는 최종 렌더에 존재하는 Deployment·StatefulSet·DaemonSet만 대상으로 합니다.
예를 들어 `triggerer.enabled: false`이면 triggerer는 재시작·대기 대상에서 제외합니다.

자원 기본값은 `helm/values.yaml`과 `k8s/postgres/stack.json`이 원본입니다.
parallelism=32, DAG별 task=16·run=16, 웹서버 worker=4이며 초기화 Job은 default_pool slots를 -1로 설정합니다.
CPU·메모리 제한은 실제 작업량과 서버 사양에 맞춰 조정합니다.

### 준비가 끝났을 때 실행

저장소 루트의 Bash에서 실행합니다. 이 두 명령은 최초 env·chart·이미지·디스크 준비를 대신하지 않습니다.

```bash
read -r -p '배포할 Kubernetes context: ' AIRFLOW_KUBE_CONTEXT
make airflow-check KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
make airflow-up KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
```

두 명령의 역할은 다음과 같습니다.

- `airflow-check`: 설정·chart·클러스터 버전·노드·기존 비밀값을 검사합니다.
- `airflow-up`: Airflow를 배포하고, Ingress를 사용하면 필요한 공용 Traefik 라우팅도 연결합니다.

Keycloak과 Keycloak DB는 재배포하지 않습니다.
공용 Traefik 연결은 최신 namespace 목록에 Airflow를 추가하는 패치만 적용합니다.
동시 변경으로 패치가 거부되면 기존 앱 연결 상태를 확인한 뒤 검사·배포 명령을 다시 실행합니다.
신규 DAG는 일시정지 상태로 만들고 기존 DAG의 활성 상태는 유지합니다.
직접 `manage.py deploy`를 실행할 때는 [실행 방식의 차이](#6-고급-직접-deploy와-helm-override)를 확인합니다.

| 선택 입력 | 사용하는 경우 |
| --- | --- |
| `AIRFLOW_ENV=/절대경로/k8s.env` | Makefile 명령에 다른 env 전달 |
| `AIRFLOW_TLS_SOURCE=namespace/secret` | 기존 인증서를 공용 Traefik 저장소에 등록하는 호환 입력 |
| `AIRFLOW_CHART_FILE=/절대경로/airflow-1.22.0.tgz` | 별도 위치의 chart 지정, 셸에서 export |

TLS 최초 등록 명령과 검사·배포별 영향은 위 단계별 절차에서 확인합니다.
기존 `make server-up`은 두 앱 통합 경로이며 Airflow 단독 배포에는 위 전용 명령을 사용합니다.
