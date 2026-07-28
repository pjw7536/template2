import { MessageSquare } from "lucide-react"
import { Outlet } from "react-router-dom"

import { AppLayout, AppSidebar } from "@/components/layout"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { RequireAuth, useAuth } from "@/lib/auth"
import { hasScopeRole } from "@/lib/access/scopeAccess"
import { DepartmentProvider } from "@/lib/affiliation"
import { APP_CATEGORIES } from "../utils/constants"
import { useVocBoardState } from "../hooks/useVocBoardState"

function VocAppCategoryNav({ appFilter, onSelectApp }) {
  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>앱 카테고리</SidebarGroupLabel>
      <SidebarGroupContent>
        <div className="flex flex-col gap-2">
          <p className="px-2 text-xs text-muted-foreground">
            앱을 선택하면 해당 VOC만 볼 수 있습니다.
          </p>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                type="button"
                isActive={!appFilter}
                onClick={() => onSelectApp(null)}
              >
                <span>전체</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            {APP_CATEGORIES.map((option) => {
              const isActive = appFilter === option.value
              return (
                <SidebarMenuItem key={option.value}>
                  <SidebarMenuButton
                    type="button"
                    isActive={isActive}
                    onClick={() => onSelectApp(option.value)}
                  >
                    <span>{option.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )
            })}
          </SidebarMenu>
        </div>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

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
            <span className="text-xs text-muted-foreground">앱 카테고리</span>
          </div>
        </div>
      )}
      nav={(
        <VocAppCategoryNav
          appFilter={boardState.appFilter}
          onSelectApp={boardState.selectAppFilter}
        />
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
