import { AuthAutoLoginGate } from "@/lib/auth"
import { HomeShell } from "./components/HomeShell"
import HomePage from "./pages/HomePage"

export const homeRoutes = [
  {
    element: <AuthAutoLoginGate />,
    children: [
      {
        element: <HomeShell />,
        children: [
          {
            index: true,
            element: <HomePage />,
          },
        ],
      },
    ],
  },
]
