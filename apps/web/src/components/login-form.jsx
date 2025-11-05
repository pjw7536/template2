"use client"

import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"

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
  const router = useRouter()
  const { login, config } = useAuth()
  const searchParams = useSearchParams()
  const nextPath = searchParams?.get("next") || "/"

  const handleLogin = async () => {
    try {
      setIsLoading(true)
      const result = await login({ next: nextPath })
      if (result?.method === "dev") {
        router.push(nextPath || "/")
      }
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
            disabled={isLoading}
          >
            {isLoading
              ? "Signing in..."
              : config?.devLoginEnabled
                ? "Development login"
                : "SSO login"}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
