import { EmailDetail } from "./EmailDetail"
import { EmailFilters } from "./EmailFilters"
import { EmailList } from "./EmailList"

export function EmailInboxView({
  filters,
  setFilters,
  handleResetFilters,
  emails,
  selectedIds,
  activeEmailId,
  handleToggleSelect,
  handleToggleSelectAll,
  handleSelectEmail,
  handleDeleteEmail,
  isListLoading,
  handleBulkDelete,
  isBulkDeleting,
  currentPage,
  totalPages,
  pageSize,
  pageSizeOptions,
  handleExactPageChange,
  handlePageSizeChange,
  handleReload,
  isReloading,
  detailData,
  htmlData,
  isDetailLoading,
  isHtmlLoading,
  splitPaneRef,
  splitPaneStyles,
  isDragging,
  handleResizeStart,
}) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-hidden">
      <div
        ref={splitPaneRef}
        style={splitPaneStyles}
        className="relative grid flex-1 min-h-0 min-w-0 grid-cols-1 gap-4 md:[grid-template-columns:minmax(0,var(--email-list-width))_minmax(0,1fr)]"
      >
        <div className="grid min-h-0 min-w-0 grid-rows-[auto_1fr] gap-3 overflow-hidden">
          <EmailFilters filters={filters} onChange={setFilters} onReset={handleResetFilters} />
          <div className="min-h-0 min-w-0 overflow-hidden">
            <EmailList
              emails={emails}
              selectedIds={selectedIds}
              activeEmailId={activeEmailId}
              onToggleSelect={handleToggleSelect}
              onToggleSelectAll={handleToggleSelectAll}
              onSelectEmail={handleSelectEmail}
              onDeleteEmail={handleDeleteEmail}
              isLoading={isListLoading}
              onBulkDelete={handleBulkDelete}
              isBulkDeleting={isBulkDeleting}
              currentPage={currentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              pageSizeOptions={pageSizeOptions}
              onPageChange={handleExactPageChange}
              onPageSizeChange={handlePageSizeChange}
              onReload={handleReload}
              isReloading={isReloading}
            />
          </div>
        </div>
        <div className="min-h-0 min-w-0 overflow-hidden">
          <EmailDetail
            email={detailData}
            html={htmlData}
            isLoading={isDetailLoading}
            isHtmlLoading={isHtmlLoading}
          />
        </div>
        <button
          type="button"
          className={`absolute top-0 z-10 hidden h-full w-3 -translate-x-1/2 cursor-col-resize select-none rounded-sm border border-transparent bg-transparent transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:block ${isDragging ? "bg-primary/10" : "hover:bg-primary/5"}`}
          style={{ left: "var(--email-handle-offset)" }}
          onPointerDown={handleResizeStart}
          aria-label="메일 목록과 상세 너비 조절"
        >
          <span
            className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border"
            aria-hidden
          />
        </button>
      </div>
    </div>
  )
}

