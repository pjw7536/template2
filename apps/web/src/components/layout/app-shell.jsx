// src/components/layout/app-shell.jsx
// 사이드바/헤더/메인 콘텐츠 영역을 묶는 앱 공통 셸 컴포넌트
// - AppSidebarProvider로 사이드바 상태를 제공하고
// - AppSidebar + AppHeader 조합으로 통일된 내비게이션 UI를 구성
// - 메인 콘텐츠는 max-w-6xl 폭과 gap-4를 유지해 페이지 간 시각적 일관성을 확보합니다.

import { SidebarInset } from "@/components/ui/sidebar"

import { AppSidebarProvider } from "./app-sidebar-provider"
import { AppHeader } from "./app-header"
import { AppSidebar } from "./app-sidebar"

export function AppShell({ lineOptions, navigation, children }) {
  return (
    <AppSidebarProvider>
      <AppSidebar lineOptions={lineOptions} navigation={navigation} />
      <SidebarInset>
        <AppHeader />
        <main className="flex-1 min-h-0 min-w-0 overflow-auto px-4 pb-6 pt-2">
          <div className="mx-auto flex h-full w-full max-w-10xl flex-col gap-4">
            {children}
          </div>
        </main>
      </SidebarInset>
    </AppSidebarProvider>
  )
}
