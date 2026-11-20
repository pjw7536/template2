# 앱별 환경설정

[배포 안내](../../../README.md) · [사내 인프라 정보](../infrastructure/README.md) · [미러 원본](../infrastructure/repositories.md)

사내 서버 앱의 env를 작성·검사하고 Kubernetes Secret으로 등록하는 계약입니다.
명령은 저장소 루트에서 실행합니다. Portal 최초 배포라면 [Portal 입력 순서](../../../portal/README.md)부터 확인합니다.

저장소의 env 파일은 저장소를 개발할 때 고칩니다. 서버에서 다른 값이 필요하면 저장소 파일을 고치지 않고 [저장소 밖 env 사본](#저장소-밖-env-사본)을 씁니다.

## 1. 파일 위치

```text
deploy/
├── keycloak/env/prod.env          # 관리자·주소·전용 DB와 사내 OIDC(CORP_OIDC_*)
├── portal/env/
│   ├── prod/api.env               # API·migration·collectstatic·client 등록
│   ├── prod/web.env               # 브라우저 공개 설정
│   ├── prod/build.env             # API·Web 이미지 빌드
│   └── test/api.env               # CI API 자동 테스트
├── minio/env/prod.env             # 독립 공용 MinIO
├── registry/env/
│   ├── k8s.env                    # Kubernetes 배포
│   └── push-initial.env           # push 계정 Secret이 없을 때만 쓰는 초기 계정
├── airflow/env/
│   ├── k8s.env                    # Kubernetes 배포
│   └── build.env                  # 이미지 빌드
├── monitoring/env/
│   ├── k8s.env                    # Kubernetes 배포
│   └── grafana-initial.env        # 관리자 Secret이 없을 때만 쓰는 초기 계정
├── headlamp/env/k8s.env           # 공개 설정·Secret 이름
├── ftp/env/
│   ├── prod.env                   # 이미지·배치 설정
│   └── initial-account.env        # 계정 Secret이 없을 때만 쓰는 초기 계정
└── iam/env/prod.env               # Keycloak에 등록할 권한관리 client 설정
```

사내 서버와 CI는 `deploy/`의 파일을 사용합니다. 사내 배포는 Kubernetes 전용이며 env 도구는 지정한 파일만 읽고 옆 파일을 합치지 않습니다.
앱이 읽는 파일과 그 경로를 바꾸는 변수 이름은 [apps.json](../../apps.json)의 `inputs`와 각 앱 가이드의 `입력` 표에 있습니다.

## 2. 비밀값 관리 방식

| 방식 | 앱 | 상세 |
| --- | --- | --- |
| env에 일반 설정과 비밀번호·토큰·서명 키·인증 헤더를 함께 넣고 비공개 Git 저장소에서 관리 | Keycloak·Portal API·MinIO·Airflow | 아래 3절 |
| 실제 비밀값은 별도 Secret으로 등록하고 env에는 Secret 이름만 기록 | Headlamp | `make headlamp-oidc-setup`이 Keycloak의 client secret을 전용 Secret으로 등록. 수동 등록은 [client secret 등록](../../../headlamp/docs/02-authentication.md#5-관리-호스트에서-client-secret-등록) |
| 신규 설치용 계정 파일, 기존 서비스는 운영 계정 유지 | Monitoring | `deploy/monitoring/env/grafana-initial.env` → Grafana 관리자 Secret. [관리자 Secret 준비](../../../monitoring/docs/01-prepare.md#grafana-관리자-계정) |
| 〃 | FTP | `deploy/ftp/env/initial-account.env` (권한 600) → 공용 FTP 계정 Secret. [계정 파일 준비](../../../ftp/docs/01-install.md#4-관리-호스트의-계정-파일-준비) |
| 〃 | Registry | `deploy/registry/env/push-initial.env` → bcrypt htpasswd → push 계정 Secret. [push 계정 준비](../../../registry/README.md#입력) |

- Portal Web 설정은 브라우저에 공개되므로 비밀값을 넣지 않습니다.
- 인증서·개인키 파일은 Git에서 제외하고 [인증서 안내](../certificates/prepare.md)에 따라 준비합니다.
- 앱 설정을 바꿀 때 다른 앱 전체 Secret을 가져오지 말고 연결에 필요한 값만 전달합니다.
- Secret 변경만으로 기존 PostgreSQL 비밀번호나 Keycloak 관리자 비밀번호가 변경되지는 않습니다.
- 비밀값은 응답·운영 기록·보고서에 옮겨 적지 않습니다.

## 3. 앱별 env 내용

| 설정 | 관리 위치 | 읽는 대상 |
| --- | --- | --- |
| Keycloak 관리자·주소·전용 DB | `deploy/keycloak/env/prod.env` 첫 부분 | Keycloak, 전용 PostgreSQL, 관리 Job |
| 사내 OIDC 접속 정보 | 같은 파일의 `CORP_OIDC_*` 부분 | 사내 OIDC 설정 Job만 |
| Portal 서버·DB·로그인 | `deploy/portal/env/<환경>/api.env` | API, migration, Django collectstatic |
| Portal client 등록 정보 | 같은 API 파일의 `OIDC_*`와 `FRONTEND_BASE_URL` | client 등록 Job에 필요한 항목만 전달 |
| 브라우저 공개 설정 | `deploy/portal/env/<환경>/web.env` | Web |
| MinIO 설정 | `deploy/minio/env/prod.env` | 독립 공용 MinIO 서버·이미지·노드·저장소·Ingress. 앱별 접근 키는 각 앱 env |
| Airflow Kubernetes 설정 | `deploy/airflow/env/k8s.env` | 전용 배포 도구 → Airflow·PostgreSQL Secret |
| Airflow 이미지 빌드 | `deploy/airflow/env/build.env` | 사내 의존성·Airflow 이미지 빌드 |
| Portal 이미지 빌드 | `deploy/portal/env/prod/build.env` | API·Web 이미지의 사내 기반 이미지·패키지 미러. `make portal-image`가 build arg로 전달하고 이미지 tag 계산에도 포함 |
| Kubernetes Monitoring | `deploy/monitoring/env/k8s.env` | 노드·local PV·이미지 미러·Grafana Secret 참조 |
| Headlamp 공개 설정 | `deploy/headlamp/env/k8s.env` | 공개 주소·issuer·Secret/CA 이름. 실제 client secret 제외 |
| FTP 배포 설정 | `deploy/ftp/env/prod.env` | `FTP_IMAGE` 사내 미러 주소·고정 tag/digest, 선택 `IMAGE_PULL_SECRET`, control plane 선택 허용 `FTP_ALLOW_CONTROL_PLANE`(생략 시 true, false면 control plane 선택 거부). `FTP_ENV`로 파일 변경. 로그인 계정 파일은 `FTP_CREDENTIAL_FILE`로 별도 지정 |

- Keycloak은 Portal 주소나 client secret 없이 기동합니다. Portal client secret과 사내 OIDC에서 받은 secret은 서로 다른 값입니다.
- 서버 이미지·실행 노드·CPU·메모리·볼륨 용량의 입력 위치는 앱마다 다릅니다. Portal·Keycloak은 배포 YAML, Airflow·Monitoring은 env에서 노드·경로·일부 이미지 설정을 읽어 렌더합니다. 공통 자원 설정은 각 앱의 manifest 또는 Helm values를 확인합니다.
- Portal API env는 서버·DB·로그인·HTTPS → 공용 연동 → 업무 기능(Emails·Assistant·Drone 포함) → 조정·개발 설정 순서로 구성하며 Keycloak 연결값도 함께 적습니다. prod에는 서버·DB·로그인·파일 저장소의 필수값을 먼저 넣고, timeout·cache 같은 선택값을 생략하면 코드 기본값을 사용합니다. 업무 연동 키의 의미·형식은 [환경 설정](../../../../docs/reference/01-configuration.md#주요-설정-그룹)에 있습니다.
- Portal 운영 API의 `DJANGO_ALLOWED_HOSTS`에는 공개 DNS와 함께 `localhost`를 포함합니다. API·edge-nginx의 health probe가 `Host: localhost`로 요청하므로 공개 DNS만 넣으면 준비 상태 검사가 실패합니다.
- Keycloak의 `COMPONENT=oidc` 입력은 `CORP_OIDC_DISCOVERY_URL`이 있으면 endpoint를 자동 해석합니다. 실행 호스트에 Python과 discovery 접속·TLS 신뢰가 필요합니다.

### 반입 후 입력할 값

| 사용 단계 | 사내에서 확정할 입력 |
| --- | --- |
| Portal 신규 배포·이전 | 외부 DB 접속 네 키(`DJANGO_DB_HOST`, `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`), 운영 Worker·업무 데이터 PVC. 기존 Portal이면 사용 중인 서명 키와 연결 계정도 유지. 이미지 tag는 `make portal-image`가 소스 내용으로 정하므로 입력하지 않음 |
| Keycloak 사내 IdP 연결 | AD FS에서 발급한 `CORP_OIDC_CLIENT_ID`와 `CORP_OIDC_CLIENT_SECRET` |
| Headlamp 로그인 | Keycloak에 등록된 Headlamp client secret과 실제 CA. `make headlamp-oidc-setup`이 등록 |
| FTP 배치 | 방화벽·저장 폴더가 준비된 실제 대상 노드 목록 `FTP_NODES` |
| HTTPS·선택 업무 연동 | 발급 인증서·개인키·CA 파일. 메일·메신저·POP3·Jira 등은 해당 기능에 필요한 실제 계정과 수신처 |

값을 받는 방법은 [접근 경로](../infrastructure/access.md)의 절을 따릅니다: 외부 DB는 [외부 DB](../infrastructure/access.md#외부-db), AD FS 값은 [AD FS](../infrastructure/access.md#ad-fs), 방화벽은 [방화벽](../infrastructure/access.md#방화벽), 인증서는 [인증서 발급](../infrastructure/access.md#인증서-발급)입니다.
신규 Airflow와 신규 Keycloak의 Airflow client 등록은 같은 Airflow env를 사용합니다. 기존 DB·client·Secret이 있는 환경에서는 설치 당시 입력을 사용합니다. 미러 URL, 이미지 이름, namespace, 서비스 주소와 파일 경로는 각 앱에 작성된 기본값을 사용합니다.

### 작성 형식

- `KEY=값` 형식을 사용하고 같은 key를 두 번 적지 않습니다.
- 값은 shell 명령으로 실행하거나 치환하지 않습니다. Kubernetes에서도 같은 값이 되도록 값 전체를 불필요한 따옴표로 감싸지 않습니다. JSON 값 내부의 따옴표는 유지합니다.
- 새로운 환경은 실제 필요할 때 추가하며 profile 사이에 숨은 상속을 만들지 않습니다.

### 저장소 밖 env 사본

서버에서 저장소의 기본 env와 다른 값을 써야 할 때의 방법입니다. 위치와 요청 기준은 [운영 입력 파일](../infrastructure/access.md#운영-입력-파일)이 원본입니다.

[변경] 기본 파일을 저장소 밖 폴더에 권한 `0600`으로 복사합니다. `<외부 env 폴더>`는 [운영 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)의 `관리 호스트 외부 앱 설정` 경로, `<기본 env>`는 위 표의 파일입니다.

```bash
install -d -m 0700 "<외부 env 폴더>"
install -m 0600 "<기본 env>" "<외부 env 폴더>/"
ls -l "<외부 env 폴더>"
```

성공: 사본 파일이 권한 `-rw-------`로 표시됩니다.

- 사본에서 바꿀 키의 줄만 `KEY=값` 형식으로 비대화형으로 고칩니다. 비밀값은 명령줄이나 응답에 쓰지 않고 [운영 입력 파일](../infrastructure/access.md#운영-입력-파일) 절의 방법으로 파일에 직접 입력받습니다.
- 사본의 경로를 앱의 env 변수(예: `AIRFLOW_ENV=<경로>`)로 검사·배포·대조·진단의 각 명령에 같게 붙입니다. 처음 만든 경로는 운영 위치에 기록합니다.
- 저장소의 기본 파일이 갱신돼도 사본에는 반영되지 않습니다. checkout을 갱신한 뒤 `diff <(cut -d= -f1 "<기본 env>" | sort) <(cut -d= -f1 "<사본>" | sort)`로 키 이름의 차이를 [조회]합니다. 값은 출력되지 않습니다.

## 4. 설정 검사

검사는 앱·환경·파일 경로와 누락된 키만 표시하며 실제 값은 출력하지 않습니다. 클러스터를 변경하지 않습니다.
배포할 때는 `make ops-deploy`의 첫 단계(`<app>-check`)가 입력과 클러스터를 함께 검사하므로 아래 명령을 따로 실행할 필요가 없습니다. 파일만 확인할 때 씁니다.

[검사] 필요한 줄만 실행합니다. 클러스터에 접속하지 않습니다.

```bash
make env-check APP=keycloak PROFILE=prod COMPONENT=server   # Keycloak 기동 입력. 사내 OIDC 없이도 검사 가능
make env-check APP=keycloak PROFILE=prod COMPONENT=oidc     # 사내 OIDC 설정 Job 입력
make env-check APP=portal PROFILE=prod COMPONENT=client     # Portal 로그인 등록 입력. DB 설정 불필요
make env-check APP=portal PROFILE=prod COMPONENT=api        # API 기동의 DB·인증 입력
make env-check APP=portal PROFILE=prod COMPONENT=web
make env-profile-key-check ENV_APP=portal ENV_PROFILE=prod  # 파일 구조만 검사
```

Airflow·Monitoring·Headlamp·MinIO의 `make env-check APP=<앱>`은 각 앱의 Kubernetes 검사 도구를 사용합니다.
Helm·chart 준비는 [Airflow](../../../airflow/README.md)·[Monitoring](../../../monitoring/README.md) 가이드를 따릅니다. 클러스터까지 포함한 검사는 모든 앱이 `make <app>-check KUBE_CONTEXT="<context>"`입니다.

[검사] 앱 도구를 직접 실행하는 예입니다.

```bash
python3 deploy/airflow/scripts/manage.py check --env deploy/airflow/env/k8s.env
```

[검사] 다른 경로의 파일은 마지막 인자로 지정합니다.

```bash
bash deploy/shared/scripts/check-env.sh keycloak prod server "<env 파일 절대 경로>"
```

**기대 결과:** `설정 검사 통과 (설정값은 출력하지 않습니다.)`가 출력됩니다. Airflow·Monitoring·Headlamp·MinIO는 각 앱 검사 도구의 통과 문구가 출력됩니다.
`make env-profile-key-check`를 인자 없이 실행하면 local을 포함한 전체 입력을 검사하므로 서버에서는 앱·환경을 지정하거나 `make server-check APP=<앱>`을 사용합니다.
검사 통과 후에도 업무 연동의 실제 연결은 따로 확인합니다.

## 5. Kubernetes Secret 등록

운영 Secret은 배포 도구가 등록합니다. `make ops-deploy`의 단계에 들어 있으므로 따로 등록하지 않습니다.

| Secret | 등록하는 단계 | 동작 |
| --- | --- | --- |
| Keycloak `etch-sso/keycloak-runtime` | `keycloak-up` | Secret이 없을 때만 만들고, 기존 Secret과 env가 다르면 중단. 값 변경은 [Keycloak 가이드](../../../keycloak/README.md#b-업데이트) |
| Keycloak `etch-sso/keycloak-oidc-settings` | `keycloak-setup` | env를 해석해 등록([사내 IdP 등록](../../../keycloak/docs/02-configure.md#realm과-사내-로그인)) |
| Portal `etch-sso/portal-keycloak-client` | `keycloak-portal-client-setup` | client 등록 Job에 필요한 키만 전달([Portal client 안내](../../../portal/docs/01-install.md#keycloak-client-등록)) |
| Portal `tailwind-internal/api-env`·`web-env` | `portal-up` | 배포마다 env 내용으로 교체하고 Pod를 다시 시작 |
| Airflow DB·Airflow Secret | `airflow-up` | 전용 배포 도구가 나누어 등록 |

`make k8s-env APP=keycloak ...`은 기존 `keycloak-runtime` Secret을 덮어써 실제 DB·관리자 비밀번호와 어긋나게 만들 수 있으므로 실행하지 않습니다.

[변경] 배포 없이 Portal의 Secret만 다시 등록해야 할 때 씁니다. 같은 이름의 Secret을 env 내용으로 교체하며, 대상 `KUBE_CONTEXT`가 필수입니다. Portal namespace가 먼저 있어야 합니다. 저장소 밖 env를 쓰면 `PROD_API_ENV_FILE=<경로>`·`PROD_WEB_ENV_FILE=<경로>`를 붙입니다. 개발 PC의 kind는 `PROFILE=local`을 씁니다.

```bash
# etch-sso namespace에 Portal client 등록용 입력만 전달합니다.
make k8s-env APP=portal PROFILE=prod COMPONENT=client KUBE_CONTEXT="<context>"

# Portal namespace와 DB 준비 후 전체 API 설정을 등록합니다.
make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT="<context>"
```

**기대 결과:** `설정 등록 완료: <namespace> / <secret>`이 출력됩니다. 등록은 설정 저장까지만 수행합니다.
서버 기동값은 해당 Pod를 다시 기동할 때, OIDC·client 설정은 별도 Job을 실행할 때 반영됩니다.
env 검사·Secret 등록 명령은 Job을 실행하지 않으므로 초기 설정은 [Keycloak 자체 설정 절차](../../../keycloak/docs/02-configure.md#realm과-사내-로그인),
client 등록은 [Portal client 안내](../../../portal/docs/01-install.md#keycloak-client-등록)를 따릅니다.

**실패 확인:** `KUBE_CONTEXT`가 비어 있거나 지원하지 않는 앱·환경이면 등록 전에 중단합니다.

## 6. 기존 설치 호환

- 설정을 여러 파일로 나누어 쓰던 서버는 현재 통합 env(`api.env`·`web.env`)에 기존 값이 보존됐는지 확인합니다. 이전 파일(`*.pre-k8s.bak`)은 Git에서 제외되며 도구가 읽지 않습니다.
- env를 Secret으로 등록하는 배포 방식과 Headlamp·Monitoring의 기존 Secret 참조는 유지합니다.

## 7. 회귀 테스트

환경변수 검사 도구를 바꿨다면 `node --test apps/tooling/tests/environment.test.cjs`로 회귀 테스트를 실행합니다.
