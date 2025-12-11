import { Button } from "@/components/ui/button"
import { Loader2, Send } from "lucide-react"

export function ChatComposer({
  inputId,
  label,
  inputValue,
  onInputChange,
  onSubmit,
  isSending,
  placeholder,
  footerLeft,
  footerRight,
  inputRef,
}) {
  const value = typeof inputValue === "string" ? inputValue : ""
  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      onSubmit?.(event)
    }
  }

  return (
    <form onSubmit={onSubmit} className="shrink-0 border-t bg-background px-3 pb-3 pt-2">
      {label && (
        <label className="sr-only" htmlFor={inputId}>
          {label}
        </label>
      )}
      <div className="flex items-end gap-2 rounded-xl border bg-muted/40 p-2">
        <textarea
          id={inputId}
          ref={inputRef}
          className="min-h-[60px] flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground/70 disabled:cursor-not-allowed disabled:opacity-60"
          placeholder={placeholder}
          value={value}
          onChange={onInputChange}
          onKeyDown={handleKeyDown}
          disabled={isSending}
        />
        <Button
          type="submit"
          size="icon"
          disabled={isSending || !value.trim()}
          className="h-10 w-10 flex-none"
        >
          {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          <span className="sr-only">Send message</span>
        </Button>
      </div>
      {(footerLeft || footerRight) && (
        <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
          <span>{footerLeft}</span>
          <span>{footerRight}</span>
        </div>
      )}
    </form>
  )
}
