// src/features/voc/routes.jsx
// VOC 게시판 라우트 정의
import { Navigate } from "react-router-dom"

import { VocBoardPage } from "./pages/VocBoardPage"

export const vocRoutes = [
  {
    path: "voc",
    element: <VocBoardPage />,
  }
]
