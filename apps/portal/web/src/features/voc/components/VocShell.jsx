import { MessageSquare } from "lucide-react"
import { Outlet } from "react-router-dom"

import { AppLayout, AppSidebar } from "@/components/layout"
import { RequireAuth, useAuth } from "@/lib/auth"
import { hasScopeRole } from "@/lib/access/scopeAccess"
import { DepartmentProvider } from "@/lib/affiliation"
import { useVocBoardState } from "../hooks/useVocBoardState"

export function VocShell() {
  const { user } = useAuth()
  const currentUserName = user?.username || user?.email || "로그인 사용자"
  const currentUser = {
    id: user?.id || user?.email || currentUserName,
    name: currentUserName,
  }
  const isAdmin = hasScopeRole(user, "voc")

  const boardState = useVocBoardState({ currentUser, isAdmin })
  const sidebar = (
    <AppSidebar
      header={(
        <div className="flex items-center gap-2 p-3">
          <div className="flex size-8 items-center justify-center rounded-md bg-primary/10 text-primary">
            <MessageSquare className="size-4" aria-hidden="true" />
          </div>
          <div className="flex flex-col group-data-[collapsible=icon]:hidden">
            <span className="text-sm font-semibold">VOC 게시판</span>
            <span className="text-xs text-muted-foreground">문의와 답변</span>
          </div>
        </div>
      )}
    />
  )

  return (
    <RequireAuth>
      <DepartmentProvider>
        <AppLayout sidebar={sidebar} scrollAreaClassName="overflow-hidden">
          <Outlet context={boardState} />
        </AppLayout>
      </DepartmentProvider>
    </RequireAuth>
  )
}
