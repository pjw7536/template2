// src/features/appstore/components/AppFilters.jsx
import { Plus, Search } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

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
    <div className="grid gap-4">
      <Card className="rounded-2xl border bg-card shadow-sm">
        <CardHeader className="space-y-2 pb-3">
          <Badge variant="secondary" className="w-fit rounded-full bg-primary/10 text-primary">
            Appstore
          </Badge>
          <CardTitle className="text-base">앱 등록 및 탐색</CardTitle>
          <CardDescription>연결 정보를 모으고 담당자 정보를 함께 관리하세요.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2 text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-2 rounded-full bg-background/80 px-3 py-1">
            {totalApps}개 앱
          </span>
          <span className="inline-flex items-center gap-2 rounded-full bg-background/80 px-3 py-1">
            {Math.max(categories.length - 1, 0)}개 카테고리
          </span>
        </CardContent>
      </Card>

      <Card className="rounded-2xl border bg-card shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">검색 및 필터</CardTitle>
          <CardDescription>카테고리/검색어로 빠르게 찾고 정리하세요.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2">
            <Search className="size-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder="앱 이름, 설명, 태그 검색"
              className="h-9 border-0 bg-transparent px-1 text-sm shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
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

          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">카테고리</div>
              <p className="text-xs text-muted-foreground">업무 영역별로 좁혀보세요.</p>
            </div>
            <div className="flex items-center gap-2">
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
              <Button
                variant="ghost"
                size="sm"
                onClick={onReset}
                type="button"
                className="text-xs text-muted-foreground"
              >
                초기화
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
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
