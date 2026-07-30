import { useState } from "react"
import { toast } from "sonner"
import { CheckCircle2, Clock3, ShieldCheck, UserPlus, Users } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useAuth } from "@/lib/auth"

import { MembersDataTable } from "../components/MembersDataTable"
import {
  useAffiliationMembers,
  useAffiliationAccessMutation,
  useAffiliationDecision,
  useAffiliationGrantCandidates,
  useInfiniteAffiliationRequests,
  useAffiliation,
} from "../hooks/useAccountData"

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
  const currentUserSdwtProd = (user?.user_sdwt_prod || "").trim()
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
  const memberRows = members.map((member) => {
    const displayName =
      member?.name?.trim() || member?.username?.trim() || member?.knoxId || "알 수 없음"
    const memberAffiliation = member?.userSdwtProd || member?.user_sdwt_prod || ""
    const normalizedRole = (member?.role || "").toLowerCase()
    return {
      id: `member-${member.userId}`,
      userId: member.userId,
      type: "member",
      name: displayName,
      knoxId: member.knoxId || "-",
      email: member.email || "",
      affiliationLabel: [member.department, memberAffiliation].filter(Boolean).join(" / ") || "-",
      memberRole: ["viewer", "member", "manager"].includes(normalizedRole)
        ? normalizedRole
        : "viewer",
      isCurrentAffiliation: Boolean(member.isCurrentAffiliation),
      approvalRole: null,
      requestedAt: null,
      changeId: null,
      status: "MEMBER",
    }
  })
  const requestRows = requests.map((change) => {
    const requesterName = change?.user?.username || change?.user?.sabun || "알 수 없음"
    const requesterKnoxId = change?.user?.knoxId || "-"
    const targetParts = [
      change?.department,
      change?.line,
      change?.toUserSdwtProd || change?.to_user_sdwt_prod,
    ].filter(Boolean)
    const targetLabel =
      targetParts.length > 0 ? targetParts.join(" / ") : change?.toUserSdwtProd || "-"
    const normalizedRole = (change?.role || "").toLowerCase()
    const role = ["viewer", "member", "manager"].includes(normalizedRole)
      ? normalizedRole
      : "viewer"
    return {
      id: `request-${change.id}`,
      type: "request",
      name: requesterName,
      knoxId: requesterKnoxId,
      email: change?.user?.email || "",
      affiliationLabel: targetLabel,
      memberRole: null,
      approvalRole: role,
      requestedAt: change.requestedAt,
      changeId: change.id,
      status: change.status || "PENDING",
    }
  })
  const combinedRows = [...requestRows, ...memberRows]
  const canApproveAny = requestRows.some(
    (row) => row.approvalRole === "manager",
  )
  const actionableRequestCount = requestRows.filter(
    (row) => row.approvalRole === "manager",
  ).length
  const showApprovalNotice = requestTotal > 0 && !canApproveAny
  const activeRows =
    activeTab === "members"
      ? memberRows
      : activeTab === "requests"
        ? requestRows
        : combinedRows

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

        <div className="grid gap-3 md:grid-cols-4">
          {summaryItems.map((item) => {
            const Icon = item.icon
            return (
              <div key={item.label} className="rounded-lg border bg-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-muted-foreground">{item.label}</p>
                    <p className="mt-1 truncate text-xl font-semibold tabular-nums text-foreground">
                      {item.value}
                    </p>
                  </div>
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                    <Icon className="size-4" aria-hidden="true" />
                  </div>
                </div>
                <p className="mt-2 truncate text-xs text-muted-foreground">{item.description}</p>
              </div>
            )
          })}
        </div>
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

      <Dialog
        open={Boolean(rejectTarget)}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) {
            setRejectTarget(null)
            setRejectReason("")
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>거절 사유 입력</DialogTitle>
            <DialogDescription>
              {rejectTarget?.name
                ? `${rejectTarget.name}님의 소속 변경 요청을 거절합니다.`
                : "소속 변경 요청을 거절합니다."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="affiliationRejectReason">거절 사유 (선택)</Label>
            <textarea
              id="affiliationRejectReason"
              value={rejectReason}
              onChange={(event) => setRejectReason(event.target.value)}
              className="min-h-24 resize-y rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="사유를 입력하지 않아도 거절할 수 있습니다."
              maxLength={500}
            />
            <p className="text-xs text-muted-foreground">
              거절 사유는 신청자에게 그대로 표시됩니다.
            </p>
            {decisionMutation.error ? (
              <p className="text-xs text-destructive">
                {decisionMutation.error?.message || "거절 처리에 실패했습니다."}
              </p>
            ) : null}
          </div>
          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setRejectTarget(null)
                setRejectReason("")
              }}
              disabled={decisionMutation.isPending}
            >
              취소
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleRejectConfirm}
              disabled={decisionMutation.isPending}
            >
              거절 확정
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={grantOpen}
        onOpenChange={(nextOpen) => {
          setGrantOpen(nextOpen)
          if (!nextOpen) {
            setGrantSearch("")
            setGrantUserId("")
            setGrantRole("viewer")
            setGrantReason("")
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>소속 접근 권한 추가</DialogTitle>
            <DialogDescription>
              {userSdwtProd} 데이터를 함께 사용할 사용자와 역할을 선택합니다.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="affiliationGrantSearch">사용자 검색</Label>
              <Input
                id="affiliationGrantSearch"
                value={grantSearch}
                onChange={(event) => {
                  setGrantSearch(event.target.value)
                  setGrantUserId("")
                }}
                placeholder="이름, Knox ID, 사번 검색"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="affiliationGrantUser">대상 사용자</Label>
              <Select
                value={grantUserId}
                onValueChange={setGrantUserId}
                disabled={grantCandidatesPending || grantCandidates.length === 0}
              >
                <SelectTrigger id="affiliationGrantUser" className="w-full">
                  <SelectValue
                    placeholder={
                      grantCandidatesPending
                        ? "사용자 조회 중..."
                        : "사용자를 선택하세요"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {grantCandidates.map((candidate) => (
                    <SelectItem
                      key={candidate.userId}
                      value={String(candidate.userId)}
                    >
                      {candidate.displayName || candidate.username || candidate.knoxId || candidate.sabun}
                      {candidate.knoxId ? ` · ${candidate.knoxId}` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {!grantCandidatesPending && grantCandidates.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  추가할 수 있는 사용자가 없습니다. 검색어를 변경해 보세요.
                </p>
              ) : null}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="affiliationGrantRole">소속 역할</Label>
              <Select value={grantRole} onValueChange={setGrantRole}>
                <SelectTrigger id="affiliationGrantRole" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer">조회 권한</SelectItem>
                  <SelectItem value="member">일반 권한</SelectItem>
                  <SelectItem value="manager">운영 권한</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                조회 권한은 읽기 전용이며, 삭제와 권한 관리는 운영 권한만 가능합니다.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="affiliationGrantReason">변경 사유 (필수)</Label>
              <Textarea
                id="affiliationGrantReason"
                value={grantReason}
                onChange={(event) => setGrantReason(event.target.value)}
                placeholder="권한을 추가하는 이유를 입력하세요"
                maxLength={500}
                disabled={accessMutation.isPending}
              />
            </div>
            {grantCandidatesError || accessMutation.error ? (
              <p className="text-xs text-destructive">
                {grantCandidatesError?.message
                  || accessMutation.error?.message
                  || "사용자 또는 권한 정보를 불러오지 못했습니다."}
              </p>
            ) : null}
          </div>
          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setGrantOpen(false)}
              disabled={accessMutation.isPending}
            >
              취소
            </Button>
            <Button
              type="button"
              onClick={handleGrantConfirm}
              disabled={!grantUserId || !grantReason.trim() || accessMutation.isPending}
            >
              {accessMutation.isPending ? "추가 중..." : "권한 추가"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(roleChangeTarget)}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) {
            setRoleChangeTarget(null)
            setRoleChangeReason("")
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>소속 역할 변경</DialogTitle>
            <DialogDescription>
              {roleChangeTarget?.row?.name
                ? `${roleChangeTarget.row.name}님의 소속 역할을 변경합니다.`
                : "선택한 사용자의 소속 역할을 변경합니다."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="affiliationRoleChangeReason">변경 사유 (필수)</Label>
            <Textarea
              id="affiliationRoleChangeReason"
              value={roleChangeReason}
              onChange={(event) => setRoleChangeReason(event.target.value)}
              placeholder="역할을 변경하는 이유를 입력하세요"
              maxLength={500}
              disabled={accessMutation.isPending}
            />
          </div>
          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setRoleChangeTarget(null)
                setRoleChangeReason("")
              }}
              disabled={accessMutation.isPending}
            >
              취소
            </Button>
            <Button
              type="button"
              onClick={handleRoleChangeConfirm}
              disabled={!roleChangeReason.trim() || accessMutation.isPending}
            >
              {accessMutation.isPending ? "변경 중..." : "역할 변경"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(revokeTarget)}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) {
            setRevokeTarget(null)
            setRevokeReason("")
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>추가 소속 접근 회수</DialogTitle>
            <DialogDescription>
              {revokeTarget?.name
                ? `${revokeTarget.name}님의 ${userSdwtProd} 추가 접근 권한을 회수합니다.`
                : "선택한 사용자의 추가 소속 접근 권한을 회수합니다."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <p className="text-sm text-muted-foreground">
              현재 소속 자체는 변경되지 않으며, 마지막 운영 권한은 회수할 수 없습니다.
            </p>
            <div className="grid gap-2">
              <Label htmlFor="affiliationRevokeReason">변경 사유 (필수)</Label>
              <Textarea
                id="affiliationRevokeReason"
                value={revokeReason}
                onChange={(event) => setRevokeReason(event.target.value)}
                placeholder="권한을 회수하는 이유를 입력하세요"
                maxLength={500}
                disabled={accessMutation.isPending}
              />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setRevokeTarget(null)
                setRevokeReason("")
              }}
              disabled={accessMutation.isPending}
            >
              취소
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleRevokeConfirm}
              disabled={!revokeReason.trim() || accessMutation.isPending}
            >
              {accessMutation.isPending ? "회수 중..." : "권한 회수"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
