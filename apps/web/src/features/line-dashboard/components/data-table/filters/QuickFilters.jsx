// src/features/line-dashboard/components/data-table/filters/QuickFilters.jsx
import * as React from "react"
import { IconChevronDown } from "@tabler/icons-react"

import { cn } from "@/lib/utils"
import { Slider } from "@/components/ui/slider"
import { GlobalFilter } from "./GlobalFilter"
import {
  isMultiSelectFilter,
  RECENT_HOURS_DEFAULT,
  RECENT_HOURS_MAX,
  RECENT_HOURS_MIN,
} from "./quickFilters"

const DROPDOWN_SECTION_KEYS = new Set([
  "sdwt_prod",
  "sample_type",
  "user_sdwt_prod",
  "main_step",
])
const FIELDSET_CLASS = "flex flex-col rounded-xl p-1 px-3"

const isNil = (value) => value === null || value === undefined

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

    if (DROPDOWN_SECTION_KEYS.has(section.key)) {
      return (
        <DropdownQuickFilterSection
          key={section.key}
          section={section}
          legendId={legendId}
          current={current}
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

function getSelectedValues(isMulti, current) {
  if (isMulti) {
    return Array.isArray(current) ? current : []
  }
  return isNil(current) ? [] : [current]
}

function DropdownQuickFilterSection({ section, legendId, current, onToggle }) {
  const hasDropdownValue = !isNil(current) && String(current).length > 0

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
        onChange={(event) => onToggle(section.key, event.target.value || null)}
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

function RecentHoursQuickFilterSection({ section, legendId, current, onToggle }) {
  const [sliderValue, setSliderValue] = React.useState(() => normalizeHoursValue(current))

  React.useEffect(() => {
    setSliderValue(normalizeHoursValue(current))
  }, [current])

  const handleSliderChange = React.useCallback((value) => {
    const next = clampHours(value?.[0])
    setSliderValue(next)
  }, [])

  const handleSliderCommit = React.useCallback(
    (value) => {
      const next = clampHours(value?.[0] ?? sliderValue)
      setSliderValue(next)
      onToggle(section.key, String(next), { forceValue: true })
    },
    [onToggle, sliderValue, section.key]
  )

  return (
    <fieldset className={FIELDSET_CLASS} aria-labelledby={legendId}>
      <legend
        id={legendId}
        className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground"
      >
        {section.label}
      </legend>

      <div className="flex flex-col w-40 rounded-lg border border border-border/40 p-3">
        <Slider
          min={RECENT_HOURS_MIN}
          max={RECENT_HOURS_MAX}
          step={5}
          value={[sliderValue]}
          onValueChange={handleSliderChange}
          onValueCommit={handleSliderCommit}
          aria-label="최근 시간 선택"
        />
        <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          <span>{RECENT_HOURS_MIN}h</span>
          <span>{RECENT_HOURS_MAX}h</span>
        </div>
      </div>
    </fieldset>
  )
}

function clampHours(value) {
  if (!Number.isFinite(value)) return RECENT_HOURS_DEFAULT
  return Math.min(Math.max(value, RECENT_HOURS_MIN), RECENT_HOURS_MAX)
}

function normalizeHoursValue(value) {
  if (value === null || value === undefined) {
    return RECENT_HOURS_DEFAULT
  }
  const numeric = Number(value)
  return clampHours(numeric)
}
