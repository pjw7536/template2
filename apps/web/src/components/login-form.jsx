"use client"

import { useEffect, useMemo, useState } from "react"
import { getProviders, signIn } from "next-auth/react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export function LoginForm({
  className,
  ...props
}) {
  const [isLoading, setIsLoading] = useState(false)
  const [providers, setProviders] = useState(null)

  useEffect(() => {
    let isMounted = true
    getProviders()
      .then((available) => {
        if (isMounted) {
          setProviders(available)
        }
      })
      .catch(() => {
        if (isMounted) {
          setProviders(null)
        }
      })
    return () => {
      isMounted = false
    }
  }, [])

  const primaryProviderId = useMemo(() => {
    if (providers?.oidc) return "oidc"
    if (providers?.dummy) return "dummy"
    return "dummy"
  }, [providers])

  const handleLogin = async () => {
    try {
      setIsLoading(true)
      await signIn(primaryProviderId, { callbackUrl: "/" })
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
            회사 SSO를 통해 로그인하세요. 개발 환경에서는 더미 계정으로 로그인합니다.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            type="button"
            className="w-full"
            onClick={handleLogin}
            disabled={isLoading || !primaryProviderId}
          >
            {isLoading ? "Signing in..." : "SSO login"}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
