# Portal Web 개발 지침

## 작업별 진입점

`apps/portal/web/**`에 적용한다. 아래 스킬 경로는 저장소 루트의 `.codex/skills/<name>/SKILL.md`다. 해당 작업에 필요한 것만 읽는다.

| 작업 | 스킬 |
| --- | --- |
| 컴포넌트 API·조합 | `shadcn` |
| 시각 디자인·상태·접근성 | `product-ui-design-system` |
| 높이·스크롤·pane 구조 | `compose-frontend-layout` |
| UI 정적 검사 | `ui-consistency-audit` |
| feature 구조·공개 경계 | `frontend-boundary-audit` |
| 실제 브라우저 검증 | `playwright` |
| 요청된 UI·접근성·UX 리뷰 | `web-design-guidelines` |

shadcn 조회는 이 폴더에서 실행한다. 스킬이 자동 주입하는 컨텍스트는 세션 시작 폴더 기준이라 저장소 루트에서는 실패하거나 다른 설정을 보여줄 수 있다. 주입 결과가 없거나 오류이거나 이 폴더의 `components.json` 기준이 아니면 이 폴더에서 `npx --yes shadcn@latest info --json`을 다시 실행한다. 최신 예시보다 기존 primitive import·export·props를 확인하고, 미설치 컴포넌트를 import하거나 테마·컴포넌트를 일괄 갱신하지 않는다.

## 구조와 공개 경계

- JSX는 `.jsx`, 그 외 모듈은 `.js`다. 컴포넌트는 PascalCase, hook·util·store는 명시된 예외 외 camelCase를 사용한다.
- Feature는 `src/features/<feature>`에 두고 `pages/`, `components/`, `hooks/`, `api/`, `store/`, `utils/`, `routes.jsx`, `index.js`만 허용한다. 각각 경로 화면·내부 UI·hook·API/query key·클라이언트 상태·도우미·라우팅·공개 facade를 담당한다.
- 기본 최대 깊이는 2다. `components/`만 기존 파일 12개 이상이거나 사용자가 그룹 구성을 명시한 경우 한 단계 더 나눌 수 있다. 그룹명은 `list`, `detail`, `form`, `dialog`, `table`, `chart`, `filters`, `cards`, `sections`이며 추가 중첩은 금지한다. 다른 그룹명은 먼저 질문한다.
- 외부 공개 진입점은 feature의 `index.js`다. Named export만 허용하고 `export *`는 금지한다.
- Feature 간 의존은 `auth -> account`, `emails -> account`, `line-dashboard -> account`만 허용하며 `@/features/<feature>` facade로 사용한다. 다른 feature 내부 경로와 `/index.js` 명시 import는 금지한다.
- `routes/*`, `components/layout/*`, `components/common/*`, `lib/*` 조립 계층은 feature facade를 사용할 수 있다. `lib/*`에는 shell context·프레임워크 어댑터·범용 도우미만 두고 도메인 HTTP client·React Query hook·업무 UI를 두지 않는다.

## Import·라우팅·데이터

- 내부 절대 경로는 `@/`를 우선한다. 기존 `components/...` alias는 유지할 수 있으나 한 파일에서 `@/components/...`와 혼용하지 않는다.
- 절대 import 대상은 `components/ui/*`, `components/layout/*`, `components/common/*`, `lib/*`와 위 규칙에 따른 feature facade다.
- 명시적으로 요청된 shadcn CLI 작업 외에는 `src/components/ui/**`를 직접 수정하지 않는다.
- 모든 feature는 `routes.jsx`를 공개하고 전역 라우팅은 `src/routes/*`에서만 조립한다. Route는 layout을 조합하되 레이아웃 정의·업무 로직·데이터 처리·파생 UI 로직을 넣지 않는다.
- 서버 데이터는 React Query로 관리한다. query key는 배열로 만들고 중복을 피하며 최소 범위만 invalidate한다. Zustand는 feature 내부 UI·상호작용 상태에만 쓰고 서버 데이터를 복제하지 않는다.

## UI 기준

- 스타일은 Tailwind로 작성한다. Semantic token과 설치된 shadcn/Radix 요소·내장 variant를 우선한다. 임의 HEX·inline style은 꼭 필요한 경우 외 금지하며 라이브러리 연결용 CSS 변수 기반 동적 크기·색상은 허용한다.
- 시각 값·loading/empty/error/disabled/selected·hover/focus·dark mode·접근성은 제품 UI 스킬을 따른다. 별도 화면별 테마를 만들지 않는다.
- 같은 영역·축의 스크롤 소유자는 하나다. 스크롤 요소는 `min-h-0`, 줄어드는 pane은 `min-w-0`를 사용한다. 앱 root는 `h-screen flex flex-col`과 고정 header·`flex-1 min-h-0 overflow-hidden` main을 소유하고 route page는 `h-screen` 없이 `h-full min-h-0`로 따른다. 상세 구조는 레이아웃 스킬을 따른다.
- `useMemo`, `useCallback`, `React.memo`는 필요한 경우에만 사용한다.

## 검증

| 변경 | 검사 |
| --- | --- |
| UI | 관련 테스트·린트·빌드 중 필요한 검사와 `make audit-ui` |
| import·export·라우팅·feature 구조 | `make audit-web-boundary` |
| 광범위한 frontend | 관련 테스트·린트·빌드와 `make audit-ui audit-web-boundary audit-hotspots`. API·배포·문서에도 영향이 있으면 `make audit` |

감사 결과는 검토 후보이며 요청 밖 기존 문제를 함께 수정하지 않는다.

### 브라우저 검증과 UI 리뷰

- 실제 렌더링·입력·스크롤·흐름 확인이 필요할 때 `playwright`를 사용한다. 작은 문구 수정마다 기동하지 않는다.
- 프로젝트 wrapper·산출물·세션 실행법은 [브라우저 검증 안내](../../../docs/agent/README.md#브라우저-검증과-ui-리뷰)를 따른다. 원문의 전역 경로·루트 `output/` 예시를 그대로 적용하지 않는다.
- `web-design-guidelines`는 리뷰 요청에 적용한다. 대상이 요청·diff로 명확하면 범위를 다시 묻지 않고 현재 웹 조회 도구로 원본 가이드를 읽는다.
- 일반 권고는 검토 후보로 다룬다. 저장소 지침·기존 API·제품 디자인·한국어 locale·desktop-first 요구를 우선하고 영어 문구·모바일 권고를 일괄 적용하지 않는다. 확인하지 못한 가이드·브라우저 동작은 제약으로 보고한다.
