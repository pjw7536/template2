# Tailwind 프로젝트 안내

Tailwind는 메일·AI 대화·설비 현황·분석 대시보드 등 업무 기능을 제공하는 Portal과,
이를 실행하는 Airflow·인증·저장소·Kubernetes 배포 구성을 함께 관리하는 저장소입니다.
Portal의 화면은 React, API는 Django로 개발합니다.

처음 참여했다면 **[개발 시작 안내](docs/getting-started/README.md)**에서 환경을 준비하고 로그인까지 확인하세요.
로컬에서는 mock 서버가 사내 외부 서비스를 대신하므로 사내망 없이 개발할 수 있습니다.

## 하려는 일에 맞게 시작하기

| 하려는 일 | 시작 문서 |
| --- | --- |
| 개발 PC에서 처음 실행하기 | [첫 셋업 가이드](docs/getting-started/01-setup.md) |
| 준비된 환경에서 작업하기 | [자주 쓰는 명령](docs/getting-started/02-usage.md) |
| 서비스 관계와 데이터 흐름 이해하기 | [개념 안내](docs/concepts/README.md) |
| Web·API·Airflow 수정하기 | [개발 안내](docs/development/README.md) |
| 기능과 화면 동작 이해하기 | [기능 안내](docs/modules/README.md) |
| API·설정·관리 명령 찾기 | [참고 자료](docs/reference/README.md), [API 명세](docs/api/README.md) |
| 서버에 설치·배포하기 | [서버 배포 안내](deploy/README.md) |
| Portal 없이 플랫폼만 실행하기 | [플랫폼 로컬 실행](local/01-PLATFORM.md) |
| AI 작업 규칙과 검증 방법 찾기 | [에이전트 문서](docs/agent/README.md) |

## 폴더별 역할

```text
apps/    직접 개발하는 Portal·Airflow 소스와 저장소 검사 도구
data/    실행 중 사용하는 데이터와 참고 파일
deploy/  서버 배포 정의·공통 구성·CI 검사 입력
docs/    입문·개념·개발·참고 문서와 기능·API 설명
local/   개발 PC용 설정·mock·실행 도구
```

앱마다 `apps/<app>`은 소스, `deploy/<app>`은 배포, `local/<app>`은 개발 환경을 담당합니다.
Keycloak·MinIO 등 설치형 제품의 설정은 `deploy`와 `local`에서 찾습니다.
전체 명령의 진입점은 루트 `Makefile`이며 Node 의존성은 Web과 검사 도구에서 각각 관리합니다.
폴더를 선택한 뒤 해당 README에서 상세 안내로 이동하면 됩니다.

## 문서 읽는 순서

**[실행하기](docs/getting-started/README.md) → [구조 이해하기](docs/concepts/README.md)
→ [개발하기](docs/development/README.md) → [필요한 값 찾기](docs/reference/README.md)** 순서로 읽습니다.

[문서 홈](docs/README.md)에는 전체 분류와 목적별 안내가 있습니다.
소스 수정 시에는 해당 폴더의 `AGENTS.md`도 확인합니다.
서버에서 필요한 앱만 받는 방법은 [선택 체크아웃 안내](deploy/01-SERVER_CHECKOUT.md)를 따릅니다.
