// src/app/(app)/layout.js
import { RequireAuth } from "@/components/auth"
import { AppShell } from "@/features/navigation"
import { getDistinctLineIds } from "@/features/line-dashboard/api/get-line-ids"

// 레이아웃에 필요한 선행 데이터를 서버에서 한번만 로드하는 헬퍼
async function loadLineOptions() {
  try {
    const result = await getDistinctLineIds()
    return Array.isArray(result) ? result : []
  } catch (error) {
    console.warn("Failed to load line options", error)
    return []
  }
}

// App 라우트 공통 레이아웃: 인증 가드 + 사이드바/헤더가 있는 앱 셸 구성
export default async function AppLayout({ children }) {
  const lineOptions = await loadLineOptions()

  return (
    <RequireAuth>
      <AppShell lineOptions={lineOptions}>{children}</AppShell>
    </RequireAuth>
  )
}
