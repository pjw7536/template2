// 파일 경로: src/components/common/AppProviders.jsx
// 앱 전역에서 공유되는 클라이언트 사이드 프로바이더(Auth/Theme/Toaster)를 한 곳에서 선언
// 루트 레이아웃이 간결해지고, 후속 프로바이더 추가/테스트가 쉬워집니다.

import { useState } from "react"
import { QueryClientProvider } from "@tanstack/react-query"

import { AuthProvider } from "@/lib/auth"
import { ThemeProvider } from "@/lib/theme"
import { Toaster } from "@/components/ui/sonner"
import { createQueryClient } from "@/lib/queryClient"

export function AppProviders({ children }) {
  const [queryClient] = useState(() => createQueryClient())

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider>
          {children}
          <Toaster />
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
