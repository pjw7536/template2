import { useLocation } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { getScopeAccess } from "@/lib/access/scopeAccess"
import { useAuth } from "../hooks/useAuth"

export function PortalAccessGate({ children, allowUnapprovedPaths = [] }) {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()
  if (!user) return null
  const path = pathname.replace(/\/+$/, "")
  if (getScopeAccess(user, "portal")?.allowed || allowUnapprovedPaths.some((value) => value.replace(/\/+$/, "") === path)) return children
  return (
    <div className="flex h-full min-h-0 items-center justify-center overflow-y-auto px-6 py-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Portal 접근 권한이 없습니다</CardTitle>
          <CardDescription>관리자에게 메일이나 메신저로 필요한 앱의 접근 권한을 요청하세요.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">권한이 부여되면 로그아웃 후 다시 로그인하세요.</CardContent>
        <CardFooter><Button onClick={logout} variant="outline">로그아웃</Button></CardFooter>
      </Card>
    </div>
  )
}
