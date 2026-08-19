const accountRootQueryKey = ["account"]

export const accountQueryKeys = {
  affiliation: [...accountRootQueryKey, "affiliation"],
  affiliationRequests: [...accountRootQueryKey, "affiliationRequests"],
  affiliationMembers: [...accountRootQueryKey, "affiliationMembers"],
  affiliationGrantCandidates: [...accountRootQueryKey, "affiliationGrantCandidates"],
  overview: [...accountRootQueryKey, "overview"],
  accessUsers: [...accountRootQueryKey, "accessUsers"],
  pendingAccessRequests: [...accountRootQueryKey, "pendingAccessRequests"],
  accessMatrix: [...accountRootQueryKey, "accessMatrix"],
  accessPolicyRules: [...accountRootQueryKey, "accessPolicyRules"],
  accessAuditLogs: [...accountRootQueryKey, "accessAuditLogs"],
  userScopeData: [...accountRootQueryKey, "userScopeData"],
}

export const AFFILIATION_QUERY_KEY = accountQueryKeys.affiliation
