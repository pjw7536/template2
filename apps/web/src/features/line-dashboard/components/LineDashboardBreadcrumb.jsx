// src/features/line-dashboard/components/LineDashboardBreadcrumb.jsx
import { Fragment } from "react"
import { Link, useLocation } from "react-router-dom"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

function safeDecodeURIComponent(value) {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

function toTitleCase(segment) {
  return safeDecodeURIComponent(String(segment ?? ""))
    .replace(/-/g, " ")
    .replace(/\b\w/g, (ch) => ch.toUpperCase())
}

function resolveLabel(segment, index, segments, overrides) {
  if (typeof overrides === "function") {
    return overrides(segment, index, segments) ?? toTitleCase(segment)
  }
  if (overrides && typeof overrides === "object" && segment in overrides) {
    return overrides[segment]
  }
  return toTitleCase(segment)
}

function buildBreadcrumbs(pathname, { overrides, hide, includeHome, homeLabel, homeHref }) {
  if (!pathname) return []

  const segments = pathname.split("/").filter(Boolean)
  const hideSet = new Set(Array.isArray(hide) ? hide : [])
  const items = []

  if (includeHome) {
    items.push({
      href: homeHref,
      segment: "__home__",
      label: homeLabel,
      isLast: segments.length === 0,
      isHome: true,
    })
  }

  segments.forEach((segment, index) => {
    if (hideSet.has(segment)) return

    const href = `/${segments.slice(0, index + 1).join("/")}`
    const label = resolveLabel(segment, index, segments, overrides)
    const isLast = index === segments.length - 1

    items.push({ href, segment, label, isLast, isHome: false })
  })

  return items
}

export function LineDashboardBreadcrumb({
  overrides = {},
  hide = [],
  includeHome = true,
  homeLabel = "Home",
  homeHref = "/",
}) {
  const { pathname } = useLocation()
  const crumbs = buildBreadcrumbs(pathname, {
    overrides,
    hide,
    includeHome,
    homeLabel,
    homeHref,
  })

  if (crumbs.length === 0) return null

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {crumbs.map((crumb, index) => (
          <Fragment key={`${crumb.href}-${index}`}>
            {index > 0 && <BreadcrumbSeparator />}
            <BreadcrumbItem>
              {crumb.isHome ? (
                <BreadcrumbLink asChild>
                  <Link to={crumb.href ?? "/"}>{crumb.label}</Link>
                </BreadcrumbLink>
              ) : crumb.isLast ? (
                <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
              ) : (
                <span className="transition-colors">{crumb.label}</span>
              )}
            </BreadcrumbItem>
          </Fragment>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
