import { useEffect, useRef, useState } from "react"
import { CalendarIcon, ChevronDown, ChevronUp, Filter, RefreshCcw, Search } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { DateRangeCalendar } from "@/components/common"

const DATE_VALUE_FORMATTER = new Intl.DateTimeFormat("en-CA")
const RANGE_LABEL_FORMATTER = new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium" })

const parseDateValue = (value) => {
  if (!value) return null
  const parsed = new Date(`${value}T00:00:00`)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const formatDateValue = (date) => {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return ""
  return DATE_VALUE_FORMATTER.format(date)
}

const isValidDate = (date) => date instanceof Date && !Number.isNaN(date.getTime())

const formatRangeLabel = (range) => {
  const from = range?.from
  const to = range?.to
  const hasFrom = isValidDate(from)
  const hasTo = isValidDate(to)

  if (hasFrom && hasTo) return `${RANGE_LABEL_FORMATTER.format(from)} ~ ${RANGE_LABEL_FORMATTER.format(to)}`
  if (hasFrom) return `${RANGE_LABEL_FORMATTER.format(from)} 이후`
  if (hasTo) return `${RANGE_LABEL_FORMATTER.format(to)} 이전`
  return "날짜 범위 선택"
}

export function EmailFilters({ filters, onChange, onReset }) {
  const [showDetails, setShowDetails] = useState(false)
  const [today] = useState(() => {
    const now = new Date()
    now.setHours(23, 59, 59, 999)
    return now
  })
  const triggerRef = useRef(null)
  const contentRef = useRef(null)

  useEffect(() => {
    if (!showDetails) {
      return
    }

    const handlePointerDown = (event) => {
      const target = event.target
      if (!target) return

      const isInsideTrigger = triggerRef.current?.contains(target)
      const isInsideContent = contentRef.current?.contains(target)

      if (!isInsideTrigger && !isInsideContent) {
        setShowDetails(false)
      }
    }

    window.addEventListener("pointerdown", handlePointerDown)
    return () => window.removeEventListener("pointerdown", handlePointerDown)
  }, [showDetails])

  const handleChange = (key, value) => {
    onChange?.({ ...filters, [key]: value, page: 1 })
  }

  const handleReset = () => {
    onReset?.()
  }

  const handleDateRangeSelect = (range) => {
    const nextFrom = range?.from ? formatDateValue(range.from) : ""
    const nextTo = range?.to ? formatDateValue(range.to) : ""
    onChange?.({ ...filters, dateFrom: nextFrom, dateTo: nextTo, page: 1 })
  }

  const handleToggleDetails = () => {
    setShowDetails((prev) => !prev)
  }

  const dateRange = {
    from: parseDateValue(filters.dateFrom),
    to: parseDateValue(filters.dateTo),
  }
  const selectedRange =
    isValidDate(dateRange.from) || isValidDate(dateRange.to) ? dateRange : undefined
  const dateRangeLabel = formatRangeLabel(selectedRange)
  const calendarDefaultMonth = selectedRange?.from ?? selectedRange?.to ?? today

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card/60 p-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span>필터</span>
        </div>
        <Button variant="ghost" size="sm" className="gap-2" onClick={handleReset}>
          <RefreshCcw className="h-4 w-4" />
          초기화
        </Button>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
        <div className="flex flex-1 items-center gap-2 rounded-md border px-3 py-2 h-8">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input
            className="border-0 p-0 focus-visible:ring-0"
            placeholder="제목, 본문, 발신자 검색"
            value={filters.q || ""}
            onChange={(e) => handleChange("q", e.target.value)}
          />
        </div>
        <Tooltip
          open={showDetails}
          delayDuration={0}
        >
          <TooltipTrigger asChild>
            <Button
              ref={triggerRef}
              variant={showDetails ? "secondary" : "outline"}
              size="sm"
              className="gap-2"
              onClick={handleToggleDetails}
            >
              상세
              {showDetails ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent
            ref={contentRef}
            side="bottom"
            align="end"
            sideOffset={8}
            className="w-[520px] bg-transparent p-0 text-foreground shadow-none"
          >
            <div className="space-y-3 rounded-md border bg-background p-3 shadow-md">
              <p className="text-xs font-semibold text-muted-foreground">상세 필터</p>
              <div className="grid gap-2">
                <Input
                  placeholder="발신자"
                  value={filters.sender || ""}
                  onChange={(e) => handleChange("sender", e.target.value)}
                />
                <Input
                  placeholder="수신자"
                  value={filters.recipient || ""}
                  onChange={(e) => handleChange("recipient", e.target.value)}
                />
                <div className="rounded-md border bg-card p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                      <CalendarIcon className="h-4 w-4" />
                      <span>날짜 범위</span>
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                      <span>{dateRangeLabel}</span>
                      {selectedRange ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2"
                          onClick={() => handleDateRangeSelect(null)}
                        >
                          기간 초기화
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  <DateRangeCalendar
                    selected={selectedRange}
                    defaultMonth={calendarDefaultMonth}
                    onSelect={handleDateRangeSelect}
                    disableAfter={today}
                  />
                </div>
              </div>
            </div>
          </TooltipContent>
        </Tooltip>
      </div>
    </div>
  )
}
