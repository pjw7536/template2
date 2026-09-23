# 기존 Keycloak + Airflow 서버 기동

[배포 문서 안내](../../../README.md) · [입문 가이드](../kubernetes/README.md)

## 앱별 순차 배포

새 실행 진입점은 앱별로 구분합니다. 필요한 파일을 준비한 후 각 단계를 별도로 실행합니다.

```bash
make keycloak-check KUBE_CONTEXT=<context>
make keycloak-up KUBE_CONTEXT=<context>
make airflow-check KUBE_CONTEXT=<context>
make airflow-up KUBE_CONTEXT=<context>
```

위 `<context>`는 실제 이름으로 바꿉니다. Keycloak만 준비한 단계에서는 첫 두 명령만 사용합니다.
Keycloak 명령은 env/TLS 최초 등록과 자기 스택을 적용하고 Airflow를 실행하지 않습니다.
Airflow 명령은 기존 공용 Traefik에 라우팅을 연결하지만 Keycloak 스택을 다시 적용하지 않습니다.
두 명령 모두 DB를 삭제하거나 빈 DB로 초기화하지 않습니다.
자세한 입력은 [Keycloak](../../../keycloak/README.md)과 [Airflow](../../../airflow/README.md) 안내를 따릅니다.
아래 `server-up` 절차는 기존 통합 실행의 호환 안내입니다.

현재 단계는 **이미 실행 중인 Keycloak을 프로젝트 원본으로 관리하고 Airflow UI를 같은 서버에서 여는 것**입니다.
Portal·Monitoring을 배포하지 않습니다. 기존 Keycloak namespace·DB·관리자·사내 OIDC 설정은 유지합니다.
공용 Traefik은 기존 `etch-sso/traefik`과 worker 80/443을 사용합니다.
**APP VIP `10.172.26.150`과 두 Worker의 443을 사용하는 현재 환경은 [VIP 실행 절차](../../ingress/VIP.md)를 따릅니다.**
이 문서는 공통 최초 준비를 설명하며, VIP 모드에서는 Traefik만 두 Worker로 확장합니다.

## 최초 준비와 이후 실행의 차이

Git pull은 소스와 일반 env 설정을 갱신합니다. 이미지·Helm chart·비밀값 파일(`*.secrets.env`)·인증서·데이터는 Git에 포함되지 않습니다.
최초 준비를 끝내면 이후에는 `git pull --ff-only`와 `make server-up`으로 같은 경로를 재실행합니다.
Airflow DAG·Dockerfile이 바뀌면 새 이미지 빌드·태그 변경도 필요합니다.
개발 PC의 변경사항은 먼저 commit/push되어야 서버에서 pull할 수 있습니다.

명령은 CP1 등의 배포용 checkout 루트에서 실행합니다.
필요 도구: Git, Bash, Make, Python 3.10+, kubectl, Helm 3.19.0+, OpenSSL.
Kubernetes는 1.30.13 이상이며 기존 Keycloak 스택이 있어야 합니다.
이미지 빌드에는 Docker가 필요하지만 CP1 이외의 빌드 환경에서 준비해도 됩니다.

## 1. 필요한 앱만 받기

기존 서버 checkout에서 실행합니다. 작업 파일 변경이 있으면 선택 범위 변경이 중단됩니다.
외부 개발 PC에서는 실행하지 않습니다.

```bash
git pull --ff-only
bash deploy/shared/scripts/checkout-server.sh keycloak-airflow

kubectl config get-contexts
read -r -p '배포할 context: ' AIRFLOW_KUBE_CONTEXT
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n etch-sso get pods
kubectl --context "$AIRFLOW_KUBE_CONTEXT" get nodes -L kubernetes.io/hostname
```

`keycloak-airflow` 기본 선택은 `deploy/keycloak`, `deploy/airflow`, `deploy/shared`, `docs`를 포함합니다.
Airflow 빌드 소스 `apps/airflow`는 `--with-source`를 지정할 때만 포함합니다.
`local/`, Portal·Monitoring 앱 소스는 필요하지 않습니다.
새 clone이라면 [선택 체크아웃 안내](../../../SERVER_CHECKOUT.md)를 따라 `deploy/shared`를 먼저 받은 뒤 같은 선택 명령을 사용합니다.

## 2. Airflow 최초 설정

```bash
python3 deploy/airflow/scripts/manage.py init-secrets
vi deploy/airflow/env/k8s.env
```

`init-secrets`는 기존 파일을 덮어쓰지 않습니다. 이미 설정했다면 편집만 합니다.
아래 항목을 실제 값으로 입력합니다. 사내 빌드 주소·BigDataQuery·ODBC 기본값은 이미 채워져 있습니다.

| 키 | 이 단계의 값 |
| --- | --- |
| `NODE_NAME` | 기존 앱 worker hostname label. 현재 원본은 `khplane01w09`. VIP 모드에서도 앱·DB 위치는 유지 |
| `AIRFLOW_IMAGE_REPOSITORY`, `AIRFLOW_IMAGE_TAG` | worker가 가져올 수 있는 DAG 포함 이미지 주소·고유 태그 |
| `AIRFLOW_ADMIN_EMAIL` | 실제 관리자 이메일 |
| `ODBC_HOST_PATH` | worker에 있는 기존 ODBC 설정 디렉터리의 절대 경로 |
| `INGRESS_ENABLED` | `true` |
| `INGRESS_CLASS_NAME` | `traefik` |
| `INGRESS_TLS_SECRET` | `airflow-tls` |
| `AIRFLOW_WEBSERVER_BASE_URL` | 현재 확정 주소 `https://etch.samsungds.net/airflow` |
| `AIRFLOW_API_BASE_URL` | 이후 Portal API 주소. 아직 서버가 없어도 이 단계의 UI 기동은 가능 |
| `AIRFLOW_TRIGGER_TOKEN` | 기존 Portal 연동 토큰. 신규 환경이면 생성 후 나중에 Portal에도 같은 값을 입력 |

기존 Keycloak URL·issuer를 Airflow 주소에 맞춰 변경하지 않습니다.
Airflow가 사용할 DNS는 Traefik으로 연결되는 주소를 가리켜야 합니다.
현재는 `etch.samsungds.net → APP VIP → 두 Worker:443`으로 연결하며, 단독 실행에서는 worker IP를 직접 사용할 수 있습니다.

신규 연동 토큰이 필요할 때만 아래 명령으로 생성해 `k8s.secrets.env`에 입력합니다. 출력은 저장소에 기록하지 않습니다.

```bash
openssl rand -hex 32
```

관리자 비밀번호·Fernet 키·DB 비밀번호는 `init-secrets`가 생성한 값을 유지합니다.
기존 Airflow DB를 복원한다면 [이전 절차](../../../airflow/README.md)에 따라 기존 Fernet 키와 계정을 유지해야 합니다.

## 3. worker 디스크·이미지·차트 준비

[Airflow 배포 안내](../../../airflow/README.md)의 디스크 준비·차트 반입·이미지 빌드 절차를 수행합니다.
특히 디스크는 CP1이 아니라 **Pod가 실행되는 worker**에 준비합니다.

기본 경로·PostgreSQL UID/GID를 쓸 경우 worker에서:

```bash
sudo install -d -o 999 -g 999 -m 0700 /srv/airflow/postgres
sudo install -d -o 50000 -g 0 -m 0770 /srv/airflow/logs
```

ODBC는 기존 `airflow/odbc`의 실제 경로를 지정하거나 그 전체 내용을 새 경로로 복사합니다.
빈 INI 파일로 대신하지 않습니다. 파일은 Airflow UID 50000이 읽을 수 있어야 합니다.

인터넷 연결 환경에서 받은 `deploy/airflow/helm/vendor/airflow-1.22.0.tgz`를 CP1의 같은 위치로 반입합니다.
이미지는 `build.env`로 빌드해 registry에 push하거나 worker containerd에 반입합니다.
Kubernetes가 접근할 수 있는 이미지와 실제 tag를 `k8s.env`에 지정합니다.

## 4. TLS 연결 확인

Airflow Ingress는 Airflow namespace의 TLS Secret을 사용합니다.
기존 인증서가 선택한 도메인을 포함한다면 기존 Secret을 최초 한 번 복사할 수 있습니다.

예를 들어 **기존 Keycloak 도메인으로 Airflow도 접속할 때**는 다음 원본을 사용할 수 있습니다.

```bash
AIRFLOW_TLS_SOURCE=etch-sso/keycloak-tls
```

기존 Portal 도메인이라면 그 도메인의 인증서가 있는 실제 `namespace/secret`을 지정합니다.
Keycloak 인증서가 Portal 도메인도 포함한다고 가정하지 않습니다.
도구는 인증서 만료·도메인을 검사하고, Airflow TLS Secret이 없을 때만 복사합니다.
대상 Secret이 이미 있으면 기존 값을 유지합니다. 원본 Secret·개인키·Keycloak 인증값은 변경하지 않습니다.

Airflow namespace에 맞는 TLS Secret을 직접 준비했다면 `AIRFLOW_TLS_SOURCE`는 비워도 됩니다.

## 5. 검사 후 한 명령으로 실행

```bash
make server-check APP=keycloak-airflow
python3 deploy/airflow/scripts/manage.py check \
  --env deploy/airflow/env/k8s.env --pause-new-dags

make server-up \
  KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT" \
  AIRFLOW_ENV="$PWD/deploy/airflow/env/k8s.env" \
  AIRFLOW_TLS_SOURCE="$AIRFLOW_TLS_SOURCE"
```

`AIRFLOW_ENV`에는 Git 밖에서 보관하는 실제 파일의 절대 경로도 지정할 수 있습니다.
`server-check`는 원본 검사이며 서버 연결 성공을 보장하지 않습니다.

`server-up`은 다음 순서로 실행합니다.

1. Airflow env·chart 렌더와 기존 Keycloak·Traefik·TLS 준비를 검사합니다.
2. Airflow namespace, 필요한 TLS Secret, Traefik의 해당 namespace 읽기 권한을 준비합니다.
3. 기존 Traefik 감시 목록에 Airflow를 추가한 Keycloak 스택을 적용합니다. 기존 Portal 등 감시 목록을 제거하지 않습니다.
4. Keycloak·DB·Traefik 준비를 기다린 뒤 Airflow DB·Helm을 배포합니다.
5. 이번 단계에만 신규 DAG를 일시정지로 생성하도록 override합니다.

Keycloak 관리자 credential·realm·사내 OIDC·claim mapper Job은 자동 갱신하지 않습니다.
이름·namespace·PV 경로가 바뀌지 않으므로 파일을 공용 폴더로 옮겼다는 이유로 기존 리소스를 삭제하지 않습니다.
단독 Traefik은 Recreate를 사용합니다. VIP 모드에서는 두 Worker를 순차 교체하며 LB가 DOWN Backend를 제외하도록 구성합니다.
갱신 중 개별 연결은 재시도가 필요할 수 있습니다.

복원한 Airflow DB의 기존 활성 DAG는 이 옵션으로 정지되지 않습니다. Portal이 없으면 기존 DAG도 UI에서 일시정지해야 합니다.

## 6. 확인과 이후 pull

```bash
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n etch-sso get pods,ingress
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get pods,pvc,ingress
```

기존 Keycloak 주소와 `k8s.env`에 지정한 Airflow `/airflow` 주소를 브라우저에서 확인합니다.
Airflow 로그인은 `AIRFLOW_ADMIN_USERNAME`, `AIRFLOW_ADMIN_PASSWORD`를 사용합니다.
현재 단계에서는 Portal 연동 업무 DAG를 활성화하지 않습니다.

이후 같은 shell에서:

```bash
git pull --ff-only
make server-up KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT" AIRFLOW_ENV="$PWD/deploy/airflow/env/k8s.env"
```

새 shell에서는 context 변수를 다시 지정합니다. 이미 복사한 TLS Secret에는 원본 인자가 필요하지 않습니다.
DAG·이미지가 바뀌었다면 먼저 새 이미지 tag를 준비합니다.
**공용 라우팅을 연결한 이후에는 Keycloak 원본이나 전달 YAML을 직접 apply하지 말고 이 명령을 사용합니다.**
정적 단독 manifest는 현재 클러스터의 다른 앱 감시 범위를 알 수 없습니다.
