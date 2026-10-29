# Agent Evals

## 목적

같은 작업과 성공 기준으로 에이전트의 결과를 비교합니다.
변경 영역에 맞는 시나리오를 골라 사용합니다.

## 사용 방법

1. 선택한 시나리오의 `Task`(작업 요청)를 에이전트에게 그대로 전달합니다.
2. 수정·검증이 끝나면 `Success Criteria`(성공 기준)를 확인합니다.
3. 실패하거나 결과가 일정하지 않은 항목은 `Regression Notes`(재발 방지 기록)에 남깁니다.
4. 같은 실패가 반복되면 관련 `AGENTS.md`, 스킬 또는 검사 스크립트에 개선사항을 반영합니다.

## 평가 시나리오

| 확인할 내용 | 시나리오 |
| --- | --- |
| UI 상태·디자인 토큰·접근성 | [프론트엔드 UI 일관성](01-frontend-ui-consistency.md) |
| feature 간 import·공개 진입점·폴더 구조 | [프론트엔드 기능 경계](02-frontend-boundary.md) |
| Django의 조회·변경·HTTP 처리 책임 분리 | [Service·Selector 경계](03-django-service-selector.md) |
| 외부 연동 변경 시 로컬 mock·환경 설정 동기화 | [외부 PC 개발 계약](04-offsite-contract-sync.md) |
| Observer의 프론트·백엔드 연동 변경 | [Observer 리팩터링 조율](05-observer-refactor-coordination.md) |
| UI·API·인증 작업의 탐색 범위와 지침 분량 | [Portal 작업 범위](06-portal-agent-scope.md) |

## 작성 규칙

- 실제 프로젝트에서 자주 발생하는 작업만 추가합니다.
- 성공 기준은 사람이 판정할 수 있어야 합니다.
- 가능한 경우 실행 명령을 포함합니다.
- 에이전트가 수정하면 안 되는 파일과 범위를 명시합니다.

현재 작업 방식은 [에이전트 문서 안내](../README.md)를 참고합니다.
