// src/features/line-dashboard/components/data-table/filters/QuickFilters.jsx
import * as React from "react"
import { IconChevronDown } from "@tabler/icons-react"
import { toast } from "sonner"
import { BookmarkCheck, BookmarkPlus, BookmarkX } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Slider } from "@/components/ui/slider"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { GlobalFilter } from "./GlobalFilter"
import {
  clampRecentHours,
  createRecentHoursRange,
  isMultiSelectFilter,
  normalizeRecentHoursRange,
  RECENT_HOURS_MAX,
  RECENT_HOURS_MIN,
} from "./quickFilters"
import { buildToastOptions } from "../utils/toast"

const DROPDOWN_SECTION_KEYS = new Set([
  "sdwt_prod",
  "sample_type",
  "sample_group",
  "user_sdwt_prod",
  "main_step",
])
const CHECKBOX_SECTION_KEYS = new Set(["my_sop"])
const FIELDSET_CLASS = "flex flex-col rounded-xl px-2"

const isNil = (value) => value === null || value === undefined

function buildDefaultFavoriteName() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, "0")
  const day = String(now.getDate()).padStart(2, "0")
  const hours = String(now.getHours()).padStart(2, "0")
  const minutes = String(now.getMinutes()).padStart(2, "0")
  return `Bookmark_${month}/${day}_${hours}:${minutes}`
}

// 여러 퀵 필터 섹션과 글로벌 검색창을 한 번에 그려주는 컴포넌트입니다.
export function QuickFilters({
  sections,
  filters,
  onToggle,
  onClear,
  activeCount,
  globalFilterValue,
  onGlobalFilterChange,
  globalFilterPlaceholder = "Search rows",
  statusSidebar = null,
}) {
  const hasSections = sections.length > 0
  const showGlobalFilter = typeof onGlobalFilterChange === "function"
  const showContainer = hasSections || showGlobalFilter
  const hasGlobalValue = showGlobalFilter && Boolean(globalFilterValue)
  const [isCollapsed, setIsCollapsed] = React.useState(false)

  const handleToggleCollapse = () => setIsCollapsed((previous) => !previous)

  const handleClearAll = () => {
    onClear?.()
    if (showGlobalFilter) onGlobalFilterChange?.("")
  }

  if (!showContainer) return null

  // ✅ 섹션 블록들(각 fieldset) 생성
  const sectionBlocks = sections.map((section) => {
    const isMulti = isMultiSelectFilter(section.key)
    const current = filters[section.key]
    const selectedValues = getSelectedValues(isMulti, current)
    const allSelected = isMulti ? selectedValues.length === 0 : isNil(current)
    const legendId = `legend-${section.key}`

    if (section.key === "recent_hours") {
      return (
        <RecentHoursQuickFilterSection
          key={section.key}
          section={section}
          legendId={legendId}
          current={current}
          onToggle={onToggle}
        />
      )
    }

    if (CHECKBOX_SECTION_KEYS.has(section.key)) {
      return (
        <CheckboxQuickFilterSection
          key={section.key}
          section={section}
          legendId={legendId}
          checked={Boolean(current)}
          onToggle={onToggle}
        />
      )
    }

    if (DROPDOWN_SECTION_KEYS.has(section.key)) {
      return (
        <DropdownQuickFilterSection
          key={section.key}
          section={section}
          legendId={legendId}
          current={current}
          isMulti={isMulti}
          selectedValues={selectedValues}
          onToggle={onToggle}
        />
      )
    }

    return (
      <ButtonQuickFilterSection
        key={section.key}
        section={section}
        legendId={legendId}
        allSelected={allSelected}
        selectedValues={selectedValues}
        onToggle={onToggle}
      />
    )
  })

  // ✅ 글로벌 필터도 “같은 줄의 섹션”으로 추가
  if (showGlobalFilter) {
    sectionBlocks.push(
      <fieldset
        key="__global__"
        className={FIELDSET_CLASS}
        aria-labelledby="legend-global-filter"
      >
        <legend
          id="legend-global-filter"
          className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground"
        >
          검색
        </legend>

        {/* 입력 너비를 버튼 그룹과 균형 잡히게 고정 폭 부여 */}
        <div className="w-52 sm:w-64 lg:w-80">
          <GlobalFilter
            value={globalFilterValue}
            onChange={onGlobalFilterChange}
            placeholder={globalFilterPlaceholder}
          />
        </div>
      </fieldset>
    )
  }

  return (
    <fieldset
      className={cn(
        "flex flex-col rounded-lg",            // 공통
        isCollapsed ? "px-3 border-0" : "gap-3 border p-3" // ⬅️ 접힘 상태일 때 테두리/패딩 제거
      )}
    >
      <legend className="flex items-center justify-between gap-3 px-1 text-xs font-semibold tracking-wide text-muted-foreground">
        <button
          type="button"
          onClick={handleToggleCollapse}
          aria-expanded={!isCollapsed}
          className="flex items-center gap-1 text-left text-xs font-semibold tracking-wide text-muted-foreground transition-colors hover:text-foreground"
        >
          <span>Quick Filters</span>
          <IconChevronDown
            aria-hidden
            className={cn(
              "size-4 transition-transform",
              !isCollapsed ? "-rotate-180" : "rotate-0"
            )}
          />
        </button>

        {(activeCount > 0 || hasGlobalValue) && (
          <button
            type="button"
            onClick={handleClearAll}
            className="flex items-center rounded-md  bg-background px-1 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            🧹필터초기화
          </button>
        )}
      </legend>


      {!isCollapsed && (
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
          {statusSidebar ? (
            <div className="w-full flex-shrink-0 lg:max-w-[200px]">{statusSidebar}</div>
          ) : null}
          <div className="flex flex-1 flex-wrap items-start gap-2">
            {sectionBlocks}
          </div>
        </div>
      )}
    </fieldset>
  )
}

export function QuickFilterFavorites({
  filters,
  favorites = [],
  onSaveFavorite,
  onUpdateFavorite,
  onApplyFavorite,
  onDeleteFavorite,
  resetSignal,
  className,
}) {
  const [selectedFavoriteId, setSelectedFavoriteId] = React.useState("")
  const hasMountedRef = React.useRef(false)
  const selectedFavorite = React.useMemo(
    () => favorites.find((favorite) => favorite.id === selectedFavoriteId),
    [favorites, selectedFavoriteId]
  )
  const hasFavoriteChanges = React.useMemo(
    () =>
      selectedFavorite
        ? !areFiltersEqual(filters, selectedFavorite.filters)
        : false,
    [filters, selectedFavorite]
  )

  React.useEffect(() => {
    if (!Array.isArray(favorites) || favorites.length === 0) {
      setSelectedFavoriteId("")
      return
    }

    if (!selectedFavoriteId) return

    const exists = favorites.some((favorite) => favorite.id === selectedFavoriteId)
    if (!exists) {
      setSelectedFavoriteId(favorites[0].id)
    }
  }, [favorites, selectedFavoriteId])

  React.useEffect(() => {
    if (!resetSignal) {
      hasMountedRef.current = true
      return
    }
    if (!hasMountedRef.current) {
      hasMountedRef.current = true
      return
    }
    setSelectedFavoriteId("")
  }, [resetSignal])

  const handleSelectFavorite = (favoriteId) => {
    setSelectedFavoriteId(favoriteId)
    if (!favoriteId || typeof onApplyFavorite !== "function") return
    onApplyFavorite(favoriteId)
  }

  const handleUpdateFavorite = () => {
    if (!selectedFavorite || !hasFavoriteChanges || typeof onUpdateFavorite !== "function")
      return
    const nextId = onUpdateFavorite(selectedFavorite.id, selectedFavorite.name)
    if (nextId) {
      setSelectedFavoriteId(nextId)
      toast.success("즐겨찾기를 업데이트했어요", {
        description: "현재 필터설정이 즐겨찾기에 저장되었습니다.",
        icon: <BookmarkCheck className="h-5 w-5" />,
        ...buildToastOptions({ color: "var(--primary)", duration: 1800 }),
      })
    }
  }

  const handleAddFavorite = (name) => {
    if (typeof onSaveFavorite !== "function") return
    const finalName = (name ?? "").trim() || buildDefaultFavoriteName()

    const normalizedName = finalName.toLowerCase()
    const isDuplicateName =
      Array.isArray(favorites) &&
      favorites.some((favorite) => {
        const favoriteName = typeof favorite?.name === "string" ? favorite.name.trim() : ""
        return favoriteName.toLowerCase() === normalizedName
      })

    if (isDuplicateName) {
      toast.error("중복된 즐겨찾기 이름이에요", {
        description: "다른 이름으로 저장해주세요.",
        icon: <BookmarkX className="h-5 w-5" />,
        ...buildToastOptions({ color: "var(--destructive)", duration: 2000 }),
      })
      return
    }

    const id = onSaveFavorite(finalName)
    if (id) {
      setSelectedFavoriteId(id)
      toast.success("즐겨찾기를 추가했어요", {
        description: "현재 필터설정이 새 즐겨찾기에 저장되었습니다.",
        icon: <BookmarkPlus className="h-5 w-5" />,
        ...buildToastOptions({ color: "var(--primary)", duration: 1800 }),
      })
    }
  }

  const handleDeleteFavorite = (favoriteId) => {
    onDeleteFavorite?.(favoriteId)
    if (favoriteId === selectedFavoriteId) {
      setSelectedFavoriteId("")
    }
  }

  const hasFavoriteActions =
    typeof onSaveFavorite === "function" ||
    typeof onApplyFavorite === "function" ||
    typeof onDeleteFavorite === "function"

  if (!hasFavoriteActions || !Array.isArray(favorites)) return null

  return (
    <FavoriteFiltersSection
      className={cn("min-w-[16rem]", className)}
      favorites={favorites}
      selectedId={selectedFavoriteId}
      onSelectFavorite={handleSelectFavorite}
      onUpdateFavorite={handleUpdateFavorite}
      showUpdateButton={hasFavoriteChanges}
      onDeleteFavorite={handleDeleteFavorite}
      onAddFavorite={handleAddFavorite}
      defaultFavoriteName={buildDefaultFavoriteName()}
    />
  )
}

function getSelectedValues(isMulti, current) {
  if (isMulti) {
    return Array.isArray(current) ? current : []
  }
  return isNil(current) ? [] : [current]
}

function CheckboxQuickFilterSection({ section, legendId, checked, onToggle }) {
  const inputId = `${section.key}-checkbox`

  return (
    <fieldset className={FIELDSET_CLASS} aria-labelledby={legendId}>
      <legend
        id={legendId}
        className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground"
      >
        {section.label}
      </legend>

      <label
        htmlFor={inputId}
        className="flex h-8 items-center gap-2 text-xs font-medium text-foreground"
      >
        <input
          id={inputId}
          type="checkbox"
          className="h-4 w-4 accent-primary"
          checked={checked}
          onChange={(event) =>
            onToggle(section.key, event.target.checked ? true : null, { forceValue: true })
          }
        />
        <div className="flex flex-col items-center justify-center leading-tight">
          {section.userId ? (
            <div className="text-[11px] font-normal text-muted-foreground">
              {section.userId}
            </div>
          ) : null}
        </div>
      </label>
    </fieldset>
  )
}

function DropdownQuickFilterSection({
  section,
  legendId,
  current,
  onToggle,
  isMulti,
  selectedValues,
}) {
  const resolvedSelectedValues = selectedValues ?? getSelectedValues(isMulti, current)

  if (isMulti) {
    const hasDropdownValue = resolvedSelectedValues.length > 0
    const displayValue =
      resolvedSelectedValues.length === 0
        ? "전체"
        : `${resolvedSelectedValues.length}개 선택`

    return (
      <fieldset className={FIELDSET_CLASS} aria-labelledby={legendId}>
        <legend
          id={legendId}
          className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground"
        >
          {section.label}
        </legend>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className={cn(
                "flex h-8 w-40 items-center justify-between rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring",
                hasDropdownValue && "border-primary bg-primary/10 text-primary"
              )}
            >
              <span className="truncate">{displayValue}</span>
              <IconChevronDown className="size-4 shrink-0" />
            </button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="start" className="w-40 p-1">
            <DropdownMenuItem
              className="text-xs"
              onSelect={(event) => {
                event.preventDefault()
                onToggle(section.key, null, { forceValue: true })
              }}
            >
              전체
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {section.options.map((option) => {
              const isChecked = resolvedSelectedValues.includes(option.value)
              return (
                <DropdownMenuCheckboxItem
                  key={`${section.key}-${String(option.value)}`}
                  checked={isChecked}
                  onCheckedChange={() => onToggle(section.key, option.value)}
                  onSelect={(event) => event.preventDefault()}
                  className={cn(
                    "text-xs",
                    "data-[state=checked]:bg-primary/10 data-[state=checked]:text-primary"
                  )}
                >
                  {option.label}
                </DropdownMenuCheckboxItem>
              )
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      </fieldset>
    )
  }

  const hasDropdownValue = !isNil(current) && String(current).length > 0

  const handleChange = (event) => {
    onToggle(section.key, event.target.value || null)
  }

  return (
    <fieldset className={FIELDSET_CLASS} aria-labelledby={legendId}>
      <legend
        id={legendId}
        className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground"
      >
        {section.label}
      </legend>

      <select
        value={current ?? ""}
        onChange={handleChange}
        className={cn(
          "quick-filter-select h-8 w-40 rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring",
          hasDropdownValue && "border-primary bg-primary/10 text-primary"
        )}
      >
        <option value="">전체</option>
        {section.options.map((option) => (
          <option key={`${section.key}-${String(option.value)}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </fieldset>
  )
}

function ButtonQuickFilterSection({
  section,
  legendId,
  selectedValues,
  allSelected,
  onToggle,
}) {
  return (
    <fieldset className={FIELDSET_CLASS} aria-labelledby={legendId}>
      <legend
        id={legendId}
        className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground"
      >
        {section.label}
      </legend>

      <div className="flex flex-wrap items-center">
        <button
          type="button"
          onClick={() => onToggle(section.key, null)}
          className={cn(
            "h-8 px-3 text-xs font-medium border border-input bg-background",
            "-ml-px first:ml-0 first:rounded-l last:rounded-r",
            "transition-colors",
            allSelected
              ? "relative z-[1] border-primary bg-primary/10 text-primary"
              : "hover:bg-muted"
          )}
        >
          전체
        </button>

        {section.options.map((option) => {
          const isActive = selectedValues.includes(option.value)
          return (
            <button
              key={`${section.key}-${String(option.value)}`}
              type="button"
              onClick={() => onToggle(section.key, option.value)}
              className={cn(
                "h-8 px-3 text-xs font-medium border border-input bg-background",
                "-ml-px first:ml-0 first:rounded-l last:rounded-r",
                "transition-colors",
                isActive
                  ? "relative z-[1] border-primary bg-primary/10 text-primary"
                  : "hover:bg-muted"
              )}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}

function FavoriteFiltersSection({
  favorites,
  selectedId,
  onSelectFavorite,
  onUpdateFavorite,
  onDeleteFavorite,
  onAddFavorite,
  showUpdateButton,
  className,
  defaultFavoriteName = buildDefaultFavoriteName(),
}) {
  const canUpdate = showUpdateButton && typeof onUpdateFavorite === "function"
  const [newFavoriteName, setNewFavoriteName] = React.useState("")
  const [deleteTarget, setDeleteTarget] = React.useState(null)
  const isDeleteDialogOpen = Boolean(deleteTarget)
  const deleteTargetName = deleteTarget?.name ?? ""
  const deleteTargetLabel = deleteTargetName || "선택한 즐겨찾기"

  const handleSelect = (favoriteId) => {
    onSelectFavorite?.(favoriteId)
  }

  const handleCreateFavorite = () => {
    const createdId = onAddFavorite?.(newFavoriteName.trim() || defaultFavoriteName)
    if (createdId) {
      setNewFavoriteName("")
    }
  }

  const handleRequestDelete = (favorite) => {
    if (typeof onDeleteFavorite !== "function") return
    setDeleteTarget(favorite)
  }

  const handleConfirmDelete = () => {
    if (deleteTarget?.id && typeof onDeleteFavorite === "function") {
      onDeleteFavorite(deleteTarget.id)
    }
    setDeleteTarget(null)
  }

  return (
    <fieldset
      className={cn(FIELDSET_CLASS, className)}
      aria-labelledby="legend-favorites"
    >
      <legend id="legend-favorites" className="sr-only">
        즐겨찾기
      </legend>

      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-end gap-2">
          {canUpdate ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onUpdateFavorite}
              className="border-primary/60 text-primary hover:bg-primary/10"
            >
              업데이트
            </Button>
          ) : null}
          <div className="flex flex-col items-start gap-1">
            <span className="text-[10px] pl-2 font-semibold uppercase tracking-wide text-muted-foreground">
              즐겨찾기
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="flex h-8 w-64 items-center justify-between rounded-md border border-input bg-background px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  <span
                    className={cn(
                      "truncate text-left",
                      !selectedId && "text-muted-foreground"
                    )}
                  >
                    {selectedId
                      ? favorites.find((favorite) => favorite.id === selectedId)?.name ?? ""
                      : "없음"}
                  </span>
                  <IconChevronDown className="size-4 shrink-0" aria-hidden />
                </button>
              </DropdownMenuTrigger>

              <DropdownMenuContent align="start" className="w-64 p-1">
                <DropdownMenuItem
                  className="text-xs text-muted-foreground"
                  onSelect={(event) => {
                    event.preventDefault()
                    handleSelect("")
                  }}
                >
                  없음
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                {favorites.map((favorite) => (
                  <DropdownMenuItem
                    key={favorite.id}
                    className="flex items-center justify-between gap-2 text-xs"
                    onSelect={(event) => {
                      event.preventDefault()
                      handleSelect(favorite.id)
                    }}
                  >
                    <span className="truncate">{favorite.name}</span>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.preventDefault()
                        event.stopPropagation()
                        handleRequestDelete(favorite)
                      }}
                      className="text-[11px] font-medium text-destructive hover:underline"
                    >
                      삭제
                    </button>
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <div className="flex flex-col gap-2 p-2">
                  <div className="text-[11px] font-semibold text-muted-foreground">
                    즐겨찾기 추가
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={newFavoriteName}
                      onChange={(event) => setNewFavoriteName(event.target.value)}
                      placeholder={defaultFavoriteName}
                      onKeyDown={(event) => event.stopPropagation()}
                      className="flex-1 rounded-md border border-input bg-background px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                    <button
                      type="button"
                      onClick={(event) => {
                        event.preventDefault()
                        event.stopPropagation()
                        handleCreateFavorite()
                      }}
                      className="h-8 flex-shrink-0 rounded-md border border-input bg-background px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      추가
                    </button>
                  </div>
                </div>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      <Dialog
        open={isDeleteDialogOpen}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setDeleteTarget(null)
        }}
      >
        <DialogContent
          className="sm:max-w-sm"
          aria-describedby="favorite-delete-description"
        >
          <DialogHeader>
            <DialogTitle>즐겨찾기 삭제</DialogTitle>
            <DialogDescription id="favorite-delete-description">
              {`"${deleteTargetLabel}"을(를) 삭제할까요?`}
              <br />
              저장된 퀵 필터 구성이 사라집니다.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-md bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
            {deleteTargetLabel}
          </div>
          <DialogFooter className="sm:justify-end">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setDeleteTarget(null)}
            >
              취소
            </Button>
            <Button type="button" variant="destructive" onClick={handleConfirmDelete}>
              삭제
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </fieldset>
  )
}

function RecentHoursQuickFilterSection({ section, legendId, current, onToggle }) {
  const [rangeValue, setRangeValue] = React.useState(() =>
    normalizeRecentHoursRange(current)
  )

  React.useEffect(() => {
    setRangeValue(normalizeRecentHoursRange(current))
  }, [current])

  const sliderPositions = React.useMemo(
    () => rangeToSliderPositions(rangeValue),
    [rangeValue]
  )

  const handleSliderChange = React.useCallback((value) => {
    setRangeValue(normalizeRecentHoursRange(sliderPositionsToRange(value)))
  }, [])

  const handleSliderCommit = React.useCallback(
    (value) => {
      const nextRange = normalizeRecentHoursRange(sliderPositionsToRange(value))
      setRangeValue(nextRange)
      onToggle(section.key, nextRange, { forceValue: true })
    },
    [onToggle, section.key]
  )

  return (
    <fieldset className={FIELDSET_CLASS} aria-labelledby={legendId}>
      <legend
        id={legendId}
        className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground"
      >
        <span>{section.label}</span>
      </legend>

      <div className="flex w-60 flex-col rounded-lg px-3 py-1">
        {/* 슬라이더 라인 */}
        <div className="flex mt-1 h-2 items-start gap-3">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            -{RECENT_HOURS_MAX}h
          </span>

          <Slider
            className="flex-1"
            min={RECENT_HOURS_MIN}
            max={RECENT_HOURS_MAX}
            step={1}
            value={sliderPositions}
            onValueChange={handleSliderChange}
            onValueCommit={handleSliderCommit}
            aria-label="최근 시간 범위 선택"
          />

          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            현재
          </span>
        </div>

        {/* 조회 텍스트 — 슬라이더 아래 중앙 */}
        <p className=" text-center text-[9px] font-medium text-muted-foreground">
          {formatRecentHoursRange(rangeValue)}
        </p>
      </div>
    </fieldset>
  )
}

function rangeToSliderPositions(range) {
  const normalized = normalizeRecentHoursRange(range)
  return [
    hoursToSliderPosition(normalized.start),
    hoursToSliderPosition(normalized.end),
  ]
}

function sliderPositionsToRange(positions) {
  if (!Array.isArray(positions) || positions.length === 0) {
    return createRecentHoursRange()
  }
  const sorted = [...positions].slice(0, 2).sort((a, b) => a - b)
  const [left = RECENT_HOURS_MIN, right = left] = sorted
  const startHours = sliderPositionToHours(left)
  const endHours = sliderPositionToHours(right)
  return createRecentHoursRange(startHours, endHours)
}

function hoursToSliderPosition(hours) {
  const safeHours = clampRecentHours(hours)
  return clampSliderPosition(RECENT_HOURS_MAX - safeHours)
}

function sliderPositionToHours(position) {
  const clamped = clampSliderPosition(position)
  return clampRecentHours(RECENT_HOURS_MAX - clamped)
}

function clampSliderPosition(value) {
  if (!Number.isFinite(value)) return RECENT_HOURS_MIN
  return Math.min(Math.max(value, RECENT_HOURS_MIN), RECENT_HOURS_MAX)
}

function formatRecentHoursRange(range) {
  const normalized = normalizeRecentHoursRange(range)
  return `${formatHoursAgo(normalized.start)} ~ ${formatHoursAgo(normalized.end)}`
}

function formatHoursAgo(hours) {
  const safe = clampRecentHours(hours)
  if (safe <= 0) return "현재"
  return `-${safe}h`
}

function normalizeForCompare(value) {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeForCompare(item))
  }
  if (value && typeof value === "object") {
    const sortedKeys = Object.keys(value).sort()
    const normalized = {}
    sortedKeys.forEach((key) => {
      normalized[key] = normalizeForCompare(value[key])
    })
    return normalized
  }
  return value
}

function areFiltersEqual(left, right) {
  return JSON.stringify(normalizeForCompare(left)) === JSON.stringify(normalizeForCompare(right))
}
