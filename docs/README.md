# 프로젝트 문서 홈

이 문서는 처음 참여하는 개발자가 실행 방법과 구조를 이해하고, 필요한 개발·참고 문서를 찾는 출발점입니다.
처음 실행한다면 **[개발 시작 안내](getting-started/README.md)**에서 시작하세요.

## 읽는 목적에 따라 선택하기

| 순서 | 안내 | 여기서 알 수 있는 것 |
| --- | --- | --- |
| 1 | [시작하기](getting-started/README.md) | 준비 도구, 첫 실행·로그인, 일상 개발 명령 |
| 2 | [개념 이해하기](concepts/README.md) | 서비스 관계, 요청·데이터 흐름, 저장소와 외부 연동 |
| 3 | [개발하기](development/README.md) | 수정할 소스 찾기, Web·API 개발과 검증, 문서 작성 |
| 4 | [참고 자료 찾기](reference/README.md) | 설정 이름, 실제 경로, 관리 명령, Kubernetes 조회 방법 |

개별 기능은 [기능 안내](modules/README.md), 요청·응답은 [API 명세](api/README.md)에서 찾습니다.
예를 들어 로그인 권한을 이해하려면 Auth·Account 기능 설명을, 클라이언트를 작성하려면 해당 API 명세를 읽습니다.

## 지금 필요한 안내

| 할 일 | 바로가기 |
| --- | --- |
| 처음 기동하고 로그인하기 | [첫 셋업](getting-started/01-setup.md) |
| 코드 변경을 실행 환경에 반영하기 | [일상 개발 명령](getting-started/02-usage.md#소스-수정-반영) |
| 화면을 수정하기 | [Web 개발](development/01-frontend.md) |
| API와 업무 로직을 수정하기 | [API 개발](development/02-backend.md) |
| 포트·계정·로컬 데이터 위치 확인하기 | [로컬 실행 상세](../local/README.md) |
| 로그인 또는 접근 거부 원인 찾기 | [셋업 문제 해결](getting-started/01-setup.md#막히는-지점별-확인), [Auth](modules/01-auth.md), [Account](modules/02-account.md) |
| 서버에 설치·배포하기 | [서버 배포 안내](../deploy/README.md) |
| AI 작업 규칙·검증 방법 찾기 | [에이전트 작업 안내](agent/README.md) |

## 문서 폴더 지도

```text
docs/
├── getting-started/  처음 실행하는 절차와 일상 작업
├── concepts/         전체 구조·데이터·연동 개념과 용어
├── development/      소스 수정·검증·migration·문서 작성
├── reference/        설정·경로·명령·미러·Kubernetes 참고
├── modules/          사용자 기능과 업무 흐름
├── api/              API 호출 계약
├── examples/         샘플 입력·HTML·이미지 자료
└── agent/            에이전트 지침·평가·진행 중 계획
```

## 상세 문서의 소유 위치

공통 개념과 개발 설명은 이 폴더에 둡니다. 소스 실행·배포·로컬 설정의 상세 절차는
해당 파일을 소유한 영역에서 관리합니다.

| 영역 | 시작점 |
| --- | --- |
| Portal 소스 | [Portal 개발](../apps/portal/README.md) → [Web](../apps/portal/web/README.md) / [API](../apps/portal/api/README.md) |
| Airflow 소스 | [DAG·이미지 개발](../apps/airflow/README.md) |
| 개발 PC | [로컬 실행](../local/README.md), [플랫폼만 실행](../local/01-PLATFORM.md) |
| 서버 배포 | [배포 문서 홈](../deploy/README.md) |
| 저장소 검사 | [검사 도구](../apps/tooling/README.md) |

문서는 최신 소스와 설정을 기준으로 유지합니다. 완료된 작업 기록은 남기지 않습니다.
문서를 추가하거나 옮길 때는 [문서 작성 안내](development/04-documentation.md)를 따릅니다.
