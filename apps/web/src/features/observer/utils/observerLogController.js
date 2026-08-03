import {
  mergeUniqueLogItems,
  OBSERVER_LOG_CONFIG,
  OBSERVER_RESIDENT_LOG_LIMIT,
} from "./logPagination"

export function shouldRetryObserverLogQuery(failureCount, error) {
  if (failureCount >= 1) return false
  return !error?.status || [429, 502, 503].includes(error.status)
}

export function buildObserverLogScopeKey(eqpId, logQueryOptions) {
  return JSON.stringify([eqpId || "", logQueryOptions])
}

function getLogTimestamp(item) {
  const timestamp = Date.parse(item?.eventTime || "")
  return Number.isNaN(timestamp) ? 0 : timestamp
}

export function mergeResidentLogs(batchData, entries, pageQueries) {
  const result = {}
  const seen = new Set()
  let residentCount = 0

  for (const { logKey } of OBSERVER_LOG_CONFIG) {
    const initialItems = mergeUniqueLogItems(
      [batchData?.[logKey]?.items || []],
      OBSERVER_RESIDENT_LOG_LIMIT,
    )
    result[logKey] = initialItems
    residentCount += initialItems.length
    initialItems.forEach((item) => seen.add(`${logKey}:${item.id}`))
  }

  const extraItems = []
  entries.forEach((entry, index) => {
    for (const item of pageQueries[index]?.data?.items || []) {
      const identity = `${entry.logKey}:${item.id}`
      if (seen.has(identity)) continue
      seen.add(identity)
      extraItems.push({
        item,
        logKey: entry.logKey,
        sequence: extraItems.length,
      })
    }
  })
  extraItems.sort(
    (left, right) => (
      getLogTimestamp(right.item) - getLogTimestamp(left.item)
      || left.sequence - right.sequence
    ),
  )

  const remainingBudget = Math.max(OBSERVER_RESIDENT_LOG_LIMIT - residentCount, 0)
  extraItems.slice(0, remainingBudget).forEach(({ item, logKey }) => {
    result[logKey].push(item)
  })
  return result
}

export function getLatestObserverLogPageState(logKey, batchData, entries, pageQueries) {
  const matchingIndexes = entries
    .map((entry, index) => ({ entry, index }))
    .filter(({ entry }) => entry.logKey === logKey)
  const lastMatch = matchingIndexes.at(-1)
  if (lastMatch) {
    const query = pageQueries[lastMatch.index]
    if (query?.data) {
      return {
        cursor: query.data.page?.nextCursor,
        hasMore: Boolean(query.data.page?.hasMore),
      }
    }
  }

  const initial = batchData?.[logKey]
  return {
    cursor: initial?.nextCursor,
    hasMore: Boolean(initial?.hasMore),
  }
}
