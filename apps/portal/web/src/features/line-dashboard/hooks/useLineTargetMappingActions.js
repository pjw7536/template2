import * as React from "react"

// 상위 controller에서 전달되는 React setter와 ref는 수명 동안 안정적이므로 기존 의존성 배열을 유지합니다.
/* eslint-disable react-hooks/exhaustive-deps */

import {
  DUPLICATE_TARGET_MAPPING_MESSAGE,
  DUPLICATE_TARGET_MESSAGE,
  MAX_TARGET_FIELD_LENGTH,
} from "../utils/lineSettingsConfig"
import {
  showDeleteToast,
  showRequestErrorToast,
  showTargetCreateToast,
  showTargetMappingCreateToast,
} from "../utils/lineSettingsToasts"
import { isDuplicateMessage, sameUserSdwtProd } from "../utils/lineSettings"
import { buildTargetMappingKey } from "../utils/lineSettingsMappings"

export function useLineTargetMappingActions({
  canCreateTarget,
  canManageMappings,
  createTarget,
  createTargetMapping,
  deleteTargetMapping,
  lineId,
  mappingDraft,
  newTargetDraft,
  notificationTargets,
  replaceTargetSearchParam,
  selectedTargetByLineRef,
  selectedUserSdwtProd,
  setDeletingMappingKey,
  setIsCreatingMapping,
  setIsCreatingTarget,
  setMappingDraft,
  setMappingFormError,
  setMappingSdwtLineId,
  setMappingUserLineId,
  setNewTargetDraft,
  setSelectedUserSdwtProd,
  setTargetFormError,
}) {
  const handleCreateTarget = React.useCallback(async () => {
    const normalized = newTargetDraft.trim()
    if (!lineId) {
      setTargetFormError("라인을 먼저 선택하세요.")
      return
    }
    if (!normalized) {
      setTargetFormError("추가할 알림 Target을 입력하세요.")
      return
    }
    if (normalized.length > MAX_TARGET_FIELD_LENGTH) {
      setTargetFormError("알림 Target은 64자 이하로 입력하세요.")
      return
    }
    if (!canCreateTarget) {
      setTargetFormError("알림 Target 추가 권한이 없습니다.")
      return
    }

    setIsCreatingTarget(true)
    setTargetFormError(null)
    try {
      const target = await createTarget({ targetUserSdwtProd: normalized })
      if (target?.targetUserSdwtProd) {
        selectedTargetByLineRef.current[lineId] = target.targetUserSdwtProd
        setSelectedUserSdwtProd(target.targetUserSdwtProd)
        replaceTargetSearchParam(target.targetUserSdwtProd)
        setNewTargetDraft("")
        showTargetCreateToast(target.targetUserSdwtProd)
      }
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to create target"
      const friendlyMessage =
        requestError?.status === 409 || isDuplicateMessage(message)
          ? DUPLICATE_TARGET_MESSAGE
          : message
      setTargetFormError(friendlyMessage)
      showRequestErrorToast(friendlyMessage)
    } finally {
      setIsCreatingTarget(false)
    }
  }, [canCreateTarget, createTarget, lineId, newTargetDraft, replaceTargetSearchParam])

  const handleMappingDraftChange = React.useCallback((key, value) => {
    setMappingDraft((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handleMappingUserLineChange = React.useCallback((value) => {
    setMappingUserLineId(value)
    setMappingFormError(null)
  }, [])

  const handleMappingSdwtLineChange = React.useCallback((value) => {
    setMappingSdwtLineId(value)
    setMappingFormError(null)
  }, [])

  const handleSelectNotificationTarget = React.useCallback((value) => {
    const normalizedValue = String(value || "").trim()
    if (lineId && normalizedValue) {
      selectedTargetByLineRef.current[lineId] = normalizedValue
    }
    setSelectedUserSdwtProd(normalizedValue)
    replaceTargetSearchParam(normalizedValue)
  }, [lineId, replaceTargetSearchParam])

  const handleCreateTargetMapping = React.useCallback(async (event) => {
    event.preventDefault()
    const normalizedUserSdwtProds = (
      Array.isArray(mappingDraft.userSdwtProds) && mappingDraft.userSdwtProds.length > 0
        ? mappingDraft.userSdwtProds
        : [mappingDraft.userSdwtProd]
    )
      .map((value) => String(value || "").trim())
      .filter(Boolean)
    const normalizedSdwtProd = mappingDraft.sdwtProd.trim()
    if (!selectedUserSdwtProd) {
      setMappingFormError("알림 Target을 먼저 선택하세요.")
      return
    }
    if (normalizedUserSdwtProds.length === 0) {
      setMappingFormError("분임조원 값을 입력하세요.")
      return
    }
    if (!normalizedSdwtProd) {
      setMappingFormError("분임조설비 값을 입력하세요.")
      return
    }
    if (
      normalizedUserSdwtProds.some((value) => value.length > MAX_TARGET_FIELD_LENGTH) ||
      normalizedSdwtProd.length > MAX_TARGET_FIELD_LENGTH
    ) {
      setMappingFormError("지정 조합 값은 64자 이하로 입력하세요.")
      return
    }
    if (!canManageMappings) {
      setMappingFormError("지정 조합 추가 권한이 없습니다.")
      return
    }
    const duplicateUserSdwtProds = normalizedUserSdwtProds.filter((userSdwtProd) =>
      notificationTargets.some(
        (target) =>
          Array.isArray(target.mappings) &&
          target.mappings.some(
            (mapping) =>
              sameUserSdwtProd(mapping.userSdwtProd, userSdwtProd) &&
              sameUserSdwtProd(mapping.sdwtProd, normalizedSdwtProd),
          ),
      ),
    )
    if (duplicateUserSdwtProds.length > 0) {
      setMappingFormError(DUPLICATE_TARGET_MAPPING_MESSAGE)
      return
    }

    setIsCreatingMapping(true)
    setMappingFormError(null)
    try {
      for (const userSdwtProd of normalizedUserSdwtProds) {
        await createTargetMapping({
          targetUserSdwtProd: selectedUserSdwtProd,
          userSdwtProd,
          sdwtProd: normalizedSdwtProd,
        })
      }
      const toastUserLabel = normalizedUserSdwtProds.length > 1
        ? `${normalizedUserSdwtProds[0]} 외 ${normalizedUserSdwtProds.length - 1}개`
        : normalizedUserSdwtProds[0]
      showTargetMappingCreateToast(toastUserLabel, normalizedSdwtProd)
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to create target mapping"
      const friendlyMessage =
        requestError?.status === 409 || isDuplicateMessage(message)
          ? DUPLICATE_TARGET_MAPPING_MESSAGE
          : message
      setMappingFormError(friendlyMessage)
      showRequestErrorToast(friendlyMessage)
    } finally {
      setIsCreatingMapping(false)
    }
  }, [
    canManageMappings,
    createTargetMapping,
    mappingDraft.sdwtProd,
    mappingDraft.userSdwtProd,
    mappingDraft.userSdwtProds,
    notificationTargets,
    selectedUserSdwtProd,
  ])

  const handleDeleteTargetMapping = React.useCallback(async (mapping) => {
    const normalizedUserSdwtProd = String(mapping?.userSdwtProd || "").trim()
    const normalizedSdwtProd = String(mapping?.sdwtProd || "").trim()
    if (!selectedUserSdwtProd) {
      setMappingFormError("알림 Target을 먼저 선택하세요.")
      return
    }
    if (!normalizedUserSdwtProd || !normalizedSdwtProd) {
      setMappingFormError("삭제할 지정 조합 값을 확인할 수 없습니다.")
      return
    }
    if (!canManageMappings) {
      setMappingFormError("지정 조합 삭제 권한이 없습니다.")
      return
    }
    const confirmed = window.confirm(
      `${normalizedUserSdwtProd} 분임조원이 ${normalizedSdwtProd} 설비로 보낸 E-SOP 지정 조합을 삭제할까요?`,
    )
    if (!confirmed) return

    const mappingKey = buildTargetMappingKey({
      userSdwtProd: normalizedUserSdwtProd,
      sdwtProd: normalizedSdwtProd,
    })
    setDeletingMappingKey(mappingKey)
    setMappingFormError(null)
    try {
      await deleteTargetMapping({
        targetUserSdwtProd: selectedUserSdwtProd,
        userSdwtProd: normalizedUserSdwtProd,
        sdwtProd: normalizedSdwtProd,
      })
      showDeleteToast()
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to delete target mapping"
      setMappingFormError(message)
      showRequestErrorToast(message)
    } finally {
      setDeletingMappingKey("")
    }
  }, [canManageMappings, deleteTargetMapping, selectedUserSdwtProd])


  return {
    handleCreateTarget,
    handleCreateTargetMapping,
    handleDeleteTargetMapping,
    handleMappingDraftChange,
    handleMappingSdwtLineChange,
    handleMappingUserLineChange,
    handleSelectNotificationTarget,
  }
}
