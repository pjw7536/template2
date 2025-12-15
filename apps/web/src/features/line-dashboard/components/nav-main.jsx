// src/components/layout/nav-main.jsx
/**
 * NavMain (리팩토링 버전)
 * - URL 스코프(특히 line 스코프)를 일관되게 처리
 * - 단일 항목 / 하위 항목이 있는 그룹 항목을 컴포넌트로 분리
 * - useParams + useActiveLine 를 안전하게 병합하여 lineId 결정
 * - 키/접근성/방어코드 강화
 */

import { useParams } from "react-router-dom"

import { SidebarNavMain } from "@/components/layout"
import { useActiveLine } from "./active-line-context"

/* =========================================================
 * 타입 정의 (JSDoc) — 에디터 인텔리센스 도움
 * ======================================================= */
/**
 * @typedef {"line" | "global" | undefined} Scope
 *
 * @typedef {Object} NavSubItem
 * @property {string} title
 * @property {string=} url
 * @property {Scope=} scope
 *
 * @typedef {Object} NavItem
 * @property {string} title
 * @property {string=} url
 * @property {Scope=} scope
 * @property {React.ComponentType<any>=} icon
 * @property {boolean=} isActive
 * @property {NavSubItem[]=} items
 */

/* =========================================
 * 유틸: URL 스코프(line) 접두어 붙이기
 *  - scope === "line" 이면 마지막 세그먼트로 lineId를 붙인다 (/ESOP_Dashboard/status/:lineId)
 *  - url이 절대경로/상대경로 모두 정규화
 *  - url이 비어있으면 "#" 반환
 * ======================================= */
/** @param {string|undefined} url @param {Scope} scope @param {string|null} lineId */
function withLineScope(url, scope, lineId) {
  if (!url) return "#"
  const normalized = url.startsWith("/") ? url.replace(/^\/+/, "") : url
  const basePath = `/${normalized}`

  if (scope !== "line" || !lineId) return basePath

  const segments = normalized.split("/").filter(Boolean)
  if (!segments.length) return basePath

  const placeholderIndex = segments.findIndex((segment) => segment.startsWith(":"))
  if (placeholderIndex !== -1) {
    const next = [...segments]
    next[placeholderIndex] = lineId
    return `/${next.join("/")}`
  }

  if (segments[segments.length - 1] !== lineId) {
    segments.push(lineId)
  }
  return `/${segments.join("/")}`
}

/* =========================================
 * 유틸: params에서 lineId 추출 (배열/문자열 방어)
 * ======================================= */
function extractLineIdFromParams(params) {
  if (!params) return null
  const raw = params.lineId
  if (Array.isArray(raw)) return raw[0] ?? null
  return typeof raw === "string" ? raw : null
}

/* =========================================================
 * 최상위 컴포넌트: NavMain
 *  - lineId 우선순위: URL 파라미터 > ActiveLine 컨텍스트
 *  - 각 item에 대해 LeafItem 또는 GroupItem으로 분기 렌더
 * ======================================================= */
/** @param {{ items: NavItem[] }} props */
export function NavMain({ items }) {
  const params = useParams()
  const { lineId: activeLineId } = useActiveLine()

  // URL 파라미터 우선, 없다면 컨텍스트의 선택 라인 사용
  const resolvedLineId = extractLineIdFromParams(params) ?? activeLineId ?? null

  const safeItems = Array.isArray(items) ? items : []

  const resolvedItems = safeItems.map((item) => {
    const next = { ...item, url: withLineScope(item.url, item.scope, resolvedLineId) }
    if (!Array.isArray(item.items)) return next

    return {
      ...next,
      items: item.items.map((sub) => ({
        ...sub,
        url: withLineScope(sub.url, sub.scope ?? item.scope, resolvedLineId),
      })),
    }
  })

  return <SidebarNavMain items={resolvedItems} label="Platform" />
}
