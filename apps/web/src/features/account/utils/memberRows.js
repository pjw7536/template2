const AFFILIATION_ROLES = new Set(["viewer", "member", "manager"])

function normalizeAffiliationRole(value) {
  const normalizedRole = String(value || "").toLowerCase()
  return AFFILIATION_ROLES.has(normalizedRole) ? normalizedRole : "viewer"
}

export function buildMemberRows(members) {
  return (Array.isArray(members) ? members : []).map((member) => {
    const displayName =
      member?.name?.trim() || member?.username?.trim() || member?.knoxId || "알 수 없음"
    const memberAffiliation = member?.userSdwtProd || ""

    return {
      id: `member-${member.userId}`,
      userId: member.userId,
      type: "member",
      name: displayName,
      knoxId: member.knoxId || "-",
      email: member.email || "",
      affiliationLabel: [member.department, memberAffiliation].filter(Boolean).join(" / ") || "-",
      memberRole: normalizeAffiliationRole(member.role),
      isCurrentAffiliation: Boolean(member.isCurrentAffiliation),
      approvalRole: null,
      requestedAt: null,
      changeId: null,
      status: "MEMBER",
    }
  })
}

export function buildAffiliationRequestRows(requests) {
  return (Array.isArray(requests) ? requests : []).map((change) => {
    const targetParts = [change?.department, change?.line, change?.toUserSdwtProd].filter(Boolean)

    return {
      id: `request-${change.id}`,
      type: "request",
      name: change?.user?.username || change?.user?.sabun || "알 수 없음",
      knoxId: change?.user?.knoxId || "-",
      email: change?.user?.email || "",
      affiliationLabel: targetParts.length > 0
        ? targetParts.join(" / ")
        : change?.toUserSdwtProd || "-",
      memberRole: null,
      approvalRole: normalizeAffiliationRole(change?.role),
      requestedAt: change.requestedAt,
      changeId: change.id,
      status: change.status || "PENDING",
    }
  })
}

export function selectVisibleMemberRows({ activeTab, memberRows, requestRows }) {
  if (activeTab === "members") return memberRows
  if (activeTab === "requests") return requestRows
  return [...requestRows, ...memberRows]
}
