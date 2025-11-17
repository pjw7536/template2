// src/components/layout/index.js
// 레이아웃 계층(AppShell/Sidebar/Header 등)을 한 번에 내보내 구조 탐색을 단순화합니다.

export { AppShell } from "./app-shell"
export { AppHeader } from "./app-header"
export { AppSidebar } from "./app-sidebar"
export { AppSidebarProvider } from "./app-sidebar-provider"
export { DynamicBreadcrumb } from "./dynamic-breadcrumb"
export { NavMain } from "./nav-main"
export { NavProjects } from "./nav-projects"
export { NavUser } from "./nav-user"
export { TeamSwitcher } from "./team-switcher"
export { ActiveLineProvider, useActiveLine } from "./active-line-context"
