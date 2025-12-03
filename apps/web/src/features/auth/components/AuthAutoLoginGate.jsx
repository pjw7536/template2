// src/features/auth/components/AuthAutoLoginGate.jsx
// 전역적으로 "로그인되지 않았다면 즉시 SSO 로그인"을 시도하는 가드 레이아웃입니다.
// - 모든 라우트 위에 배치해 어디서 진입해도 동일한 경험을 제공합니다.

import { useEffect, useMemo, useRef } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { useAuth } from "../hooks/useAuth"

export function AuthAutoLoginGate() {
  const { user, isLoading, login, config } = useAuth()
  const location = useLocation()
  const autoLoginTriggeredRef = useRef(false)

  // 현재 경로 + 쿼리를 next 파라미터로 사용해 돌아올 위치를 보존합니다.
  const nextPath = useMemo(() => {
    const basePath = location?.pathname || "/"
    const search = location?.search || ""
    return `${basePath}${search}`
  }, [location])

  useEffect(() => {
    if (autoLoginTriggeredRef.current) return
    if (isLoading) return
    if (user) return
    if (config?.providerConfigured === false) return

    autoLoginTriggeredRef.current = true
    login({ next: nextPath })
  }, [config?.providerConfigured, isLoading, login, nextPath, user])

  return <Outlet />
}
