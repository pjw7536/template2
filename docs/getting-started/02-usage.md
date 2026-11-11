# 개발 작업 흐름

[문서 홈](../README.md) · [처음 시작하기](01-setup.md) · [로컬 실행](../../local/README.md)

로컬 환경을 [로컬 실행](../../local/README.md)으로 준비한 뒤 코드를 수정하고 검사하는 순서입니다.
모든 명령은 저장소 루트에서 실행합니다. 기동·종료·주소·계정·문제 해결은 로컬 실행 문서가 원본입니다.

## 수정한 소스 반영

소스는 개발 이미지에 포함되므로 수정 후 해당 앱 이미지를 갱신합니다.

| 변경 영역 | 명령 |
| --- | --- |
| Portal API·Web | `make k8s-rebuild APP=portal` |
| 외부 서비스 mock | `make k8s-rebuild APP=mock` |
| Airflow DAG·이미지 | `make k8s-rebuild APP=airflow` |
| 그 외 앱 설정 | [로컬 실행 명령](../../local/README.md#준비와-실행)의 해당 APP |

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

## 독립 CI 검사

로컬 전체 환경과 별개로 테스트용 API 이미지를 빌드해 검사하는 명령입니다.

```bash
make build-ci-api
make test-ci-api
make check-ci-api
make makemigrations-ci-check
```

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
