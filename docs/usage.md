# 사용방법

외부 PC의 기본 `make dev`는 전체 앱을 kind에서 실행하고 DB만 별도 Docker로 구동합니다.
설정과 검증은 [로컬 실행 안내](../local/README.md)를 따릅니다.
사내 서버는 Kubernetes로만 배포합니다.

## 공통 실행 명령

| 목적 | 명령 |
| --- | --- |
| Node 의존성 설치 | `make install` |
| Web 개발·검증 | `make web-dev`, `make web-test web-lint web-build` |
| 저장소 감사·회귀 검사 | `make audit`, `make tooling-test` |
| 전체 로컬 Kubernetes | `make dev` / `make down` |
| 실행 설정 검사 | `make compose-check` |
| CI API 이미지·테스트 | `make build-ci-api test-ci-api` |
| CI 시스템·migration 검사 | `make check-ci-api makemigrations-ci-check` |


## 먼저 고르는 것

실행할 때는 환경을 먼저 고릅니다.

| 환경 | 명령 | 용도 | dependency source |
| --- | --- | --- | --- |
| `dev` | `make dev` | 로컬 개발 전용 | public registry/package source |
| 사내 서버 | [Kubernetes 배포](../deploy/README.md) | 사내 배포 | internal mirror |

기억할 규칙은 하나입니다.

```text
dev = local + public
사내 서버 = Kubernetes + internal mirror
```

`dev`는 로컬 PC에서만 쓰는 개발 환경입니다.
`repository.samsungds.net` 같은 내부 mirror 주소를 사용하지 않습니다.

사내 Kubernetes의 이미지는 내부망 기준으로 준비합니다.
Docker image, npm, pip, apt, Alpine package source를 내부 mirror로 고정합니다.

## 사내 서버

사내 서버는 Kubernetes로만 배포합니다. [서버 선택 체크아웃](../deploy/SERVER_CHECKOUT.md) 후
해당 앱을 검사하고 [배포 안내](../deploy/README.md)를 따릅니다.

```bash
make server-check APP=keycloak
make server-check APP=portal
```

Keycloak·Portal·Airflow·FTP·Monitoring은 공통 Kubernetes 정의를 사용합니다.
앱별 지원 상태는 `deploy/shared/apps.json`과 `make server-check APP=all`로 확인합니다.

## 로컬 종료

```bash
make down
```

`make down`은 로컬 kind와 새 DB 컨테이너를 종료하고 영속 데이터를 보존합니다.

## 검증 명령

백엔드 검증은 개발 API 컨테이너 기준으로 실행합니다.

```bash
make check-api
make test-api
make makemigrations-check
```

프론트엔드 검증은 Makefile을 통해 Web 프로젝트의 npm 명령을 실행합니다.

```bash
make web-lint
make web-build
```

## 파일 구조

실행 진입점은 루트 Makefile입니다. Kubernetes 공통 정의는 `deploy/<app>`, 로컬 차이는 `local/<app>`에 있습니다.
Compose는 다음 세 구성만 유지합니다.

- `local/shared/compose/k8s-db.yml`: 로컬 Kubernetes용 외부 PostgreSQL
- `local/shared/compose/k8s-check.yml`: 같은 이미지·DB를 쓰는 일회성 API 검사
- `deploy/portal/compose/test.yml`: 독립 CI API 검사

## mirror 참고

환경별 dependency source 정책은 `docs/configuration.md`에 있습니다.
전체 proxy mirror 목록은 `docs/integrations/proxy-mirrors.md`에 있습니다.
