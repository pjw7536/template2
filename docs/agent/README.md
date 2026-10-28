# 에이전트 문서 안내

AI와 함께 개발할 때 필요한 작업 규칙과 과거 변경 근거를 모았습니다.
앱 실행·배포 방법은 [전체 문서 안내](../README.md)에서 찾을 수 있습니다.

## 목적에 맞게 찾기

| 하고 싶은 일 | 읽을 문서 |
| --- | --- |
| 작업에 적용되는 규칙 확인 | [공통 지침](../../AGENTS.md)과 수정할 폴더의 `AGENTS.md` |
| Portal 작업을 시작하거나 요청문 작성 | [Portal AI 개발 흐름](ai-feature-workflow.md) |
| 여러 파일이나 계약을 바꾸는 작업 계획 작성 | [ExecPlan 작성 규칙](PLANS.md) |
| 이전 작업의 배경·검증 결과 확인 | [실행 계획의 주제별 목록](plans/README.md) |
| 설계나 운영 방침이 바뀐 이유 확인 | [결정 이력](decisions.md) |
| 에이전트 작업 품질을 반복 평가 | [평가 시나리오 안내](evals/README.md) |
| 커밋·PR 마무리 시 scope 선택 | [커밋 scope 목록](git-scopes.md) |

Portal을 수정한다면 [Portal 지침](../../apps/portal/AGENTS.md)에서 시작해
[Web](../../apps/portal/web/AGENTS.md) 또는 [API](../../apps/portal/api/AGENTS.md) 지침을 확인합니다.
서버 배포는 [배포 지침](../../deploy/AGENTS.md), 외부 PC 환경은 [개발 환경 지침](../../local/AGENTS.md)을 따릅니다.
작업과 관련 있는 문서만 필요한 만큼 읽습니다.

## 현재 안내와 작업 기록의 차이

- `AGENTS.md`와 스킬은 현재 작업에 적용할 규칙입니다.
- `ai-feature-workflow.md`, `PLANS.md`, `evals/`는 작업·계획·평가 방법을 설명합니다.
- `plans/`는 작업 당시의 목표, 실행 단계, 검증 결과를 보존합니다. 체크박스가 남아 있어도 현재 진행 중인 작업이라고 단정하지 않습니다.
- `decisions.md`에는 이후 다른 결정으로 대체된 내용도 남아 있습니다. 해당 주제의 날짜와 후속 기록을 함께 확인합니다.

과거 기록의 경로·명령·서버 상태는 지금과 다를 수 있습니다.
실제로 실행할 때는 해당 앱의 현재 README와 소스·설정을 확인합니다.

## 문서 위치

```text
docs/agent/
├── README.md               이 안내
├── ai-feature-workflow.md  Portal AI 작업 방법
├── PLANS.md                실행 계획 작성 규칙
├── git-scopes.md           커밋 scope 목록
├── decisions.md            날짜별 결정 이력
├── plans/                 작업별 실행 계획·검증 기록
│   └── README.md           주제별 목록
└── evals/                 평가 시나리오
    └── README.md           평가 방법·목록
```

새 작업 계획은 `plans/<slug>.md`에 작성하고 [주제별 목록](plans/README.md)에 연결합니다.
앱 사용법이나 운영 절차는 해당 앱의 현재 안내에 작성하고, 이 폴더에는 변경 이유와 검증 이력을 남깁니다.
