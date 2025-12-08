import { AuthAutoLoginGate } from "@/lib/auth"
import HomePage from "./pages/HomePage"
import { HomeLayout } from "./components/HomeLayout"

export const homeRoutes = [
  {
    element: <AuthAutoLoginGate />,
    children: [
      {
        element: <HomeLayout />,
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
