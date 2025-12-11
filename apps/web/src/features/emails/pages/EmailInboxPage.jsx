import { useEffect, useState } from "react"
import {
  IconChevronLeft,
  IconChevronRight,
  IconChevronsLeft,
  IconChevronsRight,
} from "@tabler/icons-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { EmailDetail } from "../components/EmailDetail"
import { EmailFilters } from "../components/EmailFilters"
import { EmailList } from "../components/EmailList"
import { useBulkDeleteEmails, useDeleteEmail } from "../hooks/useEmailActions"
import { useEmailDetail, useEmailHtml } from "../hooks/useEmailDetail"
import { useEmailList } from "../hooks/useEmailList"

const INITIAL_FILTERS = {
  page: 1,
  pageSize: 20,
  q: "",
  sender: "",
  recipient: "",
  dateFrom: "",
  dateTo: "",
}

const PAGE_SIZE_OPTIONS = [15, 20, 25, 30, 40, 50]

export function EmailInboxPage() {
  const [filters, setFilters] = useState(INITIAL_FILTERS)
  const [selectedIds, setSelectedIds] = useState([])
  const [activeEmailId, setActiveEmailId] = useState(null)

  const {
    data: listData,
    isLoading: isListLoading,
    isError: isListError,
    error: listError,
    refetch,
  } = useEmailList(filters)
  const emails = listData?.results || []

  const {
    data: detailData,
    isLoading: isDetailLoading,
  } = useEmailDetail(activeEmailId)
  const {
    data: htmlData,
    isLoading: isHtmlLoading,
  } = useEmailHtml(activeEmailId)

  const deleteMutation = useDeleteEmail()
  const bulkDeleteMutation = useBulkDeleteEmails()

  useEffect(() => {
    if (isListError && listError) {
      toast.error(listError?.message || "메일 목록을 불러오지 못했습니다.")
    }
  }, [isListError, listError])

  const handleToggleSelectAll = () => {
    if (emails.length === 0) return
    const allSelected = emails.every((item) => selectedIds.includes(item.id))
    if (allSelected) {
      setSelectedIds([])
    } else {
      setSelectedIds(emails.map((item) => item.id))
    }
  }

  const handleToggleSelect = (emailId) => {
    setSelectedIds((prev) =>
      prev.includes(emailId) ? prev.filter((id) => id !== emailId) : [...prev, emailId]
    )
  }

  const handleSelectEmail = (emailId) => {
    setActiveEmailId(emailId)
  }

  const handleDeleteEmail = async (emailId) => {
    try {
      await deleteMutation.mutateAsync(emailId)
      toast.success("메일을 삭제했습니다.")
      setSelectedIds((prev) => prev.filter((id) => id !== emailId))
      if (activeEmailId === emailId) {
        setActiveEmailId(null)
      }
      refetch()
    } catch (error) {
      toast.error(error?.message || "메일 삭제에 실패했습니다.")
    }
  }

  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return
    try {
      await bulkDeleteMutation.mutateAsync(selectedIds)
      toast.success(`${selectedIds.length}개의 메일을 삭제했습니다.`)
      setSelectedIds([])
      if (selectedIds.includes(activeEmailId)) {
        setActiveEmailId(null)
      }
      refetch()
    } catch (error) {
      toast.error(
        error?.message || "RAG 삭제 실패 등으로 메일 삭제에 실패했습니다. 다시 시도해주세요."
      )
    }
  }

  const handleResetFilters = () => {
    setFilters(INITIAL_FILTERS)
  }

  useEffect(() => {
    if (!isListLoading && emails.length > 0 && activeEmailId === null) {
      setActiveEmailId(emails[0].id)
    }
  }, [isListLoading, emails, activeEmailId])

  const pageSize = listData?.pageSize ?? filters.pageSize
  const totalCount = listData?.total ?? 0
  const currentPage = listData?.page ?? filters.page
  const effectivePageSize = Math.max(1, pageSize || 1)
  const totalPages =
    listData?.totalPages ?? Math.max(1, Math.ceil(totalCount / effectivePageSize))
  const currentPageSize = emails.length
  const startIndex = totalCount === 0 ? 0 : (currentPage - 1) * effectivePageSize + 1
  const endIndex =
    totalCount === 0 ? 0 : Math.min(totalCount, startIndex + currentPageSize - 1)

  const handleExactPageChange = (nextPage) => {
    setFilters((prev) => {
      const safePage = Math.min(Math.max(1, nextPage), totalPages)
      return { ...prev, page: safePage }
    })
  }

  const handlePageSizeChange = (value) => {
    const parsed = Number(value)
    if (Number.isNaN(parsed)) return
    setFilters((prev) => ({ ...prev, pageSize: parsed, page: 1 }))
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-hidden">
      <div className="grid flex-1 min-h-0 gap-4 md:grid-cols-2">
        <div className="grid min-h-0 grid-rows-[auto_1fr] gap-3">
          <EmailFilters filters={filters} onChange={setFilters} onReset={handleResetFilters} />
          <div className="min-h-0">
            <EmailList
              emails={emails}
              selectedIds={selectedIds}
              onToggleSelect={handleToggleSelect}
              onToggleSelectAll={handleToggleSelectAll}
              onSelectEmail={handleSelectEmail}
              onDeleteEmail={handleDeleteEmail}
              isLoading={isListLoading}
              onBulkDelete={handleBulkDelete}
              isBulkDeleting={bulkDeleteMutation.isPending}
              currentPage={currentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              pageSizeOptions={PAGE_SIZE_OPTIONS}
              onPageChange={handleExactPageChange}
              onPageSizeChange={handlePageSizeChange}
            />
          </div>
        </div>
        <div className="min-h-0 overflow-hidden">
          <EmailDetail
            email={detailData}
            html={htmlData}
            isLoading={isDetailLoading}
            isHtmlLoading={isHtmlLoading}
          />
        </div>
      </div>
    </div>
  )
}
