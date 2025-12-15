import { useEffect, useRef } from "react"
import { useLocation, useSearchParams } from "react-router-dom"
import { toast } from "sonner"

import { SidebarLayout } from "@/components/layout"
import { useAuth } from "@/lib/auth"

import { useEmailMailboxes } from "../hooks/useEmailMailboxes"
import { getMailboxFromSearchParams, normalizeMailbox } from "../utils/mailbox"
import { EmailMailboxSidebar } from "./EmailMailboxSidebar"
import { EmailsHeader } from "./EmailsHeader"

export function EmailsLayout({
  children,
  contentMaxWidthClass,
  scrollAreaClassName,
}) {
  const { pathname } = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { user } = useAuth()
  const invalidMailboxRef = useRef("")

  const {
    data: mailboxData,
    isLoading: isMailboxLoading,
    isError: isMailboxError,
    error: mailboxError,
  } = useEmailMailboxes()

  const mailboxes = Array.isArray(mailboxData?.results) ? mailboxData.results : []
  const mailboxParam = getMailboxFromSearchParams(searchParams)
  const currentUserSdwtProd = normalizeMailbox(user?.user_sdwt_prod)
  const firstMailbox = normalizeMailbox(mailboxes[0])
  const fallbackMailbox = mailboxParam || currentUserSdwtProd || firstMailbox
  const activeMailbox = mailboxParam || fallbackMailbox
  const normalizedMailboxes = mailboxes.map(normalizeMailbox).filter(Boolean)

  useEffect(() => {
    if (isMailboxError && mailboxError) {
      toast.error(mailboxError?.message || "메일함 목록을 불러오지 못했습니다.")
    }
  }, [isMailboxError, mailboxError])

  useEffect(() => {
    if (!mailboxParam) return
    if (isMailboxLoading) return
    if (isMailboxError) return
    if (normalizedMailboxes.length === 0) return
    if (normalizedMailboxes.includes(mailboxParam)) {
      invalidMailboxRef.current = ""
      return
    }

    if (invalidMailboxRef.current === mailboxParam) return
    invalidMailboxRef.current = mailboxParam
    toast.error("권한이 없는 메일함 입니다.")

    const nextMailbox =
      (currentUserSdwtProd && normalizedMailboxes.includes(currentUserSdwtProd) && currentUserSdwtProd) ||
      normalizedMailboxes[0] ||
      ""

    if (!nextMailbox) return

    const nextParams = new URLSearchParams(searchParams)
    nextParams.set("mailbox", nextMailbox)
    nextParams.delete("userSdwtProd")
    nextParams.delete("user_sdwt_prod")
    nextParams.delete("emailId")
    setSearchParams(nextParams, { replace: true })
  }, [
    mailboxParam,
    currentUserSdwtProd,
    isMailboxError,
    isMailboxLoading,
    normalizedMailboxes,
    searchParams,
    setSearchParams,
  ])

  useEffect(() => {
    if (mailboxParam) return
    if (!fallbackMailbox) return

    const nextParams = new URLSearchParams(searchParams)
    nextParams.set("mailbox", fallbackMailbox)
    nextParams.delete("userSdwtProd")
    nextParams.delete("user_sdwt_prod")
    setSearchParams(nextParams, { replace: true })
  }, [fallbackMailbox, mailboxParam, searchParams, setSearchParams])

  const handleSelectMailbox = (mailbox) => {
    const nextMailbox = normalizeMailbox(mailbox)
    if (!nextMailbox || nextMailbox === mailboxParam) return

    const nextParams = new URLSearchParams(searchParams)
    nextParams.set("mailbox", nextMailbox)
    nextParams.delete("emailId")
    nextParams.delete("userSdwtProd")
    nextParams.delete("user_sdwt_prod")
    setSearchParams(nextParams)
  }

  const sidebar = (
    <EmailMailboxSidebar
      mailboxes={mailboxes}
      activeMailbox={activeMailbox}
      onSelectMailbox={handleSelectMailbox}
      isLoading={isMailboxLoading}
      errorMessage={
        isMailboxError ? mailboxError?.message || "메일함 목록을 불러오지 못했습니다." : ""
      }
    />
  )

  return (
    <SidebarLayout
      providerKey={pathname}
      defaultOpen
      sidebar={sidebar}
      header={<EmailsHeader activeMailbox={activeMailbox} />}
      contentMaxWidthClass={contentMaxWidthClass}
      scrollAreaClassName={scrollAreaClassName}
    >
      {children}
    </SidebarLayout>
  )
}
