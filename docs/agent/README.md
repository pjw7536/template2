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

## Codex 설정과 스킬

- 개발 PC에서 쓰는 공유 작업 절차의 원본은 `.codex/skills/<name>/SKILL.md`입니다. 현재 로컬 CLI는 이 경로의 스킬을 읽습니다. 사내 운영 스킬은 아래 [사내 운영 agent](#사내-운영-agentopencode) 절을 따릅니다. 같은 스킬을 다른 탐색 경로에 복사해 중복 등록하지 않습니다.
- `.codex/config.toml`은 Git에서 제외한 로컬 실행 설정입니다. 모델·추론 강도·권한·프로젝트 신뢰는 사용하는 환경에서 관리하며, 스킬 최적화를 이유로 일괄 변경하지 않습니다.
- `.codex/auth.json`, history·sessions·log·tmp는 로컬 자격증명·실행 데이터입니다. 설정 공유나 리뷰를 위해 내용을 복사하거나 Git에 추가하지 않습니다.
- 스킬은 현재 작업에 필요한 것만 읽습니다. 요청 분류는 필요한 결정만 확인하고, 파일 수정은 영역별 지침을 참조하며, 레이아웃 예시는 해당 패턴이 필요할 때 읽습니다.
- 프론트엔드는 공식 `shadcn`이 컴포넌트 API·조합, `product-ui-design-system`이 시각·상태, `compose-frontend-layout`이 높이·스크롤을 담당합니다. 기존 컴포넌트 API와 Web 지침을 우선합니다.
- 공식 shadcn 스킬은 [설치 원본·갱신 안내](../../.codex/skills/shadcn/README.md)에 따라 원문과 라이선스를 유지합니다.
- Claude Code는 `.claude/skills/<name>`의 상대 경로 symlink(`../../.codex/skills/<name>`)로 같은 원본을 읽습니다. 스킬을 추가·삭제·이름 변경할 때 링크도 같은 커밋에서 맞추고, 원본이 커밋되지 않은 스킬의 링크는 먼저 커밋하지 않습니다. Codex 전용 `.system/` 스킬은 연결하지 않으며, `.claude/`의 다른 파일은 Git에서 제외한 로컬 설정입니다.
- 링크 정합성은 `for d in .codex/skills/*/; do test -L ".claude/skills/$(basename "$d")" || echo "누락: $d"; done; for l in .claude/skills/*; do test -f "$l/SKILL.md" || echo "깨짐: $l"; done`로 확인합니다.
- `.specify` 실행 스크립트가 없는 Spec Kit 프롬프트는 `.codex/prompts-disabled/spec-kit/`에 원문을 보관합니다. 사용하려면 필수 스크립트와 현재 저장소의 폴더·계획 규칙을 먼저 맞춘 뒤 필요한 프롬프트만 `.codex/prompts/`로 복원합니다.

공식 문서는 [스킬의 선택·탐색](https://developers.openai.com/codex/skills/)과 [설정 우선순위](https://developers.openai.com/codex/config-basic/)에서 확인합니다. Claude Code의 지침·스킬 탐색은 [Claude Code 메모리](https://docs.claude.com/en/docs/claude-code/memory)와 [스킬](https://docs.claude.com/en/docs/claude-code/skills) 문서를 따릅니다. `.agents/skills`가 필요한 다른 클라이언트에서는 기존 원본을 가리키는 symlink를 검토하되 실제 스킬 목록에서 중복이 없는지 확인합니다. 모델·권한의 실제 적용 상태는 설정 파일만으로 단정하지 않고 사용하는 클라이언트에서 확인합니다.

### 사내 운영 agent(opencode)

사내 CP1에서는 opencode의 `ops` agent가 배포·운영만 담당합니다. 정의는 `.opencode/agents/ops.md`이며 역할·권한 규칙은 [운영 agent 지침](../../deploy/AGENTS.md#사내-운영-agent)이 원본입니다.

- 운영 스킬의 원본은 `.opencode/skills/<name>/SKILL.md`입니다. 사내에서는 Claude Code·Codex를 쓰지 않으므로 `.codex/skills`·`.claude/skills`와 연결하지 않고, 개발용 스킬은 이 폴더에 복사하지 않습니다.
- opencode는 `AGENTS.md`를 루트부터 읽고 호환 경로인 `.claude/skills`의 개발용 스킬도 탐색합니다. `ops` agent의 `skill` 권한이 운영 스킬 외에는 거부합니다.
- `ops` agent는 `deploy-drift-check`, `server-deploy-routine` 스킬만 사용할 수 있으며 저장소 수정·commit·push·Secret 조회를 막거나 승인받습니다.
- Worker(khinfow01)에서는 점검 전용 `ops-check` agent(`.opencode/agents/ops-check.md`)를 씁니다. `deploy-drift-check`만 사용하며 클러스터 변경 명령은 승인으로도 실행하지 않습니다. 준비는 [Worker에서 점검](../../deploy/shared/docs/operations/04-drift.md#worker에서-점검)을 따릅니다.
- 사내 opencode 2.0의 V2 `permissions` 형식(`shell`·`subagent` action, 마지막 일치 규칙 우선, `*`는 `/` 포함)을 사용합니다. 1.x의 `permission`·`bash`·`task` 키를 쓰지 않습니다.
- 저장소 밖 env·인증서·kubeconfig 읽기와 하위 agent 실행을 거부합니다. 하위 agent는 부모 권한을 물려받지 않기 때문입니다. 프로젝트·전역 `opencode.json`의 규칙은 agent 규칙 앞에 적용되므로 사내 설정이 이를 덮지 않는지 확인합니다.
- `.opencode/`는 `agents/`·`skills/`만 Git으로 관리합니다.

### 브라우저 검증과 UI 리뷰

| 스킬 | 적용할 작업 | 설치 원본 |
| --- | --- | --- |
| [playwright](../../.codex/skills/playwright/SKILL.md) | 실제 브라우저의 화면·입력·스크롤·사용 흐름 확인 | [OpenAI 원본](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/playwright) |
| [web-design-guidelines](../../.codex/skills/web-design-guidelines/SKILL.md) | 요청된 UI·접근성·UX 리뷰 | [Vercel 원본](https://github.com/vercel-labs/agent-skills/tree/1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62/skills/web-design-guidelines) |

원문과 제공된 라이선스·NOTICE를 함께 유지합니다. 갱신 시 `skill-installer`로 검토할 commit을 임시 경로에 설치한 뒤 차이를 확인하고, 해당 원본 링크도 현재 commit으로 갱신합니다.
적용 조건과 디자인 우선순위는 [Web 지침](../../apps/portal/web/AGENTS.md#브라우저-검증과-ui-리뷰)을 따릅니다. 실제 브라우저 기동에는 별도 브라우저 런타임이 필요하며 스킬 설치·CLI 도움말 확인만으로 Portal UI 검증을 완료한 것으로 보지 않습니다.

프로젝트 전용 설치이므로 원문의 전역 `CODEX_HOME` 예시 대신 다음 wrapper를 사용합니다. `apps/portal/web`에서 시작해 Git 제외 경로 안에서 실행하면 자동 snapshot·trace도 산출물 영역에 남습니다.

```bash
portal_pwcli="$(git rev-parse --show-toplevel)/.codex/skills/playwright/scripts/playwright_cli.sh"
mkdir -p test-results/playwright
cd test-results/playwright
bash "$portal_pwcli" --help
```

- `open`에는 실제 검증 대상 URL을 사용하고 루트 `output/` 폴더를 만들지 않습니다. 작업별 이름의 세션을 사용하며 완료 후 해당 세션만 닫습니다.
- 테스트 작성 요청이 없으면 검증용 E2E 테스트나 앱 의존성을 추가하지 않습니다. 브라우저 확인은 기존 단위 테스트·정적 감사와 목적을 구분합니다.
- UI 리뷰는 스킬이 지정한 원본 가이드를 현재 제공된 웹 조회 도구로 읽습니다. `WebFetch`라는 특정 도구명에 의존하지 않습니다.
- 최신 가이드·브라우저 실행을 확인할 수 없으면 제약을 보고하고, 확인하지 않은 동작을 통과로 표시하지 않습니다.

## 현재 문서를 유지하는 방법

- 기능·권한·API·실행 절차는 해당 소유 문서에서 관리합니다.
- 작업 계획은 진행 중인 작업에만 사용하고 완료 후 필요한 설명을 현재 안내에 반영한 뒤 제거합니다.
- 소스 변경 시 관련 설명·색인·검사 기준을 함께 갱신합니다. [문서 작성 안내](../development/04-documentation.md)를 따릅니다.
- 실제 서비스 동작과 정적 검사 결과를 구분하며, 서버 상태는 대상 환경에서 조회해 확인합니다.
