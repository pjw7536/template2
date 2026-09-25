# 사내 서버 선택 체크아웃

[배포 문서 안내](README.md) · [처음부터 따라가는 가이드](shared/docs/kubernetes/README.md)

사내 서버는 `local/`을 제외하고 필요한 앱과 공통 도구를 작업 폴더에 둡니다.
외부 개발 PC에는 적용하지 않습니다. 실제 env·인증서·DB는 기존 서버 외부 경로를 유지합니다.
이 문서는 변경사항이 Git에 반영된 이후 서버에서 사용하는 절차입니다.

## 처음 clone하기

Keycloak만 배포하는 예시입니다. 저장소 주소와 배포 브랜치는 실제 운영 값을 입력합니다.

```bash
read -r -p '사내 Git 저장소 URL: ' ETCHAX_REPO_URL
read -r -p '배포 브랜치: ' ETCHAX_DEPLOY_BRANCH

git clone --sparse --filter=blob:none --branch "$ETCHAX_DEPLOY_BRANCH" \
  "$ETCHAX_REPO_URL" /appdata/etchax
cd /appdata/etchax

# 먼저 선택 체크아웃 도구만 가져옵니다.
git sparse-checkout set --cone deploy/shared
bash deploy/shared/scripts/checkout-server.sh keycloak

make server-check APP=keycloak
```

`--sparse`로 시작하므로 최초 작업 폴더에도 `local/`이 생성되지 않습니다.
`--filter=blob:none`은 Git 서버가 partial clone을 지원할 때 파일 내용 다운로드를 줄입니다.
서버가 지원하지 않으면 이 옵션을 생략할 수 있습니다. sparse checkout은 Git 이력 접근 권한을 제한하지 않습니다.
[Git clone](https://git-scm.com/docs/git-clone)과
[sparse checkout](https://git-scm.com/docs/git-sparse-checkout)의 공식 설명을 참고합니다.

## 앱 선택

| 인자 | 기본 배포 경로 |
| --- | --- |
| `keycloak` | `deploy/keycloak` |
| `keycloak-airflow` | `deploy/keycloak`, `deploy/airflow` |
| `portal` | `deploy/portal` |
| `airflow` | `deploy/airflow` |
| `monitoring` | `deploy/monitoring` |
| `headlamp` | `deploy/headlamp` |
| `ftp` | `deploy/ftp` |
| `all` | 위 앱 배포 정의 전체 |

경로 목록의 원본은 [apps.json](shared/apps.json)입니다. 기본 checkout은 소스 없이 준비된 이미지로 배포합니다.

이미지 빌드가 필요한 서버에서는 다음과 같이 소스를 추가합니다.

```bash
bash deploy/shared/scripts/checkout-server.sh airflow --with-source
bash deploy/shared/scripts/checkout-server.sh portal --with-source
```

`--with-source`는 Airflow에 `apps/airflow`, Portal에 `apps/portal`을 추가합니다. 그룹에도 같은 규칙이 적용되며 `local/`은 포함하지 않습니다.
옵션 없이 다시 실행하면 배포 전용 범위로 돌아갑니다. 기존처럼 선택 범위는 교체되며 다른 앱을 유지하려면 해당 그룹을 선택합니다.

공통 도구인 `deploy/shared`와 `docs`는 항상 포함합니다.
cone 모드 특성상 루트 파일과 상위 디렉터리의 파일도 포함되므로 Makefile과 배포 안내를 사용할 수 있습니다.
사내 서버는 Kubernetes만 사용합니다. all 선택은 파일 선택 범위이며, 모든 앱의 Kubernetes 전환 완료를 뜻하지 않습니다.

선택 범위를 바꾸려면 `bash deploy/shared/scripts/checkout-server.sh <앱>`을 실행합니다.
이 명령은 이전 선택 범위를 교체합니다. 여러 앱을 함께 관리하는 서버에는 `all`을 사용합니다.
기존 전체 checkout에서도 실행할 수 있지만, 변경된 작업 파일이 있으면 도구가 중단합니다.
기존 ignored 파일이나 실제 설정은 자동 삭제하지 않습니다.

## 검사와 배포

Keycloak과 Airflow는 [앱별 배포 순서](shared/docs/kubernetes/05-applications.md)를 따릅니다.
`keycloak-airflow`로 선택하고 `keycloak-check/up`, `airflow-check/up`을 각각 실행합니다.
`make server-up`은 [서버 기동 안내](shared/docs/operations/server-start.md)의 기존 통합 운용을 위한 호환 명령입니다.

```bash
make server-check APP=keycloak PROFILE=prod
make server-check APP=portal PROFILE=prod
```

위 명령 중 선택한 앱의 명령만 실행합니다. 현재 지원 PROFILE은 prod입니다.
`server-check`는 해당 앱의 공개 예시·존재하는 env 형식과 Kubernetes 원본을 검사합니다.
Airflow는 [전용 안내](airflow/README.md)에 따라 Helm·고정 chart를 반입한 뒤 검사합니다.
Monitoring도 [전용 안내](monitoring/README.md)에 따라 Helm·고정 chart를 준비합니다. PROFILE=oidc는 미지원입니다.
FTP는 `make server-check APP=ftp`로 검사하고 [서버별 FTP 안내](ftp/README.md)에 따라 적용합니다.
실제 비밀값이 준비되지 않아도 원본을 검사할 수 있으며, 서비스 연결이나 실제 기동 성공을 보장하지는 않습니다.

실제 입력은 별도로 검사합니다. CP1 외부 Keycloak env 예시입니다.

```bash
bash deploy/shared/scripts/check-env.sh keycloak prod server \
  /appdata/etchax-config/keycloak/prod.env
```

Keycloak 실제 배포는 [전용 안내](keycloak/README.md)의 `make keycloak-up`을 사용합니다.
`make k8s-export`와 [Keycloak 전달 YAML 참고](keycloak/operations/cp1.md#전달용-yaml)는 별도 전달 경로이며 최초 설치는 단계별 앱 도구를 사용합니다.
Portal은 [운영 안내](portal/k8s/overlays/prod/README.md)를 따릅니다.
`server-check`나 `git pull`은 클러스터에 적용하거나 Secret을 갱신하지 않습니다.

개발 PC의 전체 검사인 `make env-profile-key-check`, `make k8s-render` 대신 서버에서는 앱별 `server-check`를 사용합니다.
설정 파일 구조만 검사하려면 `make env-profile-key-check ENV_APP=portal ENV_PROFILE=prod`처럼 범위를 지정합니다.

## 이후 갱신

```bash
git status --short
git pull --ff-only
make server-check APP=keycloak
```

처음 설정한 선택 범위는 이후 pull에서도 유지됩니다. 이력에서 local 파일을 삭제하거나
개발 PC의 checkout을 바꿀 필요는 없습니다. 원래 전체 checkout으로 돌아가려면
변경사항을 정리한 뒤 `git sparse-checkout disable`을 사용합니다.
