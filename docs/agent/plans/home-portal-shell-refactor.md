# ExecPlan: Home·Portal Shell orchestration 정리

## 목표
- 전역 router, navigation, branding, access gate와 Assistant widget orchestration의 중복을 줄인다.
- 내부 참조 없는 `/react-logo-preview` route를 제거한다.

## 현재 상태
- router가 feature routes, access group, global ChatWidget/Emails mailbox context를 조립한다.
- navigation, branding, access tracking catalog가 별도 파일에서 app path를 반복한다.
- `ReactLogoBlankPage.jsx`는 빈 preview 화면이며 route 외 참조가 없다.

## 범위
- 수정: home feature, global routes/layout, 포함 feature catalog 조립, docs/tests.
- 유지: `/`, shell/layout, navigation 사용자 흐름, access gate, ChatWidget와 Emails context.
- 제외: Spider·Teamstaff route/navigation/branding/access/context entry의 값과 동작.

## 설계
- `/react-logo-preview` route/component/export를 삭제하고 wildcard error route가 해당 URL에 404를 반환하게 한다.
- app catalog는 route group이 제공하는 key/title/access scope/branding metadata를 app-shell에서 조립하되 feature 내부 business logic을 넣지 않는다.
- 제외 feature entry는 byte-equivalent value로 유지하고 catalog 이동이 필요하면 characterization snapshot으로 보호한다.
- router는 lazy feature route 조립과 global providers만 담당하고 derived access/branding은 catalog helper로 위임한다.
- Assistant widget은 shell에서 한 번만 mount하고 current app key/mailbox context를 facade로 전달한다.
- DB/API/env/migration 변화는 없다.

## 실행 단계
- [x] route/navigation/branding/access/widget characterization을 추가한다.
- [x] preview route/component/export를 제거한다.
- [x] 포함 feature의 중복 catalog metadata를 단일 shell catalog로 정리한다.
- [x] router/layout 책임과 scroll/accessibility를 검증한다.
- [x] 제외 entry와 전체 navigation snapshot을 비교한다.

## 검증
- frontend route/navigation/layout/Auth gate/ChatWidget tests.
- `/react-logo-preview` 404, `/`와 대표 URL smoke.
- `npm run web:lint`, `npm run web:build`, frontend boundary/UI/full audit.

## 위험과 대응
- 위험: 공용 catalog 정리로 제외 feature route가 바뀐다.
- 대응: Spider·Teamstaff entry snapshot과 changed-path 검사를 필수 gate로 둔다.
- 위험: provider 재배치로 widget/query가 중복 mount된다.
- 대응: router render에서 provider/widget instance 수를 검증한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md), Activity catalog와 Assistant 계획. 최종 Shared·Infra cleanup의 선행 단계다.
- 복구: route/catalog/shell을 revert하면 preview route가 다시 활성화된다. DB/API data 변화는 없다.

## 진행 기록
- 2026-08-18: 사용자 승인으로 preview route 제거와 제외 entry 불변을 확정했다.
- 2026-08-18: `portalAppCatalog`를 route gate, access tracking, navigation, branding의 공통 metadata source로 적용하고 Assistant widget 숨김 경로 판정을 helper로 이동했다. 빈 preview route/component/CSS를 제거하고 Home 404 및 Spider·Teamstaff snapshot을 추가했다. frontend 199개 테스트, lint/build와 전체 boundary/UI/docs 감사를 통과했으며 제외 feature product path 변경은 0건이다.
