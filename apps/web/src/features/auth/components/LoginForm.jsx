"use client"

// src/features/auth/components/LoginForm.jsx
// 로그인 화면에서 사용하는 폼 UI와 상호작용 로직을 담당합니다.
// - 상태/비즈니스 로직은 useAuth 훅에서 받아오고, 여기서는 UI에만 집중합니다.

import { useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldSeparator,
} from "@/components/ui/field"

import { useAuth } from "../hooks/useAuth"

export function LoginForm({
  className,
  ...props
}) {
  const [isLoading, setIsLoading] = useState(false)
  const { login, config } = useAuth()
  const [searchParams] = useSearchParams()
  const nextPath = searchParams?.get("next") || "/"

  // provider 설정이 없는 경우를 대비해 버튼을 비활성화합니다.
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
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Welcome back</CardTitle>
          <CardDescription>Login with SSO</CardDescription>
        </CardHeader>
        <CardContent>
          <form>
            <FieldGroup>
              <Field>
                <FieldLabel className="sr-only">SSO 로그인</FieldLabel>
                <Button
                  variant="outline"
                  type="button"
                  onClick={handleLogin}
                  disabled={isLoading || !providerAvailable}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                    <path
                      d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701"
                      fill="currentColor"
                    />
                  </svg>
                  Login with SSO
                </Button>
              </Field>
              <FieldSeparator className="sr-only" />
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
      <FieldDescription className="px-6 text-center">
        By clicking continue, you agree to our <a href="#">Terms of Service</a>{" "}
        and <a href="#">Privacy Policy</a>.
      </FieldDescription>
    </div>
  )
}
