export function ModelsPage() {
  return (
    // 페이지 루트 (스크롤 차단)
    <div className="flex h-full min-h-0 flex-col overflow-hidden gap-2">

      {/* ───────────────── 상단: 3개 flex 영역 ───────────────── */}
      <div className="flex h-28 gap-1 shrink-0">
        <div className="flex-1 bg-red-200 rounded-md p-2">
          Top Flex 1
        </div>
        <div className="flex-1 bg-red-200 rounded-md p-2">
          Top Flex 2
        </div>
        <div className="flex-1 bg-red-200 rounded-md p-2">
          Top Flex 3
        </div>
      </div>
      <div className="flex gap-2 shrink-0">
        <div className="flex-1 bg-red-200 rounded-md p-2">
          Top Flex 1
        </div>
      </div>
      {/* ───────────────── 하단: 여기만 스크롤 ───────────────── */}
      <div className="flex-1 min-h-0 overflow-y-auto bg-blue-200 rounded-md p-2">
        Bottom scroll area
        <div className="h-[700px]" />
      </div>

    </div>
  )
}
