// src/features/appstore/pages/AppstorePage.jsx
// 사이드바에서 이동할 수 있는 Appstore 탭 화면입니다. 기존 카드/톤앤매너에 맞춰 검색과 카테고리 필터를 제공합니다.
import { useMemo, useState } from "react"
import { ArrowUpRight, Bookmark, Search, Sparkles } from "lucide-react"

import { Badge } from "components/ui/badge"
import { Button } from "components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
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

export function AppstorePage() {
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")

  const categories = useMemo(
    () => ["all", ...new Set(APPS.map((app) => app.category))],
    []
  )

  const filteredApps = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return APPS.filter((app) => {
      const matchesCategory = category === "all" || app.category === category
      const matchesQuery =
        normalizedQuery.length === 0 ||
        app.name.toLowerCase().includes(normalizedQuery) ||
        app.description.toLowerCase().includes(normalizedQuery) ||
        app.category.toLowerCase().includes(normalizedQuery)
      return matchesCategory && matchesQuery
    })
  }, [category, query])

  return (
    <section className="grid gap-4">
      <div className="relative overflow-hidden rounded-xl border bg-card p-6 shadow-sm">
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent"
        />
        <div className="relative flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-3">
            <Badge variant="outline" className="gap-1 bg-background/70 backdrop-blur">
              <Sparkles className="size-3" />
              Curated integrations
            </Badge>
            <div className="space-y-1">
              <h1 className="text-2xl font-semibold tracking-tight">Appstore</h1>
              <p className="text-sm text-muted-foreground">
                Discover vetted tools to connect messaging, data, and automation workflows.
              </p>
            </div>
          </div>

          <div className="w-full max-w-md rounded-lg border bg-background/80 p-3 shadow-xs backdrop-blur">
            <div className="flex items-center gap-2">
              <Search className="size-4 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by name, category, or use case"
                className="h-9 border-0 bg-transparent px-1 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
              />
            </div>
          </div>
        </div>

        <div className="relative mt-4 flex flex-wrap items-center gap-2">
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

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filteredApps.map((app) => (
          <Card key={app.name} className="h-full">
            <CardHeader className="flex flex-row items-start gap-3">
              <div className="space-y-1">
                <CardTitle className="text-base">{app.name}</CardTitle>
                <CardDescription>{app.description}</CardDescription>
              </div>
              <Badge variant="secondary" className="ml-auto">
                {app.category}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                <Badge variant="outline">Fast setup</Badge>
                <Badge variant="outline">Secure</Badge>
                <Badge variant="outline">Docs available</Badge>
              </div>
            </CardContent>
            <CardFooter className="flex items-center gap-2 border-t pt-4">
              <Button variant="ghost" size="sm" className="rounded-full">
                <Bookmark className="size-4" />
                Bookmark
              </Button>
              <Button variant="outline" size="sm" className="rounded-full">
                View docs
                <ArrowUpRight className="size-4" />
              </Button>
            </CardFooter>
          </Card>
        ))}

        {filteredApps.length === 0 && (
          <Card className="md:col-span-2 xl:col-span-3">
            <CardHeader>
              <CardTitle className="text-base">No matches found</CardTitle>
              <CardDescription>
                Try a different keyword or reset the category filter.
              </CardDescription>
            </CardHeader>
          </Card>
        )}
      </div>
    </section>
  )
}
