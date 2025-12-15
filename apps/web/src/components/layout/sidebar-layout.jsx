import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"

import { ContentLayout } from "./content-layout"

export function SidebarLayout({
  children,
  sidebar,
  header,
  providerKey,
  defaultOpen = true,
  providerClassName,
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
  paddingClassName = "px-4 pb-3",
  innerClassName = "mx-auto flex h-full w-full flex-col gap-4",
  insetClassName = "h-screen",
  headerClassName = "h-16 shrink-0 bg-background",
  mainClassName = "flex-1 min-h-0 min-w-0 overflow-hidden",
}) {
  return (
    <SidebarProvider key={providerKey} defaultOpen={defaultOpen} className={providerClassName}>
      {sidebar ?? null}
      <SidebarInset className={insetClassName}>
        <header className={headerClassName}>
          <div className="h-full">{header ?? null}</div>
        </header>
        <main className={mainClassName}>
          <ContentLayout
            contentMaxWidthClass={contentMaxWidthClass}
            scrollAreaClassName={scrollAreaClassName}
            paddingClassName={paddingClassName}
            innerClassName={innerClassName}
          >
            {children}
          </ContentLayout>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}

