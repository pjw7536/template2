# shadcn/ui 공식 스킬

## 원본

- 공식 안내: [shadcn/ui Skills](https://ui.shadcn.com/docs/skills)
- 설치 원본: [shadcn-ui/ui의 skills/shadcn](https://github.com/shadcn-ui/ui/tree/dd41d19e2f80ff6891951f7ced74c2c9a650b065/skills/shadcn)
- 고정 commit: `dd41d19e2f80ff6891951f7ced74c2c9a650b065`
- 라이선스: [MIT](LICENSE). upstream 루트의 `LICENSE.md`를 포함한다.

`SKILL.md`, 규칙·참고 문서, `agents/`, `assets/`, `scripts/`, `evals/`는 공식 원문을 유지한다. 이 안내 문서와 라이선스 파일은 저장소에서 함께 관리한다.

## Portal에서 사용

- 진입점은 [Web 개발 지침](../../../apps/portal/web/AGENTS.md)이다.
- 공식 스킬은 컴포넌트 API·조합을 담당한다. 제품 디자인은 [product-ui-design-system](../product-ui-design-system/SKILL.md), 레이아웃은 [compose-frontend-layout](../compose-frontend-layout/SKILL.md)을 함께 적용한다.
- shadcn CLI는 `apps/portal/web`에서 실행한다. 루트에서 실행하면 Portal의 `components.json`을 찾지 못할 수 있다.

```bash
cd apps/portal/web
npx --yes shadcn@latest info --json
npx --yes shadcn@latest docs button dialog select
```

스킬의 동적 컨텍스트 구문은 세션 시작 폴더에서 실행된다. 이 구문을 실행하지 않는 클라이언트이거나, 결과가 없거나 오류이거나 `apps/portal/web/components.json` 기준이 아니면 `apps/portal/web`에서 `info --json`을 직접 실행한다. `docs`에는 실제 작업 대상 컴포넌트를 지정하고 반환된 공식 문서를 확인한다. CLI 조회에는 외부 패키지·문서 접근이 필요하다. 접근할 수 없으면 로컬 설정과 기존 컴포넌트 구현으로 확인하고 제약을 보고한다.

최신 공식 문서와 설치된 컴포넌트의 버전·API가 다를 수 있다. 기존 primitive import·export·props를 우선 확인하고, 공식 예시만 보고 미설치 컴포넌트를 import하거나 전체 테마·preset·의존성을 갱신하지 않는다. 코드 예시는 Portal의 `.jsx`·`.js` 규칙과 공개 facade 계약에 맞춘다.

`scripts/showcase-coverage.mjs`는 upstream의 TypeScript UI 파일을 대상으로 한다. Portal의 `.jsx` 컴포넌트 커버리지 검사로 사용하지 않는다. `evals/`는 upstream 참고 자료이며, 저장소 평가가 필요하면 `docs/agent/evals/`의 해당 시나리오를 사용한다.

## 갱신

1. 공식 원본에서 사용할 commit과 스킬 변경 내용을 확인한다.
2. `skill-installer`의 `install-skill-from-github.py`에 `--repo shadcn-ui/ui --path skills/shadcn --ref <commit> --dest <임시 skills 경로> --method git`을 지정해 임시 경로에 설치한다.
3. 현재 스킬과 차이를 검토하고 공식 파일만 반영한다. 이 안내 문서는 유지하고, 같은 commit의 upstream `LICENSE.md`를 `LICENSE`에 반영한다.
4. 이 문서의 원본 링크·고정 commit을 갱신한다. 로컬 참조 경로와 Web 지침의 호환성을 검사하고, Portal에서 `info --json`을 실행한다.

스킬 갱신과 앱 컴포넌트·패키지 갱신은 별도 작업으로 다룬다.
