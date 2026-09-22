// src/features/voc/routes.jsx
// VOC 게시판 라우트 정의
import { lazyNamed } from "@/lib/react/lazyNamed"

const VocShell = lazyNamed(() => import("./components/VocShell"), "VocShell")
const VocBoardPage = lazyNamed(() => import("./pages/VocBoardPage"), "VocBoardPage")

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
