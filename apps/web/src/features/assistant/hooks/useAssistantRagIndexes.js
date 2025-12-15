import { useQuery } from "@tanstack/react-query"

import { fetchRagIndexes } from "../api/fetchRagIndexes"

export const ASSISTANT_RAG_INDEXES_QUERY_KEY = ["assistant", "rag-indexes"]

export function useAssistantRagIndexes() {
  return useQuery({
    queryKey: ASSISTANT_RAG_INDEXES_QUERY_KEY,
    queryFn: fetchRagIndexes,
  })
}

