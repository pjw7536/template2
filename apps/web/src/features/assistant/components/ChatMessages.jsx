import { useEffect, useRef } from "react"
import { Link } from "react-router-dom"

import { AssistantStatusIndicator } from "./AssistantStatusIndicator"
import { formatAssistantMessage } from "../utils/formatAssistantMessage"

export function ChatMessages({ messages = [], isSending, fillBubbles = false }) {
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isSending])

  return (
    <div className="flex-1 min-h-0 space-y-3 overflow-y-auto px-4 py-3">
      {messages.map((message) => {
        const isUser = message.role === "user"
        const sources = Array.isArray(message.sources) ? message.sources : []
        const baseBubbleClasses = [
          "max-w-[90%]",
          "rounded-2xl",
          "px-4",
          "py-2",
          "text-sm",
          "shadow-sm",
        ].filter(Boolean)

        return (
          <div
            key={message.id}
            className={["flex", isUser ? "justify-end" : "justify-start"].join(" ")}
          >
            {isUser ? (
              <pre
                className={[
                  ...baseBubbleClasses,
                  "m-0 whitespace-pre-wrap break-words",
                  "bg-primary text-primary-foreground font-sans leading-relaxed text-xs",
                ].join(" ")}
              >
                {message.content}
              </pre>
            ) : (
              <div className={["space-y-2", fillBubbles ? "w-full" : null].filter(Boolean).join(" ")}>
                <div
                  className={[
                    ...baseBubbleClasses,
                    "bg-muted text-foreground leading-relaxed break-words space-y-2",
                    "[&_p]:my-2",
                    "[&_ul]:list-disc [&_ol]:list-decimal [&_ul]:pl-5 [&_ol]:pl-5 [&_li]:my-1",
                    "[&_table]:w-full [&_table]:border-collapse [&_th]:border [&_td]:border [&_th]:bg-muted/80 [&_th]:px-3 [&_th]:py-2 [&_td]:px-3 [&_td]:py-2 [&_tr:nth-child(even)]:bg-muted/50",
                    "[&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5",
                    "[&_pre]:rounded-lg [&_pre]:bg-muted [&_pre]:p-3 [&_pre]:overflow-x-auto",
                  ].join(" ")}
                  dangerouslySetInnerHTML={{ __html: formatAssistantMessage(message.content) }}
                />
                {sources.length > 0 ? (
                  <div
                    className={[
                      "inline-flex",
                      "max-w-[80%]",
                      "flex-wrap items-center gap-2 rounded-xl border bg-background px-3 py-2 text-[11px] text-muted-foreground shadow-sm",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <span className="text-xs font-semibold text-foreground">관련 메일</span>
                    <div className="flex flex-wrap gap-1">
                      {sources.map((source) => (
                        <Link
                          key={`${message.id}-${source.docId}`}
                          to={`/emails?emailId=${encodeURIComponent(source.docId)}`}
                          className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-[11px] text-foreground transition hover:bg-muted/80"
                        >
                          <span className="truncate max-w-[160px]">
                            {source.title || source.docId}
                          </span>
                        </Link>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        )
      })}

      <AssistantStatusIndicator isSending={isSending} />
      <div ref={messagesEndRef} />
    </div>
  )
}
