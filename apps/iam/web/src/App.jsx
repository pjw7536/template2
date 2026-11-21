import { useCallback, useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { buildColumns } from "@/lib/access"
import { loadCatalog, loadOrgRoot } from "@/lib/api"
import { canManageUsers, keycloak, realm } from "@/lib/keycloak"
import { buildOrg } from "@/lib/plan"
import { cn } from "@/lib/utils"
import OrgPage from "./pages/OrgPage"
import PermissionsPage from "./pages/PermissionsPage"
import UploadPage from "./pages/UploadPage"
import WorkloadPage from "./pages/WorkloadPage"

const TABS = [
  ["permissions", "권한"],
  ["org", "조직"],
  ["workload", "업무 부하"],
  ["upload", "소속 업로드"],
]
const TAB_KEYS = TABS.map(([key]) => key)

export default function App() {
  const allowed = canManageUsers()
  const { display_name: displayName, loginid: loginId } = keycloak.idTokenParsed ?? {}
  const profileLabel = displayName && loginId ? `${displayName}(${loginId})` : displayName || loginId
  const [tab, setTab] = useState(() => (TAB_KEYS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "permissions"))
  const [orgRoot, setOrgRoot] = useState(undefined)
  const [orgUuid, setOrgUuid] = useState("")
  const [columns, setColumns] = useState([])
  const [error, setError] = useState("")
  const org = useMemo(() => buildOrg(orgRoot), [orgRoot])

  const reload = useCallback(async () => {
    try {
      // 앱 열은 Keycloak /iam 그룹의 카탈로그에서 읽으므로 앱이 추가돼도 웹을 다시 배포하지 않습니다.
      const [nextRoot, catalog] = await Promise.all([loadOrgRoot(), loadCatalog()])
      // 소속별 역할(client org)의 uuid도 카탈로그로 받습니다. 웹 토큰은 client 목록을 볼 수 없습니다.
      if (!catalog.org?.uuid) throw new Error("카탈로그에 소속별 역할(client org) 정보가 없습니다. make keycloak-org-sync 후 make keycloak-access-apply를 실행하세요.")
      setColumns(buildColumns(catalog))
      setOrgUuid(catalog.org.uuid)
      setOrgRoot(nextRoot)
      setError("")
    } catch (failure) {
      setError(failure.message)
    }
  }, [])

  useEffect(() => {
    if (allowed) reload()
  }, [allowed, reload])

  const select = (key) => {
    setTab(key)
    history.replaceState(null, "", `#${key}`)
  }

  return (
    // 너비별 배치 변경 없이 데스크톱 배치를 유지합니다. 창이 좁으면 가로 스크롤됩니다.
    <div className="flex h-screen min-h-0 min-w-[1280px] flex-col bg-background">
      <header className="flex shrink-0 flex-wrap items-center gap-4 border-b px-6 py-3">
        <h1 className="text-lg font-semibold tracking-tight">Etch Members</h1>
        <span className="text-xs text-muted-foreground">realm {realm}</span>
        {allowed ? (
          <nav className="flex gap-1" aria-label="화면">
            {TABS.map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => select(key)}
                aria-current={tab === key ? "page" : undefined}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  tab === key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                {label}
              </button>
            ))}
          </nav>
        ) : null}
        <span className="ml-auto text-sm text-muted-foreground">{profileLabel}</span>
        <Button variant="outline" size="sm" onClick={() => keycloak.logout({ redirectUri: location.origin })}>로그아웃</Button>
      </header>
      <main className="min-h-0 flex-1 overflow-auto px-6 py-4">
        {!allowed ? (
          <p role="alert" className="rounded-md border border-destructive/30 px-3 py-2 text-sm text-destructive">
            Etch Members를 사용할 권한이 없습니다. 운영 담당자에게 플랫폼 관리자 등록을 요청한 뒤 다시 로그인하세요.
          </p>
        ) : error ? (
          <p role="alert" className="rounded-md border border-destructive/30 px-3 py-2 text-sm text-destructive">{error}</p>
        ) : orgRoot === undefined ? (
          <p role="status" className="text-sm text-muted-foreground">불러오는 중…</p>
        ) : tab === "permissions" ? (
          <PermissionsPage columns={columns} org={org} orgUuid={orgUuid} />
        ) : tab === "org" ? (
          <OrgPage orgRoot={orgRoot} org={org} orgUuid={orgUuid} reload={reload} />
        ) : tab === "workload" ? (
          <WorkloadPage org={org} />
        ) : (
          <UploadPage org={org} />
        )}
      </main>
    </div>
  )
}
