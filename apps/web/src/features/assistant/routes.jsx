// 파일 경로: src/features/assistant/routes.jsx
// LLM 어시스턴트 전체 화면 페이지 라우트
import { lazyNamed } from "@/lib/react/lazyNamed"

const AssistantShell = lazyNamed(() => import("./components/AssistantShell"), "AssistantShell")
const ChatPage = lazyNamed(() => import("./pages/ChatPage"), "ChatPage")

export const assistantRoutes = [
  {
    path: "assistant",
    element: <AssistantShell />,
    children: [
      {
        index: true,
        element: <ChatPage />,
      },
    ],
  },
]
