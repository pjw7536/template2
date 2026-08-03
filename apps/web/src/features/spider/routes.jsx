import { lazyNamed } from "@/lib/react/lazyNamed"

const DefectSpiderExternalPage = lazyNamed(
  () => import("./pages/DefectSpiderExternalPage"),
  "DefectSpiderExternalPage",
)
const SpiderHomePage = lazyNamed(() => import("./pages/SpiderHomePage"), "SpiderHomePage")

export const spiderRoutes = [
  {
    path: "spider",
    element: <SpiderHomePage />,
  },
  {
    path: "spider/defect",
    element: <DefectSpiderExternalPage />,
  },
]
