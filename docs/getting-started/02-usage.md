# 셋업 후 자주 쓰는 명령

[문서 홈](../README.md) · [첫 셋업 가이드](01-setup.md) · [로컬 설정·계정](../../local/README.md)

이 문서는 준비를 마친 개발 환경에서 사용하는 명령을 정리합니다.
모든 명령은 저장소 루트에서 실행합니다. 서버 설치는 [배포 안내](../../deploy/README.md)를 따릅니다.

## 시작·확인·종료

| 할 일 | 명령 | 확인할 내용 |
| --- | --- | --- |
| 전체 로컬 앱 기동 | `make dev` | Portal·Keycloak·Airflow 등 전체 앱 준비 후 주소 표시 |
| 상태와 접속 주소 조회 | `make k8s-status` | 앱별 Pod·PVC와 주소 확인 |
| 실행 준비 상태 확인 | `make k8s-health` | Pod 준비 상태와 공개 진입점 응답 확인 |
| 대표 기능 통합 검사 | `make k8s-smoke` | 로그인·채팅·메일·적재·Airflow 등 확인, 테스트 이력 생성 |
| Portal 없이 플랫폼 기동 | `make dev-platform` | [플랫폼 안내](../../local/01-PLATFORM.md)에 따라 접속·검사 |
| 종료 | `make down` | kind 클러스터 삭제·DB 컨테이너 종료, DB 볼륨과 호스트 데이터 보존 |

전체 앱은 kind에서, PostgreSQL은 별도 Docker 컨테이너에서 실행합니다.
다음 기동도 `make dev`를 사용합니다. 포트나 마운트를 바꾸려면 [로컬 설정과 파일 보존](../../local/README.md#로컬-설정과-파일-보존)을 먼저 확인합니다.

## 소스 수정 반영

소스는 개발 이미지에 포함됩니다. Portal·API·Airflow·mock 수정 후에는 해당 이미지를 갱신합니다.

| 변경 영역 | 명령 |
| --- | --- |
| Portal API·Web | `make k8s-rebuild APP=portal` |
| 외부 서비스 mock | `make k8s-rebuild APP=mock` |
| Airflow DAG·이미지 | `make k8s-rebuild APP=airflow` |
| 그 외 앱 설정 | [로컬 실행 명령](../../local/README.md#준비와-실행)의 해당 APP 사용 |

`make web-dev`는 Web 화면만 기본 3000 포트에서 따로 실행합니다.
통합 환경의 8080 주소와 API·로그인 연결 차이는 [Web 실행 안내](../../apps/portal/web/README.md#실행하기)를 참고합니다.

## 변경 영역별 검사

필요한 검사를 골라 실행합니다. 호스트의 Node 의존성은 처음에 `make install`로 설치합니다.
Web과 검사 도구는 각자의 lockfile과 `node_modules`를 사용합니다.

| 변경 영역 | 명령 | 실행 전제 |
| --- | --- | --- |
| Web | `make web-test`, `make web-lint`, `make web-build` | Node.js·의존성 준비 |
| API | `make check-api`, `make test-api`, `make makemigrations-check` | `make dev`로 이미지·DB 준비, 소스 변경 후 Portal 이미지 갱신 |
| 문서·API 색인 | `make audit-docs` | 현재 문서와 실제 경로 대조 |
| 저장소 구조·경계·UI 전반 | `make audit` | [감사 도구 안내](../../apps/tooling/README.md) 확인 |
| 배포 도구 회귀 | `make tooling-test` | tooling 의존성과 해당 검사 도구 준비 |
| 로컬 Kubernetes 정의 | `make k8s-render-local` | kubectl 준비, 클러스터 적용 없음 |
| 로컬 도구·자원·배포 입력 | `make k8s-check` | kind·Helm·chart·Docker 준비, 클러스터 적용 없음 |
| 보조 Compose 정의 | `make compose-check` | Docker Compose 준비 |

API 검사는 일회성 Compose `api` 컨테이너에서 실행합니다.
`make test-api`는 표준 test env와 별도 테스트 DB를, 설정·migration 누락 검사는 합성된 로컬 env를 사용합니다.
특정 기능 테스트·migration 생성과 업무 관리 명령은 [Portal 개발 안내](../../apps/portal/README.md#개발검증),
[운영·개발 명령](../reference/03-operations.md)을 참고합니다.

## 관리 화면 연결

| 화면 | 명령 | 기본 주소 |
| --- | --- | --- |
| Grafana | `make k8s-grafana` | http://localhost:3000 |
| Prometheus | `make k8s-prometheus` | http://localhost:9090 |
| Headlamp 조회 UI | `make k8s-ui` | http://localhost:4466 |

명령이 실행 중인 터미널을 유지하고 종료할 때 `Ctrl+C`를 누릅니다.
Grafana와 `make web-dev`는 기본 3000 포트를 공유합니다.
플랫폼 전용 Headlamp는 [별도 HTTPS 접속 안내](../../local/01-PLATFORM.md#접속과-계정)를 따릅니다.

## 독립 CI 검사

로컬 전체 환경과 별개로 테스트용 API 이미지를 빌드해 검사하는 명령입니다.

```bash
make build-ci-api
make test-ci-api
make check-ci-api
make makemigrations-ci-check
```

## 서버 작업

서버는 [선택 checkout](../../deploy/01-SERVER_CHECKOUT.md) 후 앱별로 검사·배포합니다.
로컬의 `make dev`를 서버 설치 명령으로 사용하지 않습니다.

```bash
make server-check APP=keycloak PROFILE=prod
make server-check APP=portal PROFILE=prod
```

`server-check`는 배포 파일을 검사하며 클러스터에 앱을 설치하지 않습니다.
앱별 실제 입력·기동·검증은 [서버 배포 안내](../../deploy/README.md)를 따릅니다.
로컬은 공개 이미지·패키지 저장소를, 서버는 내부 미러를 사용합니다.
세부 정책은 [환경 설정](../reference/01-configuration.md#환경별-dependency-source-정책)과 [미러 참고표](../reference/integrations/proxy-mirrors.md)에 있습니다.

## 실행 파일 위치

| 위치 | 역할 |
| --- | --- |
| `Makefile` | 모든 공통 실행 명령의 진입점 |
| `apps/portal`, `apps/airflow` | 직접 개발하는 앱 소스 |
| `apps/tooling` | 저장소 검사 도구 |
| `deploy/<app>` | 서버 배포·공통 정의 |
| `local/<app>` | 개발 PC의 차이와 mock |
| `local/shared/k8s` | 로컬 Kustomize 집계 |
| `local/shared/compose/k8s-db.yml` | 로컬 Kubernetes용 외부 PostgreSQL |
| `local/shared/compose/k8s-check.yml` | 같은 이미지·DB를 쓰는 일회성 API 검사 |
| `deploy/portal/compose/test.yml` | 독립 CI API 검사 |
