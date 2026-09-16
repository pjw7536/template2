// 파일 경로: src/features/line-dashboard/components/LineSettingsPage.jsx
import * as React from "react"
import { useSearchParams } from "react-router-dom"

import { useAuth } from "@/lib/auth"
import { LineSettingsHeader } from "./LineSettingsHeader"
import { AlarmChannelSettingsCard } from "./cards/AlarmChannelSettingsCard"
import { EarlyInformSettingsCard } from "./cards/EarlyInformSettingsCard"
import { NeedToSendCommentRuleCard } from "./cards/NeedToSendCommentRuleCard"
import { MyRecipientTargetsCard } from "./cards/MyRecipientTargetsCard"
import { NotificationTargetCard } from "./cards/NotificationTargetCard"
import { RecipientSettingsCards } from "./sections/RecipientSettingsCards"
import {
  fetchAccountUserPool,
  fetchMyNotificationRecipientTargets,
  fetchNotificationRecipientPermissions,
} from "../api"
import { useEarlyInformSettingsController } from "../hooks/useEarlyInformSettingsController"
import { useLineRecipientActions } from "../hooks/useLineRecipientActions"
import { useLineNotificationActions } from "../hooks/useLineNotificationActions"
import { useLineTargetMappingActions } from "../hooks/useLineTargetMappingActions"
import { useLineSettings } from "../hooks/useLineSettings"
import {
  DEFAULT_CHANNEL_ENABLED,
  DEFAULT_NEED_TO_SEND_RULE,
  DEFAULT_TEMPLATE_KEYS,
  MAX_FIELD_LENGTH,
  MAX_JIRA_KEY_LENGTH,
  MAX_NEED_TO_SEND_KEYWORD_LENGTH,
  MAX_TARGET_FIELD_LENGTH,
  RECIPIENT_CHANNELS,
} from "../utils/lineSettingsConfig"
import {
  sameUserSdwtProd,
} from "../utils/lineSettings"
import {
  buildMappingLineOptions,
  buildMappingValueLineLabels,
  findMappingDefaultOption,
  findMatchingUserSdwtValue,
  getMappingLineOptionValues,
} from "../utils/lineSettingsMappings"

export function LineSettingsPage({ lineId = "", mode = "notification" }) {
  const isRecipientSettings = mode === "recipients"
  const isNotificationSettings = !isRecipientSettings
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const targetSearchValue = isRecipientSettings
    ? String(searchParams.get("target") || "").trim()
    : ""
  const [selectedUserSdwtProd, setSelectedUserSdwtProd] = React.useState("")
  const [canManageNotificationSettings, setCanManageNotificationSettings] = React.useState(false)
  const [hasLoadedPermissionContext, setHasLoadedPermissionContext] = React.useState(false)
  const {
    entries,
    notificationTargets,
    userSdwtValues,
    mappingOptions,
    mappingOptionLines,
    jiraKey,
    channelEnabled,
    needToSendRule,
    templateKeys,
    templateOptions,
    messengerForceNewChatroom,
    mailRecipients,
    mailRecipientsTargetUserSdwtProd,
    messengerRecipients,
    messengerRecipientsTargetUserSdwtProd,
    jiraKeyError,
    mailRecipientsError,
    messengerRecipientsError,
    error,
    isLoading,
    isJiraKeyLoading,
    isMailRecipientsLoading,
    isMessengerRecipientsLoading,
    hasLoadedOnce,
    lastUpdatedLabel,
    refresh,
    createEntry,
    updateEntry,
    deleteEntry,
    updateJiraKey,
    updateNeedToSendRule,
    updateMessengerForceNewChatroom,
    createTarget,
    createTargetMapping,
    deleteTargetMapping,
    updateTargetMappingPolicy,
    updateMailRecipients,
    updateMessengerRecipients,
  } = useLineSettings({
    lineId,
    userSdwtProd: selectedUserSdwtProd,
    loadRecipients: isRecipientSettings,
  })

  const {
    formValues,
    formError,
    isCreating,
    editingId,
    editDraft,
    rowErrors,
    savingMap,
    handleFormChange,
    handleCreate,
    startEditing,
    cancelEditing,
    handleEditChange,
    handleSave,
    handleDelete,
  } = useEarlyInformSettingsController({
    lineId,
    entries,
    createEntry,
    updateEntry,
    deleteEntry,
  })
  const [newTargetDraft, setNewTargetDraft] = React.useState("")
  const [targetFormError, setTargetFormError] = React.useState(null)
  const [isCreatingTarget, setIsCreatingTarget] = React.useState(false)
  const [mappingDraft, setMappingDraft] = React.useState({
    userSdwtProd: "",
    userSdwtProds: [],
    sdwtProd: "",
  })
  const [mappingFormError, setMappingFormError] = React.useState(null)
  const [mappingUserLineId, setMappingUserLineId] = React.useState("")
  const [mappingSdwtLineId, setMappingSdwtLineId] = React.useState("")
  const [isCreatingMapping, setIsCreatingMapping] = React.useState(false)
  const [deletingMappingKey, setDeletingMappingKey] = React.useState("")
  const [jiraKeyDraft, setJiraKeyDraft] = React.useState("")
  const [channelEnabledDraft, setChannelEnabledDraft] = React.useState(DEFAULT_CHANNEL_ENABLED)
  const [templateKeyDraft, setTemplateKeyDraft] = React.useState(DEFAULT_TEMPLATE_KEYS)
  const [needToSendRuleDraft, setNeedToSendRuleDraft] = React.useState(DEFAULT_NEED_TO_SEND_RULE)
  const [jiraKeyFormError, setJiraKeyFormError] = React.useState(null)
  const [isSavingJiraKey, setIsSavingJiraKey] = React.useState(false)
  const [needToSendRuleFormError, setNeedToSendRuleFormError] = React.useState(null)
  const [isSavingNeedToSendRule, setIsSavingNeedToSendRule] = React.useState(false)
  const [savingNeedToSendMappingKey, setSavingNeedToSendMappingKey] = React.useState("")
  const [isSavingMessengerForceNewChatroom, setIsSavingMessengerForceNewChatroom] = React.useState(false)
  const [recipientDrafts, setRecipientDrafts] = React.useState({ mail: [], messenger: [] })
  const [recipientDraftTargets, setRecipientDraftTargets] = React.useState({ mail: "", messenger: "" })
  const [recipientDraftDirty, setRecipientDraftDirty] = React.useState({ mail: false, messenger: false })
  const [recipientSearches, setRecipientSearches] = React.useState({ mail: "", messenger: "" })
  const [recipientPickerOpen, setRecipientPickerOpen] = React.useState({ mail: false, messenger: false })
  const [recipientPickerTabs, setRecipientPickerTabs] = React.useState({ mail: "group", messenger: "group" })
  const [recipientPickerResults, setRecipientPickerResults] = React.useState({
    mail: { group: [], search: [] },
    messenger: { group: [], search: [] },
  })
  const [recipientPickerSelectedIds, setRecipientPickerSelectedIds] = React.useState({ mail: [], messenger: [] })
  const [recipientSourceDepartments, setRecipientSourceDepartments] = React.useState({ mail: "", messenger: "" })
  const [recipientSourceSdwt, setRecipientSourceSdwt] = React.useState({ mail: "", messenger: "" })
  const [recipientSourceSdwtOptions, setRecipientSourceSdwtOptions] = React.useState({ mail: [], messenger: [] })
  const [accountDepartmentValues, setAccountDepartmentValues] = React.useState([])
  const [accountUserSdwtValues, setAccountUserSdwtValues] = React.useState([])
  const [myRecipientTargets, setMyRecipientTargets] = React.useState([])
  const [myRecipientTargetsError, setMyRecipientTargetsError] = React.useState(null)
  const [recipientActionErrors, setRecipientActionErrors] = React.useState({ mail: null, messenger: null })
  const [isMyRecipientTargetsLoading, setIsMyRecipientTargetsLoading] = React.useState(false)
  const [isSearchingRecipients, setIsSearchingRecipients] = React.useState({ mail: false, messenger: false })
  const [isLoadingSourceGroups, setIsLoadingSourceGroups] = React.useState({ mail: false, messenger: false })
  const [isLoadingSourceUsers, setIsLoadingSourceUsers] = React.useState({ mail: false, messenger: false })
  const [isSavingRecipients, setIsSavingRecipients] = React.useState({ mail: false, messenger: false })
  const recipientContextRef = React.useRef({ lineId, selectedUserSdwtProd })
  const sourceGroupRequestRef = React.useRef({ mail: 0, messenger: 0 })
  const sourceLoadRequestRef = React.useRef({ mail: 0, messenger: 0 })
  const didResetMappingDraftRef = React.useRef(false)
  const didSyncLineChangeRef = React.useRef(false)
  const selectedTargetByLineRef = React.useRef({})
  const selectedLineIdRef = React.useRef(lineId)
  recipientContextRef.current = { lineId, selectedUserSdwtProd }

  const isRefreshing = isLoading && hasLoadedOnce
  const title = isRecipientSettings ? "E-SOP 수신인 설정" : "E-SOP 알림 설정"
  const settingsGridClassName = isRecipientSettings
    ? "grid h-full min-h-0 min-w-0 grid-cols-1 grid-rows-3 gap-3 xl:grid-cols-3 xl:grid-rows-1"
    : "grid h-full min-h-0 min-w-0 grid-cols-1 gap-3"
  const settingsBodyClassName = isRecipientSettings
    ? "flex min-h-0 flex-1 overflow-hidden pr-1"
    : "flex flex-1 min-h-0 min-w-0 flex-col"
  const selectedNotificationTarget = notificationTargets.find(
    (target) => target.targetUserSdwtProd === selectedUserSdwtProd,
  )
  const canManageRecipients = Boolean(selectedUserSdwtProd && canManageNotificationSettings)
  const canManageChannelSettings = Boolean(lineId && selectedUserSdwtProd && canManageNotificationSettings)
  const canCreateTarget = Boolean(lineId && canManageNotificationSettings)
  const canManageMappings = Boolean(selectedNotificationTarget && canManageNotificationSettings)
  const mappingUserLineOptions = React.useMemo(
    () => buildMappingLineOptions({
      lineRows: mappingOptionLines,
      currentLineId: lineId,
      currentValues: mappingOptions?.userSdwtProds,
    }),
    [lineId, mappingOptionLines, mappingOptions?.userSdwtProds],
  )
  const mappingSdwtLineOptions = React.useMemo(
    () => buildMappingLineOptions({
      lineRows: mappingOptionLines,
      currentLineId: lineId,
      currentValues: mappingOptions?.sdwtProds,
    }),
    [lineId, mappingOptionLines, mappingOptions?.sdwtProds],
  )
  const effectiveMappingOptions = React.useMemo(
    () => ({
      userSdwtProds: getMappingLineOptionValues(mappingUserLineOptions, mappingUserLineId),
      sdwtProds: getMappingLineOptionValues(mappingSdwtLineOptions, mappingSdwtLineId),
    }),
    [mappingSdwtLineId, mappingSdwtLineOptions, mappingUserLineId, mappingUserLineOptions],
  )
  const mappingValueLineLabels = React.useMemo(
    () => buildMappingValueLineLabels(mappingOptionLines, lineId),
    [lineId, mappingOptionLines],
  )
  const isRecipientDraftCurrent = React.useMemo(
    () => ({
      mail: sameUserSdwtProd(recipientDraftTargets.mail, selectedUserSdwtProd),
      messenger: sameUserSdwtProd(recipientDraftTargets.messenger, selectedUserSdwtProd),
    }),
    [recipientDraftTargets.mail, recipientDraftTargets.messenger, selectedUserSdwtProd],
  )
  const currentRecipientDrafts = React.useMemo(
    () => ({
      mail: isRecipientDraftCurrent.mail ? recipientDrafts.mail : [],
      messenger: isRecipientDraftCurrent.messenger ? recipientDrafts.messenger : [],
    }),
    [isRecipientDraftCurrent.mail, isRecipientDraftCurrent.messenger, recipientDrafts.mail, recipientDrafts.messenger],
  )

  const isCurrentRecipientContext = React.useCallback((requestLineId, requestUserSdwtProd) => {
    const context = recipientContextRef.current
    return (
      context.lineId === requestLineId &&
      sameUserSdwtProd(context.selectedUserSdwtProd, requestUserSdwtProd)
    )
  }, [])

  const replaceTargetSearchParam = React.useCallback(
    (nextTarget) => {
      if (!isRecipientSettings) return
      setSearchParams((prev) => {
        const nextParams = new URLSearchParams(prev)
        const normalizedTarget = String(nextTarget || "").trim()
        if (normalizedTarget) {
          nextParams.set("target", normalizedTarget)
        } else {
          nextParams.delete("target")
        }
        return nextParams
      }, { replace: true })
    },
    [isRecipientSettings, setSearchParams],
  )

  const loadMyRecipientTargets = React.useCallback(async () => {
    const requestLineId = lineId
    const requestUserId = user?.id
    if (!isRecipientSettings || !requestLineId || !requestUserId) {
      setMyRecipientTargets([])
      setMyRecipientTargetsError(null)
      setIsMyRecipientTargetsLoading(false)
      return { ok: true }
    }

    setIsMyRecipientTargetsLoading(true)
    setMyRecipientTargetsError(null)
    try {
      const { targets } = await fetchMyNotificationRecipientTargets({ lineId: requestLineId })
      if (recipientContextRef.current.lineId !== requestLineId) {
        return { ok: false, stale: true }
      }
      setMyRecipientTargets(targets || [])
      return { ok: true }
    } catch (requestError) {
      if (recipientContextRef.current.lineId !== requestLineId) {
        return { ok: false, stale: true }
      }
      const message =
        requestError instanceof Error ? requestError.message : "Failed to load my recipient targets"
      setMyRecipientTargets([])
      setMyRecipientTargetsError(message)
      return { ok: false }
    } finally {
      if (recipientContextRef.current.lineId === requestLineId) {
        setIsMyRecipientTargetsLoading(false)
      }
    }
  }, [isRecipientSettings, lineId, user?.id])

  const handleRefresh = React.useCallback(() => {
    if (!lineId) return
    refresh()
    void loadMyRecipientTargets()
  }, [lineId, loadMyRecipientTargets, refresh])

  const {
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
  } = useLineRecipientActions({
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
  })

  React.useEffect(() => {
    if (selectedLineIdRef.current === lineId) return
    selectedLineIdRef.current = lineId
    didSyncLineChangeRef.current = true
    if (!lineId) {
      setSelectedUserSdwtProd("")
      replaceTargetSearchParam("")
      return
    }

    const rememberedTarget = selectedTargetByLineRef.current[lineId] || ""
    setSelectedUserSdwtProd(targetSearchValue || rememberedTarget || "")
  }, [lineId, replaceTargetSearchParam, targetSearchValue])

  React.useEffect(() => {
    if (!lineId) {
      if (selectedUserSdwtProd) setSelectedUserSdwtProd("")
      replaceTargetSearchParam("")
      return
    }
    if (didSyncLineChangeRef.current) {
      didSyncLineChangeRef.current = false
      return
    }

    if (userSdwtValues.length === 0) {
      if (targetSearchValue && !sameUserSdwtProd(selectedUserSdwtProd, targetSearchValue)) {
        setSelectedUserSdwtProd(targetSearchValue)
      }
      return
    }

    const urlTarget = findMatchingUserSdwtValue(userSdwtValues, targetSearchValue)
    const currentTarget = findMatchingUserSdwtValue(userSdwtValues, selectedUserSdwtProd)
    const rememberedTarget = findMatchingUserSdwtValue(
      userSdwtValues,
      selectedTargetByLineRef.current[lineId],
    )
    const nextTarget = urlTarget || currentTarget || rememberedTarget || userSdwtValues[0] || ""

    if (!nextTarget) return

    selectedTargetByLineRef.current[lineId] = nextTarget
    if (!sameUserSdwtProd(selectedUserSdwtProd, nextTarget)) {
      setSelectedUserSdwtProd(nextTarget)
      return
    }
    if (!sameUserSdwtProd(targetSearchValue, nextTarget)) {
      replaceTargetSearchParam(nextTarget)
    }
  }, [
    lineId,
    replaceTargetSearchParam,
    selectedUserSdwtProd,
    targetSearchValue,
    userSdwtValues,
  ])

  React.useEffect(() => {
    setNewTargetDraft("")
    setTargetFormError(null)
  }, [lineId])

  React.useLayoutEffect(() => {
    if (!lineId || !selectedUserSdwtProd) {
      setMappingUserLineId("")
      setMappingSdwtLineId("")
      setMappingDraft({ userSdwtProd: "", userSdwtProds: [], sdwtProd: "" })
      return
    }

    const defaultUserOption = mappingUserLineOptions.find((option) => option.lineId === lineId) || mappingUserLineOptions[0]
    const defaultSdwtOption = mappingSdwtLineOptions.find((option) => option.lineId === lineId) || mappingSdwtLineOptions[0]
    const defaultUserValue = defaultUserOption?.values?.[0] || ""
    const defaultSdwtValue = defaultSdwtOption?.values?.[0] || ""

    setMappingUserLineId(defaultUserOption?.lineId || lineId || "")
    setMappingSdwtLineId(defaultSdwtOption?.lineId || lineId || "")
    setMappingDraft({
      userSdwtProd: defaultUserValue,
      userSdwtProds: defaultUserValue ? [defaultUserValue] : [],
      sdwtProd: defaultSdwtValue,
    })
    didResetMappingDraftRef.current = true
    setMappingFormError(null)
  }, [lineId, mappingSdwtLineOptions, mappingUserLineOptions, selectedUserSdwtProd])

  React.useEffect(() => {
    if (!lineId) {
      if (mappingUserLineId) setMappingUserLineId("")
      if (mappingSdwtLineId) setMappingSdwtLineId("")
      return
    }

    if (mappingUserLineOptions.length > 0 && !mappingUserLineOptions.some((option) => option.lineId === mappingUserLineId)) {
      const defaultUserOption = mappingUserLineOptions.find((option) => option.lineId === lineId) || mappingUserLineOptions[0]
      setMappingUserLineId(defaultUserOption.lineId)
    }

    if (mappingSdwtLineOptions.length > 0 && !mappingSdwtLineOptions.some((option) => option.lineId === mappingSdwtLineId)) {
      const defaultSdwtOption = mappingSdwtLineOptions.find((option) => option.lineId === lineId) || mappingSdwtLineOptions[0]
      setMappingSdwtLineId(defaultSdwtOption.lineId)
    }
  }, [lineId, mappingSdwtLineId, mappingSdwtLineOptions, mappingUserLineId, mappingUserLineOptions])

  React.useEffect(() => {
    void loadMyRecipientTargets()
  }, [loadMyRecipientTargets])

  React.useEffect(() => {
    if (didResetMappingDraftRef.current) {
      didResetMappingDraftRef.current = false
      setMappingFormError(null)
      setIsCreatingMapping(false)
      setDeletingMappingKey("")
      return
    }

    setMappingDraft((prev) => {
      const previousUserSdwtProds = Array.isArray(prev.userSdwtProds) ? prev.userSdwtProds : []
      const nextUserSdwtProds = previousUserSdwtProds.filter((value) => (
        effectiveMappingOptions.userSdwtProds.includes(value)
      ))
      const nextUserSdwtProd = nextUserSdwtProds[0] || (
        effectiveMappingOptions.userSdwtProds.includes(prev.userSdwtProd)
          ? prev.userSdwtProd
          : findMappingDefaultOption(effectiveMappingOptions.userSdwtProds, selectedUserSdwtProd)
      )
      const resolvedUserSdwtProds = nextUserSdwtProds.length > 0
        ? nextUserSdwtProds
        : nextUserSdwtProd
          ? [nextUserSdwtProd]
          : []
      const nextSdwtProd = effectiveMappingOptions.sdwtProds.includes(prev.sdwtProd)
        ? prev.sdwtProd
        : findMappingDefaultOption(effectiveMappingOptions.sdwtProds, selectedUserSdwtProd)
      if (
        prev.userSdwtProd === nextUserSdwtProd &&
        prev.sdwtProd === nextSdwtProd &&
        previousUserSdwtProds.length === resolvedUserSdwtProds.length &&
        previousUserSdwtProds.every((value, index) => value === resolvedUserSdwtProds[index])
      ) {
        return prev
      }
      return {
        userSdwtProd: nextUserSdwtProd,
        userSdwtProds: resolvedUserSdwtProds,
        sdwtProd: nextSdwtProd,
      }
    })
    setMappingFormError(null)
    setIsCreatingMapping(false)
    setDeletingMappingKey("")
  }, [effectiveMappingOptions, lineId, selectedUserSdwtProd])

  React.useEffect(() => {
    setJiraKeyDraft(jiraKey || "")
    setChannelEnabledDraft(channelEnabled || DEFAULT_CHANNEL_ENABLED)
    setTemplateKeyDraft(templateKeys || DEFAULT_TEMPLATE_KEYS)
    setNeedToSendRuleDraft(needToSendRule || DEFAULT_NEED_TO_SEND_RULE)
    setJiraKeyFormError(null)
    setNeedToSendRuleFormError(null)
    setIsSavingJiraKey(false)
    setIsSavingNeedToSendRule(false)
    setSavingNeedToSendMappingKey("")
  }, [channelEnabled, jiraKey, lineId, needToSendRule, selectedUserSdwtProd, templateKeys])

  React.useEffect(() => {
    sourceGroupRequestRef.current.mail += 1
    sourceGroupRequestRef.current.messenger += 1
    sourceLoadRequestRef.current.mail += 1
    sourceLoadRequestRef.current.messenger += 1
    setRecipientDrafts({ mail: [], messenger: [] })
    setRecipientDraftTargets({ mail: selectedUserSdwtProd || "", messenger: selectedUserSdwtProd || "" })
    setRecipientDraftDirty({ mail: false, messenger: false })
    setRecipientActionErrors({ mail: null, messenger: null })
    setRecipientPickerOpen({ mail: false, messenger: false })
    setRecipientPickerResults({ mail: { group: [], search: [] }, messenger: { group: [], search: [] } })
    setRecipientPickerSelectedIds({ mail: [], messenger: [] })
    setRecipientSourceDepartments({ mail: "", messenger: "" })
    setRecipientSourceSdwt({ mail: "", messenger: "" })
    setRecipientSourceSdwtOptions({ mail: [], messenger: [] })
    setIsLoadingSourceGroups({ mail: false, messenger: false })
    setIsLoadingSourceUsers({ mail: false, messenger: false })
    setIsSavingRecipients({ mail: false, messenger: false })
  }, [lineId, selectedUserSdwtProd])

  React.useEffect(() => {
    if (!sameUserSdwtProd(mailRecipientsTargetUserSdwtProd, selectedUserSdwtProd)) {
      return
    }
    if (recipientDraftDirty.mail) {
      return
    }
    setRecipientDrafts((prev) => ({ ...prev, mail: mailRecipients || [] }))
    setRecipientDraftTargets((prev) => ({ ...prev, mail: selectedUserSdwtProd || "" }))
    setRecipientActionErrors((prev) => ({ ...prev, mail: null }))
    setRecipientPickerResults((prev) => ({ ...prev, mail: { group: [], search: [] } }))
    setRecipientPickerSelectedIds((prev) => ({ ...prev, mail: [] }))
  }, [mailRecipients, mailRecipientsTargetUserSdwtProd, recipientDraftDirty.mail, selectedUserSdwtProd])

  React.useEffect(() => {
    if (!sameUserSdwtProd(messengerRecipientsTargetUserSdwtProd, selectedUserSdwtProd)) {
      return
    }
    if (recipientDraftDirty.messenger) {
      return
    }
    setRecipientDrafts((prev) => ({ ...prev, messenger: messengerRecipients || [] }))
    setRecipientDraftTargets((prev) => ({ ...prev, messenger: selectedUserSdwtProd || "" }))
    setRecipientActionErrors((prev) => ({ ...prev, messenger: null }))
    setRecipientPickerResults((prev) => ({ ...prev, messenger: { group: [], search: [] } }))
    setRecipientPickerSelectedIds((prev) => ({ ...prev, messenger: [] }))
  }, [
    messengerRecipients,
    messengerRecipientsTargetUserSdwtProd,
    recipientDraftDirty.messenger,
    selectedUserSdwtProd,
  ])

  React.useEffect(() => {
    let isActive = true
    setCanManageNotificationSettings(false)
    setHasLoadedPermissionContext(false)

    async function loadRecipientOptions() {
      const [accountOptionsResult, permissionContextResult] = await Promise.allSettled([
        fetchAccountUserPool({ limit: 1, includeExternalSnapshots: true }),
        fetchNotificationRecipientPermissions(),
      ])
      if (!isActive) {
        return
      }

      if (accountOptionsResult.status === "fulfilled") {
        const { departments, userSdwtProds } = accountOptionsResult.value
        setAccountDepartmentValues(departments || [])
        setAccountUserSdwtValues(userSdwtProds || [])
      } else {
        const message =
          accountOptionsResult.reason instanceof Error
            ? accountOptionsResult.reason.message
            : "Failed to load user groups"
        setAccountDepartmentValues([])
        setAccountUserSdwtValues([])
        setRecipientActionErrors({ mail: message, messenger: message })
      }

      if (permissionContextResult.status === "fulfilled") {
        setCanManageNotificationSettings(Boolean(permissionContextResult.value?.canManageRecipients))
      } else {
        setCanManageNotificationSettings(false)
      }
      setHasLoadedPermissionContext(true)
    }

    loadRecipientOptions()
    return () => {
      isActive = false
    }
  }, [user?.id])

  const {
    handleCreateTarget,
    handleCreateTargetMapping,
    handleDeleteTargetMapping,
    handleMappingDraftChange,
    handleMappingSdwtLineChange,
    handleMappingUserLineChange,
    handleSelectNotificationTarget,
  } = useLineTargetMappingActions({
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
  })
  const {
    handleChannelEnabledChange,
    handleJiraKeySave,
    handleNeedToSendMappingPolicyChange,
    handleNeedToSendRuleDraftChange,
    handleNeedToSendRuleSave,
    handleTemplateKeyChange,
  } = useLineNotificationActions({
    canManageChannelSettings,
    canManageMappings,
    channelEnabledDraft,
    jiraKeyDraft,
    needToSendRule,
    needToSendRuleDraft,
    selectedUserSdwtProd,
    setChannelEnabledDraft,
    setIsSavingJiraKey,
    setIsSavingNeedToSendRule,
    setJiraKeyFormError,
    setMappingFormError,
    setNeedToSendRuleDraft,
    setNeedToSendRuleFormError,
    setSavingNeedToSendMappingKey,
    setTemplateKeyDraft,
    templateKeyDraft,
    updateJiraKey,
    updateNeedToSendRule,
    updateTargetMappingPolicy,
  })

  const notificationTargetCard = (
    <NotificationTargetCard
      lineId={lineId}
      newTargetDraft={newTargetDraft}
      maxTargetFieldLength={MAX_TARGET_FIELD_LENGTH}
      canCreateTarget={canCreateTarget}
      isCreateTargetPermissionLoading={!hasLoadedPermissionContext}
      canManageMappings={canManageMappings}
      isCreatingTarget={isCreatingTarget}
      isCreatingMapping={isCreatingMapping}
      deletingMappingKey={deletingMappingKey}
      savingMappingKey={savingNeedToSendMappingKey}
      targetFormError={targetFormError}
      mappingFormError={mappingFormError}
      mappingDraft={mappingDraft}
      mappingOptions={effectiveMappingOptions}
      mappingUserLineId={mappingUserLineId}
      mappingSdwtLineId={mappingSdwtLineId}
      mappingUserLineOptions={mappingUserLineOptions}
      mappingSdwtLineOptions={mappingSdwtLineOptions}
      mappingOptionLinesError={null}
      mappingValueLineLabels={mappingValueLineLabels}
      isMappingOptionLinesLoading={false}
      userSdwtValues={userSdwtValues}
      selectedUserSdwtProd={selectedUserSdwtProd}
      selectedNotificationTarget={selectedNotificationTarget}
      isAutomaticReservationEnabled={Boolean(needToSendRule.enabled)}
      onTargetDraftChange={setNewTargetDraft}
      onMappingDraftChange={handleMappingDraftChange}
      onMappingUserLineChange={handleMappingUserLineChange}
      onMappingSdwtLineChange={handleMappingSdwtLineChange}
      onCreateTarget={handleCreateTarget}
      onCreateTargetMapping={handleCreateTargetMapping}
      onDeleteTargetMapping={handleDeleteTargetMapping}
      onMappingPolicyChange={handleNeedToSendMappingPolicyChange}
      onSelectTarget={handleSelectNotificationTarget}
    />
  )

  const alarmChannelSettingsCard = (
    <AlarmChannelSettingsCard
      selectedUserSdwtProd={selectedUserSdwtProd}
      jiraKeyDraft={jiraKeyDraft}
      channelEnabledDraft={channelEnabledDraft}
      templateKeyDraft={templateKeyDraft}
      templateOptions={templateOptions}
      maxJiraKeyLength={MAX_JIRA_KEY_LENGTH}
      jiraKeyFormError={jiraKeyFormError}
      jiraKeyError={jiraKeyError}
      isJiraKeyLoading={isJiraKeyLoading}
      isSavingJiraKey={isSavingJiraKey}
      canManage={canManageChannelSettings}
      onJiraKeyDraftChange={setJiraKeyDraft}
      onChannelEnabledChange={handleChannelEnabledChange}
      onTemplateKeyChange={handleTemplateKeyChange}
      onSaveJiraKey={handleJiraKeySave}
    />
  )

  const needToSendCommentRuleCard = (
    <NeedToSendCommentRuleCard
      selectedUserSdwtProd={selectedUserSdwtProd}
      ruleDraft={needToSendRuleDraft}
      maxKeywordLength={MAX_NEED_TO_SEND_KEYWORD_LENGTH}
      formError={needToSendRuleFormError}
      isLoading={isJiraKeyLoading}
      isSaving={isSavingNeedToSendRule}
      canManage={canManageChannelSettings}
      onDraftChange={handleNeedToSendRuleDraftChange}
      onSave={handleNeedToSendRuleSave}
    />
  )

  const myRecipientTargetsCard = (
    <MyRecipientTargetsCard
      lineId={lineId}
      targets={myRecipientTargets}
      selectedUserSdwtProd={selectedUserSdwtProd}
      isLoading={isMyRecipientTargetsLoading}
      error={myRecipientTargetsError}
      onSelectTarget={handleSelectNotificationTarget}
    />
  )

  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col gap-3 overflow-hidden">
      <LineSettingsHeader
        lineId={lineId}
        title={title}
        lastUpdatedLabel={lastUpdatedLabel}
        isRefreshing={isRefreshing}
        onRefresh={handleRefresh}
      />

      {error && (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      <div className={settingsBodyClassName}>
        <div className={settingsGridClassName}>
          {isNotificationSettings && (
            <EarlyInformSettingsCard
              lineId={lineId}
              formError={formError}
              formValues={formValues}
              maxFieldLength={MAX_FIELD_LENGTH}
              isCreating={isCreating}
              entries={entries}
              isLoading={isLoading}
              hasLoadedOnce={hasLoadedOnce}
              editingId={editingId}
              editDraft={editDraft}
              savingMap={savingMap}
              rowErrors={rowErrors}
              onCreate={handleCreate}
              onFormChange={handleFormChange}
              onEditChange={handleEditChange}
              onSave={handleSave}
              onCancelEditing={cancelEditing}
              onStartEditing={startEditing}
              onDelete={handleDelete}
            />
          )}

          {isRecipientSettings ? (
            <div className="h-full min-h-0 min-w-0">
              {notificationTargetCard}
            </div>
          ) : null}

          {isRecipientSettings ? (
            <div className="grid h-full min-h-0 min-w-0 grid-rows-[auto_auto_minmax(0,1fr)] gap-3">
              {alarmChannelSettingsCard}
              {needToSendCommentRuleCard}
              <div className="min-h-0">{myRecipientTargetsCard}</div>
            </div>
          ) : null}

          {isRecipientSettings ? (
            <div className="grid h-full min-h-0 min-w-0 grid-rows-2 gap-3">
              <RecipientSettingsCards
                recipientChannels={RECIPIENT_CHANNELS}
                selectedUserSdwtProd={selectedUserSdwtProd}
                canManageRecipients={canManageRecipients}
                currentRecipientDrafts={currentRecipientDrafts}
                isMessengerRecipientsLoading={isMessengerRecipientsLoading}
                isMailRecipientsLoading={isMailRecipientsLoading}
                onRemoveUser={handleRemoveRecipientUser}
                onSave={handleRecipientsSave}
                onOpenPicker={handleOpenRecipientPicker}
                isRecipientDraftCurrent={isRecipientDraftCurrent}
                isSavingRecipients={isSavingRecipients}
                messengerForceNewChatroom={messengerForceNewChatroom}
                isSavingMessengerForceNewChatroom={isSavingMessengerForceNewChatroom}
                onMessengerForceNewChatroomChange={handleMessengerForceNewChatroomChange}
                recipientActionErrors={recipientActionErrors}
                messengerRecipientsError={messengerRecipientsError}
                mailRecipientsError={mailRecipientsError}
                recipientPickerOpen={recipientPickerOpen}
                recipientPickerTabs={recipientPickerTabs}
                accountDepartmentValues={accountDepartmentValues}
                accountUserSdwtValues={accountUserSdwtValues}
                recipientSourceDepartments={recipientSourceDepartments}
                recipientSourceSdwtOptions={recipientSourceSdwtOptions}
                recipientSourceSdwt={recipientSourceSdwt}
                onPickerOpenChange={handleRecipientPickerOpenChange}
                onPickerTabChange={handleRecipientPickerTabChange}
                onSourceDepartmentChange={handleRecipientSourceDepartmentChange}
                onSourceSdwtChange={handleRecipientSourceSdwtChange}
                isLoadingSourceGroups={isLoadingSourceGroups}
                isLoadingSourceUsers={isLoadingSourceUsers}
                onLoadSourceRecipients={handleLoadSourceRecipients}
                recipientSearches={recipientSearches}
                onRecipientSearchChange={handleRecipientSearchChange}
                isSearchingRecipients={isSearchingRecipients}
                onRecipientSearch={handleRecipientSearch}
                recipientPickerResults={recipientPickerResults}
                recipientPickerSelectedIds={recipientPickerSelectedIds}
                onRecipientPickerUserToggle={handleRecipientPickerUserToggle}
                onRecipientPickerAllToggle={handleRecipientPickerAllToggle}
                onApplyRecipientPicker={handleApplyRecipientPicker}
              />
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}
