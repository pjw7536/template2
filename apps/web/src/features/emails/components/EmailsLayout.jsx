import { useEffect, useRef } from "react"
import { useSearchParams } from "react-router-dom"
import { toast } from "sonner"

import { AppLayout, AppSidebar } from "@/components/layout"
import { useAuth } from "@/lib/auth"
import { buildNavigationConfig } from "@/lib/config/navigation-config"
import {
  ActiveLineProvider,
  NavMain,
  TeamSwitcher,
  useLineSdwtOptionsQuery,
} from "@/features/line-dashboard"

import { useEmailMailboxes } from "../hooks/useEmailMailboxes"
import { getMailboxFromSearchParams, normalizeMailbox } from "../utils/mailbox"
import { EmailsHeader } from "./EmailsHeader"

function normalizeLineId(value) {
  return typeof value === "string" ? value.trim() : ""
}

function buildLineOptions(lineSdwtOptions) {
  const lines = Array.isArray(lineSdwtOptions?.lines) ? lineSdwtOptions.lines : []
  const lineIds = lines
    .map((line) => normalizeLineId(line?.lineId))
    .filter(Boolean)
  return Array.from(new Set(lineIds))
}

function buildAffiliationOptions(lineSdwtOptions, mailboxes) {
  const lines = Array.isArray(lineSdwtOptions?.lines) ? lineSdwtOptions.lines : []
  const mailboxSet = new Set(mailboxes)

  return lines.flatMap((line) => {
    const lineId = normalizeLineId(line?.lineId)
    if (!lineId) return []

    const userSdwtProds = Array.isArray(line?.userSdwtProds) ? line.userSdwtProds : []

    return userSdwtProds
      .map((value) => normalizeMailbox(value))
      .filter((value) => value && mailboxSet.has(value))
      .map((userSdwtProd) => ({
        id: userSdwtProd,
        label: `${lineId} / ${userSdwtProd}`,
        lineId,
      }))
  })
}

export function EmailsLayout({
  children,
  contentMaxWidthClass,
  scrollAreaClassName,
}) {
  const [searchParams, setSearchParams] = useSearchParams()
  const { user } = useAuth()
  const invalidMailboxRef = useRef("")

  const {
    data: mailboxData,
    isLoading: isMailboxLoading,
    isError: isMailboxError,
    error: mailboxError,
  } = useEmailMailboxes()
  const {
    data: lineSdwtOptions,
    isError: isLineSdwtError,
    error: lineSdwtError,
  } = useLineSdwtOptionsQuery()

  const mailboxes = Array.isArray(mailboxData?.results) ? mailboxData.results : []
  const mailboxParam = getMailboxFromSearchParams(searchParams)
  const currentUserSdwtProd = normalizeMailbox(user?.user_sdwt_prod)
  const firstMailbox = normalizeMailbox(mailboxes[0])
  const fallbackMailbox = mailboxParam || currentUserSdwtProd || firstMailbox
  const activeMailbox = mailboxParam || fallbackMailbox
  const normalizedMailboxes = mailboxes.map(normalizeMailbox).filter(Boolean)
  const lineOptions = buildLineOptions(lineSdwtOptions)
  const affiliationOptions = buildAffiliationOptions(lineSdwtOptions, normalizedMailboxes)

  useEffect(() => {
    if (isMailboxError && mailboxError) {
      toast.error(mailboxError?.message || "메일함 목록을 불러오지 못했습니다.")
    }
  }, [isMailboxError, mailboxError])

  useEffect(() => {
    if (isLineSdwtError) {
      console.warn("Failed to load line SDWT options", lineSdwtError)
    }
  }, [isLineSdwtError, lineSdwtError])

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

  const navigation = buildNavigationConfig({ mailbox: activeMailbox })
  const nav = <NavMain items={navigation.navMain} />
  const sidebar = (
    <AppSidebar
      header={
        <TeamSwitcher
          options={affiliationOptions}
          activeId={activeMailbox}
          onSelect={handleSelectMailbox}
          menuLabel="Line / SDWT"
          manageLabel="Manage mailboxes"
          ariaLabel="메일함(SDWT) 선택"
          mode="affiliation"
        />
      }
      nav={nav}
    />
  )

  return (
    <ActiveLineProvider lineOptions={lineOptions}>
      <AppLayout
        sidebar={sidebar}
        header={<EmailsHeader activeMailbox={activeMailbox} />}
        contentMaxWidthClass={contentMaxWidthClass}
        scrollAreaClassName={scrollAreaClassName}
      >
        {children}
      </AppLayout>
    </ActiveLineProvider>
  )
}
