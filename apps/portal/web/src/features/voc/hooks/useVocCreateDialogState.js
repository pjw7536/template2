import * as React from "react"

import { hasMeaningfulContent, sanitizeContentHtml } from "../utils"

export function useVocCreateDialogState({
  form,
  setIsCreateOpen,
  createPost,
  isSubmitting,
}) {
  const handleCreateOpenChange = React.useCallback(
    (open) => {
      setIsCreateOpen(open)
    },
    [setIsCreateOpen],
  )

  const handleCreatePost = React.useCallback(
    async (event) => {
      event.preventDefault()
      await createPost()
    },
    [createPost],
  )

  const sanitizedDraft = React.useMemo(
    () => sanitizeContentHtml(form.content),
    [form.content],
  )

  const hasDraftContent = React.useMemo(
    () => hasMeaningfulContent(sanitizedDraft, { skipSanitize: true }),
    [sanitizedDraft],
  )

  const isSubmitDisabled =
    isSubmitting || !form.title.trim() || !hasDraftContent

  return {
    handleCreateOpenChange,
    handleCreatePost,
    isSubmitDisabled,
  }
}
