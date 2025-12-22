import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuth } from "@/lib/auth"

import { useAffiliationDecision, useAffiliationRequests, useMailboxMembers } from "../hooks/useAccountData"

const PAGE_SIZE_OPTIONS = [10, 20, 50]

function formatDate(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "-"
  return date.toLocaleString("ko-KR")
}

export default function MembersPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState("all")
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const userSdwtProd = (user?.user_sdwt_prod || "").trim()

  const {
    data: membersData,
    isPending: membersPending,
    error: membersError,
  } = useMailboxMembers({ userSdwtProd })

  const {
    data: requestsData,
    isPending: requestsPending,
    error: requestsError,
    isFetching: requestsFetching,
  } = useAffiliationRequests({
    page,
    pageSize,
    status: "pending",
    search: "",
    userSdwtProd,
  })

  const decisionMutation = useAffiliationDecision()

  useEffect(() => {
    setPage(1)
  }, [pageSize, userSdwtProd])

  useEffect(() => {
    if (requestsData?.page && requestsData.page !== page) {
      setPage(requestsData.page)
    }
  }, [requestsData?.page, page])

  const members = membersData?.members || []
  const requests = requestsData?.results || []
  const requestTotal = requestsData?.total || 0
  const totalPages = requestsData?.totalPages || 1
  const canPrevious = page > 1
  const canNext = page < totalPages
  const canManage = Boolean(requestsData?.canManage)
  const showPagination = activeTab !== "members"

  const handleDecision = async (changeId, decision) => {
    try {
      await decisionMutation.mutateAsync({ changeId, decision })
    } catch {
      // Errors are surfaced through React Query state.
    }
  }

  const pageTitle = user?.username ? `SDWT 멤버 · ${user.username}` : "SDWT 멤버"
  const memberRows = members.map((member) => {
    const displayName =
      member?.name?.trim() || member?.username?.trim() || member?.knoxId || "알 수 없음"
    return {
      id: `member-${member.userId}`,
      type: "member",
      name: displayName,
      knoxId: member.knoxId || "-",
      requestedAt: null,
      changeId: null,
      status: "MEMBER",
    }
  })
  const requestRows = requests.map((change) => {
    const requesterName = change?.user?.username || change?.user?.sabun || "알 수 없음"
    const requesterKnoxId = change?.user?.knoxId || "-"
    return {
      id: `request-${change.id}`,
      type: "request",
      name: requesterName,
      knoxId: requesterKnoxId,
      requestedAt: change.requestedAt,
      changeId: change.id,
      status: change.status || "PENDING",
    }
  })
  const combinedRows = [...requestRows, ...memberRows]

  const renderRows = (rows) => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>이름</TableHead>
          <TableHead>Knox ID</TableHead>
          <TableHead>상태</TableHead>
          <TableHead>요청 시각</TableHead>
          <TableHead className="text-right">작업</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => {
          const isRequest = row.type === "request"
          const isPendingStatus = isRequest && row.status === "PENDING"
          return (
            <TableRow key={row.id}>
              <TableCell className="text-sm font-medium text-foreground">{row.name}</TableCell>
              <TableCell className="text-sm text-muted-foreground">{row.knoxId}</TableCell>
              <TableCell>
                <Badge variant={isRequest ? "destructive" : "secondary"}>
                  {isRequest ? "권한요청중" : "멤버"}
                </Badge>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {isRequest ? formatDate(row.requestedAt) : "-"}
              </TableCell>
              <TableCell className="text-right">
                {isRequest ? (
                  <div className="flex justify-end gap-2">
                    <Button
                      size="sm"
                      onClick={() => handleDecision(row.changeId, "approve")}
                      disabled={!isPendingStatus || !canManage || decisionMutation.isPending}
                    >
                      승인
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDecision(row.changeId, "reject")}
                      disabled={!isPendingStatus || !canManage || decisionMutation.isPending}
                    >
                      거절
                    </Button>
                  </div>
                ) : (
                  <span className="text-sm text-muted-foreground">-</span>
                )}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="grid h-full min-h-0 grid-rows-[70px_1fr] gap-4">
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-3">
            <h1 className="text-2xl font-semibold text-foreground">{pageTitle}</h1>
            {requestsFetching && !requestsPending ? (
              <span className="text-xs text-muted-foreground">새로고침 중...</span>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground">
            {userSdwtProd
              ? `${userSdwtProd} 그룹 멤버 목록과 권한 요청을 확인할 수 있습니다.`
              : "user_sdwt_prod가 설정되어 있지 않습니다."}
          </p>
        </div>

        <section className="flex flex-1 min-h-0 flex-col">
          <div className="flex h-full min-h-0 flex-col rounded-lg border bg-card">
            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="flex h-full min-h-0 flex-col"
            >
              <div className="flex flex-col gap-3 border-b p-4 md:flex-row md:items-center md:justify-between">
                <TabsList className="h-9">
                  <TabsTrigger value="all">전체</TabsTrigger>
                  <TabsTrigger value="members">
                    멤버
                    <Badge variant="secondary" className="ml-2">
                      {members.length}
                    </Badge>
                  </TabsTrigger>
                  <TabsTrigger value="requests">
                    권한 요청
                    {requestTotal > 0 ? (
                      <Badge variant="destructive" className="ml-2">
                        {requestTotal}
                      </Badge>
                    ) : null}
                  </TabsTrigger>
                </TabsList>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">페이지 크기</span>
                  <Select
                    value={String(pageSize)}
                    onValueChange={(value) => setPageSize(Number(value))}
                    disabled={activeTab === "members"}
                  >
                    <SelectTrigger className="h-8 w-[90px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PAGE_SIZE_OPTIONS.map((value) => (
                        <SelectItem key={value} value={String(value)}>
                          {value}개
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              {!canManage ? (
                <div className="px-4 pt-3">
                  <p className="text-xs text-muted-foreground">승인/거절은 관리자만 가능합니다.</p>
                </div>
              ) : null}

              <div className="flex-1 min-h-0 overflow-y-auto border-t bg-background">
                <TabsContent value="all" className="m-0 h-full min-h-0">
                  {membersError || requestsError ? (
                    <div className="p-6">
                      {membersError ? (
                        <p className="text-sm text-destructive">
                          멤버 목록을 불러오지 못했습니다.
                        </p>
                      ) : null}
                      {requestsError ? (
                        <p className="text-sm text-destructive">
                          권한 요청을 불러오지 못했습니다.
                        </p>
                      ) : null}
                    </div>
                  ) : membersPending || requestsPending ? (
                    <div className="grid gap-3 p-4">
                      {Array.from({ length: 6 }).map((_, index) => (
                        <Skeleton key={`all-skeleton-${index}`} className="h-10 w-full" />
                      ))}
                    </div>
                  ) : combinedRows.length === 0 ? (
                    <div className="p-8 text-center text-sm text-muted-foreground">
                      현재 표시할 멤버 또는 권한 요청이 없습니다.
                    </div>
                  ) : (
                    renderRows(combinedRows)
                  )}
                </TabsContent>

                <TabsContent value="members" className="m-0 h-full min-h-0">
                  {membersError ? (
                    <div className="p-6">
                      <p className="text-sm text-destructive">
                        {membersError?.message || "멤버 목록을 불러오지 못했습니다."}
                      </p>
                    </div>
                  ) : membersPending ? (
                    <div className="grid gap-3 p-4">
                      {Array.from({ length: 6 }).map((_, index) => (
                        <Skeleton key={`member-skeleton-${index}`} className="h-10 w-full" />
                      ))}
                    </div>
                  ) : memberRows.length === 0 ? (
                    <div className="p-8 text-center text-sm text-muted-foreground">
                      현재 표시할 멤버가 없습니다.
                    </div>
                  ) : (
                    renderRows(memberRows)
                  )}
                </TabsContent>

                <TabsContent value="requests" className="m-0 h-full min-h-0">
                  {requestsError ? (
                    <div className="p-6">
                      <p className="text-sm text-destructive">
                        {requestsError?.message || "권한 요청을 불러오지 못했습니다."}
                      </p>
                    </div>
                  ) : requestsPending ? (
                    <div className="grid gap-3 p-4">
                      {Array.from({ length: 6 }).map((_, index) => (
                        <Skeleton key={`request-skeleton-${index}`} className="h-10 w-full" />
                      ))}
                    </div>
                  ) : requestRows.length === 0 ? (
                    <div className="p-8 text-center text-sm text-muted-foreground">
                      현재 표시할 권한 요청이 없습니다.
                    </div>
                  ) : (
                    renderRows(requestRows)
                  )}
                </TabsContent>
              </div>

              {showPagination ? (
                <div className="flex flex-col gap-2 border-t p-4 md:flex-row md:items-center md:justify-between">
                  <p className="text-xs text-muted-foreground">
                    페이지 {page.toLocaleString("ko-KR")} / {totalPages.toLocaleString("ko-KR")}
                  </p>
                  <Pagination className="justify-end">
                    <PaginationContent>
                      <PaginationItem>
                        <PaginationPrevious
                          href="#"
                          onClick={(event) => {
                            event.preventDefault()
                            if (canPrevious) setPage((prev) => prev - 1)
                          }}
                          className={!canPrevious ? "pointer-events-none opacity-50" : ""}
                        />
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationNext
                          href="#"
                          onClick={(event) => {
                            event.preventDefault()
                            if (canNext) setPage((prev) => prev + 1)
                          }}
                          className={!canNext ? "pointer-events-none opacity-50" : ""}
                        />
                      </PaginationItem>
                    </PaginationContent>
                  </Pagination>
                </div>
              ) : null}
            </Tabs>
          </div>
        </section>
      </div>
    </div>
  )
}
