// src/app/layout.js
import "./globals.css"

import { AppProviders } from "@/components/providers/app-providers"

// 글로벌 메타데이터: 브라우저 탭 타이틀/설명을 실제 서비스 도메인에 맞춰 조정
export const metadata = {
  title: {
    default: "E-SOP Control Tower",
    template: "%s · E-SOP Control Tower",
  },
  description: "Monitor E-SOP production line performance and insights in real time.",
}

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-svh bg-background font-sans antialiased">
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  )
}
