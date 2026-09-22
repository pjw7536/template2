import { buildBackendUrl, safeParseJson } from "@/lib/api"

const ENDPOINT = "/api/v1/assistant/rag-indexes"

export async function fetchRagIndexes() {
  const response = await fetch(buildBackendUrl(ENDPOINT), {
    credentials: "include",
    cache: "no-store",
  })

  const data = await safeParseJson(response)
  if (!response.ok) {
    const message =
      typeof data?.error === "string" && data.error.trim()
        ? data.error.trim()
        : "RAG 인덱스/권한 정보를 불러오지 못했어요."
    throw new Error(message)
  }

  return data
}
