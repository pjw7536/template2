// src/features/models/routes.jsx
// 모델 기능의 라우트 정의를 묶어둡니다.
import { LineDashboardShell } from "@/features/line-dashboard"
import { ModelsPage } from "./pages/ModelsPage"

export const modelsRoutes = [
  {
    path: "models",
    element: <LineDashboardShell />,
    children: [
      {
        index: true,
        element: <ModelsPage />,
      },
    ],
  },
]
