import { useState } from "react"
import {
  ChevronLeft,
  ChevronRight,
  FilePenLine,
  HelpCircle,
  Inbox,
  MoreVertical,
  Paperclip,
  RefreshCcw,
  Search,
  Send,
  Settings,
  Star,
  Tag,
  Trash2,
} from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { SelectionCheckbox } from "../components/SelectionCheckbox"

const MOCK_THREADS = [
  {
    id: "1",
    from: "네이버페이",
    fromInitial: "N",
    subject: "[네이버페이] 구매하신 제품의 자동구매확정 안내입니다.",
    snippet: "N Pay 구매하신 상품의 자동구매확정 안내입니다...",
    labels: ["구매"],
    date: "12월 3일",
    unread: true,
    starred: false,
    hasAttachment: false,
  },
  {
    id: "2",
    from: "Notion Team",
    fromInitial: "N",
    subject: "새 기기 로그인 알림",
    snippet: "계정에 새로운 기기에서 로그인했습니다...",
    labels: ["업데이트"],
    date: "10월 8일",
    unread: false,
    starred: true,
    hasAttachment: false,
  },
  {
    id: "3",
    from: "auth",
    fromInitial: "A",
    subject: "[Shokz] Your App Verification Code",
    snippet: "Here is your verification code...",
    labels: ["중요"],
    date: "10월 6일",
    unread: true,
    starred: false,
    hasAttachment: false,
  },
  {
    id: "4",
    from: "Academy PI",
    fromInitial: "P",
    subject: "[PI 교육] Week 2-6차수_Day 4_Weekly 강의 피드백 09/25",
    snippet: "안녕하세요, 한주동안 집중하여 교육에 참여해 주셔서 감사합니다...",
    labels: ["포럼"],
    date: "9월 25일",
    unread: false,
    starred: false,
    hasAttachment: true,
  },
]

const SIDEBAR_ITEMS = [
  { key: "inbox", label: "받은편지함", icon: Inbox, count: 230, active: true },
  { key: "starred", label: "별표편지함", icon: Star },
  { key: "snoozed", label: "다시 알릴 항목", icon: Tag },
  { key: "important", label: "중요편지함", icon: Star },
  { key: "sent", label: "보낸편지함", icon: Send },
  { key: "drafts", label: "임시보관함", icon: FilePenLine, count: 2 },
  { key: "trash", label: "휴지통", icon: Trash2 },
]

const CATEGORY_TABS = [
  { key: "primary", label: "기본", icon: Inbox },
  { key: "social", label: "소셜", icon: Tag },
  { key: "promotions", label: "프로모션", icon: Tag },
]

const ACTIVE_CATEGORY_KEY = "primary"

const IconCircleButton = ({ children, className, ...props }) => (
  <button
    type="button"
    className={cn(
      "inline-flex h-7 w-7 items-center justify-center rounded-full hover:bg-muted",
      className,
    )}
    {...props}
  >
    {children}
  </button>
)

const MailboxPage = () => {
  const [threads, setThreads] = useState(MOCK_THREADS)
  const [selectedThreadId, setSelectedThreadId] = useState(MOCK_THREADS[0]?.id || null)
  const [selectedIds, setSelectedIds] = useState([])
  const [query, setQuery] = useState("")

  const normalizedQuery = query.trim().toLowerCase()
  const filteredThreads = normalizedQuery
    ? threads.filter((thread) => {
        const searchable = `${thread.subject} ${thread.from} ${thread.snippet}`.toLowerCase()
        return searchable.includes(normalizedQuery)
      })
    : threads

  const isAllSelected =
    filteredThreads.length > 0 &&
    filteredThreads.every((thread) => selectedIds.includes(thread.id))

  const toggleSelectAll = () => {
    setSelectedIds((prev) => {
      if (filteredThreads.length === 0) return prev
      const filteredIds = filteredThreads.map((thread) => thread.id)
      const allSelected = filteredIds.every((id) => prev.includes(id))

      if (allSelected) {
        return prev.filter((id) => !filteredIds.includes(id))
      }

      return Array.from(new Set([...prev, ...filteredIds]))
    })
  }

  const toggleSelectOne = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((value) => value !== id) : [...prev, id],
    )
  }

  const toggleStar = (id) => {
    setThreads((prev) =>
      prev.map((thread) =>
        thread.id === id ? { ...thread, starred: !thread.starred } : thread,
      ),
    )
  }

  const handleStarClick = (event, id) => {
    event.stopPropagation()
    toggleStar(id)
  }

  const selectThread = (id) => {
    setSelectedThreadId(id)
    setThreads((prev) =>
      prev.map((thread) =>
        thread.id === id ? { ...thread, unread: false } : thread,
      ),
    )
  }

  const paginationLabel = filteredThreads.length ? `1–${filteredThreads.length}` : "0"
  const selectedThread = threads.find((thread) => thread.id === selectedThreadId)

  return (
    <div className="grid h-full min-h-0 grid-cols-1 gap-4 overflow-hidden text-foreground lg:grid-cols-[260px_1fr]">
      <aside className="grid min-h-0 grid-rows-[auto_1fr] rounded-xl border bg-muted/20">
        <div className="px-4 pt-4 pb-2">
          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-full bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary-foreground/10">
              <FilePenLine className="h-4 w-4" />
            </span>
            <span>메일 작성</span>
          </button>
        </div>
        <div className="grid min-h-0 grid-rows-[1fr_auto] divide-y">
          <nav className="space-y-1 overflow-y-auto px-2 pb-4 pt-1">
            {SIDEBAR_ITEMS.map((item) => {
              const Icon = item.icon
              const isActive = item.active
              return (
                <button
                  key={item.key}
                  type="button"
                  className={cn(
                    "flex w-full items-center justify-between rounded-r-full px-3 py-2 text-sm transition",
                    isActive
                      ? "bg-primary/10 font-semibold text-primary"
                      : "text-muted-foreground hover:bg-muted/70",
                  )}
                >
                  <span className="flex items-center gap-3">
                    <Icon className="h-4 w-4" />
                    <span>{item.label}</span>
                  </span>
                  {item.count != null ? (
                    <span className="text-xs font-medium text-muted-foreground">
                      {item.count}
                    </span>
                  ) : null}
                </button>
              )
            })}
          </nav>
          <div className="bg-muted/30 px-4 py-3 text-xs text-muted-foreground">
            라벨
          </div>
        </div>
      </aside>

      <section className="grid min-h-0 grid-rows-[auto_auto_auto_1fr] rounded-xl border bg-card shadow-sm">
        <header className="flex items-center gap-4 border-b px-6 py-3">
          <div className="flex flex-1 items-center rounded-full bg-muted/60 px-4 py-2 text-sm">
            <Search className="mr-2 h-4 w-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="h-7 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
              placeholder="메일 검색"
            />
          </div>

          <div className="flex items-center gap-2 text-muted-foreground">
            <IconCircleButton className="h-8 w-8">
              <Settings className="h-4 w-4" />
            </IconCircleButton>
            <IconCircleButton className="h-8 w-8">
              <HelpCircle className="h-4 w-4" />
            </IconCircleButton>
            <Avatar className="h-8 w-8">
              <AvatarFallback>JW</AvatarFallback>
            </Avatar>
          </div>
        </header>

        <div className="flex items-center gap-3 border-b bg-muted/40 px-6 py-2 text-xs">
          <div className="flex items-center gap-1">
            <SelectionCheckbox
              checked={isAllSelected}
              onCheckedChange={toggleSelectAll}
              aria-label="전체 선택"
            />
            <span className="text-muted-foreground">전체 선택</span>
          </div>
          <IconCircleButton>
            <RefreshCcw className="h-3.5 w-3.5" />
          </IconCircleButton>
          <IconCircleButton>
            <MoreVertical className="h-3.5 w-3.5" />
          </IconCircleButton>
        </div>

        <div className="flex items-center gap-1 border-b bg-background px-6 pt-1 pb-0">
          {CATEGORY_TABS.map((tab) => {
            const TabIcon = tab.icon
            const isActiveCategory = tab.key === ACTIVE_CATEGORY_KEY
            return (
              <button
                key={tab.key}
                type="button"
                className={cn(
                  "flex flex-1 items-center gap-2 border-b-2 px-3 pb-2 pt-2 text-xs",
                  isActiveCategory
                    ? "border-primary font-semibold text-primary"
                    : "border-transparent text-muted-foreground hover:bg-muted/40",
                )}
              >
                <TabIcon className="h-3.5 w-3.5" />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </div>

        <div className="grid min-h-0 grid-cols-1 overflow-hidden lg:grid-cols-[480px_1fr]">
          <div className="grid min-h-0 grid-rows-[1fr_auto] border-b lg:border-b-0 lg:border-r">
            <div className="min-h-0 overflow-y-auto">
              {filteredThreads.length > 0 ? (
                <div className="divide-y">
                  {filteredThreads.map((thread) => {
                    const isSelected = selectedIds.includes(thread.id)
                    const isActive = selectedThreadId === thread.id

                    return (
                      <button
                        key={thread.id}
                        type="button"
                        onClick={() => selectThread(thread.id)}
                        className={cn(
                          "flex w-full items-center gap-3 px-6 py-2 text-left text-sm transition hover:bg-muted/70",
                          thread.unread ? "bg-muted/40 font-semibold" : "bg-background",
                          isActive && "ring-1 ring-primary/40",
                        )}
                      >
                        <div className="flex w-20 items-center gap-2">
                          <SelectionCheckbox
                            checked={isSelected}
                            onCheckedChange={() => toggleSelectOne(thread.id)}
                            onClick={(event) => event.stopPropagation()}
                            aria-label="메일 선택"
                          />
                          <IconCircleButton
                            className="h-5 w-5"
                            onClick={(event) => handleStarClick(event, thread.id)}
                          >
                            <Star
                              className={cn(
                                "h-3.5 w-3.5",
                                thread.starred
                                  ? "fill-yellow-400 text-yellow-400"
                                  : "text-muted-foreground",
                              )}
                            />
                          </IconCircleButton>
                        </div>

                        <div className="flex w-52 items-center gap-2">
                          <Avatar className="h-7 w-7">
                            <AvatarFallback className="text-xs font-semibold">
                              {thread.fromInitial}
                            </AvatarFallback>
                          </Avatar>
                          <span
                            className={cn(
                              "truncate",
                              thread.unread ? "font-semibold" : "text-muted-foreground",
                            )}
                          >
                            {thread.from}
                          </span>
                        </div>

                        <div className="flex flex-1 items-center gap-2">
                          <span
                            className={cn(
                              "max-w-[420px] truncate",
                              thread.unread && "font-semibold",
                            )}
                          >
                            {thread.subject}
                          </span>
                          <span className="hidden flex-1 truncate text-xs text-muted-foreground lg:inline">
                            — {thread.snippet}
                          </span>
                        </div>

                        <div className="flex w-56 items-center justify-end gap-2">
                          <div className="hidden items-center gap-1 md:flex">
                            {thread.labels?.slice(0, 2).map((label) => (
                              <Badge
                                key={label}
                                variant="outline"
                                className="rounded-full border-muted-foreground/30 px-2 py-0 text-[10px] text-muted-foreground"
                              >
                                {label}
                              </Badge>
                            ))}
                          </div>
                          {thread.hasAttachment ? (
                            <Paperclip className="h-3.5 w-3.5 text-muted-foreground" />
                          ) : null}
                          <span className="w-20 text-right text-xs text-muted-foreground">
                            {thread.date}
                          </span>
                        </div>
                      </button>
                    )
                  })}
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
                  <p className="text-sm font-semibold">메일이 없습니다</p>
                  <p className="text-xs text-muted-foreground">
                    검색어를 조정하거나 새로고침해 보세요.
                  </p>
                </div>
              )}
            </div>
            <div className="flex items-center justify-end border-t bg-muted/40 px-6 py-2 text-xs text-muted-foreground">
              <span>{paginationLabel} / {threads.length}</span>
              <div className="ml-3 flex items-center gap-1">
                <IconCircleButton>
                  <ChevronLeft className="h-3.5 w-3.5" />
                </IconCircleButton>
                <IconCircleButton>
                  <ChevronRight className="h-3.5 w-3.5" />
                </IconCircleButton>
              </div>
            </div>
          </div>

          <div className="flex min-h-0 flex-col bg-background">
            {selectedThread ? (
              <>
                <div className="flex items-start justify-between border-b px-6 py-4">
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <Avatar className="h-10 w-10">
                        <AvatarFallback className="text-sm font-semibold">
                          {selectedThread.fromInitial}
                        </AvatarFallback>
                      </Avatar>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold">{selectedThread.from}</span>
                          {selectedThread.labels?.map((label) => (
                            <Badge
                              key={label}
                              variant="outline"
                              className="rounded-full border-muted-foreground/30 px-2 py-0 text-[11px] text-muted-foreground"
                            >
                              {label}
                            </Badge>
                          ))}
                        </div>
                        <p className="text-xs text-muted-foreground">{selectedThread.date}</p>
                      </div>
                    </div>
                    <h2 className="text-lg font-semibold leading-tight">{selectedThread.subject}</h2>
                  </div>
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <IconCircleButton
                      className="h-8 w-8"
                      onClick={() => toggleStar(selectedThread.id)}
                    >
                      <Star
                        className={cn(
                          "h-4 w-4",
                          selectedThread.starred
                            ? "fill-yellow-400 text-yellow-400"
                            : "text-muted-foreground",
                        )}
                      />
                    </IconCircleButton>
                    <IconCircleButton className="h-8 w-8">
                      <MoreVertical className="h-4 w-4" />
                    </IconCircleButton>
                  </div>
                </div>

                <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                  <div className="space-y-4 text-sm leading-relaxed text-muted-foreground">
                    <p>{selectedThread.snippet}</p>
                    <p>
                      실제 메일 본문이 위치할 자리입니다. 샘플 데이터로 구성된 화면이므로
                      내용을 길게 표시해 스크롤을 확인할 수 있도록 했습니다.
                    </p>
                    {selectedThread.hasAttachment ? (
                      <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-xs">
                        <Paperclip className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="text-muted-foreground">첨부 파일이 있습니다.</span>
                      </div>
                    ) : null}
                    <p>
                      메일 리스트에서 항목을 선택하면 이 영역에서 상세 내용을 계속 확인할 수
                      있습니다.
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted-foreground">
                메일을 선택해 상세 내용을 확인하세요.
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}

export { MailboxPage }
