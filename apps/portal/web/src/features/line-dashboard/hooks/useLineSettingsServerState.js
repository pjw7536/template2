// 라인 설정·target·수신인 원격 상태를 하나의 React Query snapshot으로 관리합니다.
import * as React from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import {
  fetchLineSettings,
  fetchNotificationRecipients,
  fetchNotificationTargets,
  fetchNotificationTemplateOptions,
  fetchTargetJiraConfiguration,
  lineDashboardQueryKeys,
} from "../api"

const EMPTY_JIRA_CONFIGURATION = {
  jiraKey: "",
  templateKeys: { jira: "common", messenger: "common", mail: "common" },
  messengerForceNewChatroom: false,
}

async function fetchLineSettingsServerState({ lineId, targetUserSdwtProd, loadRecipients }) {
  const shouldLoadRecipients = Boolean(loadRecipients && targetUserSdwtProd)
  return Promise.allSettled([
    fetchLineSettings(lineId),
    fetchNotificationTargets({ lineId }),
    fetchNotificationTemplateOptions(),
    targetUserSdwtProd
      ? fetchTargetJiraConfiguration(targetUserSdwtProd)
      : Promise.resolve(EMPTY_JIRA_CONFIGURATION),
    shouldLoadRecipients
      ? fetchNotificationRecipients({
          lineId,
          targetUserSdwtProd,
          channel: "mail",
        })
      : Promise.resolve({ recipients: [] }),
    shouldLoadRecipients
      ? fetchNotificationRecipients({
          lineId,
          targetUserSdwtProd,
          channel: "messenger",
        })
      : Promise.resolve({ recipients: [] }),
  ])
}

export function useLineSettingsServerState({ lineId, targetUserSdwtProd, loadRecipients }) {
  const queryClient = useQueryClient()
  const queryKey = React.useMemo(
    () => lineDashboardQueryKeys.settings({ lineId, targetUserSdwtProd, loadRecipients }),
    [lineId, loadRecipients, targetUserSdwtProd],
  )
  const query = useQuery({
    queryKey,
    enabled: false,
    queryFn: () =>
      fetchLineSettingsServerState({ lineId, targetUserSdwtProd, loadRecipients }),
  })
  const invalidate = React.useCallback(
    () => queryClient.invalidateQueries({ queryKey }),
    [queryClient, queryKey],
  )

  return {
    invalidate,
    refetch: query.refetch,
  }
}
