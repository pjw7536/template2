import { useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { toast } from "sonner"

import { useBulkDeleteEmails, useDeleteEmail } from "./useEmailActions"
import { useEmailDetail, useEmailHtml } from "./useEmailDetail"
import { useEmailList } from "./useEmailList"
import { getMailboxFromSearchParams } from "../utils/mailbox"

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
const MIN_LIST_WIDTH = 385
const MIN_DETAIL_WIDTH = 420
const DEFAULT_LIST_RATIO = 0.45
const GRID_GAP_PX = 16
const EMPTY_EMAILS = []

function clampListWidth(nextWidth, container) {
  if (!container) return nextWidth
  const { width } = container.getBoundingClientRect()
  if (!width) return nextWidth

  const maxWidth = Math.max(MIN_LIST_WIDTH, width - GRID_GAP_PX - MIN_DETAIL_WIDTH)
  return Math.min(Math.max(nextWidth, MIN_LIST_WIDTH), maxWidth)
}

export function useEmailInboxController() {
  const [filters, setFilters] = useState(INITIAL_FILTERS)
  const [selectedIds, setSelectedIds] = useState([])
  const [activeEmailId, setActiveEmailId] = useState(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const [listWidth, setListWidth] = useState(420)
  const [isDragging, setIsDragging] = useState(false)
  const splitPaneRef = useRef(null)
  const dragCleanupRef = useRef(null)
  const mailboxChangeRef = useRef("")
  const mailboxInitializedRef = useRef(false)

  const mailboxParam = getMailboxFromSearchParams(searchParams)
  const listEnabled = Boolean(mailboxParam)
  const listFilters = { ...filters, userSdwtProd: mailboxParam }

  const {
    data: listData,
    isLoading: isListLoading,
    isFetching: isListFetching,
    isError: isListError,
    error: listError,
    refetch,
  } = useEmailList(listFilters, { enabled: listEnabled })
  const emails = Array.isArray(listData?.results) ? listData.results : EMPTY_EMAILS

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

  useEffect(() => {
    if (mailboxChangeRef.current === mailboxParam) return
    mailboxChangeRef.current = mailboxParam

    if (!mailboxParam) return
    setFilters((prev) => ({ ...prev, page: 1 }))
    setSelectedIds([])
    setActiveEmailId(null)

    if (!mailboxInitializedRef.current) {
      mailboxInitializedRef.current = true
      return
    }

    if (searchParams.has("emailId")) {
      const nextParams = new URLSearchParams(searchParams)
      nextParams.delete("emailId")
      setSearchParams(nextParams, { replace: true })
    }
  }, [mailboxParam, searchParams, setSearchParams])

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
      prev.includes(emailId) ? prev.filter((id) => id !== emailId) : [...prev, emailId],
    )
  }

  const handleSelectEmail = (emailId) => {
    setActiveEmailId(emailId)
    const next = new URLSearchParams(searchParams)
    next.set("emailId", String(emailId))
    setSearchParams(next)
  }

  const handleDeleteEmail = async (emailId) => {
    try {
      await deleteMutation.mutateAsync(emailId)
      toast.success("메일을 삭제했습니다.")
      setSelectedIds((prev) => prev.filter((id) => id !== emailId))
      if (activeEmailId === emailId) {
        setActiveEmailId(null)
        const next = new URLSearchParams(searchParams)
        next.delete("emailId")
        setSearchParams(next)
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
        const next = new URLSearchParams(searchParams)
        next.delete("emailId")
        setSearchParams(next)
      }
      refetch()
    } catch (error) {
      toast.error(
        error?.message || "RAG 삭제 실패 등으로 메일 삭제에 실패했습니다. 다시 시도해주세요.",
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

  useEffect(() => {
    const emailIdParam = (searchParams.get("emailId") || "").trim()
    if (!emailIdParam || emails.length === 0) return

    const targetEmail = emails.find(
      (email) =>
        String(email.id) === emailIdParam ||
        (typeof email.ragDocId === "string" && email.ragDocId.trim() === emailIdParam),
    )
    if (targetEmail) {
      setActiveEmailId(targetEmail.id)
    }
  }, [searchParams, emails])

  const pageSize = listData?.pageSize ?? filters.pageSize
  const totalCount = listData?.total ?? 0
  const currentPage = listData?.page ?? filters.page
  const effectivePageSize = Math.max(1, pageSize || 1)
  const totalPages = listData?.totalPages ?? Math.max(1, Math.ceil(totalCount / effectivePageSize))

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

  const handleReload = () => {
    if (!mailboxParam) return
    refetch()
  }

  const isReloading = isListFetching
  const stopDragging = () => {
    if (dragCleanupRef.current) {
      dragCleanupRef.current()
      dragCleanupRef.current = null
    }
  }

  const handleResizeStart = (event) => {
    if (!splitPaneRef.current) return
    event.preventDefault()
    stopDragging()
    setIsDragging(true)

    const handlePointerMove = (moveEvent) => {
      const container = splitPaneRef.current
      if (!container) return
      const { left } = container.getBoundingClientRect()
      const proposedWidth = moveEvent.clientX - left
      setListWidth(clampListWidth(proposedWidth, container))
    }

    const handlePointerEnd = () => {
      setIsDragging(false)
      stopDragging()
    }

    dragCleanupRef.current = () => {
      window.removeEventListener("pointermove", handlePointerMove)
      window.removeEventListener("pointerup", handlePointerEnd)
      window.removeEventListener("pointercancel", handlePointerEnd)
    }

    window.addEventListener("pointermove", handlePointerMove)
    window.addEventListener("pointerup", handlePointerEnd)
    window.addEventListener("pointercancel", handlePointerEnd)
  }

  useEffect(() => {
    const container = splitPaneRef.current
    if (!container) return
    const { width } = container.getBoundingClientRect()
    if (!width) return

    const proposedWidth = width * DEFAULT_LIST_RATIO
    setListWidth(clampListWidth(proposedWidth, container))
  }, [])

  useEffect(() => {
    const handleResize = () => {
      const container = splitPaneRef.current
      if (!container) return
      setListWidth((current) => clampListWidth(current, container))
    }
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  useEffect(
    () => () => {
      if (dragCleanupRef.current) {
        dragCleanupRef.current()
        dragCleanupRef.current = null
      }
    },
    [],
  )

  const splitPaneStyles = {
    "--email-list-width": `${listWidth}px`,
    "--email-handle-offset": `${listWidth + GRID_GAP_PX / 2}px`,
  }

  return {
    filters,
    setFilters,
    handleResetFilters,
    mailboxParam,
    emails,
    selectedIds,
    activeEmailId,
    isListLoading,
    detailData,
    htmlData,
    isDetailLoading,
    isHtmlLoading,
    handleToggleSelectAll,
    handleToggleSelect,
    handleSelectEmail,
    handleDeleteEmail,
    handleBulkDelete,
    isBulkDeleting: bulkDeleteMutation.isPending,
    currentPage,
    totalPages,
    pageSize,
    pageSizeOptions: PAGE_SIZE_OPTIONS,
    handleExactPageChange,
    handlePageSizeChange,
    handleReload,
    isReloading,
    splitPaneRef,
    splitPaneStyles,
    isDragging,
    handleResizeStart,
  }
}
