// src/features/appstore/pages/AppstorePage.jsx
// 사이드바에서 이동할 수 있는 Appstore 탭 화면입니다. 단순한 URL 모음집 형태로 검색/필터 후 바로 이동할 수 있습니다.
import { useState } from "react"
import { ArrowUpRight, Search } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"

const APPS = [
  {
    name: "Hunter",
    category: "Data access",
    description: "Find or verify professional email addresses easily.",
    tags: ["Enrichment", "Email verification", "Lead routing"],
    badge: "Popular",
    url: "https://hunter.io",
  },
  {
    name: "Twilio",
    category: "Messaging",
    description: "Send and receive SMS and MMS messages via API.",
    tags: ["SMS", "MMS", "Voice"],
    url: "https://www.twilio.com",
  },
  {
    name: "WhatsApp Business",
    category: "Messaging",
    description: "Business messaging with WhatsApp API.",
    tags: ["WhatsApp", "Templates", "2FA"],
    badge: "New",
    url: "https://www.facebook.com/business/m/whatsapp/business-platform",
  },
  {
    name: "Slack Platform",
    category: "Collaboration",
    description: "Automate channels, slash commands, and workflows.",
    tags: ["Workflows", "Events", "Bots"],
    url: "https://api.slack.com",
  },
  {
    name: "Notion",
    category: "Productivity",
    description: "Sync databases, pages, and comments programmatically.",
    tags: ["Databases", "Content sync"],
    url: "https://developers.notion.com",
  },
  {
    name: "Airtable",
    category: "Data access",
    description: "Work with bases, tables, and views through REST.",
    tags: ["Bases", "Views", "Automations"],
    url: "https://airtable.com/developers",
  },
  {
    name: "Stripe",
    category: "Payments",
    description: "Accept payments and manage subscriptions securely.",
    tags: ["Billing", "Subscriptions", "Invoices"],
    badge: "Certified",
    url: "https://stripe.com/docs",
  },
  {
    name: "Linear",
    category: "Productivity",
    description: "Ship faster with issue tracking and automations.",
    tags: ["Issues", "Backlog", "Roadmaps"],
    url: "https://developers.linear.app",
  },
  {
    name: "Figma",
    category: "Design",
    description: "Pull design assets, components, and comments via API.",
    tags: ["Components", "Comments", "Assets"],
    badge: "Beta",
    url: "https://www.figma.com/developers",
  },
]

const APP_CATEGORIES = ["all", ...new Set(APPS.map((app) => app.category))]
const categoryCounts = APPS.reduce((counts, app) => {
  counts[app.category] = (counts[app.category] ?? 0) + 1
  return counts
}, {})

export function AppstorePage() {
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")

  const normalizedQuery = query.trim().toLowerCase()
  const filteredApps = APPS.filter((app) => {
    const matchesCategory = category === "all" || app.category === category
    const matchesQuery =
      normalizedQuery.length === 0 ||
      app.name.toLowerCase().includes(normalizedQuery) ||
      app.description.toLowerCase().includes(normalizedQuery) ||
      app.category.toLowerCase().includes(normalizedQuery) ||
      app.tags.some((tag) => tag.toLowerCase().includes(normalizedQuery))
    return matchesCategory && matchesQuery
  })

  const resetFilters = () => {
    setCategory("all")
    setQuery("")
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-6">
      <div className="grid min-h-0 gap-6 lg:grid-cols-[320px_1fr]">
        <aside className="flex h-full min-h-0 flex-col gap-4">
          <Card className="rounded-2xl border bg-card shadow-sm">
            <CardHeader className="pb-2 space-y-2">
              <Badge variant="secondary" className="w-fit rounded-full bg-primary/10 text-primary">
                URL 컬렉션
              </Badge>
              <CardTitle className="text-base">커넥터 개요</CardTitle>
              <CardDescription>필터로 좁혀보고 링크로 바로 이동하세요.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-2 rounded-full bg-background/80 px-3 py-1">
                {APPS.length}개 앱
              </span>
              <span className="inline-flex items-center gap-2 rounded-full bg-background/80 px-3 py-1">
                {APP_CATEGORIES.length - 1}개 카테고리
              </span>
            </CardContent>
          </Card>

          <Card className="flex-1 rounded-2xl border bg-card shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">검색 및 필터</CardTitle>
              <CardDescription>필요한 커넥터를 빠르게 찾으세요.</CardDescription>
            </CardHeader>
            <CardContent className="flex h-full flex-col gap-4">
              <div className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2">
                <Search className="size-4 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="커넥터 검색 (예: Slack, Messaging)"
                  className="h-9 border-0 bg-transparent px-1 text-sm shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
                />
                {query && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs text-muted-foreground"
                    onClick={() => setQuery("")}
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
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={resetFilters}
                  type="button"
                  className="text-xs text-muted-foreground"
                >
                  초기화
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {APP_CATEGORIES.map((option) => (
                  <Button
                    key={option}
                    variant={option === category ? "secondary" : "outline"}
                    size="sm"
                    className="justify-between rounded-lg"
                    onClick={() => setCategory(option)}
                    type="button"
                  >
                    <span>{option === "all" ? "전체" : option}</span>
                    <Badge
                      variant="secondary"
                      className="ml-2 rounded-full bg-background/70 px-2 text-[11px]"
                    >
                      {option === "all" ? APPS.length : categoryCounts[option]}
                    </Badge>
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        </aside>

        <div className="flex flex-col gap-4">
          <Card className="border bg-card shadow-sm space-y-1">
            <CardHeader className="space-y-1">
              <CardDescription>
                <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <Badge variant="secondary" className="rounded-full">
                    {filteredApps.length}개 앱
                  </Badge>
                  {category !== "all" && (
                    <Badge variant="outline" className="rounded-full">
                      카테고리: {category}
                    </Badge>
                  )}
                  {normalizedQuery && (
                    <Badge variant="outline" className="rounded-full">
                      "{query.trim()}"
                    </Badge>
                  )}
                </div>
              </CardDescription>
            </CardHeader>
          </Card>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filteredApps.map((app) => (
              <Card
                key={app.name}
                className="flex h-full flex-col overflow-hidden border bg-card shadow-sm transition hover:-translate-y-1 hover:border-primary/30 hover:shadow-md"
              >
                <CardHeader className="flex flex-row items-start gap-3 p-4 pb-2">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary ring-1 ring-primary/20">
                    {app.name.charAt(0)}
                  </div>
                  <div className="flex flex-1 flex-col gap-1">
                    <div className="flex items-start gap-2">
                      <CardTitle className="text-base leading-tight">{app.name}</CardTitle>
                      {app.badge ? (
                        <Badge variant="secondary" className="rounded-full bg-primary/10 text-primary">
                          {app.badge}
                        </Badge>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline" className="rounded-full bg-background/70 px-2 py-0">
                        {app.category}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-3 px-4 pb-1 pt-2">
                  <p className="text-sm leading-relaxed text-muted-foreground">{app.description}</p>
                  <div className="flex flex-wrap gap-2">
                    {app.tags.map((tag) => (
                      <Badge key={`${app.name}-${tag}`} variant="outline" className="rounded-full bg-background/70">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <div className="mt-auto flex items-center justify-end text-xs text-muted-foreground">
                    <Button
                      asChild
                      variant="ghost"
                      size="sm"
                      className="gap-1 px-2 text-primary hover:bg-primary/10"
                    >
                      <a href={app.url} target="_blank" rel="noreferrer">
                        바로가기
                        <ArrowUpRight className="size-3" />
                      </a>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}

            {filteredApps.length === 0 && (
              <Card className="col-span-full border-dashed">
                <CardHeader className="p-6">
                  <CardTitle className="text-base">조건에 맞는 앱이 없어요</CardTitle>
                  <CardDescription>
                    필터를 초기화하거나 검색어를 줄여보세요.
                  </CardDescription>
                </CardHeader>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
