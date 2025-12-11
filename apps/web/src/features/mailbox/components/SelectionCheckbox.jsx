import { cn } from "@/lib/utils"

export function SelectionCheckbox({ checked, onCheckedChange, className, ...props }) {
  return (
    <input
      type="checkbox"
      checked={checked}
      onChange={(event) => {
        event.stopPropagation()
        onCheckedChange?.(event.target.checked)
      }}
      className={cn(
        "h-4 w-4 cursor-pointer rounded border border-input bg-background text-primary shadow-sm transition",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className,
      )}
      {...props}
    />
  )
}
