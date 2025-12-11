import { Outlet } from "react-router-dom"

import { AppLayout } from "@/components/layout"
import { ChatWidget } from "@/features/assistant"
import { navigationItems } from "../constants"
import HomeNavbar from "./Navbar"

export function HomeLayout() {
  return (
    <>
      <AppLayout
        header={<HomeNavbar navigationItems={navigationItems} />}
        innerClassName="mx-auto w-full max-w-10xl flex flex-col gap-8"
      >
        <Outlet />
      </AppLayout>
      <ChatWidget />
    </>
  )
}
