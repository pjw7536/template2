---
name: compose-frontend-layout
description: Portal 업무형 화면의 높이·스크롤·pane·여백 소유권을 구성한다. 새 page skeleton이나 fixed/scroll·목록/상세·table·dashboard 구조를 만들거나 수정할 때 적용한다.
---

# 프론트엔드 레이아웃

## 적용 범위

Desktop 중심의 Portal dashboard·table·목록/상세·settings·workbench에 적용한다.
문구나 색상만 바꾸는 작업에는 레이아웃을 다시 설계하지 않는다. 마케팅·showcase 페이지는 기본 대상이 아니다.
시각 디자인·상태는 [제품 UI 스킬](../product-ui-design-system/SKILL.md), 컴포넌트 API는 공식 `shadcn` 스킬과 기존 코드를 따른다.

## 구성 순서

페이지 유형과 전체 높이 소유자를 확인하고, 고정·sticky·스크롤 영역을 구분한다.
기존 layout 컴포넌트를 먼저 사용한 뒤 필요한 wrapper만 수정한다.
기본 패턴의 JSX가 필요할 때만 [패턴 예시](references/patterns.md)에서 해당 절을 읽는다. 모든 예시를 선독하지 않는다.

## 유지할 규칙

- 같은 region의 같은 축에는 스크롤 컨테이너 하나를 둔다. 분리된 pane과 overlay는 별도 region이다.
- flex/grid 안에서 스크롤되는 요소는 `min-h-0`, 가로로 줄어드는 pane·table 영역은 `min-w-0`를 둔다.
- 전체 높이·page padding·section gap은 outer layout이, component는 내부 padding·정렬만 소유한다.
- `h-screen`은 app root에서만 사용한다. route page는 부모의 `h-full min-h-0`를 따른다.
- sticky는 얇은 toolbar·action bar에 사용하고 배경·경계선을 둔다. 큰 본문이나 여러 겹 sticky를 기본 구조로 만들지 않는다.
- 기존 breakpoint는 보존한다. 새 반응형 재구성은 명시 요청이나 요구사항이 있을 때 추가한다.
- 동적 측정이 필요하면 CSS 변수 기반 폭을 사용한다. 임의 spacing·width 숫자를 화면마다 추가하지 않는다.
- 높이·스크롤 문제는 해당 소유 wrapper에서 해결하고 자식의 시각 스타일로 우회하지 않는다.

## 기본 shell

```jsx
<div className="flex h-full min-h-0 flex-col">
  <header className="shrink-0 px-6 py-4">페이지 제목</header>
  <main className="min-h-0 min-w-0 flex-1 overflow-hidden px-6 pb-6">
    작업 영역
  </main>
</div>
```

작업 영역의 내용에 맞춰 스크롤 소유자를 정한다. `overflow-hidden`만 두어 내용이 잘리지 않는지 확인한다.

## 패턴 선택

| 패턴 | 적합한 구조 | 주의점 |
| --- | --- | --- |
| A: 상단 고정·하단 스크롤 | 필터/요약 + 결과 | 고정 영역은 compact하게 유지 |
| B: sticky toolbar | 긴 목록·본문 | toolbar를 실제 scroll owner 안에 배치 |
| C: 두 pane | 목록 + 상세/미리보기 | 제한된 목록 폭과 유연한 상세 폭. 내용이 많을 때만 양쪽 스크롤 |
| D: dashboard | KPI + 작업 패널 | 고정 요약과 남은 높이를 쓰는 본문 분리 |
| E: table | 필터 + 넓은 표 | 표 shell 안에서 가로 스크롤. page와 표의 중복 주 스크롤 방지 |
| F: settings/form | 긴 입력·설명 | `max-w-5xl`/`max-w-6xl` 등 기존 제한 폭 재사용 |

필요한 패턴을 조합하되 위 높이·스크롤 규칙을 유지한다. 예시만을 이유로 기존 화면 구조를 바꾸지 않는다.

## 공통화와 시각 규칙

- 범용 layout은 `apps/portal/web/src/components/layout/<LayoutName>.jsx`에 둔다. feature 내부나 `src/routes/*`에 새 범용 layout을 만들지 않는다.
- 반복 구조는 기존 layout 재사용을 먼저 검토한다. 두 번 반복됐다는 이유만으로 요청 밖 리팩터링을 추가하지 않는다.
- flex는 toolbar·button row 등 한 축, grid는 pane·dashboard·고정/스크롤 영역 등 두 축 배치에 사용한다.
- spacing·Card·radius·타이포는 `product-ui-design-system`의 기본값을 따른다. layout에 별도 디자인 규칙을 만들지 않는다.

## 검증

- 높이 소유자와 주 스크롤 영역이 명확하고, 내용 증가·긴 표·pane 축소 시 overflow가 유지되는지 확인한다.
- `min-h-0`, `min-w-0`, page/child padding, sticky 배경·경계와 기존 breakpoint를 확인한다.
- 저장소 루트에서 `make audit-ui`를 실행한다. 이번 변경의 문제와 기존 감사 후보를 구분한다.
