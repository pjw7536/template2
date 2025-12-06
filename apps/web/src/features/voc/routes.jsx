// src/features/voc/routes.jsx
// VOC 게시판 라우트 정의
import { Navigate } from "react-router-dom"

import { VocBoardPage } from "./pages/VocBoardPage"

export const vocRoutes = [
  {
    path: "voc",
    element: <VocBoardPage />,
  },
  // 기존 /qna 링크 호환을 위한 리다이렉트
  {
    path: "qna",
    element: <Navigate to="/voc" replace />,
  },
]
