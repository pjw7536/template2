import { Outlet } from "react-router-dom"

import { HomeLayout as BaseHomeLayout } from "@/components/layout"
import { ChatWidget } from "@/features/assistant"
import { navigationItems } from "../constants"
import HomeNavbar from "./Navbar"

export function HomeLayout() {
  return (
    <>
      <BaseHomeLayout
        header={<HomeNavbar navigationItems={navigationItems} />}
        innerClassName="mx-auto w-full max-w-10xl flex flex-col gap-8"
      >
        <Outlet />
      </BaseHomeLayout>
      <ChatWidget />
    </>
  )
}
