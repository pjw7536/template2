"use client"

import { useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useAuth } from "@/components/auth"

export function LoginForm({
  className,
  ...props
}) {
  const [isLoading, setIsLoading] = useState(false)
  const { login, config } = useAuth()
  const searchParams = useSearchParams()
  const nextPath = searchParams?.get("next") || "/"
  const providerAvailable = useMemo(() => config?.providerConfigured !== false, [config])

  const handleLogin = async () => {
    if (!providerAvailable) return
    try {
      setIsLoading(true)
      await login({ next: nextPath })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card>
        <CardHeader>
          <CardTitle>Single Sign-On</CardTitle>
          <CardDescription>
            회사 SSO를 통해 로그인하세요. 개발 환경에서는 테스트용 ADFS 제공자가 응답합니다.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            type="button"
            className="w-full"
            onClick={handleLogin}
            disabled={isLoading || !providerAvailable}
          >
            {isLoading
              ? "Signing in..."
              : "SSO login"}
          </Button>
          {!providerAvailable && (
            <p className="mt-2 text-sm text-muted-foreground">
              SSO 설정이 비활성화되어 있습니다. 관리자에게 문의하세요.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
