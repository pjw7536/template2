import { Outlet } from "react-router-dom"

import { ChatWidget } from "@/features/assistant"
import { navigationItems } from "../constants"
import HomeNavbar from "./Navbar"

export function HomeLayout() {
  return (
    <div className="min-h-screen bg-background">
      <HomeNavbar navigationItems={navigationItems} />
      <main>
        <Outlet />
      </main>
      <ChatWidget />
    </div>
  )
}
