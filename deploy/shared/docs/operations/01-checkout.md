# 서버 파일과 입력 관리

[공통 안내](../README.md)

- [선택 checkout](#선택-checkout)
- [Git·운영 파일 관리](#git운영-파일-관리)

## 선택 checkout


사내 서버에서 필요한 앱의 배포 파일만 내려받는 방법입니다.
개발 PC의 전체 작업 폴더에는 이 절차를 적용하지 않습니다.

앱 env는 기본 파일 또는 앱 도구에 지정한 외부 경로를 사용합니다.
인증서와 DB 데이터는 기존 서버 경로에 유지합니다.
아래 절차는 변경사항이 Git에 반영된 뒤 서버에서 실행합니다.

### 처음 clone하기

기존 Kubernetes에서 Portal 외 서비스를 먼저 준비하는 예시입니다.
저장소 주소와 배포 브랜치는 실제 운영 값을 입력합니다.

```bash
read -r -p '사내 Git 저장소 URL: ' ETCHAX_REPO_URL
read -r -p '배포 브랜치: ' ETCHAX_DEPLOY_BRANCH

git clone --sparse --filter=blob:none --branch "$ETCHAX_DEPLOY_BRANCH" \
  "$ETCHAX_REPO_URL" /appdata/etchax
cd /appdata/etchax

# 먼저 선택 체크아웃 도구만 가져옵니다.
git sparse-checkout set --cone deploy/shared
bash deploy/shared/scripts/checkout-server.sh platform
```

`--sparse`로 시작하므로 최초 작업 폴더에도 `apps/`·`local/`·`docs/`가 생성되지 않습니다.
서버 운영 문서는 선택 경로에 포함된 `deploy/shared/docs/`를 사용합니다.
[사내 인프라 정보](../infrastructure/README.md)과 서버 현황·전체 미러 목록도 이 경로에 포함됩니다.
`--filter=blob:none`은 Git 서버가 partial clone을 지원할 때 파일 내용 다운로드를 줄입니다.
서버가 지원하지 않으면 이 옵션을 생략할 수 있습니다. sparse checkout은 Git 이력 접근 권한을 제한하지 않습니다.
[Git clone](https://git-scm.com/docs/git-clone)과
[sparse checkout](https://git-scm.com/docs/git-sparse-checkout)의 공식 설명을 참고합니다.

### 앱 선택

| 인자 | 기본 배포 경로 |
| --- | --- |
| `platform` | Portal을 제외한 Keycloak·Airflow·FTP·Monitoring·Headlamp·MinIO |
| `keycloak` | `deploy/keycloak` |
| `keycloak-airflow` | `deploy/keycloak`, `deploy/airflow` |
| `portal` | `deploy/portal` |
| `airflow` | `deploy/airflow` |
| `monitoring` | `deploy/monitoring` |
| `headlamp` | `deploy/headlamp` |
| `ftp` | `deploy/ftp` |
| `minio` | `deploy/minio` |
| `all` | 위 앱 배포 정의 전체 |

경로 목록의 원본은 [apps.json](../../apps.json)입니다. 기본 checkout은 소스 없이 준비된 이미지로 배포합니다.
Portal 선택은 로그인 client 등록 명령에 필요한 Keycloak의 `scripts`, `k8s/claims`, `k8s/oidc`,
`k8s/server` 지원 코드도 포함합니다. Keycloak env는 포함하지 않으며 Portal 검사는 Portal 입력만 사용합니다.

이미지 빌드가 필요한 서버에서는 다음과 같이 소스를 추가합니다.

```bash
bash deploy/shared/scripts/checkout-server.sh airflow --with-source
bash deploy/shared/scripts/checkout-server.sh portal --with-source
```

`--with-source`를 붙이면 Airflow는 `apps/airflow`, Portal은 `apps/portal` 소스도 받습니다.
그룹 선택에도 같은 규칙을 적용합니다. `local/`은 포함하지 않습니다.

옵션 없이 다시 실행하면 배포 파일만 남기는 범위로 돌아갑니다.
선택 범위는 이전 목록에 추가되는 것이 아니라 교체됩니다. 여러 앱을 유지하려면 해당 그룹을 선택합니다.

공통 도구와 운영 문서인 `deploy/shared`는 항상 포함합니다. 루트 `docs/` 전체는 받지 않습니다.
cone 모드 특성상 루트 파일과 상위 디렉터리의 파일도 포함되므로 Makefile과 배포 안내를 사용할 수 있습니다.
사내 서버는 Kubernetes만 사용합니다. all 선택은 파일 선택 범위이며, 모든 앱의 Kubernetes 전환 완료를 뜻하지 않습니다.

선택 범위를 바꾸려면 `bash deploy/shared/scripts/checkout-server.sh <앱>`을 실행합니다.
이 명령은 이전 선택 범위를 교체합니다. Portal 외 서비스를 함께 관리하면 `platform`, Portal까지 관리하면 `all`을 사용합니다.
기존 전체 checkout에서도 실행할 수 있지만, 변경된 작업 파일이 있으면 도구가 중단합니다.
선택에서 빠지는 폴더에 Git이 추적하지 않는 제외 파일(ignored 파일)이 있으면 경로를 표시하고 중단합니다.
예를 들어 Portal의 `*.pre-k8s.bak`, 소스 폴더의 `.env`, 제외될 `docs/`의 인증서를 보호합니다.
중단된 경우에는 파일과 기존 선택 범위가 그대로 남습니다.

필요한 파일을 저장소 밖에 보관하거나, 해당 앱을 포함하는 그룹을 선택한 뒤 다시 실행합니다.
도구가 파일을 자동으로 이동·삭제하지는 않습니다.
계속 포함되는 경로와 cone 모드가 유지하는 루트·상위 폴더의 파일은 전환을 막지 않습니다.

### 검사와 배포

기존 클러스터에서 [앱별 배포 순서](02-deploy.md#앱-의존-관계)를 따릅니다.
먼저 공용 Ingress를 검사·적용하고 Keycloak·Airflow·Monitoring·Headlamp·FTP의 검사와 배포를 각각 수행합니다.
공용 Ingress 명령은 앱 env·Portal 이미지 없이 실행하며 기존 감시 namespace와 VIP 배치를 보존합니다.
앱별 실행 순서는 [서버 기동 안내](../README.md#배포운영)를 따릅니다.

```bash
# 앱별 Helm·chart와 입력 파일을 준비한 뒤 기반 앱 원본을 검사합니다.
make server-check APP=platform PROFILE=prod

# 실제 클러스터를 조회·검사한 뒤 공용 Ingress만 적용합니다.
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

`KUBE_CONTEXT`에는 확인한 클러스터 context를 명시합니다. 현재 지원 PROFILE은 prod입니다.
`server-check`는 해당 앱의 공개 예시·존재하는 env 형식과 Kubernetes 원본을 검사합니다.
Airflow는 [전용 안내](../../../airflow/README.md)에 따라 Helm·고정 chart를 반입한 뒤 검사합니다.
Monitoring도 [전용 안내](../../../monitoring/README.md)에 따라 Helm·고정 chart를 준비합니다. PROFILE=oidc는 미지원입니다.
FTP는 `make server-check APP=ftp`로 검사하고 [서버별 FTP 안내](../../../ftp/README.md)에 따라 적용합니다.
실제 비밀값이 준비되지 않아도 원본을 검사할 수 있으며, 서비스 연결이나 실제 기동 성공을 보장하지는 않습니다.

실제 입력은 별도로 검사합니다. CP1 외부 Keycloak env 예시입니다.

```bash
bash deploy/shared/scripts/check-env.sh keycloak prod server \
  /appdata/etchax-config/keycloak/prod.env
```

Keycloak 실제 배포는 [전용 안내](../../../keycloak/README.md)의 `make keycloak-up`을 사용합니다.
`make k8s-export`와 [Keycloak 전달 YAML 참고](../../../keycloak/docs/04-operations.md#전달용-yaml)는 별도 전달 경로이며 최초 설치는 단계별 앱 도구를 사용합니다.
Portal을 추가하는 절차는 아래 절을 따릅니다.
`server-check`나 `git pull`은 클러스터에 적용하거나 Secret을 갱신하지 않습니다.

개발 PC의 전체 검사인 `make env-profile-key-check`, `make k8s-render` 대신 서버에서는 앱별 `server-check`를 사용합니다.
설정 파일 구조만 검사하려면 `make env-profile-key-check ENV_APP=portal ENV_PROFILE=prod`처럼 범위를 지정합니다.

### 나중에 Portal 추가하기

기존 기반 앱의 파일을 유지하려면 `platform`에서 `all`로 확장합니다.
`portal`만 선택하면 기반 앱의 선택 경로가 제외되므로 이 용도로 사용하지 않습니다.

```bash
bash deploy/shared/scripts/checkout-server.sh all
make server-check APP=portal PROFILE=prod
```

[Portal 운영 안내](../../../portal/k8s/overlays/prod/README.md)에 따라 이미지·외부 DB·env·TLS를 준비하고
client 등록·migration·overlay 적용을 완료합니다. 서버 Secret 등록은
`make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT="$KUBE_CONTEXT"`처럼 context를 명시합니다.
overlay가 Portal namespace의 `portal-traefik` 권한을 만든 뒤 감시 범위를 연결합니다.

```bash
make ingress-connect APP=portal KUBE_CONTEXT="$KUBE_CONTEXT"
```

이 명령은 기존 Portal 권한을 확인하고 공용 Traefik의 감시 namespace만 확장합니다.
Keycloak·Airflow·DB를 재배포하지 않으며 이미 연결된 경우 감시 범위를 유지합니다.

### 이후 갱신

```bash
git status --short
git pull --ff-only
make server-check APP=platform
```

처음 설정한 선택 범위는 이후 pull에서도 유지됩니다. 이력에서 local 파일을 삭제하거나
개발 PC의 checkout을 바꿀 필요는 없습니다. 원래 전체 checkout으로 돌아가려면
변경사항을 정리한 뒤 `git sparse-checkout disable`을 사용합니다.

## Git·운영 파일 관리


CP1은 저장소를 내려받고 배포 명령을 실행하는 관리 서버입니다.
앱의 Pod와 데이터가 놓이는 Worker는 앱별 배포 정의에서 정합니다.

이 문서는 공통 파일과 Git 관리 방법을 설명합니다.
앱 설치·설정 명령은 아래 앱별 안내를 따릅니다.

### 파일과 데이터의 위치

| 구분 | 관리 방법 |
| --- | --- |
| Git checkout | `Makefile`, 선택한 `deploy/<app>`, `deploy/shared`, 문서 |
| 앱 env | 해당 앱이 정한 파일 하나를 원본으로 관리. 외부 경로 사용 시 앱 도구에 명시 |
| 인증서·개인키 | [공용 인증서 안내](../certificates/prepare.md)의 경로·권한·Git 제외 규칙 적용 |
| kubeconfig | 배포 계정의 `$HOME/.kube/config` 또는 조직이 지정한 `KUBECONFIG`. Git에 넣지 않음 |
| 실제 DB·업무 데이터 | 앱의 PV/PVC·Worker·외부 저장소. checkout 복사로 백업되지 않음 |
| 백업 | 앱별 백업·외부 보관·복구 검증 절차를 별도로 준비 |

최초 저장소 준비와 앱 선택은 [서버 선택 checkout](#선택-checkout)을 따릅니다.
서버 실행에는 기본적으로 `local/`이나 앱 소스가 필요하지 않습니다.

### 갱신 전 확인

배포 checkout 루트에서 다음 명령을 하나씩 실행합니다.

```bash
git status --short
git remote -v
git branch --show-current
git rev-parse HEAD
kubectl config current-context
```

변경 파일이 있으면 내용을 먼저 확인하고 보존합니다.
변경을 없애기 위해 강제 초기화하지 않습니다.
배포 브랜치와 원격 저장소가 맞는지 확인한 뒤 갱신합니다.

```bash
git pull --ff-only
git log -1 --oneline
```

개발 PC의 미커밋·미추적 파일은 pull로 전달되지 않습니다.
Git 갱신은 파일만 바꾸며 Kubernetes 리소스·Secret·DB·실행 중인 Pod를 자동 변경하지 않습니다.

### 앱별 반영 안내

| 앱 | 원본 안내 |
| --- | --- |
| Keycloak | [CP1 반영 위치·운영 참고](../../../keycloak/docs/04-operations.md), [최초 설치](../../../keycloak/README.md) |
| Airflow | [단계별 실행](../../../airflow/docs/03-deploy.md#배포와-검증) |
| Portal | [배포 안내](../../../portal/README.md) |
| FTP | [배포 안내](../../../ftp/README.md) |
| Headlamp | [배포 안내](../../../headlamp/README.md) |
| Monitoring | [배포 안내](../../../monitoring/README.md) |

여러 앱이 공유하는 Traefik·VIP·DNS 상태는 [네트워크 정보](../infrastructure/network.md)와
[VIP 안내](../ingress/setup.md)를 따릅니다. 앱별 env·Secret·DB 변경은 각 앱이 소유합니다.
