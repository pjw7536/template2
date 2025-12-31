// src/features/voc/routes.jsx
// VOC 게시판 라우트 정의
import { VocShell } from "./components/VocShell"
import { VocBoardPage } from "./pages/VocBoardPage"

export const vocRoutes = [
  {
    path: "voc",
    element: <VocShell />,
    children: [
      {
        index: true,
        element: <VocBoardPage />,
      },
    ],
  },
]
