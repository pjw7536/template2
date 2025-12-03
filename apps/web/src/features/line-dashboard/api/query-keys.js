// src/features/line-dashboard/api/query-keys.js
// 라인 대시보드 관련 서버 상태에서 공유할 React Query 키 모음입니다.
// - feature 내부/외부에서 invalidateQuery 등에 재사용할 수 있도록 헬퍼 형태로 정의합니다.

const ROOT_KEY = ["line-dashboard"]

export const lineDashboardQueryKeys = {
  all: ROOT_KEY,
  lineOptions: () => [...ROOT_KEY, "line-options"],
}
