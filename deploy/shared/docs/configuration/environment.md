# 앱별 환경설정

[배포 안내](../../../README.md) · [사내 인프라 정보](../infrastructure/README.md) · [미러 원본](../infrastructure/repositories.md)

사내 서버 앱의 env를 작성·검사하고 Kubernetes Secret으로 등록하는 계약입니다.
명령은 저장소 루트에서 실행합니다. Portal 최초 배포라면 [Portal 입력 순서](../../../portal/README.md)부터 확인합니다.

## 1. 파일 위치

```text
deploy/
├── keycloak/env/prod.env          # 관리자·주소·전용 DB와 사내 OIDC(CORP_OIDC_*)
├── portal/env/
│   ├── prod/api.env               # API·migration·collectstatic·client 등록
│   ├── prod/web.env               # 브라우저 공개 설정
│   └── test/api.env               # CI API 자동 테스트
├── minio/env/prod.env             # 독립 공용 MinIO
├── airflow/env/
│   ├── k8s.env                    # Kubernetes 배포
│   └── build.env                  # 이미지 빌드
├── monitoring/env/
│   ├── k8s.env                    # Kubernetes 배포
│   └── grafana-admin.env.example  # Git 밖 관리자 env 예제
├── headlamp/env/k8s.env           # 공개 설정·Secret 이름
└── ftp/env/prod.env               # 이미지·배치 설정
```

사내 서버와 CI는 `deploy/`의 파일을 사용합니다. 사내 배포는 Kubernetes 전용이며 env 도구는 지정한 파일만 읽고 옆 파일을 합치지 않습니다.

## 2. 비밀값 관리 방식

| 방식 | 앱 | 상세 |
| --- | --- | --- |
| env에 일반 설정과 비밀번호·토큰·서명 키·인증 헤더를 함께 넣고 비공개 Git 저장소에서 관리 | Keycloak·Portal API·MinIO·Airflow | 아래 3절 |
| 실제 비밀값은 별도 Secret으로 등록하고 env에는 Secret 이름만 기록 | Headlamp | client secret 숨김 입력 → 전용 Secret. [client secret 등록](../../../headlamp/docs/02-authentication.md#5-cp1에서-client-secret-등록) |
| 〃 | Monitoring | Git 밖의 관리자 env 파일 → Grafana 관리자 Secret. [관리자 Secret 준비](../../../monitoring/docs/01-install.md#5-namespace와-관리자-secret-준비) |
| 〃 | FTP | 계정 예제 수정 또는 별도 계정 파일 → 공용 FTP 계정 Secret. [계정 파일 준비](../../../ftp/docs/01-install.md#4-관리-호스트의-계정-파일-준비) |

- Portal Web 설정은 브라우저에 공개되므로 비밀값을 넣지 않습니다.
- 인증서·개인키 파일은 Git에서 제외하고 [인증서 안내](../certificates/prepare.md)에 따라 준비합니다.
- 앱 설정을 바꿀 때 다른 앱 전체 Secret을 가져오지 말고 연결에 필요한 값만 전달합니다.
- Secret 변경만으로 기존 PostgreSQL 비밀번호나 Keycloak 관리자 비밀번호가 변경되지는 않습니다.

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
| Airflow 이미지 빌드 | `deploy/airflow/env/build.env` | 사내 의존성·DAG 이미지 빌드 |
| Kubernetes Monitoring | `deploy/monitoring/env/k8s.env` | 노드·local PV·이미지 미러·Grafana Secret 참조 |
| Headlamp 공개 설정 | `deploy/headlamp/env/k8s.env` | 공개 주소·issuer·Secret/CA 이름. 실제 client secret 제외 |
| FTP 배포 설정 | `deploy/ftp/env/prod.env` | `FTP_IMAGE` 사내 미러 주소·고정 tag/digest, 선택 `IMAGE_PULL_SECRET`, control plane 선택 허용 `FTP_ALLOW_CONTROL_PLANE`(생략 시 true, false면 control plane 선택 거부). `FTP_ENV`로 파일 변경. 로그인 계정 파일은 `FTP_CREDENTIAL_FILE`로 별도 지정 |

- Keycloak은 Portal 주소나 client secret 없이 기동합니다. Portal client secret과 사내 OIDC에서 받은 secret은 서로 다른 값입니다.
- 서버 이미지·실행 노드·CPU·메모리·볼륨 용량의 입력 위치는 앱마다 다릅니다. Portal·Keycloak은 배포 YAML, Airflow·Monitoring은 env에서 노드·경로·일부 이미지 설정을 읽어 렌더합니다. 공통 자원 설정은 각 앱의 manifest 또는 Helm values를 확인합니다.
- Portal API env는 서버·DB·로그인·HTTPS → 공용 연동 → 업무 기능(Emails·Assistant·Drone 포함) → 조정·개발 설정 순서로 구성하며 Keycloak 연결값도 함께 적습니다. prod에는 서버·DB·로그인·파일 저장소의 필수값을 먼저 넣고, timeout·cache 같은 선택값을 생략하면 코드 기본값을 사용합니다. 업무 연동 키의 의미·형식은 [환경 설정](../../../../docs/reference/01-configuration.md#주요-설정-그룹)에 있습니다.
- Portal 운영 API의 `DJANGO_ALLOWED_HOSTS`에는 공개 DNS와 함께 `localhost`를 포함합니다. API·edge-nginx의 health probe가 `Host: localhost`로 요청하므로 공개 DNS만 넣으면 준비 상태 검사가 실패합니다.
- Keycloak의 `COMPONENT=oidc` 입력은 `CORP_OIDC_DISCOVERY_URL`이 있으면 endpoint를 자동 해석합니다. 실행 호스트에 Python과 discovery 접속·TLS 신뢰가 필요합니다.

### 작성 형식

- `KEY=값` 형식을 사용하고 같은 key를 두 번 적지 않습니다.
- 값은 shell 명령으로 실행하거나 치환하지 않습니다. Kubernetes에서도 같은 값이 되도록 값 전체를 불필요한 따옴표로 감싸지 않습니다. JSON 값 내부의 따옴표는 유지합니다.
- 새로운 환경은 실제 필요할 때 추가하며 profile 사이에 숨은 상속을 만들지 않습니다.

## 4. 설정 검사

검사는 앱·환경·파일 경로와 누락된 키만 표시하며 실제 값은 출력하지 않습니다. 클러스터를 변경하지 않습니다.

```bash
make env-check APP=keycloak PROFILE=prod COMPONENT=server   # Keycloak 기동 입력. 사내 OIDC 없이도 검사 가능
make env-check APP=keycloak PROFILE=prod COMPONENT=oidc     # 사내 OIDC 설정 Job 입력
make env-check APP=portal PROFILE=prod COMPONENT=client     # Portal 로그인 등록 입력. DB 설정 불필요
make env-check APP=portal PROFILE=prod COMPONENT=api        # API 기동의 DB·인증 입력
make env-check APP=portal PROFILE=prod COMPONENT=web
make env-profile-key-check ENV_APP=portal ENV_PROFILE=prod  # 파일 구조만 검사
```

Airflow·Monitoring·Headlamp의 `make env-check APP=<앱>`은 각 앱의 Kubernetes 검사 도구를 사용합니다.
Helm·chart 준비는 [Airflow](../../../airflow/README.md)·[Monitoring](../../../monitoring/README.md) 안내를 따르며, Monitoring은 `make monitoring-check`로도 검사합니다.

```bash
python3 deploy/airflow/scripts/manage.py check --env deploy/airflow/env/k8s.env
```

다른 경로의 파일은 마지막 인자로 지정합니다.

```bash
bash deploy/shared/scripts/check-env.sh keycloak prod server /root/keycloak-runtime.env
```

**기대 결과:** `설정 검사 통과 (설정값은 출력하지 않습니다.)`가 출력됩니다.
`make env-profile-key-check`를 인자 없이 실행하면 local을 포함한 전체 입력을 검사하므로 서버에서는 앱·환경을 지정하거나 `make server-check APP=<앱>`을 사용합니다.
검사 통과 후에도 업무 연동의 실제 연결은 따로 확인합니다.

## 5. Kubernetes Secret 등록

Secret 등록은 Keycloak `prod`와 Portal `local`·`prod`만 지원합니다. Airflow는 전용 deploy 명령이 DB·Airflow Secret을 나누어 등록합니다.
Namespace를 먼저 준비하고 필요한 작업의 입력만 등록합니다. 서버 등록에는 대상 `KUBE_CONTEXT`가 필수이며 외부 env 파일을 지정해도 같습니다.

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

**기대 결과:** `설정 등록 완료: <namespace> / <secret>`이 출력됩니다. 등록은 설정 저장까지만 수행합니다.
서버 기동값은 해당 Pod를 다시 기동할 때, OIDC·client 설정은 별도 Job을 실행할 때 반영됩니다.
env 검사·Secret 등록 명령은 Job을 실행하지 않으므로 초기 설정은 [Keycloak 자체 설정 절차](../../../keycloak/docs/03-configure.md#realm과-사내-로그인),
client 등록은 [Portal client 안내](../../../portal/docs/01-install.md#keycloak-client-등록)를 따릅니다.

**실패 확인:** `KUBE_CONTEXT`가 비어 있거나 지원하지 않는 앱·환경이면 등록 전에 중단합니다.

## 6. 기존 설치 호환

- 설정을 여러 파일로 나누어 쓰던 서버는 현재 통합 env(`api.env`·`web.env`)에 기존 값이 보존됐는지 확인합니다. 이전 파일(`*.pre-k8s.bak`)은 Git에서 제외되며 checkout 전환 도구가 보호합니다.
- 기존 CP1의 `/root/keycloak-runtime.env`도 서버용 필수 key 4개를 유지하면 사용할 수 있습니다. 5절에서 export한 `KUBE_CONTEXT`를 유지한 상태에서 필요한 key만 전달합니다.

  ```bash
  KUBE_CONTEXT="$KUBE_CONTEXT" bash deploy/shared/scripts/apply-env.sh \
    keycloak prod server /root/keycloak-runtime.env
  ```

- `client-secret`, `portal-public-url`이 Keycloak 서버 Secret에 남아 있어도 기동 입력으로 사용하거나 자동 삭제하지 않습니다. Portal client secret과 공개 URL은 Portal API env에서 관리합니다.
- env를 Secret으로 등록하는 배포 방식과 Headlamp·Monitoring의 기존 Secret 참조는 유지합니다.

## 7. 회귀 테스트

환경변수 검사 도구를 바꿨다면 `node --test apps/tooling/tests/environment.test.cjs`로 회귀 테스트를 실행합니다.
