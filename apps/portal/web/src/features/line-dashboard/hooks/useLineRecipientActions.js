import * as React from "react"

// 상위 controller에서 전달되는 React setter와 ref는 수명 동안 안정적이므로 기존 의존성 배열을 유지합니다.
/* eslint-disable react-hooks/exhaustive-deps */

import { fetchAccountUserPool } from "../api"
import { RECIPIENT_CHANNEL_CONFIG } from "../utils/lineSettingsConfig"
import {
  showRecipientCandidatesToast,
  showRecipientsSaveToast,
  showRequestErrorToast,
  showUpdateToast,
} from "../utils/lineSettingsToasts"
import {
  getRecipientExternalKnoxId,
  getRecipientKey,
  getRecipientPickerUsers,
  getRecipientUserId,
  mergeRecipientUsers,
} from "../utils/lineSettings"
import { parseRecipientSearchTerms } from "../utils/lineSettingsMappings"

export function useLineRecipientActions({
  accountDepartmentValues,
  canManageRecipients,
  currentRecipientDrafts,
  isCurrentRecipientContext,
  lineId,
  loadMyRecipientTargets,
  recipientPickerResults,
  recipientPickerSelectedIds,
  recipientSearches,
  recipientSourceDepartments,
  recipientSourceSdwt,
  selectedUserSdwtProd,
  setIsLoadingSourceGroups,
  setIsLoadingSourceUsers,
  setIsSavingMessengerForceNewChatroom,
  setIsSavingRecipients,
  setIsSearchingRecipients,
  setRecipientActionErrors,
  setRecipientDraftDirty,
  setRecipientDrafts,
  setRecipientDraftTargets,
  setRecipientPickerOpen,
  setRecipientPickerResults,
  setRecipientPickerSelectedIds,
  setRecipientPickerTabs,
  setRecipientSearches,
  setRecipientSourceDepartments,
  setRecipientSourceSdwt,
  setRecipientSourceSdwtOptions,
  sourceGroupRequestRef,
  sourceLoadRequestRef,
  updateMailRecipients,
  updateMessengerForceNewChatroom,
  updateMessengerRecipients,
  user,
}) {
  const clearRecipientGroupResults = React.useCallback((channel) => {
    const previousGroupIds = new Set(
      (recipientPickerResults[channel]?.group || []).map(getRecipientKey).filter(Boolean),
    )
    setRecipientPickerResults((prev) => ({
      ...prev,
      [channel]: { ...(prev[channel] || { group: [], search: [] }), group: [] },
    }))
    setRecipientPickerSelectedIds((prev) => ({
      ...prev,
      [channel]: (prev[channel] || []).filter((recipientKey) => !previousGroupIds.has(recipientKey)),
    }))
  }, [recipientPickerResults])

  const handleRecipientSourceDepartmentChange = React.useCallback(
    async (channel, value) => {
      const config = RECIPIENT_CHANNEL_CONFIG[channel]
      const sourceDepartment = String(value || "").trim()
      sourceGroupRequestRef.current[channel] += 1
      sourceLoadRequestRef.current[channel] += 1
      const requestId = sourceGroupRequestRef.current[channel]
      const requestLineId = lineId
      const requestTarget = selectedUserSdwtProd

      setRecipientSourceDepartments((prev) => ({ ...prev, [channel]: sourceDepartment }))
      setRecipientSourceSdwt((prev) => ({ ...prev, [channel]: "" }))
      setRecipientSourceSdwtOptions((prev) => ({ ...prev, [channel]: [] }))
      setIsLoadingSourceUsers((prev) => ({ ...prev, [channel]: false }))
      clearRecipientGroupResults(channel)

      if (!sourceDepartment) {
        setIsLoadingSourceGroups((prev) => ({ ...prev, [channel]: false }))
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
        return
      }
      if (!canManageRecipients) {
        setIsLoadingSourceGroups((prev) => ({ ...prev, [channel]: false }))
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
        return
      }

      setIsLoadingSourceGroups((prev) => ({ ...prev, [channel]: true }))
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
      const isCurrentLoad = () =>
        sourceGroupRequestRef.current[channel] === requestId &&
        isCurrentRecipientContext(requestLineId, requestTarget)
      try {
        const { userSdwtProds } = await fetchAccountUserPool({
          department: sourceDepartment,
          contactField: config.contactField,
          limit: 1,
          includeExternalSnapshots: true,
        })
        if (!isCurrentLoad()) return
        setRecipientSourceSdwtOptions((prev) => ({ ...prev, [channel]: userSdwtProds || [] }))
        if (!userSdwtProds?.length) {
          setRecipientActionErrors((prev) => ({ ...prev, [channel]: "Department에 소속이 없습니다." }))
        }
      } catch (requestError) {
        if (!isCurrentLoad()) return
        const message =
          requestError instanceof Error ? requestError.message : "Failed to load departments"
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: message }))
        showRequestErrorToast(message)
      } finally {
        if (isCurrentLoad()) {
          setIsLoadingSourceGroups((prev) => ({ ...prev, [channel]: false }))
        }
      }
    },
    [
      canManageRecipients,
      clearRecipientGroupResults,
      isCurrentRecipientContext,
      lineId,
      selectedUserSdwtProd,
    ],
  )

  const handleRecipientSourceSdwtChange = React.useCallback((channel, value) => {
    sourceLoadRequestRef.current[channel] += 1
    setRecipientSourceSdwt((prev) => ({ ...prev, [channel]: value }))
    setIsLoadingSourceUsers((prev) => ({ ...prev, [channel]: false }))
    clearRecipientGroupResults(channel)
  }, [clearRecipientGroupResults])

  const handleRecipientSearchChange = React.useCallback((channel, value) => {
    setRecipientSearches((prev) => ({ ...prev, [channel]: value }))
  }, [])

  const handleRecipientPickerOpenChange = React.useCallback((channel, open) => {
    setRecipientPickerOpen((prev) => ({ ...prev, [channel]: open }))
  }, [])

  const handleRecipientPickerTabChange = React.useCallback((channel, value) => {
    setRecipientPickerTabs((prev) => ({ ...prev, [channel]: value }))
  }, [])

  const resolveDefaultRecipientDepartment = React.useCallback(() => {
    const userDepartment = typeof user?.department === "string" ? user.department.trim() : ""
    if (!userDepartment) return ""
    const normalizedUserDepartment = userDepartment.toLowerCase()
    return (
      accountDepartmentValues.find((department) => (
        typeof department === "string" && department.trim().toLowerCase() === normalizedUserDepartment
      )) || userDepartment
    )
  }, [accountDepartmentValues, user?.department])

  const handleOpenRecipientPicker = React.useCallback(
    (channel) => {
      const config = RECIPIENT_CHANNEL_CONFIG[channel]
      if (!selectedUserSdwtProd) {
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: "알림 Target을 선택하세요." }))
        return
      }
      setRecipientActionErrors((prev) => ({
        ...prev,
        [channel]: canManageRecipients ? null : config.permissionErrorText,
      }))
      setRecipientPickerOpen((prev) => ({ ...prev, [channel]: true }))
      if (canManageRecipients && !recipientSourceDepartments[channel]) {
        const defaultDepartment = resolveDefaultRecipientDepartment()
        if (defaultDepartment) {
          void handleRecipientSourceDepartmentChange(channel, defaultDepartment)
        }
      }
    },
    [
      canManageRecipients,
      handleRecipientSourceDepartmentChange,
      recipientSourceDepartments,
      resolveDefaultRecipientDepartment,
      selectedUserSdwtProd,
    ],
  )

  const handleRecipientPickerUserToggle = React.useCallback((channel, recipientKey, checked) => {
    setRecipientPickerSelectedIds((prev) => {
      const current = new Set(prev[channel] || [])
      if (checked) {
        current.add(recipientKey)
      } else {
        current.delete(recipientKey)
      }
      return { ...prev, [channel]: Array.from(current) }
    })
  }, [])

  const handleRecipientPickerAllToggle = React.useCallback((channel, users, checked) => {
    setRecipientPickerSelectedIds((prev) => {
      const current = new Set(prev[channel] || [])
      for (const user of users || []) {
        const recipientKey = getRecipientKey(user)
        if (!recipientKey) continue
        if (checked) {
          current.add(recipientKey)
        } else {
          current.delete(recipientKey)
        }
      }
      return { ...prev, [channel]: Array.from(current) }
    })
  }, [])

  const handleRecipientSearch = React.useCallback(
    async (channel, event) => {
      event.preventDefault()
      const config = RECIPIENT_CHANNEL_CONFIG[channel]
      const searchTerms = parseRecipientSearchTerms(recipientSearches[channel])
      if (searchTerms.length === 0) {
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: "검색어를 입력하세요." }))
        return
      }
      if (!canManageRecipients) {
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
        return
      }

      setIsSearchingRecipients((prev) => ({ ...prev, [channel]: true }))
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
      try {
        const searchResults = await Promise.allSettled(
          searchTerms.map((search) =>
            fetchAccountUserPool({
              search,
              contactField: config.contactField,
              limit: 20,
              includeExternalSnapshots: true,
            }),
          ),
        )
        const failedSearch = searchResults.find((result) => result.status === "rejected")
        const results = searchResults.flatMap((result) => (
          result.status === "fulfilled" ? result.value?.results || [] : []
        ))
        if (results.length === 0 && failedSearch?.status === "rejected") {
          throw failedSearch.reason
        }
        setRecipientPickerResults((prev) => ({
          ...prev,
          [channel]: {
            ...(prev[channel] || { group: [], search: [] }),
            search: mergeRecipientUsers(prev[channel]?.search || [], results),
          },
        }))
        if (results.length === 0) {
          setRecipientActionErrors((prev) => ({ ...prev, [channel]: "검색 결과가 없습니다." }))
        }
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to search users"
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: message }))
        showRequestErrorToast(message)
      } finally {
        setIsSearchingRecipients((prev) => ({ ...prev, [channel]: false }))
      }
    },
    [canManageRecipients, recipientSearches],
  )

  const handleRemoveRecipientUser = React.useCallback((channel, userToRemove) => {
    const config = RECIPIENT_CHANNEL_CONFIG[channel]
    if (!canManageRecipients) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
      return
    }
    const removeKey = getRecipientKey(userToRemove)
    if (!removeKey) return
    setRecipientDrafts((prev) => ({
      ...prev,
      [channel]: prev[channel].filter((item) => getRecipientKey(item) !== removeKey),
    }))
    setRecipientDraftDirty((prev) => ({ ...prev, [channel]: true }))
  }, [canManageRecipients])

  const handleLoadSourceRecipients = React.useCallback(async (channel) => {
    const config = RECIPIENT_CHANNEL_CONFIG[channel]
    const sourceDepartment = recipientSourceDepartments[channel]
    const sourceSdwt = recipientSourceSdwt[channel]
    if (!sourceDepartment) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: "Department를 먼저 선택하세요." }))
      return
    }
    if (!sourceSdwt) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: "불러올 소속을 선택하세요." }))
      return
    }
    if (!canManageRecipients) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
      return
    }

    setIsLoadingSourceUsers((prev) => ({ ...prev, [channel]: true }))
    setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
    const requestId = sourceLoadRequestRef.current[channel] + 1
    sourceLoadRequestRef.current[channel] = requestId
    const requestLineId = lineId
    const requestTarget = selectedUserSdwtProd
    const requestSourceSdwt = sourceSdwt
    const previousGroupIds = new Set(
      (recipientPickerResults[channel]?.group || []).map(getRecipientKey).filter(Boolean),
    )
    const isCurrentLoad = () =>
      sourceLoadRequestRef.current[channel] === requestId &&
      isCurrentRecipientContext(requestLineId, requestTarget)
    try {
      const { results } = await fetchAccountUserPool({
        department: sourceDepartment,
        userSdwtProd: requestSourceSdwt,
        contactField: config.contactField,
        limit: "all",
        includeExternalSnapshots: true,
      })
      if (!isCurrentLoad()) {
        return
      }
      const loadedUsers = results || []
      setRecipientPickerResults((prev) => ({
        ...prev,
        [channel]: { ...(prev[channel] || { group: [], search: [] }), group: loadedUsers },
      }))
      setRecipientPickerSelectedIds((prev) => {
        const current = new Set(
          (prev[channel] || []).filter((recipientKey) => !previousGroupIds.has(recipientKey)),
        )
        for (const user of loadedUsers) {
          const recipientKey = getRecipientKey(user)
          if (recipientKey) current.add(recipientKey)
        }
        return { ...prev, [channel]: Array.from(current) }
      })
      if (loadedUsers.length === 0) {
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: "소속 사용자 결과가 없습니다." }))
      }
    } catch (requestError) {
      if (!isCurrentLoad()) {
        return
      }
      const message =
        requestError instanceof Error ? requestError.message : "Failed to load users"
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: message }))
      showRequestErrorToast(message)
    } finally {
      if (isCurrentLoad()) {
        setIsLoadingSourceUsers((prev) => ({ ...prev, [channel]: false }))
      }
    }
  }, [
    canManageRecipients,
    isCurrentRecipientContext,
    lineId,
    recipientPickerResults,
    recipientSourceDepartments,
    recipientSourceSdwt,
    selectedUserSdwtProd,
  ])

  const handleApplyRecipientPicker = React.useCallback((channel) => {
    const config = RECIPIENT_CHANNEL_CONFIG[channel]
    if (!canManageRecipients) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
      return
    }

    const selectedIds = new Set(recipientPickerSelectedIds[channel] || [])
    const selectedUsers = getRecipientPickerUsers(recipientPickerResults[channel]).filter((user) => {
      const recipientKey = getRecipientKey(user)
      return recipientKey && selectedIds.has(recipientKey)
    })
    if (selectedUsers.length === 0) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: "적용할 인원을 선택하세요." }))
      return
    }

    setRecipientDraftTargets((prev) => ({ ...prev, [channel]: selectedUserSdwtProd || "" }))
    setRecipientDrafts((prev) => ({
      ...prev,
      [channel]: mergeRecipientUsers(prev[channel], selectedUsers),
    }))
    setRecipientDraftDirty((prev) => ({ ...prev, [channel]: true }))
    setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
    setRecipientPickerOpen((prev) => ({ ...prev, [channel]: false }))
    showRecipientCandidatesToast(selectedUsers.length)
  }, [canManageRecipients, recipientPickerResults, recipientPickerSelectedIds, selectedUserSdwtProd])

  const handleRecipientsSave = React.useCallback(async (channel) => {
    const config = RECIPIENT_CHANNEL_CONFIG[channel]
    if (!selectedUserSdwtProd) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: "알림 Target을 선택하세요." }))
      return
    }
    if (!canManageRecipients) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
      return
    }

    setIsSavingRecipients((prev) => ({ ...prev, [channel]: true }))
    setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
    const requestLineId = lineId
    const requestTarget = selectedUserSdwtProd
    try {
      const userIds = currentRecipientDrafts[channel]
        .map(getRecipientUserId)
        .filter(Boolean)
      const externalKnoxIds = currentRecipientDrafts[channel]
        .map(getRecipientExternalKnoxId)
        .filter(Boolean)
      const updater = channel === "messenger" ? updateMessengerRecipients : updateMailRecipients
      const result = await updater({ userIds, externalKnoxIds })
      if (result?.stale) {
        return
      }
      setRecipientDrafts((prev) => ({ ...prev, [channel]: result?.recipients || [] }))
      setRecipientDraftTargets((prev) => ({ ...prev, [channel]: selectedUserSdwtProd || "" }))
      setRecipientDraftDirty((prev) => ({ ...prev, [channel]: false }))
      void loadMyRecipientTargets()
      showRecipientsSaveToast(config.saveDescription)
    } catch (requestError) {
      if (!isCurrentRecipientContext(requestLineId, requestTarget)) {
        return
      }
      const message =
        requestError instanceof Error ? requestError.message : "Failed to update recipients"
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: message }))
      showRequestErrorToast(message)
    } finally {
      if (isCurrentRecipientContext(requestLineId, requestTarget)) {
        setIsSavingRecipients((prev) => ({ ...prev, [channel]: false }))
      }
    }
  }, [
    canManageRecipients,
    currentRecipientDrafts,
    isCurrentRecipientContext,
    lineId,
    loadMyRecipientTargets,
    selectedUserSdwtProd,
    updateMailRecipients,
    updateMessengerRecipients,
  ])

  const handleMessengerForceNewChatroomChange = React.useCallback(async (checked) => {
    if (!selectedUserSdwtProd) {
      setRecipientActionErrors((prev) => ({ ...prev, messenger: "알림 Target을 선택하세요." }))
      return
    }
    if (!canManageRecipients) {
      setRecipientActionErrors((prev) => ({
        ...prev,
        messenger: RECIPIENT_CHANNEL_CONFIG.messenger.permissionErrorText,
      }))
      return
    }
    if (
      checked &&
      !window.confirm(
        "다음 메신저 발송 시 현재 저장된 메신저 수신인 기준으로 새 대화방을 생성해 전송합니다.\n동의하면 새 대화방 생성 옵션이 체크됩니다.",
      )
    ) {
      return
    }

    const requestLineId = lineId
    const requestTarget = selectedUserSdwtProd
    setIsSavingMessengerForceNewChatroom(true)
    setRecipientActionErrors((prev) => ({ ...prev, messenger: null }))
    try {
      await updateMessengerForceNewChatroom({ forceNewChatroom: checked })
      showUpdateToast()
    } catch (requestError) {
      if (!isCurrentRecipientContext(requestLineId, requestTarget)) {
        return
      }
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Failed to update messenger chatroom option"
      setRecipientActionErrors((prev) => ({ ...prev, messenger: message }))
      showRequestErrorToast(message)
    } finally {
      if (isCurrentRecipientContext(requestLineId, requestTarget)) {
        setIsSavingMessengerForceNewChatroom(false)
      }
    }
  }, [
    canManageRecipients,
    isCurrentRecipientContext,
    lineId,
    selectedUserSdwtProd,
    updateMessengerForceNewChatroom,
  ])


  return {
    handleApplyRecipientPicker,
    handleLoadSourceRecipients,
    handleMessengerForceNewChatroomChange,
    handleOpenRecipientPicker,
    handleRecipientPickerAllToggle,
    handleRecipientPickerOpenChange,
    handleRecipientPickerTabChange,
    handleRecipientPickerUserToggle,
    handleRecipientSearch,
    handleRecipientSearchChange,
    handleRecipientSourceDepartmentChange,
    handleRecipientSourceSdwtChange,
    handleRecipientsSave,
    handleRemoveRecipientUser,
  }
}
