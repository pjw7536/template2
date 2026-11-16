# 레이아웃 패턴 예시

[레이아웃 지침](../SKILL.md)의 높이·스크롤 규칙을 함께 따른다.

작업에 필요한 패턴 절만 읽고 기존 layout 컴포넌트에 맞춰 적용한다. 예시의 div는 구조를 나타내며, 실제 카드 표면은 설치된 Card 컴포넌트를 우선 사용한다.

### 패턴 A) top-fixed / bottom-scroll
```jsx
<div className="grid h-full min-h-0 grid-rows-[auto_1fr] gap-4">
  <div className="shrink-0">고정 영역</div>
  <div className="min-h-0 overflow-y-auto">스크롤 영역</div>
</div>
```

사용 예:
- 상단 필터 + 하단 결과
- 상단 요약 + 하단 본문
- 상단 액션 + 하단 목록

규칙:
- 상단은 compact하게 유지한다.
- 많은 내용을 fixed area에 넣지 않는다.

### 패턴 B) sticky toolbar + content
```jsx
<div className="h-full min-h-0 overflow-y-auto">
  <div className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">도구 모음</div>
  <div>본문</div>
</div>
```

규칙:
- sticky는 content scroll owner 안에서만 동작하게 한다.
- sticky parent의 overflow 문맥을 확인한다.

### 패턴 C) two-pane list-detail
```jsx
<div className="grid h-full min-h-0 min-w-0 grid-cols-[360px_minmax(0,1fr)] gap-4">
  <section className="grid min-h-0 min-w-0 grid-rows-[auto_1fr] gap-3">
    <div className="shrink-0">필터 / 요약</div>
    <div className="min-h-0 overflow-y-auto">목록</div>
  </section>

  <section className="min-h-0 min-w-0 overflow-y-auto">상세</section>
</div>
```

사용 예:
- 왼쪽 리스트 / 오른쪽 상세
- 왼쪽 검색 / 오른쪽 미리보기

규칙:
- 왼쪽 pane은 고정폭 또는 제한된 폭을 사용한다.
- 오른쪽 detail에는 `min-w-0`를 반드시 둔다.
- 좌/우 pane 모두 많은 데이터가 있는 경우에만 양쪽 y-scroll을 분리한다.

### 패턴 D) dashboard
```jsx
<div className="flex h-full min-h-0 flex-col gap-4">
  <section className="grid grid-cols-4 gap-4">KPI 요약</section>

  <section className="grid flex-1 min-h-0 min-w-0 grid-cols-[2fr_1fr] gap-4">
    <div className="min-h-0 min-w-0 overflow-hidden rounded-2xl border bg-card">주 패널</div>
    <div className="min-h-0 min-w-0 overflow-hidden rounded-2xl border bg-card">보조 패널</div>
  </section>
</div>
```

규칙:
- KPI는 상단, heavy content는 하단에 둔다.
- card 내부에서 다시 layout을 나눌 때만 추가 grid를 사용한다.

### 패턴 E) table page
```jsx
<div className="grid h-full min-h-0 grid-rows-[auto_1fr] gap-4">
  <div className="shrink-0">제목 / 필터 / 동작</div>

  <div className="min-h-0 min-w-0 overflow-hidden rounded-2xl border bg-card">
    <div className="grid h-full min-h-0 grid-rows-[auto_1fr]">
      <div className="shrink-0 border-b px-4 py-3">표 도구 모음</div>
      <div className="min-h-0 min-w-0 overflow-auto">표</div>
    </div>
  </div>
</div>
```

규칙:
- wide table은 table shell 안에서만 scroll시킨다.
- page 전체와 table 내부가 동시에 주 scroll owner가 되지 않게 한다.
- table 때문에 page가 가로로 밀리지 않도록 `min-w-0`를 둔다.

### 패턴 F) settings / form
```jsx
<div className="h-full min-h-0 overflow-y-auto">
  <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
    <section className="rounded-2xl border bg-card p-6">기본 설정</section>
    <section className="rounded-2xl border bg-card p-6">고급 설정</section>
  </div>
</div>
```

규칙:
- 읽기와 입력이 많은 화면은 폭을 제한한다.
- form은 full width보다 constrained width를 우선한다.
- destructive action은 맨 아래 별도 section으로 분리한다.
