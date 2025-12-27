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
import { isSentMailbox, SENT_MAILBOX_LABEL } from "../utils/mailbox"

export function EmailsHeader({ activeMailbox = "" }) {
  const trimmedMailbox = typeof activeMailbox === "string" ? activeMailbox.trim() : ""
  const displayMailbox = isSentMailbox(trimmedMailbox) ? SENT_MAILBOX_LABEL : trimmedMailbox

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
          {displayMailbox ? (
            <>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage className="max-w-64 truncate">{displayMailbox}</BreadcrumbPage>
              </BreadcrumbItem>
            </>
          ) : null}
        </BreadcrumbList>
      </Breadcrumb>
    </SidebarHeaderBar>
  )
}
