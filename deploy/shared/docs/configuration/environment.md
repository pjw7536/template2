# 앱별 환경설정

[배포 문서 안내](../../../README.md)

먼저 앱을 선택하고 그 안에서 실행 환경을 선택합니다. 명령은 저장소 루트에서 실행합니다.
Portal을 처음 배포한다면 [Portal 입력 순서](../../../portal/README.md)를 먼저 확인합니다.

```text
local/
├── portal/env/               # 외부 PC API·Web·MinIO와 K8s 차이
└── shared/env/k8s.env        # 전체 로컬 실행 입력

deploy/
├── keycloak/env/             # prod.env.example / Git 제외 prod.env
├── portal/env/
│   ├── test/                 # CI API 자동 테스트
│   └── prod/                 # 예시와 Git 제외 실제 값
├── airflow/env/              # k8s.env·build.env 예시
└── monitoring/env/           # k8s.env 예시
```

외부 PC는 `local/`, 사내와 CI는 `deploy/`에서 앱을 선택합니다.
공통 env 검사 도구는 PROFILE=local일 때만 local 경로를 사용합니다.
사내 배포는 Kubernetes 전용입니다. Keycloak 사내 OIDC는 prod 환경의 oidc component로 관리합니다.

## 무엇을 어디에 적나요?

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

Keycloak은 Portal 주소나 client secret 없이 기동합니다. Portal의 client secret과 사내
OIDC에서 받은 secret은 서로 다른 값입니다. 서버 이미지, 실행 노드, CPU·메모리와 볼륨
용량은 배포 YAML에서 관리합니다.

API는 서버·DB·로그인·HTTPS, 공용 연동, 업무 기능, 조정·개발 설정 순서입니다. Emails·Assistant·Drone별 별도
파일을 합성하지 않습니다. prod 예시는 서버·DB·로그인·파일 저장소 필수값 위주이며,
업무 연동을 사용할 때 필요한 값을 [설정 설명](../../../../docs/configuration.md)에서 추가합니다.
timeout/cache 등의 선택값을 생략하면 코드 기본값을 사용합니다. local/test는 유지하고,
prod는 기존 업무 설정과 준비한 Keycloak 입력을 통합했습니다. 실제 파일을 예시로 덮어쓰지 않습니다.

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

검사는 앱, 환경, 파일 경로와 누락된 key만 출력하며 실제 값은 출력하지 않습니다.
`server`는 사내 OIDC가 아직 없어도 통과합니다. `client`는 Portal DB 설정이 없어도
로그인 client를 등록할 수 있는지 검사합니다. `api`는 실제 API 기동에 필요한 DB·인증을
검사합니다. 업무 기능 전체의 연결 성공까지 보장하는 검사는 아닙니다.

다른 경로의 파일을 검사하려면 마지막 인자를 사용합니다.

```bash
bash deploy/shared/scripts/check-env.sh keycloak prod server /root/keycloak-runtime.env
```

`KEY=값` 형식을 사용하고 같은 key를 두 번 적지 않습니다. 값은 shell 명령으로 실행하거나
치환하지 않습니다. Kubernetes에서도 같은 값이 되도록 값 전체를 불필요한 따옴표로 감싸지
않습니다. JSON 값 내부의 따옴표는 유지합니다.

## Kubernetes에 전달

Namespace를 먼저 준비하고 필요한 작업의 입력만 등록합니다.

```bash
# etch-sso namespace에 서버 기동용 Secret을 등록합니다.
make k8s-env APP=keycloak PROFILE=prod COMPONENT=server

# 사내 OIDC 설정을 env에서 갱신할 때만 실행합니다.
make k8s-env APP=keycloak PROFILE=prod COMPONENT=oidc

# etch-sso namespace에 Portal client 등록용 입력만 전달합니다.
make k8s-env APP=portal PROFILE=prod COMPONENT=client

# Portal namespace와 DB 준비 후 전체 API 설정을 등록합니다.
make k8s-env APP=portal PROFILE=prod COMPONENT=api
```

Secret 등록은 설정 저장까지만 수행합니다. 서버 기동값은 해당 Pod를 다시 기동할 때,
OIDC·client 설정은 별도 Job을 실행할 때 반영됩니다. 상세 단계는
[Keycloak 안내](../../../keycloak/README.md)와
[Portal client 안내](../../../portal/k8s/jobs/keycloak-client/README.md)를 참고합니다.

기존 CP1의 `/root/keycloak-runtime.env`도 서버용 필수 key 4개를 유지하면 사용할 수 있습니다.
`bash deploy/shared/scripts/apply-env.sh keycloak prod server /root/keycloak-runtime.env`가
필요한 key만 전달합니다. 기존 `client-secret`, `portal-public-url`은 자동 삭제하지 않지만
더 이상 서버 기동 입력으로 사용하지 않습니다. 이 값은 Portal API 설정으로 옮겨 관리합니다.

## 로컬 Kubernetes 입력 합성

Kubernetes는 `local/portal/env/api.env`에 `local/portal/env/api-k8s.env`와 생성된 runtime override의 명시적 차이를 한 번만 적용하고 MinIO client
credential을 선택해 최종 `api-env` Secret 하나를 생성합니다. API, migration, collectstatic은
동일한 결과를 사용하며 Pod YAML에서 다시 값을 덮어쓰지 않습니다.

`make k8s-up`이 합성을 수행합니다. 예전 `api-local-overrides` Secret은 더 이상 참조하지
않지만 클러스터에서 자동 삭제하지는 않습니다. 기존 local-runtime의 Keycloak 테스트 계정도
현재 로컬 Keycloak을 위한 값이므로 유지합니다.

## 관리 규칙

- 새로운 환경은 실제 필요할 때 추가하며, profile 사이에 숨은 상속을 만들지 않습니다.
- 새 실제 credential 파일은 Git 제외하고 권한을 600으로 제한합니다. 예시는 실제 값을 담지 않습니다.
- 앱 설정을 바꿀 때 다른 앱 전체 Secret을 가져오지 말고 연결에 필요한 값만 전달합니다.
- Secret 변경만으로 기존 PostgreSQL 비밀번호나 Keycloak 관리자 비밀번호가 변경되지는 않습니다.
- 환경변수 검사 회귀 테스트는 `node --test apps/tooling/tests/environment.test.cjs`로 실행합니다.

Kubernetes Monitoring은 `make monitoring-check`로 검사하고 `make monitoring-up`으로 배포합니다.
실제 설정·Grafana 관리자 Secret·차트 준비는 [Monitoring 안내](../../../monitoring/README.md)를 따릅니다.
