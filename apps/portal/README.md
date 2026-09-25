# Portal

React Web과 Django API로 구성된 업무 포털입니다. 업무 기능은 기존 Django 도메인과 React feature 내부에서 관리합니다.

## 파일 위치

| 작업 | 경로 |
| --- | --- |
| 소스·이미지 빌드 | [api](api/README.md), [web](web/README.md), 각 폴더의 Dockerfile |
| 서버 배포·입력 | [deploy/portal](../../deploy/portal/README.md) |
| 개발 env·실행 | [local/portal](../../local/README.md) |
| 앱 목록·서버 checkout | [앱 목록](../../deploy/shared/apps.json), [선택 checkout](../../deploy/SERVER_CHECKOUT.md) |

## AI 개발 시작점

에디터·에이전트 작업 폴더를 `apps/portal`로 열고 [Portal 지침](AGENTS.md)을 적용합니다.
Web 전용 작업은 `web`, API 전용 작업은 `api`에서 시작해도 됩니다. 각 수정 영역의 하위 지침도 확인합니다.
대상 feature부터 찾고, 필요한 공개 facade·공통 코드·외부 계약 순서로 범위를 넓힙니다.

| 작업 | 먼저 확인할 위치 | 범위를 넓히는 조건 |
| --- | --- | --- |
| 화면·상태·스타일 | `web/src/features/<feature>`와 [Web 지침](web/AGENTS.md) | 공통 UI·전역 라우팅에 실제 의존할 때 |
| 업무 API·모델 | `api/api/<feature>`와 [API 지침](api/AGENTS.md) | 다른 도메인 공개 facade·공통 설정에 영향이 있을 때 |
| 외부 인증·RAG·메일 | 해당 API 호출부 | 계약·env·mock 변경이면 [local 지침](../../local/AGENTS.md) |
| 이미지·운영 env·파일 마운트 | 해당 Portal 계약 | [deploy 지침](../../deploy/AGENTS.md)과 관련 Portal 설정 |

스킬·문서는 작업에 해당하는 항목만 읽습니다. 재현용 프롬프트와 탐색 평가 방법은
[AI 작업 안내](../../docs/agent/ai-feature-workflow.md)에 있습니다.

## 개발·검증

아래 명령은 저장소 루트 기준입니다. 이 폴더에서는 `make -C ../.. <target>`,
`web`·`api`에서는 `make -C ../../.. <target>`으로 같은 루트 Makefile을 호출합니다.

| 목적 | 명령 |
| --- | --- |
| 의존성 설치 | `make install` |
| 전체 로컬 환경 준비·기동 | `make dev` — Portal·Keycloak·Airflow·FTP·MinIO·mock·모니터링을 실행 |
| Web 개발 서버 | `make web-dev` |
| 준비된 환경의 Portal 이미지 갱신 | `make k8s-rebuild APP=portal` |
| Web 테스트·린트·빌드 | `make web-test`, `make web-lint`, `make web-build` |
| UI 또는 Web 경계 검사 | `make audit-ui`, `make audit-web-boundary` 중 변경에 해당하는 검사 |
| API 테스트·설정·migration 누락 검사 | `make test-api`, `make check-api`, `make makemigrations-check` |
| API 경계 검사 | `make audit-api-boundary` |
| Portal 서버 배포 설정 검사 | `make server-check APP=portal PROFILE=prod` |

변경 영역에 필요한 검사를 선택합니다. 전체 `make audit`은 저장소 전반의 변경을 검증할 때 사용합니다.
로컬 환경 준비는 [local 실행 안내](../../local/README.md)를 따릅니다. 작업 범위를 Portal로 좁혀도 전체 기동 방식은 동일합니다.

Django 검사는 준비된 이미지·DB를 사용하는 일회성 Compose `api`에서 실행합니다.
`make test-api`는 표준 test env와 별도 테스트 DB를 사용하고, 설정·migration 검사는 합성된 로컬 env를 사용합니다.
이미지에 소스가 포함되므로 API 수정 후 이미지를 갱신해야 변경분이 검사됩니다.
특정 feature 검사·migration 생성 방법은 [테스트 스킬](../../.codex/skills/django-test-migration-flow/SKILL.md)을 참조합니다.

## 빌드·배포

빌드 context는 `apps/portal/api`, `apps/portal/web`입니다. 이미지 이름·빌드 인자·운영 env 계약은 유지합니다.
준비된 이미지 배포는 `deploy/portal`과 공통 배포 도구만 필요합니다.
서버에서 소스를 빌드하려면 `bash deploy/shared/scripts/checkout-server.sh portal --with-source`를 사용합니다.

## 서비스 의존성

API는 PostgreSQL·MinIO와 인증 서비스를 사용합니다. 개발 환경은 `local/adfs_dummy`로 외부계를 대체합니다.
Airflow는 Portal의 공개 API를 호출하며 Portal 내부 Python 코드를 직접 가져오지 않습니다.
전체 계약은 [아키텍처](../../docs/architecture.md)와 [환경설정](../../docs/configuration.md)에 있습니다.

## 경로 이전 후 준비

루트에서 `make install`을 실행하면 Web과 도구의 독립 lockfile로 각각 의존성을 설치합니다.
기존 Python 가상환경·생성 산출물은 새 경로에서 재생성합니다. API 실행·검증은 Compose 컨테이너를 사용합니다.
실제 env 내용과 DB·파일 데이터 경로는 유지합니다.

## 참조 파일로 사용자 사전 등록

사용자의 등록 소속과 접근 권한은 별도로 관리합니다. SDWT 입력은 관리자 일괄
등록 시에만 받으며 로그인 시 소속 입력·재확인을 요구하지 않습니다. 현재 소속을
접근 범위에 자동으로 포함하지 않습니다. 기존 소속에서 파생되던 권한은 account
migration `0007`이 명시적 역할·앱별 소속 grant로 보존합니다. migration은 기존
권한을 자동 회수하지 않으며 역방향 실행도 이관한 권한을 삭제하지 않습니다.

참조테이블을 UTF-8 CSV로 내보냅니다. 필수 헤더는 `epid,sabun,knox_id,user_sdwt_prod`,
선택 헤더는 `username,email,department`입니다. EPID는 현재 모델의 `avatarid`에
저장하고 로그인은 기존 사번(`sabun`)으로 계정을 연결합니다. `department`는 인증
identity 부서이며 SDWT에서 자동 복사하지 않습니다. 기존 부서 접근 정책은 유지됩니다.

SDWT는 기존 활성 조직 목록(`Affiliation`)에 있어야 하며 line은 그 조직에서
조회합니다. SDWT가 없는 사용자는 CSV의 해당 칸을 비웁니다. 신규 계정에는 비밀번호나
명시적 접근 권한을 부여하지 않습니다. 앱 접근과 데이터 범위는 권한 관리 화면에서
별도로 부여합니다. 동일한 EPID·사번·Knox ID의 기존 계정은 건너뛰며, 일부 식별자만
충돌하면 전체 등록을 취소합니다. 재실행으로 기존 사용자 소속을 덮어쓰지 않습니다.

개발 환경의 DB와 최신 migration을 준비한 뒤 저장소 루트에서 실행합니다.

```bash
# 전체 파일 검증: 저장하지 않습니다.
make register-reference-users REFERENCE_USERS_CSV=/absolute/path/users.csv
# 검증한 파일을 등록합니다.
make register-reference-users REFERENCE_USERS_CSV=/absolute/path/users.csv REGISTER_REFERENCE_USERS_APPLY=1
```

서버에서는 기존 API 이미지에 포함된 `manage.py register_reference_users` 명령에
`/data/account` 아래 읽기 전용으로 마운트한 CSV 경로를 전달합니다. 기본은 dry-run,
`--apply`가 있을 때만 저장합니다. 실제 참조 CSV·인증정보는 저장소에 커밋하지 않습니다.
