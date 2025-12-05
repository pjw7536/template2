// src/features/line-dashboard/components/LineDashboardProvider.jsx
import * as React from "react"

import { useLineDashboardData } from "../hooks/useLineDashboardData"

// 전역 상태를 공유하기 위한 컨텍스트를 한 번 생성해 둡니다.
const LineDashboardContext = React.createContext(null)

// 라인별 데이터 로딩 훅을 실행해서 자손에게 전달합니다.
export function LineDashboardProvider({ lineId, children }) {
  const value = useLineDashboardData(lineId)
  return <LineDashboardContext.Provider value={value}>{children}</LineDashboardContext.Provider>
}

// 컨텍스트가 없을 때는 개발 단계에서 바로 오류가 나도록 가드합니다.
export function useLineDashboardContext() {
  const context = React.useContext(LineDashboardContext)
  if (!context) {
    throw new Error("useLineDashboardContext must be used within LineDashboardProvider")
  }
  return context
}
