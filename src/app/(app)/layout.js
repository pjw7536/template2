// src/app/(app)/layout.js
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarTrigger } from "@/components/ui/sidebar"
import { ThemeToggle } from "@/components/theme-toggle"
import { DynamicBreadcrumb } from "@/components/navigation/dynamic-breadcrumb"
import { AppSidebar, AppSidebarProvider } from "@/features/navigation"
import { getDistinctLineIds } from "@/features/line-dashboard/api/get-line-ids"

export default async function AppLayout({ children }) {
  let lineOptions = []

  try {
    lineOptions = await getDistinctLineIds()
  } catch {
    lineOptions = []
  }

  return (
    <AppSidebarProvider>
      <AppSidebar lineOptions={lineOptions} />
      <SidebarInset>
        <header
          className="flex h-14 shrink-0 items-center justify-between gap-2 px-4 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12"
        >
          <div className="flex items-center gap-2">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
            <DynamicBreadcrumb />
          </div>
          <ThemeToggle />
        </header>
        <main className="flex-1 min-h-0 min-w-0 p-2 pt-0 overflow-hidden">
          <div className="h-full overflow-hidden">
            {children}
          </div>
        </main>
      </SidebarInset>
    </AppSidebarProvider>
  )
}
