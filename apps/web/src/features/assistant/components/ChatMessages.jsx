import { useEffect, useRef } from "react"

import { AssistantStatusIndicator } from "./AssistantStatusIndicator"
import { formatAssistantMessage } from "../utils/formatAssistantMessage"

export function ChatMessages({ messages = [], isSending }) {
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isSending])

  return (
    <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
      {messages.map((message) => {
        const isUser = message.role === "user"
        const baseBubbleClasses = [
          "max-w-[80%]",
          "rounded-2xl",
          "px-4",
          "py-2",
          "text-sm",
          "shadow-sm",
        ]

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
            )}
          </div>
        )
      })}

      <AssistantStatusIndicator isSending={isSending} />
      <div ref={messagesEndRef} />
    </div>
  )
}
