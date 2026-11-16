---
name: safe-file-edit-output
description: 파일 생성·수정 시 요청 범위, 기존 사용자 변경, 실제 import·공개 facade를 보존하고 변경 경로와 검증 결과를 간결하게 보고한다.
---

# 파일 수정과 결과 보고

## 수정 기준

- 사용자 지시를 우선하고 루트와 수정 영역의 `AGENTS.md`, feature 공개 facade 계약, 기존 파일 관례 순으로 적용한다. 이 스킬이 상위 지침의 우선순위를 바꾸지 않는다.
- 기존 사용자 변경을 먼저 확인하고 이번 요청의 수정만 수행한다. 자동 stage·commit·push 여부는 루트 Git 규칙과 사용자 요청을 따른다.
- 요청 밖 rename·move·리팩터링·새 추상화를 추가하지 않는다.
- 문법, 실제 import 경로, 명시적 export와 호출부의 정합성을 확인한다. 존재하지 않는 모듈이나 미설치 컴포넌트를 import하지 않는다.
- 주석·docstring 언어와 Markdown 관리 방식은 루트 지침을 따른다.

## 영역별 확인

경계 규칙을 이 문서에 복제하지 않고 다음 원본을 확인한다. 경로는 저장소 루트 기준이다.

| 변경 | 확인할 원본·스킬 |
| --- | --- |
| Portal 프론트엔드 | `apps/portal/web/AGENTS.md`: alias·`.jsx`·feature facade·`components/ui/**` 수정 제한 |
| Portal 백엔드 | `apps/portal/api/AGENTS.md`: 도메인 공개면·service/selector/view 책임 |
| 프론트엔드 컴포넌트·상태 | `shadcn`, `product-ui-design-system` |
| 높이·스크롤·pane 구조 | `compose-frontend-layout` |
| import·export·구조 경계 | 해당 frontend/backend boundary audit |

스킬·문서는 실제 변경에 필요한 것만 읽는다. 경로·명명만 고치는 작업에 UI·백엔드 전체 검사를 일괄 적용하지 않는다.

## 검증과 보고

- 변경한 동작에 맞는 검사를 실행한다. 단순 문서 수정은 참조·구문 검사로 검증하고 앱 테스트를 새로 만들지 않는다.
- 실패가 기존 문제인지 이번 변경에서 생겼는지 구분한다. 실행하지 못한 검사는 이유를 밝힌다.
- 실제 파일 경로, 핵심 변경과 목적, 검증 결과, 남은 제약을 보고한다. 같은 목적의 여러 파일은 묶어서 설명한다.
- 파일 전체나 파일별 고정 템플릿을 반복 출력하지 않는다. 사용자가 전체 내용을 요청했을 때만 제공하며 필요한 스니펫은 짧게 제시한다.
