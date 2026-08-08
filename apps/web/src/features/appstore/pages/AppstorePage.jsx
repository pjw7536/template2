// 앱스토어 메인 페이지
import { useEffect, useMemo, useState } from "react"
import { GripVertical, LoaderCircle } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { useAuth } from "@/lib/auth"
import { useAppstorePageActions } from "../hooks/useAppstorePageActions"
import { useAppstoreMutations } from "../hooks/useAppstoreMutations"
import { useAppDetailQuery, useAppsQuery } from "../hooks/useAppstoreQueries"
import { AppDetail } from "../components/AppDetail"
import { AppFilters } from "../components/AppFilters"
import { AppFormDialog } from "../components/AppFormDialog"
import { AppList } from "../components/AppList"
import {
  buildAppCategories,
  buildCategoryCounts,
  buildFormCategoryOptions,
  filterApps,
} from "../utils/appFilters"
import { hasAppOrderChanged, moveAppWithinCategory } from "../utils/appOrder"

const EMPTY_APPS = []

export function AppstorePage() {
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")
  const [selectedAppId, setSelectedAppId] = useState(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [isDetailOpen, setIsDetailOpen] = useState(false)
  const [isOrderEditing, setIsOrderEditing] = useState(false)
  const [draftApps, setDraftApps] = useState([])
  const [draftOrderVersion, setDraftOrderVersion] = useState("")
  const [orderError, setOrderError] = useState("")
  const [editingApp, setEditingApp] = useState(null)
  const [updatingCommentId, setUpdatingCommentId] = useState(null)
  const [deletingCommentId, setDeletingCommentId] = useState(null)
  const [togglingCommentLikeId, setTogglingCommentLikeId] = useState(null)

  const appsQuery = useAppsQuery()
  const apps = appsQuery.data?.apps ?? EMPTY_APPS
  const canReorderApps = Boolean(appsQuery.data?.permissions?.canReorder)
  const { user } = useAuth()

  const mutations = useAppstoreMutations()
  const {
    createAppMutation,
    updateAppMutation,
    toggleLikeMutation,
    toggleCommentLikeMutation,
    createCommentMutation,
    reorderAppsMutation,
  } = mutations

  useEffect(() => {
    if (selectedAppId && !apps.some((app) => app.id === selectedAppId)) {
      setSelectedAppId(null)
      setIsDetailOpen(false)
    }
  }, [apps, selectedAppId])

  const appDetailQuery = useAppDetailQuery(selectedAppId, {
    staleTime: 30_000,
  })

  const defaultContactName = useMemo(() => {
    return user?.username || user?.knox_id || ""
  }, [user])

  const defaultContactKnoxid = useMemo(() => {
    return user?.usr_id || ""
  }, [user])

  const categories = useMemo(() => {
    return buildAppCategories(apps)
  }, [apps])

  const formCategoryOptions = useMemo(() => {
    return buildFormCategoryOptions(apps)
  }, [apps])

  const categoryCounts = useMemo(() => {
    return buildCategoryCounts(apps)
  }, [apps])

  const displayedApps = useMemo(() => {
    const sourceApps = isOrderEditing ? draftApps : apps
    return filterApps(sourceApps, { category, query })
  }, [apps, category, draftApps, isOrderEditing, query])
  const isOrderDirty = hasAppOrderChanged(apps, draftApps)
  const orderScopeLabel = category === "all" ? "전체 앱" : category

  const detailApp = appDetailQuery.data?.app ?? null
  const isDetailLoading =
    Boolean(selectedAppId) &&
    !detailApp &&
    !appDetailQuery.isError

  const handleSelect = (appId) => {
    setSelectedAppId(appId)
    setIsDetailOpen(true)
  }

  const {
    handleAddComment,
    handleDeleteApp,
    handleDeleteComment,
    handleEditApp,
    handleOpenLink,
    handleOpenManual,
    handleSubmitApp,
    handleToggleCommentLike,
    handleToggleLike,
    handleUpdateComment,
  } = useAppstorePageActions({
    apps,
    editingApp,
    mutations,
    setDeletingCommentId,
    setEditingApp,
    setIsDetailOpen,
    setIsFormOpen,
    setSelectedAppId,
    setTogglingCommentLikeId,
    setUpdatingCommentId,
  })

  const resetFilters = () => {
    setQuery("")
    setCategory("all")
  }

  const handleStartOrderEdit = () => {
    setQuery("")
    setDraftApps(apps)
    setDraftOrderVersion(appsQuery.data?.orderVersion ?? "")
    setOrderError("")
    setIsOrderEditing(true)
  }

  const handleCancelOrderEdit = () => {
    if (reorderAppsMutation.isPending) return
    setIsOrderEditing(false)
    setDraftApps([])
    setDraftOrderVersion("")
    setOrderError("")
  }

  const handleMoveApp = (sourceAppId, targetAppId) => {
    setDraftApps((current) =>
      moveAppWithinCategory(current, sourceAppId, targetAppId, category),
    )
    setOrderError("")
  }

  const handleSaveOrder = async () => {
    setOrderError("")
    try {
      await reorderAppsMutation.mutateAsync({
        appIds: draftApps.map((app) => app.id),
        orderVersion: draftOrderVersion,
      })
      setIsOrderEditing(false)
      setDraftApps([])
      setDraftOrderVersion("")
      toast.success("앱 노출 순서를 저장했어요.")
    } catch (error) {
      if (error?.status === 409) {
        const result = await appsQuery.refetch()
        if (result.error) {
          setOrderError(result.error.message || "최신 앱 순서를 불러오지 못했습니다.")
          return
        }
        setDraftApps(result.data.apps)
        setDraftOrderVersion(result.data.orderVersion)
        setOrderError(
          "앱 목록 또는 순서가 변경되어 최신 목록을 불러왔습니다. 다시 정렬해 주세요.",
        )
        return
      }
      setOrderError(error?.message || "앱 순서를 저장하지 못했습니다.")
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="grid flex-1 min-h-0 gap-4 lg:grid-cols-[280px_1fr]">
        <div className="h-full min-h-0">
          <AppFilters
            totalApps={apps.length}
            query={query}
            onQueryChange={setQuery}
            category={category}
            categories={categories}
            categoryCounts={categoryCounts}
            onCategoryChange={setCategory}
            onReset={resetFilters}
            onCreate={() => {
              setEditingApp(null)
              setIsFormOpen(true)
            }}
            isCreating={createAppMutation.isPending}
            canReorder={canReorderApps}
            onReorder={handleStartOrderEdit}
            isOrderEditing={isOrderEditing}
          />
        </div>

        <div className="flex min-h-0 min-w-0 flex-col gap-3 overflow-hidden">
          {isOrderEditing ? (
            <div className="flex shrink-0 items-start justify-between gap-4 rounded-xl border bg-card px-4 py-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <GripVertical className="size-4 text-primary" aria-hidden="true" />
                  {orderScopeLabel} 순서 편집
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {category === "all"
                    ? "카드를 원하는 위치로 끌어 놓으세요."
                    : "다른 카테고리 앱은 그대로 두고 이 카테고리 앱끼리 순서를 바꿉니다."}
                  {" "}화살표 키로도 한 칸씩 이동할 수 있습니다.
                </p>
                {orderError ? (
                  <p className="mt-2 text-sm text-destructive" role="alert">
                    {orderError}
                  </p>
                ) : null}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCancelOrderEdit}
                  disabled={reorderAppsMutation.isPending}
                >
                  취소
                </Button>
                <Button
                  type="button"
                  onClick={handleSaveOrder}
                  disabled={
                    reorderAppsMutation.isPending || !isOrderDirty || !draftApps.length
                  }
                >
                  {reorderAppsMutation.isPending ? (
                    <>
                      <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
                      저장 중
                    </>
                  ) : (
                    "순서 저장"
                  )}
                </Button>
              </div>
            </div>
          ) : null}

          <div className="min-h-0 flex-1 overflow-y-auto pt-0.5">
            <AppList
              apps={displayedApps}
              selectedAppId={selectedAppId}
              onSelect={handleSelect}
              onOpenLink={handleOpenLink}
              onToggleLike={handleToggleLike}
              onEdit={handleEditApp}
              onDelete={handleDeleteApp}
              isLoading={!isOrderEditing && (appsQuery.isLoading || appsQuery.isFetching)}
              isOrderEditing={isOrderEditing}
              isOrderSaving={reorderAppsMutation.isPending}
              onMoveApp={handleMoveApp}
            />
          </div>
        </div>
      </div>

      <Dialog
        open={isDetailOpen}
        onOpenChange={(open) => {
          setIsDetailOpen(open)
          if (!open) {
            setSelectedAppId(null)
          }
        }}
      >
        <DialogContent className="sm:max-w-4xl overflow-hidden p-0">
          <DialogTitle className="sr-only">앱 상세</DialogTitle>
          <DialogDescription className="sr-only">선택한 앱의 상세 정보와 댓글을 확인합니다.</DialogDescription>
          <div className="grid max-h-[80vh] min-h-[60vh] grid-rows-[auto,1fr]">
            <div className="border-b px-6 py-4">
              <div className="text-sm font-semibold">앱 상세</div>
              <p className="text-xs text-muted-foreground">
                카드 선택 시 상세 정보와 댓글을 모달에서 확인할 수 있습니다.
              </p>
            </div>
            <div className="min-h-0 overflow-y-auto px-1 py-4">
              <div className="px-4">
                <AppDetail
                  app={detailApp}
                  isLoading={isDetailLoading}
                  error={appDetailQuery.isError ? appDetailQuery.error : null}
                  onOpenLink={handleOpenLink}
                  onOpenManual={handleOpenManual}
                  onToggleLike={handleToggleLike}
                  onEdit={handleEditApp}
                  onDelete={handleDeleteApp}
                  onAddComment={handleAddComment}
                  onUpdateComment={handleUpdateComment}
                  onDeleteComment={handleDeleteComment}
                  onToggleCommentLike={handleToggleCommentLike}
                  isLiking={toggleLikeMutation.isPending}
                  isAddingComment={createCommentMutation.isPending}
                  updatingCommentId={updatingCommentId}
                  deletingCommentId={deletingCommentId}
                  togglingCommentLikeId={togglingCommentLikeId}
                  isTogglingCommentLike={toggleCommentLikeMutation.isPending}
                />
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <AppFormDialog
        open={isFormOpen}
        onOpenChange={(open) => {
          setIsFormOpen(open)
          if (!open) {
            setEditingApp(null)
          }
        }}
        onSubmit={handleSubmitApp}
        initialData={editingApp}
        categoryOptions={formCategoryOptions}
        defaultContactName={defaultContactName}
        defaultContactKnoxid={defaultContactKnoxid}
        isSubmitting={createAppMutation.isPending || updateAppMutation.isPending}
      />
    </div>
  )
}
