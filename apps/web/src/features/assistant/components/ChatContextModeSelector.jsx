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
      label: "현재 화면",
      disabled: !currentAppReady,
    },
    {
      value: ASSISTANT_KNOWLEDGE_MODES.auto,
      label: "자동",
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

export function ChatKnowledgeToggle({ checked, onChange, disabled = false }) {
  return (
    <label className="inline-flex h-8 shrink-0 items-center gap-2 rounded-lg border bg-muted/50 px-2 text-[10px] font-medium text-foreground">
      <span>업무 지식 자동 사용</span>
      <button
        type="button"
        role="switch"
        aria-label="업무 지식 자동 사용"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(
          checked
            ? ASSISTANT_KNOWLEDGE_MODES.generalOnly
            : ASSISTANT_KNOWLEDGE_MODES.auto,
        )}
        className={`relative inline-flex h-5 w-9 items-center rounded-full border outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 ${checked ? "border-primary bg-primary" : "border-input bg-background"}`}
      >
        <span
          className={`block size-3.5 rounded-full bg-primary-foreground shadow-sm transition-transform ${checked ? "translate-x-[17px]" : "translate-x-0.5"}`}
        />
      </button>
    </label>
  )
}
