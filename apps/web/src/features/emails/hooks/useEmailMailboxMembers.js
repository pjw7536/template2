import { useQuery } from "@tanstack/react-query"

import { fetchEmailMailboxMembers } from "../api/emails"

function normalizeText(value) {
  return typeof value === "string" ? value.trim() : ""
}

function normalizeMailbox(value) {
  return normalizeText(value)
}

function getInitials(value) {
  const trimmed = normalizeText(value)
  if (!trimmed) return "?"

  const parts = trimmed.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) {
    return `${parts[0].slice(0, 1)}${parts[1].slice(0, 1)}`.toUpperCase()
  }

  return trimmed.slice(0, 2).toUpperCase()
}

function toSafeNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function buildMemberRow(member) {
  const userId = member?.userId ?? member?.user_id ?? ""
  const name = normalizeText(member?.name)
  const username = normalizeText(member?.username)
  const userSdwtProd = normalizeText(member?.userSdwtProd ?? member?.user_sdwt_prod)

  const primary = name || username || userSdwtProd || "Unknown"
  const secondaryCandidates = [username, userSdwtProd].filter(Boolean).filter((item) => item !== primary)
  const secondary = secondaryCandidates[0] || ""

  const idParts = [userId, userSdwtProd, username].map((value) => String(value || "").trim()).filter(Boolean)
  const id = idParts.join("-") || primary

  return {
    id,
    userId,
    userSdwtProd,
    name,
    username,
    user: primary,
    secondary,
    fallback: getInitials(primary),
    permission: member?.canManage || member?.can_manage ? "admin" : "member",
    emailCount: toSafeNumber(member?.emailCount),
  }
}

export function useEmailMailboxMembers(mailbox, options = {}) {
  const mailboxUserSdwtProd = normalizeMailbox(mailbox)
  const enabled = options.enabled ?? Boolean(mailboxUserSdwtProd)

  const query = useQuery({
    queryKey: ["emails", "mailboxMembers", mailboxUserSdwtProd],
    queryFn: () => fetchEmailMailboxMembers(mailboxUserSdwtProd),
    enabled,
    staleTime: 60 * 1000,
  })

  const rawMembers = Array.isArray(query.data?.members) ? query.data.members : []
  const members = rawMembers.map(buildMemberRow)

  return {
    ...query,
    mailboxUserSdwtProd,
    members,
  }
}
