import DOMPurify from "dompurify"
import { Inbox, Loader2, MailOpen, User } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { formatEmailDate } from "../utils/date"

export function EmailDetail({ email, isLoading, html, isHtmlLoading }) {
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center rounded-xl border bg-card/60">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!email) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 rounded-xl border bg-card/60 text-center text-muted-foreground">
        <Inbox className="h-8 w-8" />
        <p className="text-sm">메일을 선택하면 상세 내용이 여기에 표시됩니다.</p>
      </div>
    )
  }

  const sanitizedHtml = html ? DOMPurify.sanitize(html) : ""
  const hasHtml = Boolean(sanitizedHtml)

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="space-y-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <MailOpen className="h-4 w-4" />
          <span>수신</span>
          <span>·</span>
          <span>{formatEmailDate(email.receivedAt)}</span>
          {email.ragDocId ? (
            <Badge variant="outline" className="ml-2 text-[10px] uppercase">
              RAG 연동
            </Badge>
          ) : null}
        </div>
        <CardTitle className="break-words text-lg font-semibold leading-tight">
          {email.subject || "(제목 없음)"}
        </CardTitle>
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <User className="h-4 w-4" />
            <span className="font-medium text-foreground">From</span>
            <span className="truncate">{email.sender}</span>
          </div>
          <Separator orientation="vertical" className="h-4" />
          <div className="flex items-center gap-2">
            <User className="h-4 w-4" />
            <span className="font-medium text-foreground">To</span>
            <span className="truncate">{email.recipient}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 overflow-hidden">
        <div className="h-full min-w-0 overflow-auto overflow-x-auto rounded-lg border bg-background">
          {hasHtml ? (
            <div
              className="space-y-4 p-3 text-sm leading-relaxed text-foreground"
              dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
            />
          ) : email.bodyText ? (
            <pre className="whitespace-pre-wrap p-3 text-sm leading-relaxed text-foreground">
              {email.bodyText}
            </pre>
          ) : isHtmlLoading ? (
            <div className="flex h-full items-center justify-center gap-2 p-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              메일 본문을 불러오는 중입니다...
            </div>
          ) : (
            <div className="flex h-full items-center justify-center p-3 text-sm text-muted-foreground">
              본문이 비어 있습니다.
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
