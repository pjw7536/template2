import { useCallback, useEffect, useRef, useState } from "react"

import { streamAssistantTurn } from "../api/turnApi"

export function useAssistantRun() {
  const controllerRef = useRef(null)
  const [activeRun, setActiveRun] = useState(null)

  useEffect(
    () => () => {
      controllerRef.current?.abort()
      controllerRef.current = null
    },
    [],
  )

  const startRun = useCallback(async (payload, { onEvent } = {}) => {
    if (controllerRef.current) {
      throw new Error("이미 Assistant 답변을 생성하고 있습니다.")
    }
    const controller = new AbortController()
    controllerRef.current = controller
    setActiveRun({ roomId: payload.conversationId, runId: null })
    try {
      return await streamAssistantTurn(payload, {
        signal: controller.signal,
        onEvent: (event) => {
          if (event.event === "run.started") {
            setActiveRun({
              roomId: payload.conversationId,
              runId: event.payload.runId || null,
            })
          }
          onEvent?.(event)
        },
      })
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null
        setActiveRun(null)
      }
    }
  }, [])

  const stopRun = useCallback(() => controllerRef.current?.abort(), [])

  return {
    activeRun,
    isRunning: Boolean(activeRun),
    startRun,
    stopRun,
  }
}
