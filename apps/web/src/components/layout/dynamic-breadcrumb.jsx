// src/components/layout/dynamic-breadcrumb.jsx
/**
 * DynamicBreadcrumb
 * -----------------------------------------------------------------------------
 * - 현재 URL 경로를 "/" 기준으로 잘라 "홈 > 섹션 > 상세" 형태의 breadcrumb를 만들어 줍니다.
 * - 마지막 항목은 현재 페이지이므로 <BreadcrumbPage>로 표시하고,
 *   마지막이 아닌 항목들도 링크 없이 텍스트로만 렌더링합니다.
 *
 * ✅ 유연한 옵션
 * - includeHome: 홈 링크를 맨 앞에 추가할지 여부 (기본 true)
 * - homeLabel, homeHref: 홈 라벨/경로 커스터마이즈
 * - hide: 숨기고 싶은 세그먼트 이름 배열 (예: ["settings"])
 * - overrides: 세그먼트 라벨 대체 (객체 또는 함수)
 */

import { Fragment } from "react"
import { useLocation } from "react-router-dom"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
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
 * segment 라벨을 계산합니다.
 * - overrides가 객체면 매핑 우선
 * - overrides가 함수면 그 반환값 사용
 * - 둘 다 아니면 기본 toTitleCase 사용
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
 * pathname을 "/"로 나눠 breadcrumb 항목 배열로 변환합니다.
 */
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

/* -----------------------------------------------------------------------------
 * 컴포넌트
 * -------------------------------------------------------------------------- */

export function DynamicBreadcrumb({
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
              {crumb.isLast ? (
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
