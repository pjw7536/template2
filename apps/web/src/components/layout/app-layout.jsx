// src/components/layout/app-layout.jsx
import { HomeNavbar, navigationItems as homeNavigationItems } from "@/features/home"

export function AppLayout({
  children,
  navbar,
  contentMaxWidthClass = "max-w-10xl",
  mainOverflowClass = "overflow-auto",
}) {
  const navbarNode = navbar ?? <HomeNavbar navigationItems={homeNavigationItems} />

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {navbarNode}
      <main
        className={[
          "flex-1 min-h-0 min-w-0 px-4 pb-6 pt-2",
          mainOverflowClass,
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <div
          className={[
            "mx-auto flex h-full w-full flex-col gap-4",
            contentMaxWidthClass,
          ]
            .filter(Boolean)
            .join(" ")}
        >
          {children}
        </div>
      </main>
    </div>
  )
}
