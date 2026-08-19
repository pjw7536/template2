// 파일 경로: src/features/line-dashboard/components/LineDashboardShell.jsx
import { useEffect, useState } from "react"
import { ServerCrash } from "lucide-react"
import { Outlet } from "react-router-dom"

import { TeamSwitcher } from "@/components/common"
import { AppShellLayout } from "@/components/layout"
import { Button } from "@/components/ui/button"
import { buildLineSwitcherOptions } from "@/features/account"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { RequireAuth, useAuth } from "@/lib/auth"
import { hasScopeRole } from "@/lib/access/scopeAccess"
import { buildNavigationConfig } from "@/lib/config/navigationConfig"
import {
  ActiveLineProvider,
  DepartmentProvider,
  useLineSwitcher,
} from "@/lib/affiliation"

import { NavProjects } from "./NavProjects"
import { useLineOptionsQuery } from "../hooks/useLineOptionsQuery"

export function LineDashboardShell({
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
}) {
  return (
    <RequireAuth>
      <LineDashboardShellContent
        contentMaxWidthClass={contentMaxWidthClass}
        scrollAreaClassName={scrollAreaClassName}
      />
    </RequireAuth>
  )
}

function LineDashboardShellContent({ contentMaxWidthClass, scrollAreaClassName }) {
  const { user } = useAuth()
  const {
    data: lineOptions = [],
    isError,
    error,
  } = useLineOptionsQuery({
    preferredUserSdwtProd:
      typeof user?.userSdwtProd === "string" ? user.userSdwtProd.trim() : "",
  })

  useEffect(() => {
    if (isError) {
      console.warn("Failed to load line options", error)
    }
  }, [isError, error])

  const navigation = buildNavigationConfig({
    adminScopes: hasScopeRole(user, "line-dashboard") ? ["line-dashboard"] : [],
  })

  return (
    <DepartmentProvider>
      <ActiveLineProvider lineOptions={lineOptions}>
        <LineDashboardShellLayout
          navigation={navigation}
          lineOptions={lineOptions}
          contentMaxWidthClass={contentMaxWidthClass}
          scrollAreaClassName={scrollAreaClassName}
        />
      </ActiveLineProvider>
    </DepartmentProvider>
  )
}

function LineDashboardShellLayout({ navigation, lineOptions, contentMaxWidthClass, scrollAreaClassName }) {
  const [isNoticeOpen, setIsNoticeOpen] = useState(false)
  const { activeLineId, onSelect } = useLineSwitcher()
  const lineSwitcherOptions = buildLineSwitcherOptions(lineOptions)

  return (
    <>
      <AppShellLayout
        navItems={navigation.navMain}
        sidebarHeader={(
          <TeamSwitcher
            options={lineSwitcherOptions}
            activeId={activeLineId}
            onSelect={onSelect}
          />
        )}
        sidebarSecondary={<NavProjects projects={navigation.projects} />}
        contentMaxWidthClass={contentMaxWidthClass}
        scrollAreaClassName={scrollAreaClassName}
      >
        <Outlet />
      </AppShellLayout>

      <Dialog open={isNoticeOpen} onOpenChange={setIsNoticeOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="mb-2 flex size-10 items-center justify-center rounded-full bg-muted">
              <ServerCrash className="size-5 text-destructive" aria-hidden="true" />
            </div>
            <DialogTitle>ESOP Dashboard 서비스 일시 중단 안내</DialogTitle>
            <DialogDescription className="space-y-2 leading-6">
              <span className="block">
                현재 서버 과부하로 인해 ESOP Dashboard 서비스 운영을 당분간 중단할 예정입니다.
              </span>
              <span className="block">
                빠른 시일 내에 더 안정적인 다른 방법으로 서비스를 제공할 수 있도록 준비하겠습니다.
                이용에 불편을 드려 죄송합니다.
              </span>
              <span className="block border-t border-border pt-3 text-xs">
                담당자: 박진우 (jw0509.park)
              </span>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" onClick={() => setIsNoticeOpen(false)}>
              확인
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
