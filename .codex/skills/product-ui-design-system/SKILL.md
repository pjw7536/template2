---
name: product-ui-design-system
description: Portal 업무형 UI의 디자인 토큰·타이포·간격·컴포넌트 위계·상태·접근성을 통일한다. 새 화면이나 시각·상태 수정에 적용하며, 컴포넌트 API는 공식 shadcn 스킬과 기존 코드를 따른다.
---

# 제품 UI 디자인

## 범위와 역할

`apps/portal/web/src`의 업무형 화면·form·table·dialog에 적용한다.
브랜드·마케팅 페이지, SVG·차트 라이브러리 내부 구현은 기본 대상이 아니다.

- 컴포넌트 API·조회·조합: [공식 shadcn](../shadcn/SKILL.md). 실행 위치와 기존 API 호환 기준은 `apps/portal/web/AGENTS.md`를 따른다.
- 높이·스크롤·pane 구성: [레이아웃 스킬](../compose-frontend-layout/SKILL.md). 해당 구조를 바꿀 때 읽는다.
- 이 스킬: 제품의 시각 위계·밀도·상태·상호작용. 기존 테마와 semantic token을 유지한다.

기존 shadcn/Radix 컴포넌트와 내장 variant를 먼저 조합한다. 컴포넌트의 색상·타이포를 호출부에서 임의로 덮어쓰지 않는다. `components/ui/**` 수정 제한은 Web 지침을 따른다.

## 색상과 표면

| 용도 | 기본 토큰 |
| --- | --- |
| 표면 | `bg-background`, `bg-card`, `bg-popover`, `bg-muted` |
| 본문·보조 텍스트 | `text-foreground`, `text-muted-foreground`, `text-card-foreground` |
| 경계·입력·focus | `border-border`, `border-input`, `ring-ring` |
| 주요 동작·위험 | `bg-primary`, `text-primary-foreground`, `text-destructive` |
| 선택·보조 동작 | `bg-accent`, `text-accent-foreground`, `bg-secondary`, `text-secondary-foreground` |

- 임의 HEX·raw palette·토큰으로 대체할 수 있는 inline 색상을 추가하지 않는다.
- light/dark는 토큰으로 함께 처리한다. 차트·상태 색은 `--chart-*`, `--primary`, `--destructive` 등을 먼저 사용한다.
- 측정된 pane·외부 라이브러리의 동적 크기·색상·SVG API 요구는 Web 지침의 예외 범위에서 처리한다.
- 업무형 UI는 절제된 대비와 낮은 장식 밀도를 유지한다. 구획은 간격·경계·muted 표면을 사용하고 큰 shadow와 카드 중첩을 피한다.

## 타이포와 밀도

| 역할 | 기본값 |
| --- | --- |
| 페이지 제목 | `text-2xl font-semibold tracking-tight` |
| 섹션 제목 | `text-base font-semibold` |
| 카드 제목 | `text-sm font-semibold` |
| 본문·보조 설명 | `text-sm` + foreground/muted-foreground |
| 메타데이터 | `text-xs text-muted-foreground` |
| 수치 | `tabular-nums`, 필요한 경우 `font-mono` |
| 페이지 여백 | `px-6 py-4`, 작업 영역 하단 `pb-6` |
| 섹션 간격 | `gap-4`, 큰 구획 `gap-6` |
| 필드·내부 간격 | `gap-2`, 필요한 경우 `gap-3` |
| 카드 내부 여백 | `p-4`, 큰 form은 `p-6` |
| 기본 control | `h-9`에 해당하는 기존 size variant |

- 같은 깊이의 요소는 같은 padding·radius·border를 사용한다. 기존 컴포넌트가 토큰·variant로 소유하는 값은 그 정의를 우선한다.
- heading 깊이는 3단계 이하를 기본으로 한다. label과 helper text를 분리하고 긴 설명은 `leading-6`을 사용한다.
- 아이콘은 `components.json`과 기존 파일의 라이브러리를 따른다. 독립 아이콘은 `size-4`를 기본으로 하고, Button 등 내부 아이콘은 컴포넌트가 크기를 소유하면 별도로 덮어쓰지 않는다.
- 애니메이션은 상태 전환을 이해하는 데 필요한 범위로 제한한다.

## 컴포넌트별 판단

| 요소 | 제품 규칙 |
| --- | --- |
| Button | 영역별 주요 동작 하나. 보조는 `outline`/`secondary`, 위험 동작은 `destructive`. 내장 size·variant 우선 |
| Card | 기존 `Card`와 header/content/footer 조합 우선. 새 정보 묶음의 기본 표면은 `rounded-2xl border bg-card`, header `px-4 py-3`, body `p-4`. 기존 Card 정의를 무조건 덮어쓰지 않음 |
| Table/List | 행 hover는 `hover:bg-muted/50`, 선택은 accent와 border/icon 등 보조 단서. 숫자·날짜·상태의 정렬·폭 통일 |
| Form | 설치된 `Field` 계열로 label·control·설명·오류를 묶음. 저장·취소는 한 곳에 모으고 위험 설정은 분리 |
| Dialog/Sheet | 하나의 결정·짧은 form은 Dialog, 긴 편집·탐색은 page/Sheet. footer는 보조 왼쪽·주요 동작 오른쪽 |

새 컴포넌트가 필요하면 설치 여부와 공개 API를 먼저 확인한다. 일관성을 이유로 새 primitive를 직접 만들거나 전체 UI를 갱신하지 않는다.

## 상태와 접근성

변경한 화면에 필요한 상태를 구현하고, 기존 상태를 보존한다.

- Loading: Skeleton/Spinner와 작업 문구. 빈 화면으로 남기지 않는다.
- Empty: 원인과 다음 행동 하나. Error와 구분한다.
- Error: 원인 요약과 재시도·복구 동작. toast만 띄우고 화면 상태를 그대로 두지 않는다.
- Disabled: 이유가 불명확하면 설명한다. 변경 중에는 중복 클릭을 막고 진행 label을 제공한다.
- Selected: 색상 외 border·icon·font weight로도 표현한다.
- 입력 label 연결, 키보드 focus, icon-only action의 접근 가능한 이름, Dialog 제목·설명, focus로도 접근 가능한 보조 정보를 제공한다.
- 커스텀 표면·색상이 있으면 light/dark 대비를 함께 확인한다.

## 검증

변경 화면의 위계·밀도·상태·키보드 접근·dark mode를 확인한다.
저장소 루트에서 `make audit-ui`를 실행한다. 감사 결과는 검토 후보이며 관련 예외와 기존 문제를 이번 변경과 구분한다.
