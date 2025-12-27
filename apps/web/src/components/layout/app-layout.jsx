// src/components/layout/app-layout.jsx
import { useLocation } from "react-router-dom"

import { SidebarLayout } from "./sidebar-layout"

export function AppLayout({
  children,
  sidebar,
  header,
  providerKey,
  defaultOpen,
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
  paddingClassName = "px-4 pb-3",
  innerClassName = "mx-auto flex h-full w-full flex-col gap-4",
}) {
  const { pathname } = useLocation()
  const resolvedProviderKey = providerKey ?? pathname
  const resolvedDefaultOpen = defaultOpen ?? pathname !== "/"

  return (
    <SidebarLayout
      providerKey={resolvedProviderKey}
      defaultOpen={resolvedDefaultOpen}
      sidebar={sidebar}
      header={header}
      contentMaxWidthClass={contentMaxWidthClass}
      scrollAreaClassName={scrollAreaClassName}
      paddingClassName={paddingClassName}
      innerClassName={innerClassName}
    >
      {children}
    </SidebarLayout>
  )
}
