import { RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"

import { formatPermissionCount, PERMISSION_PAGE_SIZE } from "../utils/permissionDisplay"


export function PermissionPager({ pagination, onPageChange, disabled = false }) {
  const page = pagination?.page || 1
  const pageSize = pagination?.pageSize || PERMISSION_PAGE_SIZE
  const total = pagination?.total || 0
  const totalPages = pagination?.totalPages || 1
  const canPrevious = page > 1
  const canNext = page < totalPages
  const start = total > 0 ? (page - 1) * pageSize + 1 : 0
  const end = total > 0 ? Math.min(page * pageSize, total) : 0

  return (
    <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
      <p className="text-xs text-muted-foreground">
        표시 {formatPermissionCount(start)}-{formatPermissionCount(end)} / 총 {formatPermissionCount(total)}
      </p>
      <Pagination className="mx-0 w-auto justify-end">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              href="#"
              aria-label="이전 페이지"
              title="이전 페이지"
              aria-disabled={!canPrevious || disabled}
              tabIndex={!canPrevious || disabled ? -1 : undefined}
              className={`xl:size-8 xl:p-0 xl:[&>span]:hidden ${
                !canPrevious || disabled ? "pointer-events-none opacity-50" : ""
              }`}
              onClick={(event) => {
                event.preventDefault()
                if (canPrevious && !disabled) onPageChange(page - 1)
              }}
            />
          </PaginationItem>
          <PaginationItem>
            <PaginationNext
              href="#"
              aria-label="다음 페이지"
              title="다음 페이지"
              aria-disabled={!canNext || disabled}
              tabIndex={!canNext || disabled ? -1 : undefined}
              className={`xl:size-8 xl:p-0 xl:[&>span]:hidden ${
                !canNext || disabled ? "pointer-events-none opacity-50" : ""
              }`}
              onClick={(event) => {
                event.preventDefault()
                if (canNext && !disabled) onPageChange(page + 1)
              }}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  )
}

export function PermissionErrorState({ error, onRetry }) {
  const message = error?.message === "forbidden"
    ? "권한 관리 권한이 없습니다."
    : "데이터를 불러오지 못했습니다."

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-4" role="alert">
      <p className="text-sm text-destructive">{message}</p>
      <Button type="button" size="sm" variant="outline" onClick={() => onRetry()}>
        <RefreshCw className="size-4" />
        다시 시도
      </Button>
    </div>
  )
}
