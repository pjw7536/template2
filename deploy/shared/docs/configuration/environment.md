# 앱별 환경설정

[배포 문서 안내](../../../README.md)

설정할 앱과 실행 환경을 먼저 고릅니다. 아래 명령은 저장소 루트에서 실행합니다.
Portal 최초 배포라면 [Portal 입력 순서](../../../portal/README.md)부터 확인합니다.

```text
local/
├── portal/env/               # 외부 PC API·Web·MinIO와 K8s 차이
└── shared/env/k8s.env        # 전체 로컬 실행 입력

deploy/
├── keycloak/env/             # prod.env
├── portal/env/
│   ├── test/                 # CI API 자동 테스트
│   └── prod/                 # API·Web·MinIO 통합 .env
├── airflow/env/              # k8s.env·build.env 일반 설정
└── monitoring/env/           # k8s.env 일반 설정
```

외부 PC는 `local/`, 사내와 CI는 `deploy/`에서 앱을 선택합니다.
공통 env 검사 도구는 PROFILE=local일 때만 local 경로를 사용합니다.
사내 배포는 Kubernetes 전용입니다. Keycloak 사내 OIDC는 prod 환경의 oidc component로 관리합니다.

## 무엇을 어디에 적나요?

Keycloak·Portal API/MinIO·Airflow는 해당 env에 일반 설정과 비밀번호·토큰·서명 키·인증 헤더를
함께 넣고 비공개 Git 저장소에서 관리합니다. Portal Web 설정은 브라우저에 공개되므로 비밀값을 넣지 않습니다.
도구는 지정한 파일만 읽으며 옆에 있는 다른 파일을 자동으로 합치지 않습니다.

다음 앱은 실제 비밀값을 별도로 등록합니다. env에는 해당 Kubernetes Secret의 이름만 넣습니다.

| 앱 | 실제 비밀값의 입력·보관 방식 | 상세 절차 |
| --- | --- | --- |
| Headlamp | client secret 숨김 입력 → 전용 Kubernetes Secret. env에는 Secret 이름 | [client secret 등록](../../../headlamp/04_KEYCLOAK_SETUP.md#5-cp1에서-client-secret-등록) |
| Monitoring | Git 밖의 관리자 env 파일 → Grafana 관리자 Secret. env에는 Secret 이름 | [관리자 Secret 준비](../../../monitoring/README.md#4-namespace와-관리자-secret-준비) |
| FTP | Git 밖의 계정 파일 → 공용 FTP 계정 Secret. 앱 env 파일은 사용하지 않음 | [계정 파일 준비](../../../ftp/01_SERVER_SETUP.md#4-관리-호스트의-계정-파일-준비) |

Kubernetes Secret은 설정을 클러스터에 전달하는 리소스입니다.
env를 Secret으로 등록하는 배포 방식과 Headlamp·Monitoring의 기존 Secret 참조는 유지합니다.
인증서·개인키 파일은 Git에서 제외하고 별도로 준비합니다.

설정을 여러 파일로 나누어 쓰던 서버는 최신 통합 env에 기존 값이 보존됐는지 확인합니다.

| 설정 | 관리 위치 | 읽는 대상 |
| --- | --- | --- |
| 로컬 Portal | `local/portal/env/<서비스>.env` | 외부 PC API·Web·MinIO |
| 로컬 Airflow | `local/shared/scripts/k8s_config.py` | 외부 PC Airflow |
| Keycloak 관리자·주소·전용 DB | `deploy/keycloak/env/prod.env` 첫 부분 | Keycloak, 전용 PostgreSQL, 관리 Job |
| 사내 OIDC 접속 정보 | 같은 파일의 `CORP_OIDC_*` 부분 | 사내 OIDC 설정 Job만 |
| Portal 서버·DB·로그인 | `deploy/portal/env/<환경>/api.env` | API, migration, Django collectstatic |
| Portal client 등록 정보 | 같은 API 파일의 `OIDC_*`와 `FRONTEND_BASE_URL` | client 등록 Job에 필요한 항목만 전달 |
| 브라우저 공개 설정 | `deploy/portal/env/<환경>/web.env` | Web |
| MinIO 설정 | `deploy/portal/env/<환경>/minio.env` | MinIO, 연결에 필요한 API 설정 |
| Airflow Kubernetes 설정 | `deploy/airflow/env/k8s.env` | 전용 배포 도구 → Airflow·PostgreSQL Secret |
| Airflow 이미지 빌드 | `deploy/airflow/env/build.env` | 사내 의존성·DAG 이미지 빌드 |
| Kubernetes Monitoring | `deploy/monitoring/env/k8s.env` | 노드·local PV·이미지 미러·Grafana Secret 참조 |
| Headlamp 공개 설정 | `deploy/headlamp/env/k8s.env` | 공개 주소·issuer·Secret/CA 이름. 실제 client secret 제외 |

Keycloak은 Portal 주소나 client secret 없이 기동합니다. Portal의 client secret과 사내
OIDC에서 받은 secret은 서로 다른 값입니다. 서버 이미지, 실행 노드, CPU·메모리와 볼륨
용량의 입력 위치는 앱마다 다릅니다. Portal·Keycloak은 배포 YAML을 사용하고,
Airflow·Monitoring은 env에서 노드·경로·일부 이미지 설정을 읽어 렌더합니다.
CPU·메모리 등 공통 자원 설정은 각 앱의 manifest 또는 Helm values를 확인합니다.

API env는 서버·DB·로그인·HTTPS → 공용 연동 → 업무 기능 → 조정·개발 설정 순서로 구성합니다.
Emails·Assistant·Drone 설정도 같은 API env에 적습니다.

prod env에는 서버·DB·로그인·파일 저장소의 필수값을 먼저 넣습니다.
업무 연동을 사용할 때는 [설정 설명](../../../../docs/configuration.md)을 보고 필요한 값을 추가합니다.
timeout·cache 같은 선택값을 생략하면 코드 기본값을 사용합니다.

local/test 설정은 유지하며 prod에는 기존 업무 설정과 준비한 Keycloak 입력을 통합했습니다.
이후 env 변경 이력도 Git에서 관리합니다.

Keycloak의 `COMPONENT=oidc` 입력은 `CORP_OIDC_DISCOVERY_URL`이 있으면 endpoint를 자동 해석합니다.
실행 호스트에 Python과 discovery 접속·TLS 신뢰가 필요합니다. env 검사·Secret 등록 명령은
Job을 실행하지 않으므로 전체 초기 설정은 [Keycloak 자체 설정 절차](../../../keycloak/04_SETUP_FLOW.md)를 사용합니다.

## 설정 검사

Airflow·Monitoring·Headlamp의 `make env-check APP=<앱>`은 전용 Kubernetes 검사 도구를 사용합니다.

```bash
python3 deploy/airflow/scripts/manage.py check --env deploy/airflow/env/k8s.env
```

[Airflow 배포 안내](../../../airflow/README.md)에 따라 Helm·chart를 준비합니다. 전용 deploy 명령이 DB·Airflow Secret을 나누어 등록합니다.

```bash
make env-check APP=keycloak PROFILE=prod COMPONENT=server
make env-check APP=keycloak PROFILE=prod COMPONENT=oidc
make env-check APP=portal PROFILE=prod COMPONENT=client
make env-check APP=portal PROFILE=prod COMPONENT=api
make env-check APP=portal PROFILE=prod COMPONENT=web
make env-profile-key-check ENV_APP=portal ENV_PROFILE=prod
```

`make env-profile-key-check`를 인자 없이 실행하면 local을 포함한 전체 입력을 검사합니다.
서버에서는 앱·환경을 지정하거나 `make server-check APP=<앱>`을 사용합니다.

검사는 앱·환경·파일 경로와 누락된 키만 표시하며 실제 값은 출력하지 않습니다.
검사 대상은 작업별로 다릅니다.

- `server`: Keycloak 기동 입력. 사내 OIDC가 아직 없어도 검사할 수 있습니다.
- `client`: Portal 로그인 등록 입력. Portal DB 설정은 필요하지 않습니다.
- `api`: API 기동에 필요한 DB·인증 입력.

Portal 운영 API의 `DJANGO_ALLOWED_HOSTS`에는 실제 공개 DNS와 함께 `localhost`를 포함합니다.
API·edge-nginx의 health probe가 `Host: localhost`로 요청하므로 공개 DNS만 넣으면 준비 상태 검사가 실패합니다.

검사 통과 후에도 업무 연동의 실제 연결은 따로 확인합니다.

다른 경로의 파일을 검사하려면 마지막 인자를 사용합니다.

```bash
bash deploy/shared/scripts/check-env.sh keycloak prod server /root/keycloak-runtime.env
```

`KEY=값` 형식을 사용하고 같은 key를 두 번 적지 않습니다. 값은 shell 명령으로 실행하거나
치환하지 않습니다. Kubernetes에서도 같은 값이 되도록 값 전체를 불필요한 따옴표로 감싸지
않습니다. JSON 값 내부의 따옴표는 유지합니다.

## Kubernetes에 전달

Namespace를 먼저 준비하고 필요한 작업의 입력만 등록합니다.
Secret 등록은 Keycloak의 `prod`와 Portal의 `local`·`prod`만 지원합니다.
외부 env 파일을 지정해도 이 제한과 운영 `KUBE_CONTEXT` 필수 조건을 적용합니다.
서버 등록에는 대상 `KUBE_CONTEXT`가 필수이며 kubectl의 현재 context를 자동 선택하지 않습니다.

```bash
kubectl config get-contexts
read -r -p '설정을 등록할 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT

# etch-sso namespace에 서버 기동용 Secret을 등록합니다.
make k8s-env APP=keycloak PROFILE=prod COMPONENT=server KUBE_CONTEXT="$KUBE_CONTEXT"

# 사내 OIDC 설정을 env에서 갱신할 때만 실행합니다.
make k8s-env APP=keycloak PROFILE=prod COMPONENT=oidc KUBE_CONTEXT="$KUBE_CONTEXT"

# etch-sso namespace에 Portal client 등록용 입력만 전달합니다.
make k8s-env APP=portal PROFILE=prod COMPONENT=client KUBE_CONTEXT="$KUBE_CONTEXT"

# Portal namespace와 DB 준비 후 전체 API 설정을 등록합니다.
make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT="$KUBE_CONTEXT"
```

Secret 등록은 설정 저장까지만 수행합니다. 서버 기동값은 해당 Pod를 다시 기동할 때,
OIDC·client 설정은 별도 Job을 실행할 때 반영됩니다. 상세 단계는
[Keycloak 안내](../../../keycloak/README.md)와
[Portal client 안내](../../../portal/k8s/jobs/keycloak-client/README.md)를 참고합니다.

기존 CP1의 `/root/keycloak-runtime.env`도 서버용 필수 key 4개를 유지하면 사용할 수 있습니다.
위에서 내보낸 `KUBE_CONTEXT`를 유지한 상태에서 다음 명령이 필요한 key만 전달합니다.

```bash
KUBE_CONTEXT="$KUBE_CONTEXT" bash deploy/shared/scripts/apply-env.sh \
  keycloak prod server /root/keycloak-runtime.env
```

기존 `client-secret`, `portal-public-url`은 자동 삭제하지 않지만
더 이상 서버 기동 입력으로 사용하지 않습니다. 이 값은 Portal API 설정으로 옮겨 관리합니다.

## 로컬 Kubernetes 입력 합성

로컬 Kubernetes는 `local/portal/env/api.env`를 기본으로 읽습니다.
여기에 `api-k8s.env`와 생성된 runtime override의 명시적인 차이를 한 번만 적용하고,
MinIO 접근 계정을 선택해 최종 `api-env` Secret 하나를 만듭니다.

API·migration·collectstatic은 이 결과를 함께 사용합니다.
Pod YAML에서 같은 값을 다시 덮어쓰지 않습니다.

`make k8s-up`이 합성을 수행합니다. 예전 `api-local-overrides` Secret은 더 이상 참조하지
않지만 클러스터에서 자동 삭제하지는 않습니다. 기존 local-runtime의 Keycloak 테스트 계정도
현재 로컬 Keycloak을 위한 값이므로 유지합니다.

## 관리 규칙

- 새로운 환경은 실제 필요할 때 추가하며, profile 사이에 숨은 상속을 만들지 않습니다.
- Keycloak·Portal API/MinIO·Airflow credential은 해당 env에 함께 저장합니다. Headlamp·Monitoring·FTP는 위 별도 입력 방식을 따릅니다. 인증서·개인키 파일은 Git에서 제외합니다.
- 앱 설정을 바꿀 때 다른 앱 전체 Secret을 가져오지 말고 연결에 필요한 값만 전달합니다.
- Secret 변경만으로 기존 PostgreSQL 비밀번호나 Keycloak 관리자 비밀번호가 변경되지는 않습니다.
- 환경변수 검사 회귀 테스트는 `node --test apps/tooling/tests/environment.test.cjs`로 실행합니다.

Kubernetes Monitoring은 `make monitoring-check`로 검사하고 `make monitoring-up`으로 배포합니다.
실제 설정·Grafana 관리자 Secret·차트 준비는 [Monitoring 안내](../../../monitoring/README.md)를 따릅니다.
