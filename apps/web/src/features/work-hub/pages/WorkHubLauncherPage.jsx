import { useEffect, useState } from "react"
import {
  AlertCircle,
  ArrowUpRight,
  ClipboardList,
  Database,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

import { useWorkHubContext } from "../hooks/useWorkHubContext"

const ROLE_LABELS = {
  viewer: "조회",
  member: "근무자",
  manager: "관리자",
}

function openGrist(launchUrl, onFailure, { replaceHistory = false } = {}) {
  try {
    if (replaceHistory) {
      window.location.replace(launchUrl)
    } else {
      window.location.assign(launchUrl)
    }
  } catch {
    onFailure("Grist 화면으로 이동하지 못했습니다. 아래 버튼으로 다시 시도해주세요.")
  }
}

function LauncherState({ icon: Icon, title, description, action }) {
  return (
    <Card className="mx-auto w-full max-w-3xl rounded-2xl shadow-none">
      <CardContent className="flex min-h-64 flex-col items-center justify-center gap-4 text-center">
        <div className="rounded-full bg-muted p-4 text-muted-foreground">
          <Icon className="size-8" aria-hidden="true" />
        </div>
        <div className="space-y-2">
          <h2 className="text-base font-semibold">{title}</h2>
          <p className="max-w-xl text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
        {action}
      </CardContent>
    </Card>
  )
}

function LoadingState() {
  return (
    <Card className="mx-auto w-full max-w-3xl rounded-2xl shadow-none">
      <CardContent className="space-y-4 p-6" aria-live="polite">
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <RefreshCw className="size-4 animate-spin" aria-hidden="true" />
          접근 가능한 설비 업무일지를 확인하고 있습니다.
        </div>
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </CardContent>
    </Card>
  )
}

export function WorkHubLauncherPage() {
  const contextQuery = useWorkHubContext()
  const [redirectError, setRedirectError] = useState("")
  const context = contextQuery.data
  const singleGroup = context?.mode === "single" ? context.groups?.[0] : null

  useEffect(() => {
    if (!singleGroup?.launch_url) return undefined
    const timer = window.setTimeout(() => {
      openGrist(singleGroup.launch_url, setRedirectError, { replaceHistory: true })
    }, 700)
    return () => window.clearTimeout(timer)
  }, [singleGroup?.launch_url])

  let content = null
  if (contextQuery.isPending) {
    content = <LoadingState />
  } else if (contextQuery.isError) {
    const denied = contextQuery.error?.status === 403
    content = (
      <LauncherState
        icon={AlertCircle}
        title={denied ? "Work Hub 접근 권한이 없습니다" : "Work Hub 정보를 불러오지 못했습니다"}
        description={
          denied
            ? "Portal 설정에서 설비 업무일지 앱 접근 승인을 확인해주세요."
            : "기존 Portal 기능은 정상적으로 사용할 수 있습니다. 잠시 후 다시 시도해주세요."
        }
        action={
          <Button variant="outline" onClick={() => contextQuery.refetch()}>
            <RefreshCw /> 다시 시도
          </Button>
        }
      />
    )
  } else if (!context?.enabled) {
    content = (
      <LauncherState
        icon={ShieldCheck}
        title="설비 업무일지가 비활성화되어 있습니다"
        description="현재 환경의 Work Hub 기능 플래그가 꺼져 있습니다. 기존 Portal 데이터에는 영향이 없습니다."
      />
    )
  } else if (!context?.available || !context.groups?.length) {
    content = (
      <LauncherState
        icon={Database}
        title="연결된 Grist 업무일지가 없습니다"
        description="현재 소속에 활성 Grist document mapping이 없습니다. 관리자에게 그룹 연결 상태를 확인해주세요."
        action={
          <Button variant="outline" onClick={() => contextQuery.refetch()}>
            <RefreshCw /> 연결 상태 새로고침
          </Button>
        }
      />
    )
  } else if (singleGroup) {
    content = (
      <LauncherState
        icon={ClipboardList}
        title={`${singleGroup.user_sdwt_prod} 업무일지로 이동합니다`}
        description={
          redirectError ||
          "Grist OSS의 실시간 공동편집 화면을 새 최상위 페이지에서 엽니다. 자동 이동하지 않으면 버튼을 눌러주세요."
        }
        action={
          <Button onClick={() => openGrist(singleGroup.launch_url, setRedirectError)}>
            업무일지 열기 <ArrowUpRight />
          </Button>
        }
      />
    )
  } else {
    content = (
      <div className="grid grid-cols-2 gap-4">
        {context.groups.map((group) => (
          <Card key={group.user_sdwt_prod} className="rounded-2xl shadow-none">
            <CardHeader className="border-b">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <CardTitle className="text-base">{group.user_sdwt_prod}</CardTitle>
                  <CardDescription>{group.department} · {group.line}</CardDescription>
                </div>
                <Badge variant="secondary">{ROLE_LABELS[group.role] || group.role}</Badge>
              </div>
            </CardHeader>
            <CardContent className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Users className="size-4" aria-hidden="true" />
                그룹 공동편집
              </div>
              <Button onClick={() => openGrist(group.launch_url, setRedirectError)}>
                열기 <ArrowUpRight />
              </Button>
            </CardContent>
          </Card>
        ))}
        {redirectError ? (
          <p className="col-span-2 text-sm text-destructive" role="alert">{redirectError}</p>
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="shrink-0 px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight">설비 업무일지</h1>
            <p className="text-sm text-muted-foreground">
              Shift 업무일지와 후속 조치 Task를 Grist OSS에서 함께 기록합니다.
            </p>
          </div>
          <Badge variant="outline">Grist OSS Work Hub</Badge>
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto px-6 pb-6">
        {content}
      </main>
    </div>
  )
}
