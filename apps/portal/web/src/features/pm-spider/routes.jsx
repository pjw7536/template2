// 파일 경로: src/features/pm-spider/routes.jsx
// PM SPIDER 기능 라우트 정의입니다.
import { lazyNamed } from "@/lib/react/lazyNamed"

const PmSpiderPage = lazyNamed(() => import("./pages/PmSpiderPage"), "PmSpiderPage")

export const pmSpiderRoutes = [
  {
    path: "spider/pm",
    element: <PmSpiderPage />,
  },
  {
    path: "pm_spider",
    element: <PmSpiderPage />,
  },
]
