import { Ban, Eye, RefreshCw, RotateCcw, Search, ShieldCheck, UserRound } from "lucide-react"
import { memo, useCallback, useEffect, useRef, useState } from "react"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cellState, LEVEL_LABELS, planChange } from "@/lib/access"
import { applyChange, listUsers, loadAccess } from "@/lib/api"
import { attr, displayName } from "@/lib/users"
import UserPanel from "./UserPanel"

/** Portal 권한 매트릭스(features/account/components/ScopePermissionMatrix.jsx)와 같은 형식입니다. */

const NONE = "none"
const LEVEL_ICONS = { viewer: Eye, user: UserRound, admin: ShieldCheck }
const SOURCE_LABELS = { direct: "직접 부여", inherited: "SDWT·기본·묶음 역할", none: "권한 없음", unavailable: "앱 없음" }

function describe(column, state) {
  if (state.source === "unavailable") return "Keycloak에 이 앱 client가 없습니다. 카탈로그 반영을 확인하세요."
  if (column.group) return state.level ? "그룹에 가입해 관리자 권한이 있습니다." : "그룹에 가입하지 않았습니다."
  if (state.source === "direct") return "이 사용자에게 직접 부여한 역할입니다."
  if (state.source === "inherited") {
    return state.direct
      ? `직접 부여(${LEVEL_LABELS[state.direct]})보다 높은 권한을 SDWT·기본·묶음 역할로 받습니다.`
      : "SDWT 앱 역할, 기본 역할 또는 Portal 전체 역할로 받습니다. 여기서 직접 권한을 빼도 유지됩니다."
  }
  return column.closed ? "닫힌 앱이라 부여받은 사람만 사용할 수 있습니다." : "부여된 역할이 없습니다."
}

function AccessDetails({ column, state }) {
  const allowed = Boolean(state.level)
  return (
    <div className="grid w-full gap-3 text-xs text-popover-foreground">
      <div className="truncate text-sm font-semibold text-foreground" title={column.label}>{column.label}</div>
      <div className="grid gap-2 rounded-md border bg-muted/30 p-3">
        <div className="flex items-center justify-between gap-3">
          <span className="inline-flex items-center gap-2 text-sm font-semibold">
            <span aria-hidden="true" className={`size-2 rounded-full ${allowed ? "bg-chart-2" : "bg-muted-foreground"}`} />
            {allowed ? "접근 가능" : "접근 불가"}
          </span>
          <Badge variant="outline" className="h-5 shrink-0 px-1.5 text-[10px]">
            {allowed ? LEVEL_LABELS[state.level] : "권한 없음"}
          </Badge>
        </div>
        <p className="leading-5 text-muted-foreground">{describe(column, state)}</p>
      </div>
    </div>
  )
}

const CHOICE_CLASS =
  "justify-center gap-1.5 px-2 py-2 pl-2 text-xs data-[state=checked]:bg-accent data-[state=checked]:font-medium [&>span]:hidden"

const PermissionCell = memo(function PermissionCell({ user, column, access, onChange, isPending }) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(null)
  const state = cellState(column, access)
  const current = state.direct ?? NONE
  const selected = draft ?? current
  const changed = selected !== current
  const allowed = Boolean(state.level)
  const disabled = state.source === "unavailable" || isPending
  const summary = `${allowed ? "접근 가능" : "접근 불가"}, ${allowed ? LEVEL_LABELS[state.level] : "권한 없음"}, ${SOURCE_LABELS[state.source]}`

  return (
    <div className="flex w-16 min-w-16 max-w-16 items-center justify-center overflow-visible">
      <DropdownMenu
        open={open}
        onOpenChange={(next) => {
          setOpen(next)
          setDraft(next ? current : null)
        }}
      >
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="relative inline-flex size-8 items-center justify-center rounded-md bg-background transition hover:bg-accent hover:text-accent-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
            aria-label={`${displayName(user)} ${column.label} 권한, ${summary}. 권한 상세 및 변경 메뉴 열기`}
          >
            {isPending ? (
              <RefreshCw className="size-3.5 animate-spin" />
            ) : (
              <>
                <span
                  aria-hidden="true"
                  className={`block size-3.5 rounded-full shadow-sm transition ${
                    state.source === "unavailable" ? "bg-muted" : allowed ? "bg-chart-2" : "bg-muted-foreground dark:bg-muted"
                  } ${state.source === "direct" ? "border-2 border-foreground/50 dark:border-foreground" : ""}`}
                />
                {state.level === "admin" ? (
                  <span aria-hidden="true" className="absolute bottom-0 left-1/2 -translate-x-1/2 text-[8px] font-semibold leading-none tracking-tight text-muted-foreground">
                    ADMIN
                  </span>
                ) : null}
              </>
            )}
            <span className="sr-only">{summary}</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <div className="p-3">
            <AccessDetails column={column} state={state} />
          </div>
          <DropdownMenuSeparator />
          {disabled ? (
            <div className="px-3 py-2 text-xs text-muted-foreground">
              {isPending ? "권한 변경을 처리하고 있습니다." : "이 권한은 여기서 변경할 수 없습니다."}
            </div>
          ) : (
            <>
              <DropdownMenuLabel className="px-3 py-1.5 text-xs text-muted-foreground">직접 부여 변경</DropdownMenuLabel>
              <DropdownMenuRadioGroup value={selected} onValueChange={setDraft} className={`grid gap-1 p-1 ${column.group ? "grid-cols-1" : "grid-cols-3"}`}>
                {column.levels.map((level) => {
                  const Icon = LEVEL_ICONS[level]
                  return (
                    <DropdownMenuRadioItem
                      key={level}
                      value={level}
                      className={`${CHOICE_CLASS} ${level === "user" ? "text-chart-2" : ""}`}
                      onSelect={(event) => event.preventDefault()}
                    >
                      <Icon className="size-3.5" />
                      {LEVEL_LABELS[level]}
                    </DropdownMenuRadioItem>
                  )
                })}
              </DropdownMenuRadioGroup>
              <DropdownMenuSeparator />
              <DropdownMenuRadioGroup value={selected} onValueChange={setDraft}>
                <DropdownMenuRadioItem
                  value={NONE}
                  className="mx-1 justify-center gap-1.5 px-2 py-2 pl-2 text-xs text-destructive focus:bg-destructive/10 focus:text-destructive data-[state=checked]:bg-destructive/10 data-[state=checked]:font-medium [&>span]:hidden"
                  onSelect={(event) => event.preventDefault()}
                >
                  <Ban className="size-3.5" />
                  {column.group ? "그룹에서 제외" : "직접 부여 없음"}
                </DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
              {selected === NONE && state.source === "inherited" && !column.group ? (
                <p className="px-3 py-1.5 text-xs text-muted-foreground">SDWT·기본·묶음 역할로 받은 권한은 유지됩니다.</p>
              ) : null}
              <DropdownMenuSeparator />
              <div className="p-1">
                <Button
                  type="button"
                  size="sm"
                  className="w-full"
                  disabled={!changed}
                  onClick={() => {
                    if (column.infra && !window.confirm(`${column.label}은 인프라(클러스터) 관리 권한입니다. 변경할까요?`)) return
                    setOpen(false)
                    onChange(user, column, { level: selected === NONE ? null : selected })
                  }}
                >
                  권한 변경
                </Button>
              </div>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
})

const columnClass = "w-20 min-w-20 max-w-20"

export default function PermissionsPage({ columns, org, orgUuid }) {
  const [draft, setDraft] = useState({ search: "", department: "" })
  const [filters, setFilters] = useState({ search: "", department: "" })
  const [rows, setRows] = useState([])
  const [status, setStatus] = useState("loading")
  const [hasMore, setHasMore] = useState(false)
  const [pendingCell, setPendingCell] = useState("")
  const [message, setMessage] = useState("")
  const [selectedId, setSelectedId] = useState(null)
  const loadingRef = useRef(false)
  const clients = [...new Map(columns.filter((column) => column.client && column.uuid).map((column) => [column.client, { client: column.client, uuid: column.uuid }])).values()]
  const clientsKey = clients.map((item) => item.uuid).join(",")

  const load = useCallback(async (first, reset) => {
    if (loadingRef.current) return
    loadingRef.current = true
    setStatus(reset ? "loading" : "more")
    try {
      const users = await listUsers({ ...filters, first })
      const loaded = await Promise.all(users.map(async (user) => ({ user, access: await loadAccess(user.id, clients) })))
      setRows((current) => (reset ? loaded : [...current, ...loaded]))
      setHasMore(users.length === 50)
      setStatus("ready")
    } catch (error) {
      setMessage(error.message)
      setStatus("error")
    } finally {
      loadingRef.current = false
    }
    // clients는 카탈로그에서 정해지며 clientsKey로 변경을 감지합니다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, clientsKey])

  useEffect(() => {
    load(0, true)
  }, [load])

  const refreshRow = async (userId) => {
    const access = await loadAccess(userId, clients)
    setRows((current) => current.map((row) => (row.user.id === userId ? { ...row, access } : row)))
  }

  const onChange = async (user, column, choice) => {
    setPendingCell(`${user.id}:${column.key}`)
    setMessage("")
    const access = rows.find((row) => row.user.id === user.id)?.access
    try {
      await applyChange(user.id, column, planChange(column, access, choice), access)
    } catch (error) {
      setMessage(error.message)
    } finally {
      await refreshRow(user.id).catch(() => {})
      setPendingCell("")
    }
  }

  const selected = rows.find((row) => row.user.id === selectedId)?.user

  return (
    <div className="grid h-full min-h-0 grid-cols-[minmax(0,1fr)_auto] gap-4">
      <Card className="grid h-full min-h-0 min-w-0 grid-rows-[auto_auto_minmax(0,1fr)] gap-0 overflow-hidden py-0">
        <form
          className="grid grid-cols-[240px_240px_auto] items-end gap-3 border-b px-4 py-3"
          onSubmit={(event) => {
            event.preventDefault()
            setFilters({ ...draft })
          }}
        >
          <div className="grid min-w-0 gap-1.5">
            <Label htmlFor="iam-user-search">사용자</Label>
            <Input id="iam-user-search" value={draft.search} placeholder="EPID, 이름, 이메일"
              onChange={(event) => setDraft((current) => ({ ...current, search: event.target.value }))} />
          </div>
          <div className="grid min-w-0 gap-1.5">
            <Label htmlFor="iam-department-search">팀(부서)</Label>
            <Input id="iam-department-search" value={draft.department} placeholder="정확한 팀(부서)명"
              onChange={(event) => setDraft((current) => ({ ...current, department: event.target.value }))} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={status === "loading"}>
              <Search className="size-4" />
              검색
            </Button>
            <Button type="button" variant="outline" disabled={!draft.search && !draft.department && !filters.search && !filters.department}
              onClick={() => {
                setDraft({ search: "", department: "" })
                setFilters({ search: "", department: "" })
              }}>
              <RotateCcw className="size-4" />
              초기화
            </Button>
          </div>
        </form>
        <div className="border-b px-4 py-2 text-xs text-muted-foreground">
          {message ? <span className="text-destructive">{message}</span> : "셀을 눌러 권한을 바꿉니다. 테두리가 있는 점은 직접 부여한 역할이고, 테두리가 없으면 SDWT 앱 역할·기본 역할·Portal 전체 역할로 받은 권한입니다. 이름을 누르면 소속·소속별 역할·세션을 관리합니다."}
        </div>
        <CardContent
          className="min-h-0 min-w-0 overflow-auto p-0"
          aria-busy={status !== "ready"}
          onScrollCapture={(event) => {
            const { scrollTop, scrollHeight, clientHeight } = event.target
            if (hasMore && status === "ready" && scrollHeight - scrollTop - clientHeight <= 96) load(rows.length, false)
          }}
        >
          {status === "loading" ? (
            <div className="grid gap-3 p-4">
              {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-14 w-full" />)}
            </div>
          ) : status === "error" && !rows.length ? (
            <div className="flex min-h-40 flex-col items-center justify-center gap-3 p-6" role="alert">
              <p className="text-sm text-destructive">권한 매트릭스를 불러오지 못했습니다.</p>
              <Button type="button" size="sm" variant="outline" onClick={() => load(0, true)}>
                <RefreshCw className="size-4" />
                다시 시도
              </Button>
            </div>
          ) : !rows.length ? (
            <div className="flex min-h-40 items-center justify-center p-6 text-sm text-muted-foreground">표시할 사용자가 없습니다.</div>
          ) : (
            <Table stickyHeader className="w-max min-w-full" aria-label="사용자별 앱 권한 매트릭스">
              <TableHeader>
                <TableRow className="h-12 bg-muted hover:bg-muted">
                  <TableHead className="sticky left-0 z-40 w-44 min-w-44 max-w-44 bg-muted px-2 text-center text-xs font-medium text-muted-foreground shadow-[inset_0_-1px_0_var(--border)]">이름</TableHead>
                  <TableHead className="sticky left-44 z-40 w-36 min-w-36 max-w-36 bg-muted px-2 text-center text-[11px] font-medium text-muted-foreground shadow-[inset_0_-1px_0_var(--border)]">로그인 ID</TableHead>
                  <TableHead className="sticky left-80 w-32 min-w-32 max-w-32 z-40 bg-muted px-2 text-center text-xs font-medium text-muted-foreground shadow-[inset_0_-1px_0_var(--border)]">팀(부서)</TableHead>
                  <TableHead className="sticky left-112 w-28 min-w-28 max-w-28 z-40 bg-muted px-2 text-center text-xs font-medium text-muted-foreground shadow-[inset_0_-1px_0_var(--border)]">라인</TableHead>
                  <TableHead className="sticky left-140 w-32 min-w-32 max-w-32 border-r z-40 bg-muted px-2 text-center text-xs font-medium text-muted-foreground shadow-[inset_0_-1px_0_var(--border)]">SDWT</TableHead>
                  {columns.map((app) => (
                    <TableHead key={app.key} className={`z-30 ${columnClass} bg-muted px-1 text-center align-middle shadow-[inset_0_-1px_0_var(--border)]`}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span tabIndex={0} title={app.label} className="mx-auto block max-w-16 truncate rounded-sm whitespace-nowrap text-xs font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring">
                            {app.label}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="top">
                          {app.group ? `그룹 ${app.group}` : `${app.client} 역할 ${app.roles.viewer.replace(/viewer$/, "*")}${app.closed ? " · 닫힌 앱" : ""}`}
                        </TooltipContent>
                      </Tooltip>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(({ user, access }) => {
                  const sdwt = attr(user, "user_sdwt_prod")
                  return (
                    <TableRow key={user.id} className={`group h-12 hover:bg-muted/40 ${selectedId === user.id ? "bg-muted/60" : ""}`}>
                      <TableCell className="sticky left-0 z-20 w-44 min-w-44 max-w-44 overflow-hidden bg-card px-2 py-2 text-center group-hover:bg-muted">
                        <button type="button" onClick={() => setSelectedId(user.id)} className="block w-full truncate text-sm font-medium hover:underline" title={displayName(user)}>
                          {displayName(user)}
                        </button>
                      </TableCell>
                      <TableCell className="sticky left-44 z-20 w-36 min-w-36 max-w-36 overflow-hidden bg-card px-2 py-2 text-center group-hover:bg-muted">
                        <span className="block truncate text-sm" title={attr(user, "loginid")}>{attr(user, "loginid") || "-"}</span>
                      </TableCell>
                      {[
                        ["deptname", "left-80 w-32 min-w-32 max-w-32"],
                        ["line_id", "left-112 w-28 min-w-28 max-w-28"],
                        ["user_sdwt_prod", "left-140 w-32 min-w-32 max-w-32 border-r"],
                      ].map(([key, position]) => (
                        <TableCell key={key} className={`sticky ${position} z-20 overflow-hidden bg-card px-2 py-2 text-center group-hover:bg-muted`}>
                          <span className="block truncate text-sm text-muted-foreground" title={attr(user, key)}>
                            {key === "deptname" || sdwt ? attr(user, key) || "-" : "-"}
                          </span>
                        </TableCell>
                      ))}
                      {columns.map((app) => (
                        <TableCell key={app.key} className={`${columnClass} px-1 py-2 text-center ${app.bundle ? "bg-muted/30" : ""}`}>
                          <PermissionCell user={user} column={app} access={access} onChange={onChange}
                            isPending={pendingCell === `${user.id}:${app.key}`} />
                        </TableCell>
                      ))}
                    </TableRow>
                  )
                })}
                {status === "more" ? (
                  <TableRow className="h-12 hover:bg-transparent">
                    <TableCell colSpan={columns.length + 5} className="text-center text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-2">
                        <RefreshCw className="size-3.5 animate-spin" />
                        추가 사용자를 불러오는 중...
                      </span>
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      {selected ? (
        <UserPanel
          key={selected.id}
          user={selected}
          org={org}
          orgUuid={orgUuid}
          onClose={() => setSelectedId(null)}
          onSaved={(user) => {
            setRows((current) => current.map((row) => (row.user.id === user.id ? { ...row, user } : row)))
          }}
          onGroupsChanged={() => refreshRow(selected.id)}
        />
      ) : null}
    </div>
  )
}
