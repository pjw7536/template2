import { Loader2 } from "lucide-react"

import { useAssistantStatusSteps } from "../hooks/useAssistantStatusSteps"

export function AssistantStatusIndicator({ isSending }) {
  const { statusText, stepIndex, totalSteps } = useAssistantStatusSteps(isSending)

  if (!isSending) return null

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground" aria-live="polite">
      <Loader2 className="h-3 w-3 animate-spin" />
      <div className="flex items-center gap-1">
        <span>{statusText}</span>
        <span className="text-[10px] text-muted-foreground/80">
          {stepIndex + 1}/{totalSteps}
        </span>
      </div>
    </div>
  )
}
