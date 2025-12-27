// src/components/layout/home-layout.jsx
import { ContentLayout } from "./content-layout"

export function HomeLayout({
  children,
  header,
  headerClassName = "relative z-30 h-16 shrink-0 border-b bg-background",
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
  paddingClassName = "p-3 md:p-3",
  innerClassName = "mx-auto flex h-full w-full flex-col gap-4",
}) {
  return (
    <div className="h-screen flex flex-col bg-background">
      <header className={headerClassName}>
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
