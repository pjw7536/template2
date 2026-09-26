import { normalizeMailbox, isSentMailbox, isUnassignedMailbox, SENT_MAILBOX_ID, SENT_MAILBOX_LABEL, UNASSIGNED_MAILBOX_LABEL } from "./mailbox"

export function buildAffiliationOptions(
  lineSdwtOptions,
  mailboxes,
  {
    includeSent = false,
    includeUnassigned = false,
    unassignedMailboxId = "",
    unassignedLabel = UNASSIGNED_MAILBOX_LABEL,
  } = {},
) {
  const lines = Array.isArray(lineSdwtOptions?.lines) ? lineSdwtOptions.lines : []
  const mailboxSet = new Set(mailboxes)

  const options = lines.flatMap((line) => {
    const lineId = typeof line?.lineId === "string" ? line.lineId.trim() : ""
    if (!lineId) return []

    const userSdwtProds = Array.isArray(line?.userSdwtProds) ? line.userSdwtProds : []

    return userSdwtProds
      .map((value) => normalizeMailbox(value))
      .filter((value) => value && mailboxSet.has(value))
      .map((userSdwtProd) => ({
        id: userSdwtProd,
        label: `${lineId} / ${userSdwtProd}`,
        lineId,
        userSdwtProd,
      }))
  })

  const known = new Set(options.map((option) => option.id))
  for (const mailbox of mailboxes) {
    if (!mailbox || known.has(mailbox) || isSentMailbox(mailbox) || isUnassignedMailbox(mailbox)) continue
    options.push({ id: mailbox, label: mailbox, lineId: null, userSdwtProd: mailbox })
    known.add(mailbox)
  }

  const normalizedUnassigned = normalizeMailbox(unassignedMailboxId)
  if (includeUnassigned && normalizedUnassigned) {
    options.unshift({
      id: normalizedUnassigned,
      label: unassignedLabel,
      description: "미분류 메일함",
      lineId: null,
      userSdwtProd: normalizedUnassigned,
    })
  }

  if (includeSent) {
    options.unshift({
      id: SENT_MAILBOX_ID,
      label: SENT_MAILBOX_LABEL,
      lineId: null,
      userSdwtProd: null,
    })
  }

  return options
}
