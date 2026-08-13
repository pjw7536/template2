import { useId } from "react"

import { cn } from "@/lib/utils"

const OPTION_CLASS_NAME =
  "flex min-w-0 cursor-pointer items-center justify-center rounded-md px-2 py-1.5 text-xs font-medium text-muted-foreground transition-colors peer-checked:bg-card peer-checked:text-foreground peer-checked:shadow-sm peer-focus-visible:outline-none peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-1 peer-disabled:cursor-not-allowed"

export function ChatContextModeSelector({
  appLabel,
  usesAppContext,
  onChange,
  disabled = false,
}) {
  const groupId = useId()
  const generalId = `${groupId}-general`
  const appId = `${groupId}-app`

  return (
    <fieldset disabled={disabled} className="min-w-0 disabled:opacity-60">
      <legend className="sr-only">대화 배경지식 선택</legend>
      <div className="grid grid-cols-2 gap-1 rounded-lg border bg-muted p-1">
        <label htmlFor={generalId} className="min-w-0">
          <input
            id={generalId}
            type="radio"
            name={groupId}
            checked={!usesAppContext}
            onChange={() => onChange(false)}
            className="peer sr-only"
          />
          <span className={OPTION_CLASS_NAME}>일반 대화</span>
        </label>
        <label htmlFor={appId} className="min-w-0" title={`${appLabel} 배경지식 사용`}>
          <input
            id={appId}
            type="radio"
            name={groupId}
            checked={usesAppContext}
            onChange={() => onChange(true)}
            className="peer sr-only"
          />
          <span className={cn(OPTION_CLASS_NAME, "truncate")}>{appLabel} 지식 사용</span>
        </label>
      </div>
    </fieldset>
  )
}
