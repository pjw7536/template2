import { cn } from "@/lib/utils"

/** shadcn Input과 같은 모양의 기본 select입니다. */
export function NativeSelect({ className, ...props }) {
  return (
    <select
      className={cn(
        "h-9 min-w-0 rounded-md border border-input bg-transparent px-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30",
        className,
      )}
      {...props}
    />
  )
}
