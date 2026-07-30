// 파일 경로: src/features/tttm-spider/pages/TttmSpiderLayout.jsx
// Target 선택 페이지와 Score 페이지가 선택 상태를 공유하는 레이아웃(Outlet context).
import { useState } from "react"
import { Outlet } from "react-router-dom"

export function TttmSpiderLayout() {
  // targets: [{eqp,chamber}], compLotwf/refLotwf: lotwf 객체 배열, refMode: "self"|"other"
  const [selection, setSelection] = useState({
    rows: [{ comp: null, ref: null }], // [{comp:{eqp,chamber,from,to}|null, ref:...|null}] · 초기 빈 행 1개
    compLotwf: [],     // 선택된 lotwf
    refLotwf: [],
    dataType: "trace",
    focusKey: null,    // Summary 카드 클릭 시 상세에서 먼저 볼 조합 key
  })

  const patch = (p) => setSelection((s) => ({ ...s, ...(typeof p === "function" ? p(s) : p) }))

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col bg-background">
      <Outlet context={{ selection, patch, setSelection }} />
    </div>
  )
}
