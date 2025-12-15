import { Link } from "react-router-dom"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { ThemeControls } from "@/components/common"
import { SidebarHeaderBar } from "@/components/layout"

export function EmailsHeader({ activeMailbox = "" }) {
  const trimmedMailbox = typeof activeMailbox === "string" ? activeMailbox.trim() : ""

  return (
    <SidebarHeaderBar right={<ThemeControls />}>
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/">Home</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Emails</BreadcrumbPage>
          </BreadcrumbItem>
          {trimmedMailbox ? (
            <>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage className="max-w-64 truncate">{trimmedMailbox}</BreadcrumbPage>
              </BreadcrumbItem>
            </>
          ) : null}
        </BreadcrumbList>
      </Breadcrumb>
    </SidebarHeaderBar>
  )
}
