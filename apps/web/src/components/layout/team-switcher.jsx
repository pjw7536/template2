// src/components/layout/team-switcher.jsx
import * as React from "react"
import { ChevronsUpDown, Plus } from "lucide-react"
import { useLocation, useNavigate, useParams } from "react-router-dom"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"
import { useActiveLine } from "./active-line-context"

/* -----------------------------------------------------------------------------
 * 유틸: 라인 옵션/표기 처리
 * ---------------------------------------------------------------------------*/

/** 라인 ID를 문자열로 정규화 (null/undefined는 null 유지) */
function normalizeLineId(value) {
  if (value === null || value === undefined) return null
  return typeof value === "string" ? value : String(value)
}

/** 라벨에서 머리글자(이니셜) 추출: 'LINE-01' -> 'L1' 등 */
function getInitials(label) {
  if (!label) return "?"
  const parts = label.split(/[\s-_]+/).filter(Boolean)
  if (parts.length === 0) return label.slice(0, 2).toUpperCase()
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

/** 다양한 입력 형태(lines 배열 요소)를 { id, label, description }로 통일 */
function toLineOption(line) {
  if (!line) return null

  // 문자열만 넘어오면 label=id로 취급
  if (typeof line === "string") {
    const id = normalizeLineId(line)
    return id ? { id, label: line, description: "" } : null
  }

  // 객체 형태일 때: id/label/description 우선순위 지정
  const rawId = line.id ?? line.label ?? line.name
  const id = normalizeLineId(rawId)
  const label = line.label ?? line.name ?? id
  const description = line.description ?? ""
  if (!id || !label) return null
  return { id, label, description }
}

/** URL params에서 lineId 추출 (동적 라우트 /ESOP_Dashboard/.../:lineId) */
function getLineIdFromParams(params) {
  if (!params) return null
  const raw = params.lineId
  if (typeof raw === "string") return raw
  if (Array.isArray(raw)) return normalizeLineId(raw[0])
  return null
}

/** 현재 경로와 선택된 라인ID를 기반으로 이동할 경로를 생성 */
function buildNextPath({ pathname, newLineId, currentLineId }) {
  if (!pathname || !newLineId) return null

  const segments = pathname.split("/").filter(Boolean)
  if (segments.length === 0) return null

  const esopIndex = segments.indexOf("ESOP_Dashboard")
  if (esopIndex === -1) return null

  const currentIndex = currentLineId ? segments.lastIndexOf(currentLineId) : -1

  if (currentIndex !== -1) {
    const next = [...segments]
    next[currentIndex] = newLineId
    return `/${next.join("/")}`
  }

  // 라인 파라미터가 없으면 기본적으로 라인 랜딩으로 연결한다.
  return `/ESOP_Dashboard/${newLineId}`
}

/* -----------------------------------------------------------------------------
 * 컴포넌트
 * ---------------------------------------------------------------------------*/

/**
 * TeamSwitcher
 * - 사이드바 상단에서 "라인(팀)"을 전환하는 드롭다운
 * - 옵션이 없어도 항상 렌더링되며, 'Unknown'을 표시
 * - 우선순위(선택 라인 결정): 컨텍스트 값 > URL 파라미터 > 첫 옵션 > 'unknown'
 */
export function TeamSwitcher({ lines }) {
  const { isMobile } = useSidebar()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const params = useParams()
  const paramLineId = getLineIdFromParams(params)

  // 전역(컨텍스트)에서 현재 선택된 라인ID와 setter 획득
  const { lineId: ctxLineId, setLineId: setCtxLineId } = useActiveLine()

  // 1) 입력 받은 lines를 화면 렌더용 옵션 배열로 정규화
  const options = React.useMemo(() => {
    if (!Array.isArray(lines)) return []
    return lines.map(toLineOption).filter(Boolean)
  }, [lines])

  // 2) 옵션 유무 판단 + 폴백(Unknown) 정의
  const hasOptions = options.length > 0
  const UNKNOWN_ID = "unknown"
  const fallbackActiveLine = { id: UNKNOWN_ID, label: "Unknown", description: "" }

  // 3) 활성 라인ID 결정: 컨텍스트 > URL 파라미터 > 첫 옵션 > 'unknown'
  const activeLineId = React.useMemo(() => {
    if (ctxLineId) return ctxLineId
    if (paramLineId) return paramLineId
    if (hasOptions) return options[0].id
    return UNKNOWN_ID
  }, [ctxLineId, paramLineId, hasOptions, options])

  // 4) 활성 라인 객체 (라벨/설명 표시용) — 없으면 Unknown으로 대체
  const activeLine =
    options.find((o) => o.id === activeLineId) ?? (hasOptions ? options[0] : fallbackActiveLine)

  // 5) 활성 라인ID가 바뀌면 컨텍스트 동기화
  //    단, 'unknown'일 땐 굳이 전역 상태를 unknown으로 덮어쓰지 않음(노이즈 방지)
  React.useEffect(() => {
    if (activeLineId && activeLineId !== ctxLineId && activeLineId !== UNKNOWN_ID) {
      setCtxLineId(activeLineId)
    }
  }, [activeLineId, ctxLineId, setCtxLineId])

  // 6) 드롭다운에서 라인 선택 시 실행할 라우팅/상태 업데이트
  const handleSelect = React.useCallback(
    (nextId) => {
      // 선택 불가/중복/Unknown(폴백)일 때는 무시
      if (!nextId || nextId === activeLineId || nextId === UNKNOWN_ID) return

      // (a) 먼저 컨텍스트 갱신 → UI 즉시 반영
      setCtxLineId(nextId)

      // (b) 경로 재구성 후 이동
      const target = buildNextPath({
        pathname,
        newLineId: nextId,
        currentLineId: paramLineId,
      })
      if (target) {
        navigate(target)
      }
    },
    [activeLineId, paramLineId, pathname, navigate, setCtxLineId]
  )

  // ❗️이전에는 옵션이 없으면 `return null`로 렌더를 생략했는데,
  //    요구사항에 따라 항상 렌더링해야 하므로 제거했다.

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          {/* 트리거: 현재 활성 라인의 이니셜/라벨 표시 (항상 렌더링) */}
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              {/* 왼쪽 원형 배지: 이니셜 */}
              <div className="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg font-semibold">
                {getInitials(activeLine.label)}
              </div>

              {/* 가운데: 라벨 + 서브텍스트(설명) */}
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{activeLine.label}</span>
                {activeLine.description ? (
                  <span className="truncate text-xs text-muted-foreground">
                    {activeLine.description}
                  </span>
                ) : null}
              </div>

              {/* 오른쪽: 펼치기 아이콘 */}
              <ChevronsUpDown className="ml-auto" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>

          {/* 드롭다운 목록 */}
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            align="start"
            side={isMobile ? "bottom" : "right"}
            sideOffset={4}
          >
            <DropdownMenuLabel className="text-muted-foreground text-xs">
              Production Lines
            </DropdownMenuLabel>

            {/* 라인 목록: 옵션이 있으면 실제 목록, 없으면 Unknown 1개(비활성화) */}
            {hasOptions
              ? options.map((line) => {
                const isActive = line.id === activeLineId
                return (
                  <DropdownMenuItem
                    key={line.id}
                    className={cn(
                      "gap-2 p-2",
                      isActive && "bg-sidebar-accent/20 focus:bg-sidebar-accent/20"
                    )}
                    onSelect={() => handleSelect(line.id)}
                  >
                    {/* 좌측 작은 배지(이니셜) */}
                    <div className="flex size-6 items-center justify-center rounded-md border text-xs font-semibold">
                      {getInitials(line.label)}
                    </div>

                    {/* 라벨/설명 */}
                    <div className="flex flex-col">
                      <span>{line.label}</span>
                      {line.description ? (
                        <span className="text-muted-foreground text-xs">{line.description}</span>
                      ) : null}
                    </div>
                  </DropdownMenuItem>
                )
              })
              : (
                <DropdownMenuItem
                  key="__unknown__"
                  className="gap-2 p-2 opacity-70"
                  disabled
                >
                  <div className="flex size-6 items-center justify-center rounded-md border text-xs font-semibold">
                    {getInitials("Unknown")}
                  </div>
                  <div className="flex flex-col">
                    <span>Unknown</span>
                    <span className="text-muted-foreground text-xs">
                      사용할 라인 옵션이 없습니다.
                    </span>
                  </div>
                </DropdownMenuItem>
              )
            }

            {/* 추후 '라인 관리' 기능 연결 예정인 플레이스홀더 */}
            <DropdownMenuSeparator />
            <DropdownMenuItem className="gap-2 p-2" disabled>
              <div className="flex size-6 items-center justify-center rounded-md border bg-transparent">
                <Plus className="size-4" />
              </div>
              <div className="text-muted-foreground font-medium">Manage lines</div>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
