import { useEffect } from "react"

import { useAuth } from "@/lib/auth"

import { useAssistantRagIndexes } from "./useAssistantRagIndexes"
import { useAssistantRagIndexStore } from "../store/useAssistantRagIndexStore"

function normalizeUserSdwtProd(value) {
  return typeof value === "string" ? value.trim() : ""
}

function buildOptions({ fetched = [], fallbackValue = "" }) {
  const normalized = []

  fetched.forEach((value) => {
    const trimmed = normalizeUserSdwtProd(value)
    if (!trimmed) return
    normalized.push(trimmed)
  })

  const fallbackTrimmed = normalizeUserSdwtProd(fallbackValue)
  if (fallbackTrimmed) {
    normalized.push(fallbackTrimmed)
  }

  return Array.from(new Set(normalized)).sort((a, b) => a.localeCompare(b))
}

export function useAssistantRagIndex() {
  const { user } = useAuth()
  const currentUserSdwtProd = normalizeUserSdwtProd(user?.user_sdwt_prod)

  const ragIndexesQuery = useAssistantRagIndexes()
  const fetchedResults = Array.isArray(ragIndexesQuery.data?.results)
    ? ragIndexesQuery.data.results
    : []
  const options = buildOptions({ fetched: fetchedResults, fallbackValue: currentUserSdwtProd })

  const userSdwtProd = useAssistantRagIndexStore((state) => state.userSdwtProd)
  const setUserSdwtProd = useAssistantRagIndexStore((state) => state.setUserSdwtProd)

  const resolvedUserSdwtProd =
    normalizeUserSdwtProd(userSdwtProd) ||
    currentUserSdwtProd ||
    options[0] ||
    ""

  useEffect(() => {
    if (!resolvedUserSdwtProd) return
    if (!options.length) {
      if (userSdwtProd !== resolvedUserSdwtProd) {
        setUserSdwtProd(resolvedUserSdwtProd)
      }
      return
    }

    if (!options.includes(resolvedUserSdwtProd)) {
      const fallback = currentUserSdwtProd && options.includes(currentUserSdwtProd)
        ? currentUserSdwtProd
        : options[0]
      if (fallback && fallback !== userSdwtProd) {
        setUserSdwtProd(fallback)
      }
      return
    }

    if (resolvedUserSdwtProd !== userSdwtProd) {
      setUserSdwtProd(resolvedUserSdwtProd)
    }
  }, [
    currentUserSdwtProd,
    options.join("|"),
    resolvedUserSdwtProd,
    setUserSdwtProd,
    userSdwtProd,
  ])

  return {
    userSdwtProd: resolvedUserSdwtProd,
    setUserSdwtProd,
    options,
    isLoading: ragIndexesQuery.isLoading,
    isError: ragIndexesQuery.isError,
    errorMessage: ragIndexesQuery.isError ? ragIndexesQuery.error?.message || "" : "",
    canSelect: options.length > 1,
  }
}

