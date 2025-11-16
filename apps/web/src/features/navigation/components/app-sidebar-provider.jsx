// src/features/navigation/components/app-sidebar-provider.jsx
"use client"

import { useLocation } from "react-router-dom"

import { SidebarProvider } from "@/components/ui/sidebar"

export function AppSidebarProvider({ children }) {
  const { pathname } = useLocation()
  // 첫 진입 화면("/")에서는 집중력 있는 온보딩을 위해 닫힌 상태로, 그 외 페이지는 열린 상태로 노출
  const defaultOpen = pathname !== "/"

  return (
    <SidebarProvider key={pathname} defaultOpen={defaultOpen}>
      {children}
    </SidebarProvider>
  )
}
