import { useMemo, useState } from "react"

import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/lib/auth"

import { AccessListCard } from "../components/AccessListCard"
import { AffiliationCard } from "../components/AffiliationCard"
import { ManageGrantsCard } from "../components/ManageGrantsCard"
import {
  useAffiliation,
  useManageableGroups,
  useUpdateAffiliation,
  useUpdateGrant,
} from "../hooks/useAccountData"

export default function AccountPage() {
  const { user } = useAuth()
  const {
    data: affiliation,
    isLoading: isLoadingAffiliation,
    error: affiliationLoadError,
  } = useAffiliation()
  const {
    data: manageableGroups,
    isLoading: isLoadingManageable,
    error: manageableLoadError,
  } = useManageableGroups()
  const updateAffiliation = useUpdateAffiliation()
  const updateGrant = useUpdateGrant()

  const [affiliationError, setAffiliationError] = useState("")
  const [grantError, setGrantError] = useState("")

  const pageTitle = useMemo(() => {
    const base = "My account"
    if (user?.name) return `${base} · ${user.name}`
    if (user?.username) return `${base} · ${user.username}`
    return base
  }, [user?.name, user?.username])

  const handleAffiliationSubmit = async (payload, onSuccess) => {
    setAffiliationError("")
    try {
      await updateAffiliation.mutateAsync(payload)
      onSuccess?.()
    } catch (err) {
      setAffiliationError(err?.message || "소속 변경에 실패했습니다.")
    }
  }

  const handleGrant = async (payload, onSuccess) => {
    setGrantError("")
    try {
      await updateGrant.mutateAsync({ ...payload, action: "grant" })
      onSuccess?.()
    } catch (err) {
      setGrantError(err?.message || "권한 부여에 실패했습니다.")
    }
  }

  const handleRevoke = async (userSdwtProd, userId) => {
    setGrantError("")
    try {
      await updateGrant.mutateAsync({
        userSdwtProd,
        userId,
        action: "revoke",
      })
    } catch (err) {
      setGrantError(err?.message || "권한 회수에 실패했습니다.")
    }
  }

  const isLoadingPage = isLoadingAffiliation || isLoadingManageable
  const initialLoadError = affiliationLoadError || manageableLoadError

  return (
    <div className="h-full min-h-0">
      <div className="grid h-full min-h-0 grid-rows-[auto,1fr] gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold text-foreground">{pageTitle}</h1>
          <p className="text-muted-foreground text-sm">
            소속(user_sdwt_prod) 변경을 신청하고 접근 권한을 관리합니다. 소속 변경은 해당 소속 관리자 또는 슈퍼유저 승인 시점으로 적용됩니다.
          </p>
        </div>

        {initialLoadError ? (
          <div className="rounded-lg border bg-card p-6">
            <p className="text-destructive text-sm">
              {initialLoadError?.message || "계정 정보를 불러오지 못했습니다."}
            </p>
          </div>
        ) : isLoadingPage ? (
          <div className="grid h-full min-h-0 grid-cols-1 gap-4 md:grid-cols-2">
            <Skeleton className="h-96 w-full" />
            <Skeleton className="h-96 w-full" />
            <Skeleton className="h-72 w-full md:col-span-2" />
          </div>
        ) : (
          <div className="grid h-full min-h-0 grid-cols-1 gap-4 md:grid-cols-2">
            <AffiliationCard
              data={affiliation}
              onSubmit={handleAffiliationSubmit}
              isSubmitting={updateAffiliation.isPending}
              error={affiliationError}
            />
            <ManageGrantsCard
              manageableGroups={manageableGroups}
              onGrant={handleGrant}
              onRevoke={handleRevoke}
              isSubmitting={updateGrant.isPending}
              error={grantError}
            />
            <div className="md:col-span-2">
              <AccessListCard data={affiliation} />
            </div>
          </div>
        )}
      </div>
      <Separator className="sr-only" />
    </div>
  )
}
