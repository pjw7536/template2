// src/features/line-dashboard/components/data-table/filters/GlobalFilter.jsx
"use client"

import { Input } from "@/components/ui/input"

import { searchableValue } from "../utils/formatters.jsx"

// 사용자가 입력한 키워드를 소문자 문자열로 정리합니다.
function normalizeFilterValue(filterValue) {
  if (filterValue === null || filterValue === undefined) return ""
  return String(filterValue).trim().toLowerCase()
}

// 테이블 전체를 훑는 글로벌 필터 함수를 생성합니다.
export function createGlobalFilterFn(columns) {
  const searchableKeys = Array.from(new Set(columns)).filter(Boolean)

  return (row, _columnId, filterValue) => {
    const keyword = normalizeFilterValue(filterValue)
    if (!keyword) return true

    return searchableKeys.some((key) => {
      const columnValue = row.original?.[key]
      if (columnValue === undefined || columnValue === null) return false
      return searchableValue(columnValue).includes(keyword)
    })
  }
}

// 입력창 UI를 단순히 감싼 컴포넌트입니다.
export function GlobalFilter({ value, onChange, placeholder = "Search rows" }) {
  return (
    <Input
      value={value ?? ""}
      onChange={(event) => onChange?.(event.target.value)}
      placeholder={placeholder}
      className="h-8 w-full max-w-xs"
    />
  )
}
