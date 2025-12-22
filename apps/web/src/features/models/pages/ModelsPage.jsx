import { SidebarHeaderBar, SidebarLayout } from "@/components/layout"
import { Breadcrumb, BreadcrumbItem, BreadcrumbList, BreadcrumbPage } from "@/components/ui/breadcrumb"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarSeparator,
} from "@/components/ui/sidebar"

export function ModelsPage() {
  const sidebar = (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-12" />

      <SidebarContent />
      <SidebarFooter className="h-12" />
    </Sidebar>
  )

  const header = (
    <SidebarHeaderBar>
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbPage className="inline-block h-5 w-32" />
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    </SidebarHeaderBar>
  )

  return (
    <SidebarLayout
      providerKey="models"
      defaultOpen
      sidebar={sidebar}
      header={header}
      headerClassName="h-16 shrink-0 border-b bg-background"
      paddingClassName="p-4 md:p-6"
      scrollAreaClassName="overflow-hidden"
    >
      <div className="grid flex-1 min-h-0 gap-4 md:grid-cols-2">
        <div className="grid min-h-0 grid-rows-[auto,1fr] gap-2">
          <div className="h-10" />
          <div className="min-h-0 overflow-y-auto" />
        </div>
        <div className="min-h-0 overflow-y-auto" />
      </div>
    </SidebarLayout>
  )
}
