// src/app/[lineId]/ESOP_Dashboard/history/page.jsx
import { LineHistoryDashboard } from "@/features/line-dashboard/components"

export default async function Page({ params, searchParams }) {
  const { lineId: raw } = await params
  const resolvedSearch = (await searchParams) ?? {}

  const lineId = Array.isArray(raw) ? raw[0] : raw ?? ""

  const rangeParam = Array.isArray(resolvedSearch?.rangeDays)
    ? resolvedSearch.rangeDays[0]
    : resolvedSearch?.rangeDays ?? resolvedSearch?.range

  const parsedRange = Number.parseInt(rangeParam ?? "", 10)
  const initialRangeDays = Number.isFinite(parsedRange) && parsedRange > 0 ? parsedRange : undefined

  return (
    <div className="h-[calc(100vh-5rem)]">
      <LineHistoryDashboard lineId={lineId} initialRangeDays={initialRangeDays} />
    </div>
  )
}
