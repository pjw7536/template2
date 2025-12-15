import DOMPurify from "dompurify"
import { Inbox, Loader2, MailOpen, User } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { formatEmailDate } from "../utils/date"

function getLocalPart(emailAddress) {
  if (!emailAddress) return ""
  const atIndex = emailAddress.indexOf("@")
  if (atIndex <= 0) return ""
  return emailAddress.slice(0, atIndex)
}

function formatDisplayAddress(value) {
  if (!value) return ""

  const cleaned = String(value).replace(/\s+/g, " ").trim()
  if (!cleaned) return ""

  const angleMatch = cleaned.match(/<\s*([^<>]+?)\s*>/)
  if (angleMatch) {
    const address = String(angleMatch[1] || "").trim()
    const rawName = cleaned.slice(0, angleMatch.index).trim()
    const normalizedName = rawName.replace(/^["']|["']$/g, "").trim()
    const fallbackName = getLocalPart(address)
    const displayName = normalizedName || fallbackName

    if (!address) return normalizedName
    return displayName ? `${displayName} <${address}>` : address
  }

  if (cleaned.includes("@") && !/\s/.test(cleaned)) {
    const fallbackName = getLocalPart(cleaned)
    return fallbackName ? `${fallbackName} <${cleaned}>` : cleaned
  }

  return cleaned
}

function parseRecipients(value) {
  if (!value) return []
  if (Array.isArray(value)) {
    return value.map(formatDisplayAddress).filter(Boolean)
  }
  if (typeof value !== "string") return []

  const trimmed = value.trim()
  if (!trimmed) return []

  const angleMatches = trimmed.match(/[^<>]*<[^<>]+>/g)
  if (angleMatches) {
    return angleMatches.map(formatDisplayAddress).filter(Boolean)
  }

  return trimmed
    .split(/\s*[,;\n]\s*/)
    .map(formatDisplayAddress)
    .filter(Boolean)
}

function RecipientSummary({ value }) {
  const recipients = parseRecipients(value)

  if (!recipients.length) {
    return <span className="truncate">-</span>
  }

  if (recipients.length === 1) {
    return <span className="truncate">{recipients[0]}</span>
  }

  const hiddenCount = recipients.length - 1

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="flex min-w-0 items-center gap-2">
          <span className="min-w-0 flex-1 truncate">{recipients[0]}</span>
          <span className="shrink-0">외 {hiddenCount}명</span>
        </span>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        align="start"
        sideOffset={8}
        className="bg-transparent p-0 text-foreground shadow-none [&>*:last-child]:hidden"
      >
        <div className="max-h-60 max-w-sm overflow-y-auto rounded-lg border border-border bg-popover p-3 text-popover-foreground shadow-md">
          <ul className="grid gap-2 text-xs">
            {recipients.map((recipient, index) => (
              <li
                key={`${recipient}-${index}`}
                className="rounded-md bg-muted/50 p-2 text-popover-foreground"
              >
                <span className="break-words">{recipient}</span>
              </li>
            ))}
          </ul>
        </div>
      </TooltipContent>
    </Tooltip>
  )
}

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
  const hasCc = parseRecipients(email.cc).length > 0
  const hasBcc = parseRecipients(email.bcc).length > 0

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="space-y-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <MailOpen className="h-4 w-4" />
          <span>수신</span>
          <span>·</span>
          <span>{formatEmailDate(email.receivedAt)}</span>
          {email.ragDocId ? (
            <Badge variant="default" className="ml-2 text-[10px] uppercase">
              RAG
            </Badge>
          ) : null}
        </div>
        <CardTitle className="break-words text-lg font-semibold leading-tight">
          {email.subject || "(제목 없음)"}
        </CardTitle>
        <div className="grid gap-2 text-sm text-muted-foreground">
          <div className="flex min-w-0 items-center gap-2">
            <User className="h-4 w-4" />
            <span className="shrink-0 font-medium text-foreground">From</span>
            <div className="min-w-0 flex-1">
              <RecipientSummary value={email.sender} />
            </div>
          </div>
          <Separator />
          <div className="flex min-w-0 items-center gap-2">
            <User className="h-4 w-4" />
            <span className="shrink-0 font-medium text-foreground">To</span>
            <div className="min-w-0 flex-1">
              <RecipientSummary value={email.recipient} />
            </div>
          </div>
          {hasCc ? (
            <div className="flex min-w-0 items-center gap-2">
              <User className="h-4 w-4" />
              <span className="shrink-0 font-medium text-foreground">Cc</span>
              <div className="min-w-0 flex-1">
                <RecipientSummary value={email.cc} />
              </div>
            </div>
          ) : null}
          {hasBcc ? (
            <div className="flex min-w-0 items-center gap-2">
              <User className="h-4 w-4" />
              <span className="shrink-0 font-medium text-foreground">Bcc</span>
              <div className="min-w-0 flex-1">
                <RecipientSummary value={email.bcc} />
              </div>
            </div>
          ) : null}
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
