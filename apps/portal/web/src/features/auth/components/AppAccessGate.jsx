import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { getScopeAccess } from "@/lib/access/scopeAccess"
import { useAuth } from "../hooks/useAuth"

export function AppAccessGate({ children, scopeKey, appName }) {
  const { user, logout } = useAuth()
  if (!user) return null
  if (getScopeAccess(user, scopeKey)?.allowed) return children
  return (
    <div className="flex h-full min-h-0 items-center justify-center overflow-y-auto px-6 py-4">
      <Card className="w-full max-w-md">
        <CardHeader><CardTitle>{appName || scopeKey} 접근 권한이 없습니다</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground">관리자에게 메일이나 메신저로 앱 접근을 요청하세요. 권한 변경은 다시 로그인하면 반영됩니다.</CardContent>
        <CardFooter className="gap-2">
          <Button asChild variant="outline"><Link to="/">홈으로</Link></Button>
          <Button onClick={logout} variant="outline">로그아웃</Button>
        </CardFooter>
      </Card>
    </div>
  )
}
