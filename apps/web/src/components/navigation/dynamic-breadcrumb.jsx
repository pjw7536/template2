// src/components/navigation/dynamic-breadcrumb.jsx
"use client"

/**
 * DynamicBreadcrumb
 * -----------------------------------------------------------------------------
 * - 현재 URL 경로를 "/" 기준으로 잘라 "홈 > 섹션 > 상세" 형태의 breadcrumb를 만들어 줍니다.
 * - 마지막 항목은 현재 페이지이므로 <BreadcrumbPage>로 표시하고,
 *   마지막이 아닌 항목들은 <BreadcrumbLink>로 이동 가능하게 렌더링합니다.
 *
 * ✅ 유연한 옵션
 * - includeHome: 홈 링크를 맨 앞에 추가할지 여부 (기본 true)
 * - homeLabel, homeHref: 홈 라벨/경로 커스터마이즈
 * - hide: 숨기고 싶은 세그먼트 이름 배열 (예: ["settings"])
 * - overrides: 세그먼트 라벨 대체
 *    1) 객체: { "eqp": "장비", "logs": "로그" }
 *    2) 함수: (segment, index, segments) => string | ReactNode
 *
 * 사용 예시:
 * <DynamicBreadcrumb
 *   overrides={{ "line-dashboard": "라인 대시보드" }}
 *   hide={["app"]}  // /app/line-dashboard → "라인 대시보드"만 보이게
 * />
 */

import Link from "next/link"
import { Fragment } from "react"
import { usePathname } from "next/navigation"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  BreadcrumbLink,
} from "@/components/ui/breadcrumb"

/* -----------------------------------------------------------------------------
 * 유틸: 안전 디코딩 + 보기 좋은 문자열로 변환
 * -------------------------------------------------------------------------- */

/** decodeURIComponent 사용 시 에러가 날 수 있어 try/catch로 안전 처리 */
function safeDecodeURIComponent(value) {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

/** "my-page-id" → "My Page Id" 로 보기 좋게 변경 */
function toTitleCase(segment) {
  return safeDecodeURIComponent(String(segment ?? ""))
    .replace(/-/g, " ")
    .replace(/\b\w/g, (ch) => ch.toUpperCase())
}

/* -----------------------------------------------------------------------------
 * 핵심: pathname → breadcrumb 모델로 변환
 * -------------------------------------------------------------------------- */

/**
 * segment 라벨을 계산
 * - overrides가 객체면 매핑 우선
 * - overrides가 함수면 그 반환값 사용
 * - 둘 다 아니면 기본 toTitleCase
 */
function resolveLabel(segment, index, segments, overrides) {
  if (typeof overrides === "function") {
    return overrides(segment, index, segments) ?? toTitleCase(segment)
  }
  if (overrides && typeof overrides === "object" && segment in overrides) {
    return overrides[segment]
  }
  return toTitleCase(segment)
}

/**
 * pathname을 "/"로 나눠 [{ href, segment, label, isLast }, ...] 모델로 변환
 */
function buildBreadcrumbs(pathname, { overrides, hide, includeHome, homeLabel, homeHref }) {
  if (!pathname) return []

  // "/a/b/c" → ["a","b","c"]
  const segments = pathname.split("/").filter(Boolean)

  // 숨길 목록 빠르게 조회 가능하도록 Set
  const hideSet = new Set(Array.isArray(hide) ? hide : [])

  const items = []

  // 옵션: 홈 추가
  if (includeHome) {
    items.push({
      href: homeHref,
      segment: "__home__",
      label: homeLabel,
      isLast: segments.length === 0, // 루트("/")인 경우 홈이 곧 마지막
      isHome: true,
    })
  }

  // 경로 세그먼트 → breadcrumb 항목
  segments.forEach((segment, index) => {
    if (hideSet.has(segment)) return

    const href = `/${segments.slice(0, index + 1).join("/")}`
    const label = resolveLabel(segment, index, segments, overrides)
    const isLast = index === segments.length - 1

    items.push({ href, segment, label, isLast, isHome: false })
  })

  return items
}

/* -----------------------------------------------------------------------------
 * 컴포넌트
 * -------------------------------------------------------------------------- */

export function DynamicBreadcrumb({
  overrides = {},              // 라벨 대체 (객체 또는 함수)
  hide = [],                   // 숨길 세그먼트
  includeHome = true,          // 홈 표시 여부
  homeLabel = "Home",          // 홈 라벨
  homeHref = "/",              // 홈 경로
}) {
  const pathname = usePathname()

  // 계산이 가볍기 때문에 별도 memo 없이 매 렌더마다 재계산해도 충분합니다.
  const crumbs = buildBreadcrumbs(pathname, {
    overrides,
    hide,
    includeHome,
    homeLabel,
    homeHref,
  })

  // 루트에서 includeHome=false라면 아무것도 렌더하지 않음
  if (crumbs.length === 0) return null

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {crumbs.map((crumb, index) => (
          <Fragment key={`${crumb.href}-${index}`}>
            {/* 첫 항목 앞에는 구분자 표시 X */}
            {index > 0 && <BreadcrumbSeparator />}

            <BreadcrumbItem>
              {crumb.isLast ? (
                // 마지막: 현재 페이지
                <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
              ) : (
                // 마지막이 아니면 이동 가능한 링크
                <BreadcrumbLink asChild>
                  <Link href={crumb.href}>{crumb.label}</Link>
                </BreadcrumbLink>
              )}
            </BreadcrumbItem>
          </Fragment>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
