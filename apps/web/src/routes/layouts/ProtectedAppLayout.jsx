// src/routes/layouts/ProtectedAppLayout.jsx
import { useEffect } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import { AppShell } from "@/components/layout"
import { NAVIGATION_CONFIG } from "@/lib/config/navigation-config"
import { useLineOptionsQuery } from "@/features/line-dashboard"
import { ChatWidget } from "@/features/assistant"

export function ProtectedAppLayout() {
  const location = useLocation()
  const { data: lineOptions = [], isError, error } = useLineOptionsQuery()
  // VOC 화면은 글/리스트 동시 표시를 위해 레이아웃 폭을 확장
  const isVocRoute =
    typeof location?.pathname === "string" &&
    (/\/voc(\/|$)|\/qna(\/|$)/).test(location.pathname)

  useEffect(() => {
    if (isError) {
      console.warn("Failed to load line options", error)
    }
  }, [isError, error])

  return (
    <RequireAuth>
      <AppShell
        lineOptions={lineOptions}
        navigation={NAVIGATION_CONFIG}
        contentMaxWidthClass={isVocRoute ? "max-w-screen-2xl" : undefined}
        mainOverflowClass={isVocRoute ? "overflow-hidden" : undefined}
      >
        <Outlet />
      </AppShell>
      <ChatWidget />
    </RequireAuth>
  )
}
