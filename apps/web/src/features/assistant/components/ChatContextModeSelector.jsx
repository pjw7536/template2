import { useId } from "react"
import { Switch as SwitchPrimitive } from "@base-ui/react/switch"

export function ChatContextModeSelector({
  usesAppContext,
  onChange,
  disabled = false,
  disabledReason = "",
}) {
  const switchId = useId()

  return (
    <div
      title={disabled && disabledReason ? disabledReason : undefined}
      className={`inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap text-[11px] font-medium text-foreground ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
    >
      <SwitchPrimitive.Root
        id={switchId}
        checked={usesAppContext}
        onCheckedChange={(checked) => onChange(checked === true)}
        disabled={disabled}
        data-slot="switch"
        data-size="sm"
        aria-label="현재 앱 지식 사용"
        className="peer group/switch relative inline-flex h-[14px] w-[24px] shrink-0 items-center rounded-full border border-transparent bg-input outline-none transition-all after:absolute after:-inset-x-3 after:-inset-y-2 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 data-checked:bg-primary data-disabled:cursor-not-allowed data-disabled:opacity-50 dark:data-unchecked:bg-input/80"
      >
        <SwitchPrimitive.Thumb
          data-slot="switch-thumb"
          className="pointer-events-none block size-3 translate-x-0 rounded-full bg-background ring-0 transition-transform group-data-checked/switch:translate-x-[calc(100%-2px)] dark:data-checked:bg-primary-foreground dark:data-unchecked:bg-foreground"
        />
      </SwitchPrimitive.Root>
      <label
        htmlFor={switchId}
        className={`inline-flex h-8 items-center ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}
      >
        현재 앱 지식 사용
      </label>
    </div>
  )
}
