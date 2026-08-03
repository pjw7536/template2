import { useAuth } from "@/lib/auth"
import {
  useAccessUserDecision as useAccessUserDecisionBase,
  useApplyAllUserAccess as useApplyAllUserAccessBase,
  useBulkApplyAccessPolicyRules as useBulkApplyAccessPolicyRulesBase,
  useBulkApprovePendingAccessRequests as useBulkApprovePendingAccessRequestsBase,
  useCreateAccessPolicyRule as useCreateAccessPolicyRuleBase,
  useDeleteAccessPolicyRule as useDeleteAccessPolicyRuleBase,
  useUpdateAccessPolicyRule as useUpdateAccessPolicyRuleBase,
} from "@/lib/account/useAccountData"

export {
  useAccessAuditLogs,
  useAccessMatrix,
  useAccessPolicyRules,
  useAccessUsers,
  usePendingAccessRequests,
  useAccountOverview,
  useAffiliation,
  useAffiliationAccessMutation,
  useAffiliationDecision,
  useAffiliationGrantCandidates,
  useAffiliationMembers,
  useInfiniteAffiliationRequests,
  useUpdateAffiliation,
  useUpdateUserScopeData,
  useUserScopeData,
} from "@/lib/account/useAccountData"

function useRefreshAuth() {
  return useAuth().refresh
}

export function useBulkApprovePendingAccessRequests() {
  return useBulkApprovePendingAccessRequestsBase({ refreshAuth: useRefreshAuth() })
}

export function useAccessUserDecision() {
  return useAccessUserDecisionBase({ refreshAuth: useRefreshAuth() })
}

export function useApplyAllUserAccess() {
  return useApplyAllUserAccessBase({ refreshAuth: useRefreshAuth() })
}

export function useCreateAccessPolicyRule() {
  return useCreateAccessPolicyRuleBase({ refreshAuth: useRefreshAuth() })
}

export function useBulkApplyAccessPolicyRules() {
  return useBulkApplyAccessPolicyRulesBase({ refreshAuth: useRefreshAuth() })
}

export function useUpdateAccessPolicyRule() {
  return useUpdateAccessPolicyRuleBase({ refreshAuth: useRefreshAuth() })
}

export function useDeleteAccessPolicyRule() {
  return useDeleteAccessPolicyRuleBase({ refreshAuth: useRefreshAuth() })
}
