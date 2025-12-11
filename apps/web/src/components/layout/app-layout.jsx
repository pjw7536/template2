// src/components/layout/app-layout.jsx
import { ContentLayout } from "./content-layout"

export function AppLayout({
  children,
  header,
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
  paddingClassName = "p-4 md:p-6",
  innerClassName = "mx-auto flex h-full w-full flex-col gap-4",
}) {
  return (
    <div className="h-screen flex flex-col bg-background">
      <header className="relative z-30 h-16 shrink-0 border-b bg-background">
        <div className="h-full">{header ?? null}</div>
      </header>
      <main className="flex-1 min-h-0 min-w-0 overflow-hidden">
        <ContentLayout
          contentMaxWidthClass={contentMaxWidthClass}
          scrollAreaClassName={scrollAreaClassName}
          paddingClassName={paddingClassName}
          innerClassName={innerClassName}
        >
          {children}
        </ContentLayout>
      </main>
    </div>
  )
}
