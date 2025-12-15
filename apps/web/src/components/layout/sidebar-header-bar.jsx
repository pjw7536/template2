import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

export function SidebarHeaderBar({
  children,
  right,
  showSidebarTrigger = true,
  className,
  leftClassName,
  rightClassName,
}) {
  return (
    <div
      className={cn(
        "flex h-full items-center justify-between gap-2 px-4 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-full",
        className
      )}
    >
      <div className={cn("flex min-w-0 items-center gap-2", leftClassName)}>
        {showSidebarTrigger ? (
          <>
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
          </>
        ) : null}
        {children}
      </div>
      <div className={cn("flex shrink-0 items-center", rightClassName)}>{right ?? null}</div>
    </div>
  )
}
