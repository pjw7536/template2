import { Outlet } from "react-router-dom"

import { HomeLayout } from "@/components/layout"
import { ChatWidget } from "@/features/assistant"
import HomeNavbar from "./Navbar"
import { navigationItems } from "../utils/constants"

export function HomeShell() {
  return (
    <>
      <HomeLayout
        header={<HomeNavbar navigationItems={navigationItems} />}
        innerClassName="mx-auto w-full max-w-10xl flex flex-col gap-8"
      >
        <Outlet />
      </HomeLayout>
      <ChatWidget />
    </>
  )
}
