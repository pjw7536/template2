// Shared layout container for consistent page spacing and scrolling behavior
import { cn } from "@/lib/utils"

export function ContentLayout({
  children,
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
  paddingClassName = "p-4 md:p-6",
  innerClassName = "mx-auto flex h-full w-full flex-col gap-4",
}) {
  return (
    <div className="h-full min-h-0 min-w-0">
      <div className={cn("h-full min-h-0 min-w-0", scrollAreaClassName)}>
        <div className={cn(innerClassName, contentMaxWidthClass, paddingClassName)}>
          {children}
        </div>
      </div>
    </div>
  )
}
