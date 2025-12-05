// src/features/appstore/pages/AppstorePage.jsx
// 사이드바에서 이동할 수 있는 Appstore 탭 화면입니다. 기존 카드/톤앤매너에 맞춰 검색과 카테고리 필터를 제공합니다.
import { useState } from "react"
import { ArrowUpRight, Search } from "lucide-react"

import { Badge } from "components/ui/badge"
import { Button } from "components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "components/ui/input"

const APPS = [
  {
    name: "Hunter",
    category: "Data access",
    description: "Find or verify professional email addresses easily.",
  },
  {
    name: "Twilio",
    category: "Messaging",
    description: "Send and receive SMS and MMS messages via API.",
  },
  {
    name: "WhatsApp Business",
    category: "Messaging",
    description: "Business messaging with WhatsApp API.",
  },
  {
    name: "Slack Platform",
    category: "Collaboration",
    description: "Automate channels, slash commands, and workflows.",
  },
  {
    name: "Notion",
    category: "Productivity",
    description: "Sync databases, pages, and comments programmatically.",
  },
  {
    name: "Airtable",
    category: "Data access",
    description: "Work with bases, tables, and views through REST.",
  },
  {
    name: "Stripe",
    category: "Payments",
    description: "Accept payments and manage subscriptions securely.",
  },
  {
    name: "Linear",
    category: "Productivity",
    description: "Ship faster with issue tracking and automations.",
  },
  {
    name: "Figma",
    category: "Design",
    description: "Pull design assets, components, and comments via API.",
  },
]

const APP_CATEGORIES = ["all", ...new Set(APPS.map((app) => app.category))]

export function AppstorePage() {
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")
  const layoutVars = {
    "--appstore-offset": "7.5rem", // accounts for navbar height plus surrounding padding
    "--app-card-height": "11.5rem",
  }

  const categories = APP_CATEGORIES

  const normalizedQuery = query.trim().toLowerCase()
  const filteredApps = APPS.filter((app) => {
    const matchesCategory = category === "all" || app.category === category
    const matchesQuery =
      normalizedQuery.length === 0 ||
      app.name.toLowerCase().includes(normalizedQuery) ||
      app.description.toLowerCase().includes(normalizedQuery) ||
      app.category.toLowerCase().includes(normalizedQuery)
    return matchesCategory && matchesQuery
  })

  return (
    <section
      style={layoutVars}
      className="flex min-h-[calc(100dvh-var(--appstore-offset))] max-h-[calc(100dvh-var(--appstore-offset))] flex-col gap-3 overflow-hidden"
    >
      <div className="relative overflow-hidden rounded-xl border bg-card p-3 shadow-sm flex-shrink-0">
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent"
        />
        <div className="relative flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="px-3 space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight">Appstore</h1>
            <p className="text-sm text-muted-foreground">
              Discover vetted tools to connect messaging, data, and automation workflows.
            </p>
          </div>
        </div>
      </div>

      <div className="grid flex-1 min-h-0 gap-4 lg:grid-cols-[260px_1fr]">
        <aside className="flex min-h-0 flex-col gap-4">

          <div className="rounded-xl border bg-card p-4 shadow-sm">
            <div className="text-sm font-medium text-muted-foreground">Search apps</div>
            <div className="mt-2 flex items-center gap-2 rounded-lg border bg-background/80 px-3 py-2 shadow-xs">
              <Search className="size-4 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Apps 검색"
                className="h-5 border-0 bg-transparent px-1 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
              />
            </div>
          </div>

          <div className="rounded-xl border bg-card p-4 shadow-sm flex-1 overflow-y-auto">
            <div className="text-sm font-medium text-muted-foreground">Categories</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {categories.map((option) => (
                <Button
                  key={option}
                  variant={option === category ? "default" : "outline"}
                  size="sm"
                  className="rounded-full"
                  onClick={() => setCategory(option)}
                  type="button"
                >
                  {option === "all" ? "All apps" : option}
                </Button>
              ))}
            </div>
          </div>
        </aside>

        <div className="grid h-full min-h-0 grid-cols-1 gap-4 overflow-y-auto auto-rows-[var(--app-card-height)] md:grid-cols-2 xl:grid-cols-3">
          {filteredApps.map((app) => (
            <Card key={app.name} className="flex h-full flex-col">
              <CardHeader className="flex flex-row items-start gap-3 p-4 pb-2">
                <div className="space-y-1">
                  <CardTitle className="text-base">{app.name}</CardTitle>
                  <CardDescription>{app.description}</CardDescription>
                </div>
                <Badge variant="secondary" className="ml-auto">
                  {app.category}
                </Badge>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-3 px-4 pb-4 pt-2">
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline">Fast setup</Badge>
                  <Badge variant="outline">Secure</Badge>
                  <Badge variant="outline">Docs available</Badge>
                </div>
                <Button variant="outline" size="sm" className="mt-auto rounded-full self-start">
                  Click
                  <ArrowUpRight className="size-3" />
                </Button>
              </CardContent>
            </Card>
          ))}

          {filteredApps.length === 0 && (
            <Card className="flex h-full flex-col md:col-span-2 xl:col-span-3">
              <CardHeader className="p-4">
                <CardTitle className="text-base">No matches found</CardTitle>
                <CardDescription>
                  Try a different keyword or reset the category filter.
                </CardDescription>
              </CardHeader>
            </Card>
          )}
        </div>
      </div>
    </section>
  )
}
