# ExecPlan: L3 Spider 페이지 설명서 갱신

## 목표
- Summary의 라인별 이상감지 요약 Total이 3개에서 6개로 확장된 현재 화면과 항목 설명을 반영한다.
- Chart 선택 패널의 접기/펼치기 및 드래그 높이 조절 기능을 현재 화면 캡처와 설명에 반영한다.

## 현재 상태
- 페이지 설명은 `apps/web/src/features/l3-spider/components/L3SpiderGuideDialog.jsx`에서 관리한다.
- Summary와 Chart 캡처는 `apps/web/public/l3-spider/l3-spider-guide-assets/`에 있다.
- 기존 Summary 캡처는 Total 5개, Chart 캡처는 패널 조절 핸들 도입 전 화면이다.

## 범위
- 페이지 설명서의 Summary/Chart 문구와 캡처 실행일을 수정한다.
- `summary-overview.png`, `chart-workflow.png`를 현재 개발 화면 기준으로 교체한다.
- L3 Spider 화면 동작, API, DB, 권한 계약은 변경하지 않는다.

## 설계
- 기존 번호형 캡처와 설명 목록 구조를 유지한다.
- Summary 번호 4는 6개 Total 항목을 명시한다.
- Chart에는 선택 패널 하단 조절 핸들을 새 번호로 표시하고 클릭/드래그 동작을 설명한다.
- public API, migration, env, auth 영향은 없다.

## 실행 단계
- [x] 현재 개발 화면에서 Summary와 Chart를 같은 데이터 날짜로 캡처한다.
- [x] 캡처에 기존 설명 목록과 일치하는 번호를 표시한다.
- [x] 페이지 설명과 캡처 실행일을 갱신한다.
- [x] 프론트엔드 검증과 캡처 육안 검사를 실행한다.

## 검증
- `cd apps/web && npm run lint`
- `cd apps/web && npm run build`
- `npm run agent:audit:ui`
- 생성 PNG의 크기와 화면 내용을 육안으로 확인한다.

## 위험과 대응
- 위험: 캡처 번호와 설명 순서가 어긋날 수 있다.
- 대응: 최종 PNG를 원본 해상도로 열어 번호 위치와 문구를 대조한다.
- 위험: 개발 서버의 mock 데이터 로딩이 캡처 시 완료되지 않을 수 있다.
- 대응: 로딩 완료와 선택 상태를 확인한 뒤 캡처한다.

## 진행 기록
- 2026-07-14: 현재 Total 6개 항목과 Chart 패널 조절 핸들 구현을 확인하고 작업 범위를 확정했다.
- 2026-07-14: 개발 mock의 2026-06-20 데이터를 사용해 Summary/Chart 캡처를 교체하고 설명 번호를 갱신했다.
- 2026-07-14: lint와 production build를 통과했다. UI audit은 기존 L3SpiderChart raw color/inline style 후보를 보고해 실패했으며 이번 변경 범위에서는 수정하지 않았다.
- 2026-07-14: 실제 설명서 모달에서 6개 Total 문구, 패널 조절 문구, 두 캡처와 실행일 표시를 확인했다.
