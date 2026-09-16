# CP1에서 Git pull로 관리하는 배포 구조

[배포 문서 안내](../../../README.md)

처음 배포하는 담당자는 [입문 가이드](../kubernetes/README.md)와 [앱별 배포](../kubernetes/05-applications.md)를 따릅니다.
권장 경로는 `keycloak-check/up`, `airflow-check/up`이며 `make server-up`은 기존 통합 운용의 호환 명령입니다.
아래는 **Keycloak 단독 수동 YAML 배포**와 기존 CP1 설정 보관 절차입니다.
공용 앱 또는 두 Worker VIP를 연결한 환경에서는 4~5절의 정적 스택 apply를 실행하지 않고 앱별 도구를 사용합니다.

CP 3대의 IP·노드 정보와 **2026-09-15 APP VIP·DNS·두 Worker Backend 현황**은
[사내 운영 클러스터 현황](../infrastructure/cluster.md)에 함께 기록합니다.
사용자가 확인한 인프라 설정과 아직 확인하지 못한 서버 배포 상태를 구분합니다.

## 1. 폴더 구조

CP1은 저장소를 내려받고 Kubernetes 배포 명령을 실행하는 위치입니다.
단독 manifest의 Keycloak·PostgreSQL·Traefik Pod는 Worker `khplane01w09`에서 실행됩니다.
APP VIP 환경에서는 [VIP 실행 절차](../../ingress/VIP.md)에 따라 Traefik만 두 Worker로 확장합니다.
다음은 배치 설계이며 문서를 추가하는 것만으로 서버의 폴더나 배포가 변경되지는 않습니다.
기본은 Keycloak 선택 체크아웃입니다. 다른 앱을 함께 운영할 때만
[선택 범위 변경](../../../SERVER_CHECKOUT.md)을 적용하며 `local/`은 서버 작업 폴더에 포함하지 않습니다.

```text
CP1
/appdata/
├── etchax/                         # Git checkout: 여기서 pull과 배포 실행
│   ├── apps/                       # --with-source 선택 시 앱 소스
│   ├── deploy/
│   │   ├── keycloak/
│   │   │   ├── env/                # 설정 예시
│   │   │   ├── k8s/                # 서버·프로필·mapper 원본
│   │   │   ├── scripts/            # 전달 YAML 생성
│   │   │   └── rendered/           # 자동 생성 YAML 두 개
│   │   ├── portal/                 # Portal 선택 시 포함
│   │   ├── airflow/                # Airflow 선택 시 포함
│   │   ├── monitoring/             # Monitoring 선택 시 포함
│   │   └── shared/
│   │       ├── docs/operations/    # 이 운영 안내와 서버 기동 절차
│   │       └── scripts/           # 설정 검사·Secret 등록
│   └── Makefile
├── etchax-config/                  # CP1에서만 관리하는 실제 설정, Git 바깥
│   └── keycloak/
│       └── prod.env                # 서버 기동값 및 선택적인 CORP_OIDC_* 값
├── certs/                          # 기존 인증서 위치 유지, Git 바깥
│   ├── etch-sso.samsungds.net.pfx
│   ├── keycloak-fullchain.crt
│   ├── keycloak.key
│   ├── SECDS-T2IssuingCA.crt
│   └── SECDS-T2RootCA.crt
└── etchax-backups/                 # 백업 절차를 별도로 마련할 때 사용
    ├── config/                    # 설정·인증서 백업, 접근 제한
    └── postgres/                  # Worker DB의 별도 백업 결과

Worker khplane01w09
/appdata/keycloak-postgres/         # 기존 PostgreSQL local PV 실제 데이터
```

백업 폴더를 만드는 것만으로 DB 백업이 실행되지는 않습니다. 백업 수집·외부 보관·복구 검증은
별도 운영 작업입니다. CP1의 저장소를 복사해도 Worker DB 데이터는 포함되지 않습니다.
Portal을 준비할 때만 `/appdata/etchax-config/portal/prod/`에 `api.env`, `web.env`,
`minio.env`를 추가합니다. 필요하지 않은 폴더를 미리 만들 필요는 없습니다.

| 내용 | 수정 위치 | 반영 방법 |
| --- | --- | --- |
| 서버 실행·노드·TLS 연결 | 개발 저장소의 `deploy/keycloak/k8s/server/stack.yaml` | commit/push 후 CP1 pull 및 스택 apply |
| 프로필·claim 매핑 | 개발 저장소의 `deploy/keycloak/k8s/` | 생성 YAML을 포함해 commit/push 후 CP1에서 mapper Job 재실행 |
| 실제 비밀번호·공개 URL | CP1 `/appdata/etchax-config/keycloak/prod.env` | 필요한 Secret 갱신 및 해당 작업 반영 |
| 인증서·개인키 | CP1 `/appdata/certs/` | `keycloak-tls` Secret 갱신 |
| PostgreSQL 데이터 | Worker의 local PV 경로 | DB 운영·백업 절차로 관리 |

CP1의 kubeconfig는 배포 계정의 기존 `$HOME/.kube/config` 또는 조직에서 지정한
`KUBECONFIG` 경로를 사용합니다. 저장소에는 넣지 않습니다.

## 2. 최초 저장소 준비

배포 계정에는 사내 Git 읽기 권한과 대상 클러스터의 배포 권한이 필요합니다.
Git, Bash, Make, kubectl(Kustomize 포함), OpenSSL을 준비합니다.
아래 수동 YAML 절차만 사용할 때는 Python·Node.js·Docker가 필요하지 않습니다.
권장 `make keycloak-check/up`은 Python 3.10+가 필요하며 Helm·Docker는 필요하지 않습니다.
이미지는 Worker에서 registry로부터 가져옵니다.

`/appdata/etchax`는 전용 배포 계정이 쓸 수 있도록 준비합니다. 기존 checkout이 있다면
새 clone을 덮어씌우지 말고 remote와 브랜치를 먼저 확인합니다. 최초 clone 예시입니다.

```bash
read -r -p '사내 Git 저장소 URL: ' ETCHAX_REPO_URL
read -r -p '배포 브랜치: ' ETCHAX_DEPLOY_BRANCH

git clone --sparse --filter=blob:none --branch "$ETCHAX_DEPLOY_BRANCH" "$ETCHAX_REPO_URL" /appdata/etchax
cd /appdata/etchax

git sparse-checkout set --cone deploy/shared
bash deploy/shared/scripts/checkout-server.sh keycloak
make server-check APP=keycloak

git remote -v
git branch --show-current
kubectl config current-context
```

배포용 브랜치는 조직에서 정한 브랜치를 사용합니다. 개발 PC의 미커밋·미추적 파일은
CP1에서 pull되지 않습니다. 원본과 최신 `deploy/keycloak/rendered/` YAML을 함께 commit/push한 뒤 사용합니다.

## 3. 실제 설정은 저장소 밖에 준비

배포 계정이 `/appdata/etchax-config`를 소유하도록 준비한 뒤 실행합니다.
기존 실제 파일은 예시로 덮어쓰지 않습니다.

```bash
cd /appdata/etchax
install -d -m 0700 /appdata/etchax-config/keycloak

test -f /appdata/etchax-config/keycloak/prod.env || \
  install -m 0600 deploy/keycloak/env/prod.env.example /appdata/etchax-config/keycloak/prod.env

vi /appdata/etchax-config/keycloak/prod.env

bash deploy/shared/scripts/check-env.sh keycloak prod server \
  /appdata/etchax-config/keycloak/prod.env
```

이 구조에서는 외부 경로를 명시합니다. 기본 `make env-check`·`make k8s-env`는
저장소 내부의 `deploy/keycloak/env/prod.env`를 읽으므로 아래 명령으로 대신합니다.
실제 설정을 두 곳에 중복 관리하지 않습니다.

```bash
kubectl create namespace etch-sso --dry-run=client -o yaml | kubectl apply -f -

bash deploy/shared/scripts/apply-env.sh keycloak prod server \
  /appdata/etchax-config/keycloak/prod.env
```

기존 DB·관리자 비밀번호를 그대로 사용합니다. Secret 값을 바꾸는 것만으로 DB 계정이나
이미 생성된 Keycloak 관리자 비밀번호가 바뀌지는 않습니다.
인증서와 `keycloak-tls`는 [TLS 가이드](../../../keycloak/TLS.md)의 절차로 별도 준비합니다.
Worker 디스크·포트·DNS 준비는 [Keycloak 배포 안내](../../../keycloak/README.md)를 따릅니다.

## 4. 최초 서버 배포와 매핑 설정

개발 단계에서 생성해 Git에 반영한 YAML을 사용합니다. 배포 전에 렌더링 가능 여부를 확인합니다.

```bash
cd /appdata/etchax
kubectl kustomize deploy/keycloak/k8s >/dev/null
kubectl apply -f deploy/keycloak/rendered/internal-keycloak-stack.yaml

kubectl rollout status statefulset/keycloak-postgres -n etch-sso --timeout=5m
kubectl rollout status deployment/keycloak -n etch-sso --timeout=10m
kubectl rollout status deployment/traefik -n etch-sso --timeout=5m
```

새 DB라면 사내 OIDC 연결을 먼저 준비합니다. 관리 화면으로 설정하거나, 외부 env 파일의
`CORP_OIDC_*` 항목을 작성한 뒤 다음 선택 작업을 실행합니다. 정상인 기존 연결은 생략합니다.

```bash
bash deploy/shared/scripts/check-env.sh keycloak prod oidc /appdata/etchax-config/keycloak/prod.env
bash deploy/shared/scripts/apply-env.sh keycloak prod oidc /appdata/etchax-config/keycloak/prod.env

kubectl delete job keycloak-oidc-setup -n etch-sso --ignore-not-found
kubectl apply -f deploy/keycloak/k8s/oidc/oidc-setup-job.yaml
kubectl wait --for=condition=complete job/keycloak-oidc-setup -n etch-sso --timeout=15m
kubectl logs job/keycloak-oidc-setup -n etch-sso
```

사내 OIDC 연결이 준비되면 프로필과 mapper를 적용합니다.

```bash
kubectl delete job keycloak-oidc-claim-mappers -n etch-sso --ignore-not-found
kubectl apply -f deploy/keycloak/rendered/internal-keycloak-claim-mappers.yaml
kubectl logs -f job/keycloak-oidc-claim-mappers -n etch-sso --pod-running-timeout=120s
kubectl wait --for=condition=complete job/keycloak-oidc-claim-mappers -n etch-sso --timeout=15m
```

완료 후 사내 OIDC를 거쳐 재로그인하여 사용자 값을 확인합니다.
Portal client 등록과 앱 배포는 이후 [Portal 안내](../../../portal/k8s/overlays/prod/README.md)에서 진행합니다.

## 5. 이후 pull과 배포

CP1에서는 원본과 생성 YAML을 직접 편집하지 않고 개발 저장소에서 수정합니다.
pull 전에 추적 파일에 로컬 변경이 없는지 확인합니다. 아래 명령은 단계별로 실행하며
오류가 나면 다음 단계로 진행하지 않습니다.

```bash
cd /appdata/etchax
git status --short
git branch --show-current
git rev-parse HEAD
```

로컬 변경이 있으면 먼저 내용을 확인하고 해결합니다. 변경을 버리기 위해 강제 초기화하지 않습니다.
배포할 브랜치와 현재 커밋을 확인한 다음 갱신합니다.

```bash
git pull --ff-only
git log -1 --oneline
kubectl config current-context
```

`git pull`은 파일만 갱신합니다. Kubernetes 리소스·Secret·DB·Pod는 자동으로 바뀌지 않습니다.
변경 내용에 해당하는 작업만 실행합니다.

| 이번 변경 | 실행할 작업 |
| --- | --- |
| 문서만 변경 | 배포 불필요 |
| 서버 manifest 변경 | 스택 YAML apply 및 rollout 확인 |
| 프로필·mapper 변경 | mapper YAML의 Job 삭제 후 apply 및 완료 확인 |
| 실제 env 변경 | 필요한 Secret 등록 후 대상 서버·Job 반영 |
| 인증서 갱신 | TLS 가이드대로 Secret 갱신 및 실제 endpoint 검증 |
| Portal 소스 변경 | 별도 이미지 빌드·배포 절차 적용. pull만으로 앱이 갱신되지 않음 |

서버 스택을 다시 적용하면 Traefik의 namespace 감시 설정도 원본 값으로 돌아갑니다.
Portal을 함께 운영한다면 [Portal 운영 안내](../../../portal/k8s/overlays/prod/README.md)의 선택 패치를
다시 적용해야 합니다. 지금 Keycloak만 운영한다면 해당 단계는 필요하지 않습니다.

`make k8s-export`는 원본에서 YAML 두 개를 다시 만드는 명령입니다. 개발 PC에서 실행하고
결과를 함께 commit/push하는 것을 기본으로 합니다. CP1에서 실행해도 배포가 자동 실행되지는
않으며, 생성 결과가 Git 파일과 달라지면 배포 전에 원인을 확인합니다.

## 6. 운영 경계

- Git으로 갱신: `/appdata/etchax`의 소스·배포 정의·문서.
- CP1에서 별도 보관: 실제 env·인증서·kubeconfig·백업.
- Kubernetes에 저장: Secret과 실행 중인 리소스. 폴더 복사와는 별개.
- Worker에 저장: PostgreSQL 실제 데이터. 저장소 경로를 바꿔도 이동하지 않음.

이 구조는 기존 `/appdata/certs`와 Worker DB 경로를 유지합니다.
이미 서버에 있는 파일을 자동 이동하거나 기존 Secret을 재생성하는 작업은 포함하지 않습니다.
