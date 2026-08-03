import { lazyNamed } from "@/lib/react/lazyNamed"

const AccessStatsShell = lazyNamed(
  () => import("./components/AccessStatsShell"),
  "AccessStatsShell",
)
const AccessStatsPage = lazyNamed(() => import("./pages/AccessStatsPage"), "AccessStatsPage")

export const accessStatsRoutes = [
  {
    path: "access-stats",
    element: <AccessStatsShell />,
    children: [
      {
        index: true,
        element: <AccessStatsPage />,
      },
    ],
  },
]
