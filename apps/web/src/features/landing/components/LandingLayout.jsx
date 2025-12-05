import { Outlet } from "react-router-dom"

import Navbar from "./Navbar"
import { navigationItems } from "../constants"

export function LandingLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar navigationItems={navigationItems} />
      <main>
        <Outlet />
      </main>
    </div>
  )
}
