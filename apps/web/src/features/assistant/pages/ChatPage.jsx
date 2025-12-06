import { useEffect, useRef, useState } from "react"
import { useLocation } from "react-router-dom"
import { Loader2, MessageCircle, RefreshCw, Send } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { useChatSession } from "../hooks/useChatSession"

export function ChatPage() {
  const location = useLocation()
  const handoffMessages = Array.isArray(location?.state?.initialMessages)
    ? location.state.initialMessages
    : undefined

  const { messages, isSending, errorMessage, clearError, sendMessage, resetConversation } =
    useChatSession({ initialMessages: handoffMessages })
  const [input, setInput] = useState("")
  const messagesEndRef = useRef(null)

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [messages, isSending])

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!input.trim()) return
    await sendMessage(input)
    setInput("")
  }

  return (
    <div className="flex h-full flex-col gap-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Assistant</p>
          <h1 className="text-2xl font-semibold leading-tight">LLM 대화형 도우미</h1>
          <p className="text-sm text-muted-foreground">
            화면 하단 위젯과 동일한 세션을 전체 화면에서 이어서 사용할 수 있습니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={resetConversation}
            disabled={isSending}
            className="gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            새 대화 시작
          </Button>
        </div>
      </div>

      <Card className="flex h-[70vh] flex-col">
        <CardHeader className="flex flex-row items-center justify-between gap-3 border-b">
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-primary ring-2 ring-primary/20" />
            <CardTitle className="text-base">실시간 LLM 상담</CardTitle>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <MessageCircle className="h-4 w-4" />
            연결됨
          </div>
        </CardHeader>

        <CardContent className="flex-1 space-y-3 overflow-y-auto bg-muted/30 px-4 py-4">
          {messages.map((message) => {
            const isUser = message.role === "user"
            return (
              <div
                key={message.id}
                className={["flex", isUser ? "justify-end" : "justify-start"].join(" ")}
              >
                <div
                  className={[
                    "max-w-2xl rounded-2xl px-4 py-3 text-sm shadow-sm",
                    isUser ? "bg-primary text-primary-foreground" : "bg-card text-foreground",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  {message.content}
                </div>
              </div>
            )
          })}

          {isSending && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              답변을 준비하고 있어요...
            </div>
          )}

          {errorMessage && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <div className="flex items-center justify-between gap-3">
                <span>{errorMessage}</span>
                <Button variant="ghost" size="sm" className="h-8 px-2 text-destructive" onClick={clearError}>
                  닫기
                </Button>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </CardContent>

        <CardFooter className="border-t bg-background px-4 py-3">
          <form onSubmit={handleSubmit} className="flex w-full flex-col gap-2">
            <label className="sr-only" htmlFor="assistant-page-input">
              어시스턴트에게 질문하기
            </label>
            <div className="flex items-end gap-2 rounded-xl border bg-muted/30 p-3">
              <textarea
                id="assistant-page-input"
                className="min-h-[96px] flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground/70"
                placeholder="질문을 작성하세요. 줄바꿈은 Shift+Enter"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault()
                    handleSubmit(event)
                  }
                }}
                disabled={isSending}
              />
              <Button
                type="submit"
                size="icon"
                disabled={isSending || !input.trim()}
                className="h-12 w-12 flex-none"
              >
                {isSending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
                <span className="sr-only">메시지 전송</span>
              </Button>
            </div>
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <span>LLM API에 바로 연결되어 답변을 제공합니다.</span>
              <span>Shift+Enter로 줄바꿈</span>
            </div>
          </form>
        </CardFooter>
      </Card>
    </div>
  )
}
