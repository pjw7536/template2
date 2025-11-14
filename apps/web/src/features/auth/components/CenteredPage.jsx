// src/features/auth/components/CenteredPage.jsx
// 인증 관련 화면에서 자주 쓰이는 "가운데 정렬 카드" 레이아웃 컴포넌트입니다.
// - 전체 화면을 중앙 정렬하고, 내부 카드 폭을 제한해 줍니다.
// - 다른 기능에서 필요하면 재사용할 수 있도록 props 설명을 자세히 남겼습니다.

import { cn } from "@/lib/utils"

export function CenteredPage({
  children,
  className,
  containerClassName,
  ...props
}) {
  return (
    <div
      className={cn(
        "flex min-h-svh w-full items-center justify-center bg-background px-6 py-10 md:px-10",
        className,
      )}
      {...props}
    >
      <div className={cn("w-full max-w-md", containerClassName)}>{children}</div>
    </div>
  )
}
