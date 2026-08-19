import { useState } from "react"
import { toast } from "sonner"
import { CheckCircle2, Clock3, ShieldCheck, UserPlus, Users } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useAuth } from "@/lib/auth"

import { MembersDataTable } from "../components/MembersDataTable"
import { MembersSummaryCards } from "../components/cards/MembersSummaryCards"
import { MembersAccessDialogs } from "../components/dialog/MembersAccessDialogs"
import {
  useAffiliationMembers,
  useAffiliationAccessMutation,
  useAffiliationDecision,
  useAffiliationGrantCandidates,
  useInfiniteAffiliationRequests,
  useAffiliation,
} from "../hooks/useAccountData"
import {
  buildAffiliationRequestRows,
  buildMemberRows,
  selectVisibleMemberRows,
} from "../utils/memberRows"

const REQUEST_PAGE_SIZE = 20

export default function MembersPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState("all")
  const [roleFilter, setRoleFilter] = useState("all")
  const [searchTerm, setSearchTerm] = useState("")
  const [rejectTarget, setRejectTarget] = useState(null)
  const [rejectReason, setRejectReason] = useState("")
  const [grantOpen, setGrantOpen] = useState(false)
  const [grantSearch, setGrantSearch] = useState("")
  const [grantUserId, setGrantUserId] = useState("")
  const [grantRole, setGrantRole] = useState("viewer")
  const [grantReason, setGrantReason] = useState("")
  const [roleChangeTarget, setRoleChangeTarget] = useState(null)
  const [roleChangeReason, setRoleChangeReason] = useState("")
  const [revokeTarget, setRevokeTarget] = useState(null)
  const [revokeReason, setRevokeReason] = useState("")
  const [selectedUserSdwtProd, setSelectedUserSdwtProd] = useState("")
  const currentUserSdwtProd = (user?.userSdwtProd || "").trim()
  const { data: affiliationData } = useAffiliation()
  const manageableUserSdwtProds = Array.isArray(affiliationData?.manageableUserSdwtProds)
    ? affiliationData.manageableUserSdwtProds
    : []
  const visibleUserSdwtProds = Array.from(
    new Set([currentUserSdwtProd, ...manageableUserSdwtProds].filter(Boolean)),
  )
  const userSdwtProd = selectedUserSdwtProd || currentUserSdwtProd

  const {
    data: membersData,
    isPending: membersPending,
    error: membersError,
    refetch: refetchMembers,
  } = useAffiliationMembers({ userSdwtProd })

  const {
    data: requestsData,
    isPending: requestsPending,
    error: requestsError,
    isFetching: requestsFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch: refetchRequests,
  } = useInfiniteAffiliationRequests({
    pageSize: REQUEST_PAGE_SIZE,
    status: "pending",
    search: "",
    userSdwtProd,
  })

  const decisionMutation = useAffiliationDecision()
  const accessMutation = useAffiliationAccessMutation()
  const {
    data: grantCandidatesData,
    isPending: grantCandidatesPending,
    error: grantCandidatesError,
  } = useAffiliationGrantCandidates({
    search: grantSearch,
    enabled: grantOpen,
  })

  const members = membersData?.members || []
  const canManage = Boolean(membersData?.canManage)
  const existingMemberUserIds = new Set(members.map((member) => member.userId))
  const grantCandidates = (grantCandidatesData?.results || []).filter(
    (candidate) =>
      candidate.recipientType === "user"
      && candidate.userId
      && !existingMemberUserIds.has(candidate.userId),
  )
  const requestPages = requestsData?.pages || []
  const requests = requestPages.flatMap((pageData) => pageData?.results || [])
  const latestRequestPage = requestPages[requestPages.length - 1]
  const requestTotal = latestRequestPage?.total || 0

  const handleDecision = async (changeId, decision, rejectionReason) => {
    try {
      await decisionMutation.mutateAsync({ changeId, decision, rejectionReason })
      toast.success(
        decision === "approve"
          ? "소속 변경 요청을 승인했습니다."
          : "소속 변경 요청을 거절했습니다.",
      )
      return true
    } catch (error) {
      toast.error(error?.message || "소속 변경 요청을 처리하지 못했습니다.")
      return false
    }
  }

  const handleRejectOpen = (row) => {
    setRejectTarget(row)
    setRejectReason("")
  }

  const handleRejectConfirm = async () => {
    if (!rejectTarget) return
    const normalizedReason = rejectReason.trim()
    const didComplete = await handleDecision(
      rejectTarget.changeId,
      "reject",
      normalizedReason ? normalizedReason : undefined,
    )
    if (didComplete) {
      setRejectTarget(null)
      setRejectReason("")
    }
  }

  const handleRoleChange = (row, role) => {
    if (!canManage || !row?.userId || role === row.memberRole) return
    setRoleChangeTarget({ row, role })
    setRoleChangeReason("")
  }

  const handleRoleChangeConfirm = async () => {
    if (!roleChangeTarget || !roleChangeReason.trim()) return
    const { row, role } = roleChangeTarget
    try {
      await accessMutation.mutateAsync({
        action: "grant",
        userId: row.userId,
        userSdwtProd,
        role,
        reason: roleChangeReason.trim(),
      })
      toast.success(`${row.name}님의 소속 역할을 변경했습니다.`)
      setRoleChangeTarget(null)
      setRoleChangeReason("")
    } catch (error) {
      toast.error(error?.message || "소속 역할을 변경하지 못했습니다.")
    }
  }

  const handleGrantConfirm = async () => {
    const userId = Number.parseInt(grantUserId, 10)
    if (!canManage || !Number.isFinite(userId) || !grantReason.trim()) return
    try {
      await accessMutation.mutateAsync({
        action: "grant",
        userId,
        userSdwtProd,
        role: grantRole,
        reason: grantReason.trim(),
      })
      toast.success("소속 접근 권한을 추가했습니다.")
      setGrantOpen(false)
      setGrantSearch("")
      setGrantUserId("")
      setGrantRole("viewer")
      setGrantReason("")
    } catch (error) {
      toast.error(error?.message || "소속 접근 권한을 추가하지 못했습니다.")
    }
  }

  const handleRevokeConfirm = async () => {
    if (!canManage || !revokeTarget?.userId || !revokeReason.trim()) return
    try {
      await accessMutation.mutateAsync({
        action: "revoke",
        userId: revokeTarget.userId,
        userSdwtProd,
        reason: revokeReason.trim(),
      })
      toast.success(`${revokeTarget.name}님의 추가 소속 접근을 회수했습니다.`)
      setRevokeTarget(null)
      setRevokeReason("")
    } catch (error) {
      toast.error(error?.message || "소속 접근 권한을 회수하지 못했습니다.")
    }
  }

  const pageTitle = user?.username ? `Members · ${user.username}` : "Members"
  const memberRows = buildMemberRows(members)
  const requestRows = buildAffiliationRequestRows(requests)
  const canApproveAny = requestRows.some(
    (row) => row.approvalRole === "manager",
  )
  const actionableRequestCount = requestRows.filter(
    (row) => row.approvalRole === "manager",
  ).length
  const showApprovalNotice = requestTotal > 0 && !canApproveAny
  const activeRows = selectVisibleMemberRows({ activeTab, memberRows, requestRows })

  const isActiveLoading =
    activeTab === "members"
      ? Boolean(userSdwtProd) && membersPending
      : activeTab === "requests"
        ? Boolean(userSdwtProd) && requestsPending
        : Boolean(userSdwtProd) && (membersPending || requestsPending)

  const activeErrors =
    activeTab === "members"
      ? [membersError].filter(Boolean)
      : activeTab === "requests"
        ? [requestsError].filter(Boolean)
        : [membersError, requestsError].filter(Boolean)

  const activeEmptyMessage =
    activeTab === "members"
      ? "현재 표시할 멤버가 없습니다."
      : activeTab === "requests"
        ? "현재 표시할 소속 변경 요청이 없습니다."
        : "현재 표시할 멤버 또는 소속 변경 요청이 없습니다."

  const activeErrorMessage = activeErrors.length > 0
    ? activeErrors
      .map((errorItem) => errorItem?.message || "사용자 목록을 불러오지 못했습니다.")
      .join(" ")
    : ""

  const handleRetry = () => {
    if (activeTab !== "requests") refetchMembers()
    if (activeTab !== "members") refetchRequests()
  }

  const handleLoadMoreRequests = () => {
    if (activeTab === "members" || !hasNextPage || isFetchingNextPage) return
    fetchNextPage()
  }

  const summaryItems = [
    {
      label: "조회 소속",
      value: userSdwtProd || "미지정",
      description: userSdwtProd === currentUserSdwtProd
        ? "현재 소속"
        : "관리 가능한 추가 소속",
      icon: ShieldCheck,
    },
    {
      label: "현재 멤버",
      value: members.length.toLocaleString("ko-KR"),
      description: "선택한 소속 기준",
      icon: Users,
    },
    {
      label: "승인 대기",
      value: requestTotal.toLocaleString("ko-KR"),
      description: `${requests.length.toLocaleString("ko-KR")}건 로드됨`,
      icon: Clock3,
    },
    {
      label: "처리 가능",
      value: actionableRequestCount.toLocaleString("ko-KR"),
      description: "내 권한으로 승인/거절 가능",
      icon: CheckCircle2,
    },
  ]

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col gap-4 overflow-hidden">
      <div className="shrink-0 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-2">
            <h2 className="text-2xl font-semibold text-foreground">{pageTitle}</h2>
            <p className="text-sm text-muted-foreground">
              {userSdwtProd
                ? `${userSdwtProd} 소속 멤버와 소속 변경 요청을 확인할 수 있습니다.`
                : "user_sdwt_prod가 설정되어 있지 않습니다."}
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            {visibleUserSdwtProds.length > 1 ? (
              <div className="grid gap-1.5">
                <Label htmlFor="membersAffiliationScope">조회 소속</Label>
                <Select
                  value={userSdwtProd}
                  onValueChange={setSelectedUserSdwtProd}
                >
                  <SelectTrigger id="membersAffiliationScope" className="w-56">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {visibleUserSdwtProds.map((value) => (
                      <SelectItem key={value} value={value}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
            {canManage ? (
              <Button
                type="button"
                onClick={() => setGrantOpen(true)}
                disabled={!userSdwtProd}
              >
                <UserPlus className="size-4" />
                접근 권한 추가
              </Button>
            ) : null}
          </div>
        </div>

        <MembersSummaryCards items={summaryItems} />
      </div>

      <div className="min-h-0 min-w-0 flex-1">
        <MembersDataTable
          rows={activeRows}
          activeTab={activeTab}
          onActiveTabChange={setActiveTab}
          memberTotal={members.length}
          requestTotal={requestTotal}
          requestLoadedCount={requests.length}
          roleFilter={roleFilter}
          onRoleFilterChange={setRoleFilter}
          searchTerm={searchTerm}
          onSearchTermChange={setSearchTerm}
          isLoading={isActiveLoading}
          isFetching={requestsFetching}
          isLoadingMore={isFetchingNextPage}
          hasMoreRequests={Boolean(hasNextPage)}
          onLoadMore={handleLoadMoreRequests}
          error={activeErrorMessage}
          emptyMessage={activeEmptyMessage}
          onRetry={handleRetry}
          isMutating={decisionMutation.isPending || accessMutation.isPending}
          canManage={canManage}
          showApprovalNotice={showApprovalNotice}
          onApprove={(row) => handleDecision(row.changeId, "approve")}
          onReject={handleRejectOpen}
          onRoleChange={handleRoleChange}
          onRevoke={(row) => {
            setRevokeTarget(row)
            setRevokeReason("")
          }}
        />
      </div>

      <MembersAccessDialogs
        rejectDialog={{
          target: rejectTarget,
          reason: rejectReason,
          isPending: decisionMutation.isPending,
          error: decisionMutation.error,
          onReasonChange: setRejectReason,
          onClose: () => {
            setRejectTarget(null)
            setRejectReason("")
          },
          onConfirm: handleRejectConfirm,
        }}
        grantDialog={{
          open: grantOpen,
          userSdwtProd,
          search: grantSearch,
          userId: grantUserId,
          role: grantRole,
          reason: grantReason,
          candidates: grantCandidates,
          isCandidatesPending: grantCandidatesPending,
          candidatesError: grantCandidatesError,
          isPending: accessMutation.isPending,
          error: accessMutation.error,
          onOpenChange: (nextOpen) => {
            setGrantOpen(nextOpen)
            if (!nextOpen) {
              setGrantSearch("")
              setGrantUserId("")
              setGrantRole("viewer")
              setGrantReason("")
            }
          },
          onSearchChange: (value) => {
            setGrantSearch(value)
            setGrantUserId("")
          },
          onUserIdChange: setGrantUserId,
          onRoleChange: setGrantRole,
          onReasonChange: setGrantReason,
          onConfirm: handleGrantConfirm,
        }}
        roleChangeDialog={{
          target: roleChangeTarget,
          reason: roleChangeReason,
          isPending: accessMutation.isPending,
          onReasonChange: setRoleChangeReason,
          onClose: () => {
            setRoleChangeTarget(null)
            setRoleChangeReason("")
          },
          onConfirm: handleRoleChangeConfirm,
        }}
        revokeDialog={{
          target: revokeTarget,
          userSdwtProd,
          reason: revokeReason,
          isPending: accessMutation.isPending,
          onReasonChange: setRevokeReason,
          onClose: () => {
            setRevokeTarget(null)
            setRevokeReason("")
          },
          onConfirm: handleRevokeConfirm,
        }}
      />
    </div>
  )
}
