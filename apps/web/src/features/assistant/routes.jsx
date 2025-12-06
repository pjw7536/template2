// src/features/assistant/routes.jsx
// LLM 어시스턴트 전체 화면 페이지 라우트
import { ChatPage } from "./pages/ChatPage"

export const assistantRoutes = [
  {
    path: "assistant",
    element: <ChatPage />,
  },
]
