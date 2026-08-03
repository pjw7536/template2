import { lazyNamed } from "@/lib/react/lazyNamed"

const L1SpiderPage = lazyNamed(() => import("./pages/L1SpiderPage"), "L1SpiderPage")

export const l1SpiderRoutes = [
  {
    path: "spider/l1",
    element: <L1SpiderPage />,
  },
]
