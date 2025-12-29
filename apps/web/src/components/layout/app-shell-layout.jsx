import { AppLayout } from "./app-layout"
import { AppSidebar } from "./app-sidebar"
import { NavMain } from "./nav-main"

export function AppShellLayout({
  children,
  header,
  navItems,
  sidebarHeader,
  sidebarSecondary,
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
  paddingClassName,
  innerClassName,
  providerKey,
  defaultOpen,
}) {
  const safeNavItems = Array.isArray(navItems) ? navItems : []
  const nav = <NavMain items={safeNavItems} />
  const sidebar = (
    <AppSidebar header={sidebarHeader ?? null} nav={nav} secondary={sidebarSecondary} />
  )

  return (
    <AppLayout
      sidebar={sidebar}
      header={header}
      contentMaxWidthClass={contentMaxWidthClass}
      scrollAreaClassName={scrollAreaClassName}
      paddingClassName={paddingClassName}
      innerClassName={innerClassName}
      providerKey={providerKey}
      defaultOpen={defaultOpen}
    >
      {children}
    </AppLayout>
  )
}
