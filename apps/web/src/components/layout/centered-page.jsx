// src/components/layout/centered-page.jsx
// 페이지 전체를 가운데 정렬된 카드 레이아웃으로 감싸는 재사용 컨테이너
// - 인증 로딩, 로그인, 에러 등 단일 카드 UI가 필요한 화면에서 일관된 경험 제공
// - className/containerClassName props를 통해 섬세한 커스터마이징 가능

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
