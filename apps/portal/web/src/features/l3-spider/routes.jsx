// 파일 경로: src/features/l3-spider/routes.jsx
// L3 Spider feature 라우트 정의입니다.
import { lazyNamed } from "@/lib/react/lazyNamed"

const L3SpiderPage = lazyNamed(() => import("./pages/L3SpiderPage"), "L3SpiderPage")

export const l3SpiderRoutes = [
  {
    path: "spider/l3",
    element: <L3SpiderPage />,
  },
  {
    path: "l3_spider",
    element: <L3SpiderPage />,
  },
]
