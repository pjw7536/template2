// src/features/voc/routes.jsx
// VOC(Q&A) 게시판 라우트 정의
import { QnaBoardPage } from "./pages/QnaBoardPage"

export const vocRoutes = [
  {
    path: "qna",
    element: <QnaBoardPage />,
  },
]
