import { useEffect, useLayoutEffect, useRef, useState } from "react"
import {
  Check,
  ChevronDown,
  Copy,
  Loader2,
  Pencil,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react"
import { Link, useNavigate } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Textarea } from "@/components/ui/textarea"

import { AssistantStatusIndicator } from "./AssistantStatusIndicator"
import { StreamingText } from "./StreamingText"
import { formatAssistantMessage } from "../utils/formatAssistantMessage"
import { buildEmailSourceUrl } from "../utils/buildEmailSourceUrl"

function normalizeScopeList(value) {
  return Array.isArray(value)
    ? value.map((item) => String(item || "").trim()).filter(Boolean).sort()
    : []
}

function getScopeSignature(scope) {
  if (!scope || typeof scope !== "object") return ""
  return JSON.stringify({
    eqpId: String(scope.eqpId || "").trim().toUpperCase(),
    from: String(scope.from || "").slice(0, 10),
    to: String(scope.to || "").slice(0, 10),
    logTypes: normalizeScopeList(scope.logTypes),
    tipGroups: normalizeScopeList(scope.tipGroups),
  })
}

function formatScopeSummary(scope) {
  if (!scope || typeof scope !== "object") return "범위 정보 없음"
  const period = [String(scope.from || "").slice(0, 10), String(scope.to || "").slice(0, 10)]
    .filter(Boolean)
    .join(" ~ ")
  const logTypeCount = normalizeScopeList(scope.logTypes).length
  return [scope.eqpId, period, logTypeCount ? `로그 유형 ${logTypeCount}개` : ""]
    .filter(Boolean)
    .join(" · ")
}

function buildObserverEvidenceHref(scope, evidenceId) {
  const eqpId = String(scope?.eqpId || "").trim()
  const normalizedEvidenceId = String(evidenceId || "").trim()
  if (!eqpId || !normalizedEvidenceId) return ""

  const params = new URLSearchParams()
  const from = String(scope?.from || "").trim().slice(0, 10)
  const to = String(scope?.to || "").trim().slice(0, 10)
  if (from) params.set("from", from)
  if (to) params.set("to", to)
  params.set("evidenceId", normalizedEvidenceId)
  normalizeScopeList(scope?.logTypes).forEach((logType) => {
    params.append("analysisLogType", logType)
  })
  normalizeScopeList(scope?.tipGroups).forEach((tipGroup) => {
    params.append("analysisTipGroup", tipGroup)
  })
  return `/observer/${encodeURIComponent(eqpId)}?${params.toString()}`
}

function getEvidenceTargets(contextSnapshot, evidence) {
  if (Array.isArray(evidence?.evidenceTargets) && evidence.evidenceTargets.length) {
    return evidence.evidenceTargets
  }
  if (contextSnapshot?.kind !== "observer" || !Array.isArray(evidence?.evidenceIds)) {
    return []
  }
  return evidence.evidenceIds.map((evidenceId) => ({
    id: evidenceId,
    href: buildObserverEvidenceHref(contextSnapshot.scope, evidenceId),
  }))
}

const KNOWLEDGE_SOURCE_LABELS = {
  emails: "Emails",
  observer: "Observer",
  appstore: "App Store",
  "line-dashboard": "Line Dashboard",
}

function getKnowledgeRouteLabel(knowledgeContext) {
  if (!knowledgeContext || typeof knowledgeContext !== "object") return ""
  if (knowledgeContext.route === "clarify") return "지식 범위 확인"
  if (knowledgeContext.route !== "retrieve" || !knowledgeContext.sourceApp) {
    return knowledgeContext.fallback ? "일반 답변 · 라우팅 대체" : "일반 답변"
  }
  const sourceLabel = KNOWLEDGE_SOURCE_LABELS[knowledgeContext.sourceApp]
    || knowledgeContext.sourceApp
  if (knowledgeContext.mode === "current_scope") {
    return knowledgeContext.sourceApp === "emails"
      ? `${sourceLabel} · 현재 메일함`
      : `${sourceLabel} · 현재 화면`
  }
  return `${sourceLabel} · 자동 선택`
}

export function ChatMessages({
  messages = [],
  conversationKey = "",
  isGenerating,
  fillBubbles = false,
  availableMailboxes = [],
  statusMode = "openwebui",
  hasOlderMessages = false,
  isLoadingOlderMessages = false,
  onLoadOlderMessages,
  onEditMessage,
  onRegenerateMessage,
  onRateMessage,
  isActionDisabled = false,
  currentPageScope = null,
}) {
  const messagesEndRef = useRef(null)
  const scrollContainerRef = useRef(null)
  const previousScrollHeightRef = useRef(null)
  const loadOlderRequestRef = useRef(0)
  const scrollFrameRef = useRef(null)
  const previousConversationKeyRef = useRef(conversationKey)
  const navigate = useNavigate()
  const [copiedMessageId, setCopiedMessageId] = useState("")
  const [editTargetId, setEditTargetId] = useState("")
  const [editValue, setEditValue] = useState("")
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false)
  const [isNearLatest, setIsNearLatest] = useState(true)
  useLayoutEffect(() => {
    if (previousConversationKeyRef.current === conversationKey) return
    previousConversationKeyRef.current = conversationKey
    previousScrollHeightRef.current = null
    loadOlderRequestRef.current += 1
    if (scrollFrameRef.current !== null) {
      window.cancelAnimationFrame(scrollFrameRef.current)
      scrollFrameRef.current = null
    }
    setIsNearLatest(true)
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight
    }
  }, [conversationKey])

  useEffect(() => {
    if (!editTargetId) return
    const editTargetExists = messages.some(
      (message) => message.id === editTargetId && message.role === "user",
    )
    if (editTargetExists) return
    setEditTargetId("")
    setEditValue("")
  }, [editTargetId, messages])

  useEffect(() => {
    if (previousScrollHeightRef.current !== null && scrollContainerRef.current) {
      const previousScrollHeight = previousScrollHeightRef.current
      previousScrollHeightRef.current = null
      scrollContainerRef.current.scrollTop +=
        scrollContainerRef.current.scrollHeight - previousScrollHeight
      const distanceFromBottom =
        scrollContainerRef.current.scrollHeight -
        scrollContainerRef.current.scrollTop -
        scrollContainerRef.current.clientHeight
      setIsNearLatest(distanceFromBottom <= 80)
      return
    }
    if (!isNearLatest) return
    const scrollToLatest = () => {
      scrollFrameRef.current = null
      messagesEndRef.current?.scrollIntoView({ behavior: "auto" })
    }
    if (typeof window !== "undefined" && window.requestAnimationFrame) {
      scrollFrameRef.current = window.requestAnimationFrame(scrollToLatest)
      return () => {
        if (scrollFrameRef.current !== null) {
          window.cancelAnimationFrame(scrollFrameRef.current)
          scrollFrameRef.current = null
        }
      }
    }
    scrollToLatest()
    return undefined
  }, [isNearLatest, messages])

  const handleScroll = () => {
    const container = scrollContainerRef.current
    if (!container) return
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight
    const nextIsNearLatest = distanceFromBottom <= 80
    setIsNearLatest((previous) =>
      previous === nextIsNearLatest ? previous : nextIsNearLatest,
    )
  }

  const handleJumpToLatest = () => {
    setIsNearLatest(true)
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  const handleLoadOlderMessages = async () => {
    const requestId = loadOlderRequestRef.current + 1
    loadOlderRequestRef.current = requestId
    if (scrollContainerRef.current) {
      previousScrollHeightRef.current = scrollContainerRef.current.scrollHeight
    }
    try {
      const result = await onLoadOlderMessages?.()
      if (
        loadOlderRequestRef.current === requestId &&
        (result?.ok !== true || result.addedCount < 1)
      ) {
        previousScrollHeightRef.current = null
      }
    } catch {
      if (loadOlderRequestRef.current === requestId) {
        previousScrollHeightRef.current = null
      }
    }
  }

  const handleCopy = async (message) => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopiedMessageId(message.id)
      window.setTimeout(() => setCopiedMessageId(""), 1200)
    } catch {
      setCopiedMessageId("")
    }
  }

  const handleEditSubmit = async () => {
    if (!editTargetId || !editValue.trim() || isActionDisabled || isSubmittingEdit) {
      return
    }
    const targetId = editTargetId
    setIsSubmittingEdit(true)
    try {
      const result = await onEditMessage?.(targetId, editValue)
      if (result?.ok !== false) {
        setEditTargetId("")
        setEditValue("")
      }
    } finally {
      setIsSubmittingEdit(false)
    }
  }

  const handleEditCancel = () => {
    if (isSubmittingEdit) return
    setEditTargetId("")
    setEditValue("")
  }

  const handleEditKeyDown = (event) => {
    if (event.nativeEvent.isComposing) return
    if (event.key === "Escape") {
      event.preventDefault()
      handleEditCancel()
      return
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      void handleEditSubmit()
    }
  }

  return (
    <div className="relative flex-1 min-h-0">
      <div
        ref={scrollContainerRef}
        className="h-full min-h-0 space-y-3 overflow-y-auto px-4 py-3"
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        aria-label="대화 메시지"
      >
      {hasOlderMessages ? (
        <div className="flex justify-center">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-xs text-muted-foreground"
            onClick={handleLoadOlderMessages}
            disabled={isLoadingOlderMessages}
          >
            {isLoadingOlderMessages ? <Loader2 className="size-3.5 animate-spin" /> : null}
            이전 메시지 불러오기
          </Button>
        </div>
      ) : null}

      {messages.map((message) => {
        const isUser = message.role === "user"
        const isLocked = message.accessState === "locked"
        const isEditing = isUser && editTargetId === message.id
        const sources = Array.isArray(message.sources) ? message.sources : []
        const knowledgeRouteLabel = getKnowledgeRouteLabel(message.knowledgeContext)
        const messageMailbox =
          typeof message.userSdwtProd === "string" ? message.userSdwtProd.trim() : ""
        const isGreeting =
          message.isGreeting === true ||
          (message.content === "무엇을 도와드릴까요?" &&
            !message.contextKey &&
            sources.length === 0)
        const shouldStreamGreeting =
          isGreeting && messages.length === 1 && Boolean(message.streamId)
        const snapshotScope = message.contextSnapshot?.scope
        const isCurrentScopeAvailable = Boolean(getScopeSignature(currentPageScope))
        const isSameAsCurrentScope =
          isCurrentScopeAvailable &&
          getScopeSignature(snapshotScope) === getScopeSignature(currentPageScope)
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
            <div
              className={[
                "group space-y-1",
                fillBubbles && !isUser
                  ? "w-full"
                  : isEditing
                    ? "w-full max-w-[90%]"
                    : "max-w-[90%]",
              ].join(" ")}
            >
              {isUser ? (
                isEditing ? (
                  <div className="w-full rounded-2xl border bg-muted p-3 shadow-sm">
                    <Textarea
                      value={editValue}
                      onChange={(event) => setEditValue(event.target.value)}
                      onKeyDown={handleEditKeyDown}
                      onFocus={(event) => {
                        const end = event.currentTarget.value.length
                        event.currentTarget.setSelectionRange(end, end)
                      }}
                      aria-label="메시지 수정 입력"
                      aria-describedby={`message-edit-help-${message.id}`}
                      className="max-h-48 min-h-20 resize-none bg-background text-sm leading-relaxed"
                      disabled={isSubmittingEdit}
                      autoFocus
                    />
                    <p
                      id={`message-edit-help-${message.id}`}
                      className="mt-2 text-xs text-muted-foreground"
                    >
                      원본은 보존되고 이 지점부터 새 답변이 생성됩니다.
                    </p>
                    <div className="mt-2 flex items-center justify-end gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={isSubmittingEdit}
                        onClick={handleEditCancel}
                      >
                        취소
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        disabled={!editValue.trim() || isActionDisabled || isSubmittingEdit}
                        onClick={handleEditSubmit}
                      >
                        {isSubmittingEdit ? <Loader2 className="size-3.5 animate-spin" /> : null}
                        {isSubmittingEdit ? "수정 중" : "수정 후 다시 생성"}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <pre
                    className={[
                      ...baseBubbleClasses,
                      "m-0 max-w-full whitespace-pre-wrap break-words",
                      "bg-primary text-primary-foreground font-sans leading-relaxed text-xs",
                    ].join(" ")}
                  >
                    {message.content}
                  </pre>
                )
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
                    "[&_a[data-email-source]]:inline-flex [&_a[data-email-source]]:items-center [&_a[data-email-source]]:rounded-full [&_a[data-email-source]]:border [&_a[data-email-source]]:border-border [&_a[data-email-source]]:bg-background [&_a[data-email-source]]:px-2 [&_a[data-email-source]]:py-0.5 [&_a[data-email-source]]:text-xs [&_a[data-email-source]]:font-medium [&_a[data-email-source]]:text-foreground [&_a[data-email-source]]:no-underline [&_a[data-email-source]]:hover:bg-muted",
                  ].join(" ")}
                >
                  {knowledgeRouteLabel ? (
                    <Badge variant="secondary" className="w-fit text-[10px] font-medium">
                      {knowledgeRouteLabel}
                    </Badge>
                  ) : null}
                  {isGreeting ? (
                    <StreamingText
                      content={message.content}
                      streamId={shouldStreamGreeting ? message.streamId : undefined}
                    />
                  ) : (
                    <div
                      dangerouslySetInnerHTML={{
                        __html: formatAssistantMessage(
                          message.content,
                          sources,
                          messageMailbox,
                          availableMailboxes,
                        ),
                      }}
                    />
                  )}
                  {sources.length > 0 ? (
                    <div className="flex flex-wrap items-center gap-1 pt-1">
                      {sources.map((source) => (
                        <Badge
                          key={`${message.id}-${source.docId}`}
                          asChild
                          variant="outline"
                          className="max-w-60"
                        >
                          <Link
                            to={buildEmailSourceUrl(source.docId, messageMailbox, {
                              availableMailboxes,
                            })}
                          >
                            <span className="truncate">
                              {source.title || "관련 메일 보기"}
                            </span>
                          </Link>
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              )}

              {!isEditing && message.contextSnapshot ? (
                <Collapsible className="rounded-lg border bg-background/70 px-2 py-1.5 text-xs">
                  <CollapsibleTrigger asChild>
                    <Button type="button" variant="ghost" size="sm" className="h-7 w-full justify-between px-1.5 text-xs">
                      분석 범위와 근거
                      <ChevronDown className="size-3.5" />
                    </Button>
                  </CollapsibleTrigger>
                  <CollapsibleContent className="space-y-2 px-1.5 pb-1.5 text-muted-foreground">
                    <p>분석 당시: {formatScopeSummary(snapshotScope)}</p>
                    {isCurrentScopeAvailable && !isSameAsCurrentScope ? (
                      <p>현재 조회: {formatScopeSummary(currentPageScope)}</p>
                    ) : null}
                    <p>
                      커버리지: {Object.entries(message.contextSnapshot.coverage || {})
                        .filter(([, value]) => ["number", "boolean"].includes(typeof value))
                        .map(([key, value]) => `${key}=${value}`)
                        .join(" · ") || "없음"}
                    </p>
                    {message.contextSnapshot.coverage?.analysisModel ||
                    message.contextSnapshot.coverage?.promptVersion ? (
                      <p>
                        분석 버전: {[
                          message.contextSnapshot.coverage?.analysisModel,
                          message.contextSnapshot.coverage?.promptVersion,
                        ].filter(Boolean).join(" · ")}
                      </p>
                    ) : null}
                    {(message.contextSnapshot.evidence || []).length ? (
                      <ul className="list-disc space-y-1 pl-4">
                        {message.contextSnapshot.evidence.map((evidence, evidenceIndex) => {
                          const evidenceTargets = getEvidenceTargets(
                            message.contextSnapshot,
                            evidence,
                          )
                          return (
                            <li key={`${message.id}-evidence-${evidenceIndex}`}>
                              <span>
                                {[evidence?.category, evidence?.target].filter(Boolean).join(" · ")}
                              </span>
                              {evidenceTargets.length ? (
                                <span className="mt-1 flex flex-wrap gap-1">
                                  {evidenceTargets.map((target) => (
                                    <Button
                                      key={`${message.id}-${target.id}`}
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      className="h-6 max-w-full px-2 text-[10px]"
                                      disabled={!target?.href}
                                      onClick={() => target?.href && navigate(target.href)}
                                      aria-label={`근거 로그 ${target?.id || ""} 열기`}
                                    >
                                      <span className="truncate">{target?.id}</span>
                                    </Button>
                                  ))}
                                </span>
                              ) : null}
                            </li>
                          )
                        })}
                      </ul>
                    ) : null}
                  </CollapsibleContent>
                </Collapsible>
              ) : null}

              {!isEditing && !message.isStreaming && !isGreeting && !isLocked ? (
                <div className={["flex items-center gap-0.5 opacity-70 transition-opacity group-hover:opacity-100", isUser ? "justify-end" : "justify-start"].join(" ")}>
                  <Button type="button" variant="ghost" size="icon" className="size-7" onClick={() => handleCopy(message)} aria-label="메시지 복사">
                    {copiedMessageId === message.id ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                  </Button>
                  {isUser ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-7"
                      disabled={isActionDisabled}
                      onClick={() => {
                        setEditTargetId(message.id)
                        setEditValue(message.content)
                      }}
                      aria-label="메시지 수정"
                    >
                      <Pencil className="size-3.5" />
                    </Button>
                  ) : (
                    <>
                      <Button type="button" variant="ghost" size="icon" className="size-7" disabled={isActionDisabled} onClick={() => onRegenerateMessage?.(message.id)} aria-label="답변 다시 생성">
                        <RefreshCw className="size-3.5" />
                      </Button>
                      <Button type="button" variant={message.feedback?.rating === "up" ? "secondary" : "ghost"} size="icon" className="size-7" onClick={() => onRateMessage?.(message.id, message.feedback?.rating === "up" ? null : "up")} aria-label="도움됨">
                        <ThumbsUp className="size-3.5" />
                      </Button>
                      <Button type="button" variant={message.feedback?.rating === "down" ? "secondary" : "ghost"} size="icon" className="size-7" onClick={() => onRateMessage?.(message.id, message.feedback?.rating === "down" ? null : "down")} aria-label="도움 안 됨">
                        <ThumbsDown className="size-3.5" />
                      </Button>
                    </>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        )
      })}

        <AssistantStatusIndicator isActive={isGenerating} mode={statusMode} />
        <div ref={messagesEndRef} />
      </div>

      {!isNearLatest ? (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="absolute bottom-3 left-1/2 -translate-x-1/2 shadow-md"
          onClick={handleJumpToLatest}
          aria-label="최신 답변으로 이동"
        >
          최신 답변 보기
        </Button>
      ) : null}

    </div>
  )
}
