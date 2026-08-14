import { lazyNamed } from "@/lib/react/lazyNamed"

const WorkHubLauncherPage = lazyNamed(
  () => import("./pages/WorkHubLauncherPage"),
  "WorkHubLauncherPage"
)

export const workHubRoutes = [
  {
    path: "work-hub",
    element: <WorkHubLauncherPage />,
  },
]
