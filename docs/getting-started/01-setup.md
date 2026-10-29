# 처음 시작하는 셋업 가이드

[문서 홈](../README.md) · [셋업 후 자주 쓰는 명령](02-usage.md) · [로컬 실행 상세](../../local/README.md)

이 문서는 **개발 PC에서 Portal을 처음 실행하고 로그인하는 과정**을 순서대로 안내합니다.
명령은 별도 표시가 없으면 `Makefile`이 있는 저장소 루트에서 실행합니다.

## 1. 실행할 환경 선택

| 목적 | 따라갈 절차 | 완료 기준 |
| --- | --- | --- |
| 내 PC에서 Portal과 관련 서비스를 함께 실행 | 아래 2~6단계 | Portal 로그인과 로컬 통합 검사 성공 |
| Portal 없이 Keycloak·Airflow 등 플랫폼만 실행 | [플랫폼 로컬 실행](../../local/01-PLATFORM.md) | `make k8s-platform-smoke` 성공 |
| 서버에 설치 | [서버 셋업 순서](#서버-셋업-순서) | 앱별 배포와 접속 확인 완료 |

전체 로컬 환경은 다음과 같이 동작합니다.

```text
내 PC
├── Docker
│   ├── kind: Docker 안에서 실행되는 개발용 Kubernetes
│   │   └── Portal(Web/API), Keycloak, Airflow, MinIO, FTP, 모니터링, mock
│   └── PostgreSQL: 별도 컨테이너와 DB 볼륨
└── 저장소의 data/와 local/shared/runtime/: 데이터·생성 설정
```

로그인은 Keycloak이 담당하고, mock은 RAG·LLM·메일·Jira 등의 외부 서비스를 대신합니다.
로컬 실행에 사내망은 필요하지 않으며 처음 도구·이미지·패키지를 받을 때 인터넷 연결이 필요합니다.

## 2. 저장소와 도구 준비

개발 PC에는 전체 저장소가 필요합니다. 이미 내려받았다면 그 폴더를 사용합니다.
새로 받는 경우 접근 가능한 Git 주소를 입력합니다.

```bash
read -r -p 'Git 저장소 URL: ' TAILWIND_REPO_URL
git clone "$TAILWIND_REPO_URL" tailwind
cd tailwind
```

현재 kind 설치 도구는 Linux 실행 파일을 받습니다. 아래 명령은 Linux 또는 Windows의 WSL2 안에서 실행하는 기준입니다.
WSL2에서는 같은 터미널에서 Docker에 연결할 수 있도록 Docker Desktop의 WSL 연결을 준비합니다.

| 준비 항목 | 필요한 이유·기준 | 확인 명령 |
| --- | --- | --- |
| Git, Bash, Make | 저장소 받기와 공통 실행 명령 | `git --version`, `bash --version`, `make --version` |
| Docker와 Compose v2 | kind 노드·이미지 빌드·로컬 DB 실행 | `docker info`, `docker compose version` |
| Python 3와 PyYAML | 로컬 실행 도구와 YAML 처리 | `python3 --version`, `python3 -c "import yaml; print(yaml.__version__)"` |
| kubectl | Kubernetes 설정과 상태 확인 | `kubectl version --client` |
| Helm 3.19.0 이상 | Airflow·Monitoring chart 처리 | `helm version --short` |
| curl, sha256sum, install | kind 다운로드·검증·설치 | `command -v curl sha256sum install` |
| Node.js와 npm | 호스트에서 Web 개발·검사 시 사용 | `node --version`, `npm --version` |

Web 개발·테스트에는 현재 lockfile 요구사항에 맞춰 **Node.js 22.13 이상인 22.x**를 사용합니다.
`make dev`의 컨테이너 빌드만 사용한다면 호스트의 Node.js 설치와 `make install`은 필수가 아닙니다.
Docker에 할당한 메모리 **10GiB 이상**, PC 메모리 **16GB 이상**, 저장소가 있는 디스크의 여유 공간 **15GiB 이상**을 준비합니다.

PyYAML이 없다면 가상환경에 설치할 수 있습니다. 아래 환경을 사용했다면 이후 실행도 활성화된 터미널에서 진행합니다.
`venv` 명령 자체가 없다면 OS의 Python 가상환경 패키지를 먼저 설치합니다.

```bash
python3 -m venv .tools/setup-venv
source .tools/setup-venv/bin/activate
python3 -m pip install PyYAML
```

## 3. kind와 배포 묶음 준비

kind는 개발용 클러스터를 만드는 도구이며 `make k8s-tools`로 저장소의 `.tools/bin/kind`에 설치합니다.
chart는 Airflow·Monitoring을 설치하는 데 필요한 배포 묶음입니다. 아래 명령은 고정 버전과 SHA-256을 확인해 받습니다.

```bash
make k8s-tools
python3 deploy/airflow/scripts/manage.py fetch-chart
python3 deploy/monitoring/scripts/manage.py fetch-chart
make k8s-check
```

`make k8s-check`가 성공하면 도구·자원·배포 정의를 확인한 상태입니다. 아직 앱은 실행되지 않았습니다.
Helm을 `.tools/bin/helm`에 준비했다면 `export PATH="$PWD/.tools/bin:$PATH"`로 위 직접 실행 명령에서도 찾을 수 있게 합니다.

기본 포트·데이터 경로로 실행할 때 별도 env 복사는 필요하지 않습니다.
포트가 이미 사용 중이면 시작 전에 [로컬 설정 안내](../../local/README.md#로컬-설정과-파일-보존)를 따라
`local/shared/env/k8s.env`에 필요한 항목만 작성합니다. 이때 서버용 `deploy/*/env` 값을 바꿀 필요는 없습니다.

## 4. 기동하고 준비 상태 확인

```bash
make dev
make k8s-status
make k8s-health
```

`make dev`는 DB 준비, 이미지 빌드, 클러스터 생성, 앱 배포, Portal migration과 개발 데이터 준비까지 수행합니다.
첫 실행은 다운로드와 이미지 빌드 때문에 오래 걸릴 수 있습니다. 마지막에 접속 주소가 표시되고
`make k8s-health`에서 `전체 앱 준비 상태·공개 진입점 정상`이 나오면 다음 단계로 진행합니다.

## 5. 브라우저 로그인과 기능 확인

1. 브라우저에서 **http://localhost:8080**을 엽니다.
2. 로그인 화면에서 [로컬 테스트 계정](../../local/README.md#주소와-계정)을 사용합니다.
3. 로그인 후 홈과 업무 화면이 열리는지 확인합니다. 계정에 따라 접근 권한이 다릅니다.
4. 터미널에서 대표 기능의 통합 검사를 실행합니다.

```bash
make k8s-smoke
```

이 검사는 로그인·채팅/RAG·메일·파일 적재·Airflow·저장소·모니터링을 확인합니다.
검사 과정에서 테스트 대화·메일·적재 이력·DAG 실행 기록이 생성됩니다.
준비 상태 검사와 통합 검사가 모두 성공하고 브라우저 로그인이 되면 첫 셋업을 마친 것입니다.

| 서비스 | 로컬 기본 주소·접속 방법 |
| --- | --- |
| Portal·API | http://localhost:8080, 상태 확인은 `/api/v1/health/` |
| Keycloak | http://localhost:8180 |
| Airflow | http://localhost:8080/airflow |
| MinIO 콘솔 | http://localhost:8080/minio-console/ |
| Grafana | `make k8s-grafana` 실행 중 http://localhost:3000 |
| Headlamp 조회 UI | `make k8s-ui` 실행 중 http://localhost:4466 |

계정·생성된 비밀번호 위치는 [로컬 계정 안내](../../local/README.md#주소와-계정)를 확인합니다.
플랫폼 전용 실행의 Headlamp는 별도 HTTPS 주소와 인증서 준비를 사용하므로 [플랫폼 접속 안내](../../local/01-PLATFORM.md#접속과-계정)를 따릅니다.

## 6. 수정·검사·종료

Portal 소스는 이미지에 포함됩니다. 코드를 바꾼 후 반영하려면 다음 명령을 사용합니다.

```bash
make k8s-rebuild APP=portal
make check-api
make makemigrations-check
```

API 업무 로직을 바꿨다면 `make test-api`로 테스트합니다. 이 명령은 별도 테스트 DB를 사용합니다.
특정 기능만 검사하거나 migration을 만들 때는 [Portal 개발·검증 안내](../../apps/portal/README.md#개발검증)를 따릅니다.

Web을 호스트에서 개발하거나 검사하려면 Node.js를 준비하고 다음 명령을 실행합니다.

```bash
make install
make web-test
make web-lint
make web-build
```

`make web-dev`는 기본 3000 포트의 화면 개발 서버를 따로 실행합니다. API·로그인 설정은
[Web 실행 안내](../../apps/portal/web/README.md#실행하기)를 확인합니다. 통합 환경의 기본 접속 주소는 계속 8080입니다.
Grafana port-forward도 3000을 사용하므로 동시에 실행할 때 포트 충돌을 확인합니다.

작업을 마칠 때:

```bash
make down
```

이 명령은 로컬 kind 클러스터를 삭제하고 별도 DB 컨테이너를 종료합니다. DB 볼륨과 호스트 파일·생성된 자격증명은 보존합니다.
다음 실행은 `make dev`를 사용합니다. Python 가상환경을 사용했다면 먼저 다시 활성화합니다.
백업 대상은 [데이터 보존 안내](../../local/README.md#로컬-설정과-파일-보존)를 확인합니다.

## 막히는 지점별 확인

| 증상 | 먼저 할 일 |
| --- | --- |
| `No module named yaml` | PyYAML을 설치한 Python 환경이 활성화되어 있는지 확인 |
| `docker info` 실패 | Docker 기동·현재 사용자 접근 권한·WSL 연결 확인 |
| kind·Helm·chart 준비 오류 | 2단계의 도구 확인 후 3단계 실행 |
| 메모리·디스크 검사 실패 | Docker 메모리와 저장소 디스크 여유 확인 |
| `ImagePullBackOff` 또는 MinIO 이미지 다운로드 거부 | [이미지 준비 안내](../../local/README.md#준비와-실행)에 따라 이미지 접근 확인 |
| 포트 사용 중 | 충돌 프로그램을 확인하고 [로컬 설정](../../local/README.md#로컬-설정과-파일-보존)에서 지원하는 포트 변경 |
| kind 설정 변경 메시지 | 포트·마운트 변경 내용을 확인하고 `make down` 후 `make dev` 실행 |
| DB 볼륨은 있는데 자격증명 파일이 없다는 오류 | 백업한 `local/shared/runtime/credentials.env` 복구 |
| Docker Desktop·WSL 재시작 뒤 파일 마운트 오류 | [기존 환경 갱신과 복구](../../local/README.md#기존-환경-갱신과-복구) 순서 확인 |
| 로그인되지만 화면 접근이 거부됨 | [계정별 권한](../../local/README.md#주소와-계정)과 기존 realm 갱신 안내 확인 |

기동 이후 상태가 이상하면 먼저 아래 조회 명령으로 실패한 앱을 찾습니다.

```bash
make k8s-status
kubectl --context kind-tailwind-local get pods -A
kubectl --context kind-tailwind-local -n tailwind-local get events --sort-by=.metadata.creationTimestamp
```

Pod 상세·로그를 읽는 방법은 [Kubernetes 명령어 안내](../reference/kubernetes/README.md#6-상세-상태와-로그-확인하기)를 참고합니다.

## 서버 셋업 순서

서버 설치는 서버별 주소·인증서·DB·이미지·저장소가 필요합니다. 아래 단계에서 담당 문서로 이동합니다.
서버의 선택 checkout에는 루트 `docs/`가 없을 수 있으므로 실제 작업에서는 `deploy/` 안의 안내를 사용합니다.

| 순서 | 할 일 | 상세 안내·완료 기준 |
| --- | --- | --- |
| 1 | 클러스터 준비 또는 기존 상태 확인 | [제어면 준비](../../deploy/shared/docs/kubernetes/01-control-plane.md) → [Worker 추가](../../deploy/shared/docs/kubernetes/03-worker.md), 노드 Ready 확인 |
| 2 | 서버에 필요한 배포 파일 받기 | [선택 checkout](../../deploy/01-SERVER_CHECKOUT.md), 담당 앱·그룹 선택 |
| 3 | 공용 HTTPS 진입점·TLS·VIP 준비 | [Traefik 셋업](../../deploy/shared/docs/kubernetes/02-traefik.md), 진입점 접속 확인 |
| 4 | 앱별 이미지·env·DB·저장소 준비 | [환경설정](../../deploy/shared/docs/configuration/environment.md), 앱별 필수 입력 검사 |
| 5 | 앱별 검사·배포 | [앱별 설치 순서](../../deploy/shared/docs/kubernetes/05-applications.md), Portal은 client·migration 준비 후 배포 |
| 6 | 로그인·기능·운영 확인 | [접속 검증](../../deploy/shared/docs/kubernetes/06-verification.md), 각 앱의 실제 접속과 로그 확인 |

`make server-check APP=<앱> PROFILE=prod`는 배포 파일 검사입니다. 실제 설치와 서비스 접속 확인은 해당 앱의 절차로 이어서 진행합니다.
앱별 문서 목록과 운영 안내는 [서버 배포 문서 홈](../../deploy/README.md)에서 찾습니다.
