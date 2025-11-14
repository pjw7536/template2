// src/components/providers/app-providers.jsx
// 앱 전역에서 공유되는 클라이언트 사이드 프로바이더(Auth/Theme/Toaster)를 한 곳에서 선언
// 루트 레이아웃이 간결해지고, 후속 프로바이더 추가/테스트가 쉬워집니다.

"use client"

import { AuthProvider } from "@/components/auth"
import { ThemeProvider } from "@/components/theme-provider"
import { Toaster } from "@/components/ui/sonner"

export function AppProviders({ children }) {
  return (
    <AuthProvider>
      <ThemeProvider>
        {children}
        <Toaster />
      </ThemeProvider>
    </AuthProvider>
  )
}
