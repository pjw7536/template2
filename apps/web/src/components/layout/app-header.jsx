// src/components/layout/app-header.jsx
// 상단 헤더(버거 버튼 + breadcrumb + 테마 토글)를 분리해 유지보수성과 재사용성을 확보

import { memo } from "react"

import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { ThemeColorSelector } from "@/components/theme-color-selector"
import { ThemeToggle } from "@/components/theme-toggle"

import { DynamicBreadcrumb } from "./dynamic-breadcrumb"

export const AppHeader = memo(function AppHeader() {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between gap-2 px-4 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
      <div className="flex items-center gap-2">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
        <DynamicBreadcrumb />
      </div>
      <div className="flex items-center">
        <ThemeToggle />
        <ThemeColorSelector />
      </div>
    </header>
  )
})
