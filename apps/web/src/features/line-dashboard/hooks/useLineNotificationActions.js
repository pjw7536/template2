import * as React from "react"

// 상위 controller에서 전달되는 React setter는 수명 동안 안정적이므로 기존 의존성 배열을 유지합니다.
/* eslint-disable react-hooks/exhaustive-deps */

import { MAX_JIRA_KEY_LENGTH, MAX_NEED_TO_SEND_KEYWORD_LENGTH } from "../utils/lineSettingsConfig"
import {
  showAlarmChannelApplyToast,
  showJiraKeyToast,
  showNeedToSendMappingApplyToast,
  showNeedToSendRuleApplyToast,
  showNeedToSendRuleToast,
  showRequestErrorToast,
} from "../utils/lineSettingsToasts"
import { buildTargetMappingKey } from "../utils/lineSettingsMappings"

export function useLineNotificationActions({
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
}) {
  const handleJiraKeySave = React.useCallback(
    async (event) => {
      event.preventDefault()
      if (!selectedUserSdwtProd) {
        setJiraKeyFormError("알림 Target을 선택하세요.")
        return
      }

      const normalized = jiraKeyDraft.trim()
      if (channelEnabledDraft.jira && !normalized) {
        setJiraKeyFormError("Jira Project Key를 입력하세요.")
        return
      }
      if (normalized.length > MAX_JIRA_KEY_LENGTH) {
        setJiraKeyFormError(`Jira key must be ${MAX_JIRA_KEY_LENGTH} characters or fewer`)
        return
      }
      if (!canManageChannelSettings) {
        setJiraKeyFormError("Jira Project Key 변경 권한이 없습니다.")
        return
      }

      setIsSavingJiraKey(true)
      setJiraKeyFormError(null)

      try {
        await updateJiraKey({
          jiraKey: normalized,
          channelEnabled: channelEnabledDraft,
          templateKeys: templateKeyDraft,
        })
        showJiraKeyToast()
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to update Jira key"
        setJiraKeyFormError(message)
        showRequestErrorToast(message)
      } finally {
        setIsSavingJiraKey(false)
      }
    },
    [
      canManageChannelSettings,
      channelEnabledDraft,
      jiraKeyDraft,
      selectedUserSdwtProd,
      templateKeyDraft,
      updateJiraKey,
    ],
  )

  const handleTemplateKeyChange = React.useCallback((channelKey, value) => {
    setTemplateKeyDraft((prev) => ({ ...prev, [channelKey]: value }))
  }, [])

  const handleChannelEnabledChange = React.useCallback(async (channelKey, isEnabled) => {
    if (!selectedUserSdwtProd) {
      setJiraKeyFormError("알림 Target을 선택하세요.")
      return
    }
    if (!canManageChannelSettings) {
      setJiraKeyFormError("알람 채널 설정 변경 권한이 없습니다.")
      return
    }

    const previousDraft = channelEnabledDraft
    const nextDraft = { ...channelEnabledDraft, [channelKey]: isEnabled }
    setChannelEnabledDraft(nextDraft)
    setIsSavingJiraKey(true)
    setJiraKeyFormError(null)
    try {
      await updateJiraKey({
        jiraKey: jiraKeyDraft.trim(),
        channelEnabled: nextDraft,
        templateKeys: templateKeyDraft,
      })
      showAlarmChannelApplyToast(channelKey, isEnabled)
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to update alarm channel"
      setChannelEnabledDraft(previousDraft)
      setJiraKeyFormError(message)
      showRequestErrorToast(message)
    } finally {
      setIsSavingJiraKey(false)
    }
  }, [
    canManageChannelSettings,
    channelEnabledDraft,
    jiraKeyDraft,
    selectedUserSdwtProd,
    templateKeyDraft,
    updateJiraKey,
  ])

  const handleNeedToSendRuleDraftChange = React.useCallback(async (key, value) => {
    if (key === "commentKeyword") {
      setNeedToSendRuleDraft((prev) => {
        const nextKeyword = String(value ?? "")
        return { ...prev, commentKeyword: nextKeyword, enabled: nextKeyword.trim() ? true : prev.enabled }
      })
      setNeedToSendRuleFormError(null)
      return
    }

    if (!selectedUserSdwtProd) {
      setNeedToSendRuleFormError("알림 Target을 선택하세요.")
      return
    }
    if (!canManageChannelSettings) {
      setNeedToSendRuleFormError("자동 예약 코멘트 규칙 변경 권한이 없습니다.")
      return
    }

    const previousDraft = needToSendRuleDraft
    const normalizedKeyword = String(needToSendRuleDraft.commentKeyword || "").trim()
    const nextRule = {
      commentKeyword: normalizedKeyword,
      enabled: key === "enabled" ? Boolean(value) : Boolean(needToSendRuleDraft.enabled),
      ignoreSampleType: key === "ignoreSampleType" ? Boolean(value) : Boolean(needToSendRuleDraft.ignoreSampleType),
    }
    setNeedToSendRuleDraft(nextRule)
    setIsSavingNeedToSendRule(true)
    setNeedToSendRuleFormError(null)
    try {
      await updateNeedToSendRule({ needToSendRule: nextRule })
      showNeedToSendRuleApplyToast(key, Boolean(value))
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to update needtosend rule"
      setNeedToSendRuleDraft(previousDraft)
      setNeedToSendRuleFormError(message)
      showRequestErrorToast(message)
    } finally {
      setIsSavingNeedToSendRule(false)
    }
  }, [
    canManageChannelSettings,
    needToSendRuleDraft,
    selectedUserSdwtProd,
    updateNeedToSendRule,
  ])

  const handleNeedToSendRuleSave = React.useCallback(
    async (event) => {
      event.preventDefault()
      if (!selectedUserSdwtProd) {
        setNeedToSendRuleFormError("알림 Target을 선택하세요.")
        return
      }
      if (!canManageChannelSettings) {
        setNeedToSendRuleFormError("자동 예약 코멘트 규칙 변경 권한이 없습니다.")
        return
      }

      const normalizedKeyword = String(needToSendRuleDraft.commentKeyword || "").trim()
      if (normalizedKeyword.length > MAX_NEED_TO_SEND_KEYWORD_LENGTH) {
        setNeedToSendRuleFormError(`포함 키워드는 ${MAX_NEED_TO_SEND_KEYWORD_LENGTH}자 이하여야 합니다.`)
        return
      }
      const nextRule = {
        commentKeyword: normalizedKeyword,
        enabled: Boolean(needToSendRuleDraft.enabled),
        ignoreSampleType: Boolean(needToSendRuleDraft.ignoreSampleType),
      }
      setIsSavingNeedToSendRule(true)
      setNeedToSendRuleFormError(null)

      try {
        await updateNeedToSendRule({ needToSendRule: nextRule })
        showNeedToSendRuleToast()
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to update needtosend rule"
        setNeedToSendRuleFormError(message)
        showRequestErrorToast(message)
      } finally {
        setIsSavingNeedToSendRule(false)
      }
    },
    [
      canManageChannelSettings,
      needToSendRuleDraft,
      selectedUserSdwtProd,
      updateNeedToSendRule,
    ],
  )

  const handleNeedToSendMappingPolicyChange = React.useCallback(async (mapping, nextValue) => {
    if (!selectedUserSdwtProd) {
      setMappingFormError("알림 Target을 선택하세요.")
      return
    }
    if (!canManageMappings) {
      setMappingFormError("지정 조합의 자동 예약 설정 변경 권한이 없습니다.")
      return
    }

    const mappingKey = buildTargetMappingKey(mapping)
    setSavingNeedToSendMappingKey(mappingKey)
    setMappingFormError(null)
    try {
      await updateTargetMappingPolicy({
        targetUserSdwtProd: selectedUserSdwtProd,
        sdwtProd: mapping.sdwtProd,
        userSdwtProd: mapping.userSdwtProd,
        needtosendWithoutComment: nextValue,
      })
      showNeedToSendMappingApplyToast(
        mapping.userSdwtProd,
        mapping.sdwtProd,
        nextValue,
        Boolean(needToSendRule.enabled),
      )
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to update target mapping"
      setMappingFormError(message)
      showRequestErrorToast(message)
    } finally {
      setSavingNeedToSendMappingKey("")
    }
  }, [
    canManageMappings,
    needToSendRule.enabled,
    selectedUserSdwtProd,
    updateTargetMappingPolicy,
  ])

  return {
    handleChannelEnabledChange,
    handleJiraKeySave,
    handleNeedToSendMappingPolicyChange,
    handleNeedToSendRuleDraftChange,
    handleNeedToSendRuleSave,
    handleTemplateKeyChange,
  }
}
