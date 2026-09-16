// 파일 경로: src/features/tttm-spider/routes.jsx
// TTTM Spider feature 라우트: Target 선택 페이지 + Score 페이지(선택 상태 공유 레이아웃).
import { lazyNamed } from "@/lib/react/lazyNamed"

const TttmSpiderLayout = lazyNamed(
  () => import("./pages/TttmSpiderLayout"),
  "TttmSpiderLayout",
)
const TttmSpiderScorePage = lazyNamed(
  () => import("./pages/TttmSpiderScorePage"),
  "TttmSpiderScorePage",
)
const TttmSpiderTargetPage = lazyNamed(
  () => import("./pages/TttmSpiderTargetPage"),
  "TttmSpiderTargetPage",
)

const childRoutes = () => [
  { index: true, element: <TttmSpiderTargetPage /> },
  { path: "score", element: <TttmSpiderScorePage /> },
]

export const tttmSpiderRoutes = [
  { path: "tttm_spider", element: <TttmSpiderLayout />, children: childRoutes() },
  { path: "spider/tttm", element: <TttmSpiderLayout />, children: childRoutes() },
]
