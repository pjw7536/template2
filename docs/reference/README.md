# 참고 자료

[문서 홈](../README.md) · [개념 이해하기](../concepts/README.md) · [개발하기](../development/README.md)

설정 이름·실제 코드 경로·명령을 확인할 때 사용하는 자료입니다.
처음 실행하는 순서는 [셋업 가이드](../getting-started/01-setup.md), 평소 작업 명령은 [일상 개발 안내](../getting-started/02-usage.md)를 따릅니다.

## 필요한 정보 찾기

| 찾는 정보 | 문서 | 사용 방법 |
| --- | --- | --- |
| 환경변수와 파일별 역할 | [환경 설정](01-configuration.md) | 수정할 env의 소유 영역을 먼저 확인 |
| 실제 route·모델·명령 이름 | [구현 색인](02-inventory.md) | 기능 이름으로 검색해 실제 파일과 연결 |
| API 검사·Django 관리 명령 | [관리·검사 명령](03-operations.md) | 실행 전제·옵션·데이터 변경 여부 확인 |
| 요청·응답·인증·오류 | [API 명세](../api/README.md) | 공통 규칙을 읽은 뒤 해당 API 선택 |
| Kubernetes 상태·로그 조회 | [Kubernetes 명령어](kubernetes/README.md) | 실패한 Pod·이벤트·로그를 확인 |
| 패키지 프록시·미러 매핑 | [미러 참고표](integrations/proxy-mirrors.md) | 환경별 사용 정책을 확인한 뒤 이름 조회 |
| 배포·렌더링 검사 종류 | [검사 도구 안내](../../apps/tooling/README.md) | 변경 영역에 맞는 검사 선택 |

## 설정과 명령의 원본

공통 실행 명령의 정의는 루트 `Makefile`입니다. 이곳에서는 명령의 목적과 사용 조건을 설명합니다.
로컬 주소·계정·포트·데이터 보존은 [local 안내](../../local/README.md),
서버별 입력과 배포 절차는 [deploy 안내](../../deploy/README.md)를 기준으로 확인합니다.
샘플 입력과 부속 자료는 [예제 안내](../examples/README.md)에서 찾습니다.
