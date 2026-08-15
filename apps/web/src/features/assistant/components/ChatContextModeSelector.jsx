import { ASSISTANT_KNOWLEDGE_MODES } from "../utils/profileKeys"

export function ChatContextModeSelector({
  appLabel,
  mode,
  onChange,
  disabled = false,
  currentAppReady = true,
  disabledReason = "",
}) {
  const knowledgeLabel = appLabel === "Appstore" ? "App Store" : appLabel
  const groupLabel = `${knowledgeLabel} 지식 선택 모드`
  const options = [
    {
      value: ASSISTANT_KNOWLEDGE_MODES.currentApp,
      label: "현재 앱 지식만 사용",
      disabled: !currentAppReady,
    },
    {
      value: ASSISTANT_KNOWLEDGE_MODES.auto,
      label: "자동 지식 선택",
      disabled: false,
    },
  ]

  return (
    <div
      role="radiogroup"
      aria-label={groupLabel}
      className="inline-flex h-8 shrink-0 items-center rounded-lg border bg-muted/50 p-0.5 text-[10px] font-medium"
    >
      {options.map((option) => {
        const isSelected = mode === option.value
        const isDisabled = disabled || option.disabled
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isSelected}
            disabled={isDisabled}
            title={option.disabled && disabledReason ? disabledReason : undefined}
            onClick={() => onChange(option.value)}
            className={`inline-flex h-6 items-center rounded-md px-2 whitespace-nowrap outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring ${isSelected ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"} disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
