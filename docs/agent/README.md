# 에이전트 작업 안내

[문서 홈](../README.md)

AI와 개발할 때 적용하는 현재 지침과 검증 방법을 안내합니다.
문서의 기준은 최신 소스와 설정이며, 완료된 작업 계획·결정 이력·점검 기록은 별도로 쌓지 않습니다.

## 작업에 맞는 안내

| 할 일 | 안내 |
| --- | --- |
| 공통 규칙 확인 | [루트 지침](../../AGENTS.md)과 수정할 영역의 `AGENTS.md` |
| Portal 작업 시작·요청문 작성 | [Portal AI 개발 흐름](01-ai-feature-workflow.md) |
| 여러 파일이나 계약을 바꾸는 작업 계획 | [진행 중 계획 작성법](PLANS.md) |
| 작업 품질 평가 | [평가 시나리오](evals/README.md) |
| 커밋 scope 선택 | [커밋 scope](02-git-scopes.md) |

Portal은 [Portal 지침](../../apps/portal/AGENTS.md)에서 시작해
[Web](../../apps/portal/web/AGENTS.md) 또는 [API](../../apps/portal/api/AGENTS.md) 지침을 적용합니다.
서버 배포는 [deploy 지침](../../deploy/AGENTS.md), 개발 PC는 [local 지침](../../local/AGENTS.md)을 따릅니다.

## 현재 문서를 유지하는 방법

- 기능·권한·API·실행 절차는 해당 소유 문서에서 관리합니다.
- 작업 계획은 진행 중인 작업에만 사용하고 완료 후 필요한 설명을 현재 안내에 반영한 뒤 제거합니다.
- 소스 변경 시 관련 설명·색인·검사 기준을 함께 갱신합니다. [문서 작성 안내](../development/04-documentation.md)를 따릅니다.
- 실제 서비스 동작과 정적 검사 결과를 구분하며, 서버 상태는 대상 환경에서 조회해 확인합니다.
