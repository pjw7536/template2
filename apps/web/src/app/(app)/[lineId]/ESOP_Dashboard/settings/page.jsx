// src/app/[lineId]/ESOP_Dashboard/settings/page.jsx
import { LineSettingsPage } from "@/features/line-dashboard/components"

export default async function Page({ params }) {
  const { lineId: raw } = await params
  const lineId = Array.isArray(raw) ? raw[0] : raw ?? ""

  return (
    <div className="h-[calc(100vh-5rem)] px-2">
      <LineSettingsPage lineId={lineId} />
    </div>
  )
}
