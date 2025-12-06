// src/features/line-dashboard/components/DataTableToolbar.jsx
import { IconDatabase, IconRefresh } from "@tabler/icons-react"

import { cn } from "@/lib/utils"
import { Button } from "components/ui/button"
import { QuickFilterFavorites } from "./QuickFilterFavorites"

/**
 * 테이블 상단의 타이틀, 즐겨찾기, 새로고침 버튼을 묶어둔 헤더입니다.
 * - DataTable은 상태 계산에 집중하고, 이 컴포넌트는 UI 조립만 담당합니다.
 */
export function DataTableToolbar({
  lineId,
  labels,
  lastUpdatedLabel,
  isRefreshing,
  onRefresh,
  favorites,
}) {
  const {
    filters,
    favorites: favoriteList,
    onSaveFavorite,
    onUpdateFavorite,
    onApplyFavorite,
    onDeleteFavorite,
    resetSignal,
  } = favorites ?? {}

  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <IconDatabase className="size-5" />
          {lineId} {labels.titleSuffix}
          <span
            className="ml-2 text-[10px] font-normal text-muted-foreground self-end"
            aria-live="polite"
          >
            {labels.updated} {lastUpdatedLabel || "-"}
          </span>
        </div>
      </div>

      <div className="ml-auto flex flex-wrap items-end gap-2">
        <QuickFilterFavorites
          filters={filters}
          favorites={favoriteList}
          onSaveFavorite={onSaveFavorite}
          onUpdateFavorite={onUpdateFavorite}
          onApplyFavorite={onApplyFavorite}
          onDeleteFavorite={onDeleteFavorite}
          resetSignal={resetSignal}
        />
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          className="gap-1"
          aria-label={labels.refresh}
          title={labels.refresh}
          aria-busy={isRefreshing}
        >
          <IconRefresh className={cn("size-3", isRefreshing && "animate-spin")} />
          {labels.refresh}
        </Button>
      </div>
    </div>
  )
}
