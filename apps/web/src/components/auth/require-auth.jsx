"use client"

import { useEffect, useMemo } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { useAuth } from "@/components/auth"
import { CenteredPage } from "@/components/layout/centered-page"

function buildNextParam(pathname, searchParams) {
  if (!pathname) {
    return ""
  }

  const queryString = searchParams?.toString()
  if (queryString) {
    return `${pathname}?${queryString}`
  }

  return pathname
}

export function RequireAuth({ children }) {
  const { user, isLoading } = useAuth()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const nextParam = useMemo(() => buildNextParam(pathname, searchParams), [pathname, searchParams])

  useEffect(() => {
    if (!isLoading && !user) {
      const search = nextParam && nextParam !== "/" ? `?next=${encodeURIComponent(nextParam)}` : ""
      router.replace(`/login${search}`)
    }
  }, [isLoading, user, router, nextParam])

  if (isLoading || !user) {
    return (
      <CenteredPage>
        <div className="rounded-xl border bg-card p-6 shadow-sm">
          <p className="text-sm text-muted-foreground">인증 상태를 확인하는 중입니다...</p>
        </div>
      </CenteredPage>
    )
  }

  return children
}
