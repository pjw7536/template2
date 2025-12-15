// src/features/appstore/components/AppFilters.jsx
import { Plus, Search } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"

export function AppFilters({
  totalApps,
  query,
  onQueryChange,
  category,
  categories,
  categoryCounts,
  onCategoryChange,
  onReset,
  onCreate,
  isCreating,
}) {
  return (
    <div className="grid h-full min-h-0 grid-rows-[190px_1fr] gap-2">
      <Card className="rounded-2xl border bg-card shadow-sm gap-0">
        <CardHeader className="space-y-2 pb-3">
          <Badge variant="secondary" className="w-fit rounded-full bg-primary/10 text-primary">
            Appstore
          </Badge>
          <CardTitle className="text-base">앱 등록 및 탐색</CardTitle>
          <CardDescription>Etch기술팀 Appstore입니다</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm text-muted-foreground">
          <Button
            variant="outline"
            size="sm"
            onClick={onCreate}
            disabled={isCreating}
            className="gap-1"
            type="button"
          >
            <Plus className="size-4" />
            앱 등록
          </Button>
        </CardContent>
      </Card>

      <Card className="min-h-0 rounded-2xl border bg-card shadow-sm flex flex-col gap-0">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">검색 및 필터</CardTitle>
          <CardDescription>
            <span className="inline-flex items-center gap-2 rounded-full bg-background/80 px-3 py-1">
              {totalApps}개 앱
            </span>
            <span className="inline-flex items-center gap-2 rounded-full bg-background/80 px-3 py-1">
              {Math.max(categories.length - 1, 0)}개 카테고리
            </span>
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-1 min-h-0 flex-col gap-4">
          <div className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2">
            <Search className="size-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder="앱 이름, 설명, 태그 검색"
              className="h-6 border-0 bg-transparent px-1 text-sm shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
            />
            {query && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-muted-foreground"
                onClick={() => onQueryChange("")}
                type="button"
              >
                지우기
              </Button>
            )}
          </div>

          <Separator className="bg-border" />
          <div className="flex justify-between">
            <div className="text-sm font-medium">카테고리</div>
            <Button
              variant="ghost"
              size="xs"
              onClick={onReset}
              type="button"
              className="text-xs text-muted-foreground"
            >
              필터초기화
            </Button>
          </div>

          <div className="grid flex-1 min-h-0 grid-cols-2 gap-2 overflow-y-auto">
            {categories.map((option) => (
              <Button
                key={option}
                variant={option === category ? "secondary" : "outline"}
                size="sm"
                className="justify-between rounded-lg"
                onClick={() => onCategoryChange(option)}
                type="button"
              >
                <span>{option === "all" ? "전체" : option}</span>
                <Badge
                  variant="secondary"
                  className="ml-2 rounded-full bg-background/70 px-2 text-[11px]"
                >
                  {option === "all" ? totalApps : categoryCounts[option] ?? 0}
                </Badge>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
