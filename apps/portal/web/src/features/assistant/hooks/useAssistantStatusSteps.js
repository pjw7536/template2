import { useEffect, useState } from "react"

const STATUS_SEQUENCES = {
  email: [
    "메일 RAG 배경지식을 찾는 중이에요...",
    "LLM이 답변을 작성하고 있어요...",
    "답변을 정리하고 있어요...",
  ],
  observer: [
    "현재 조회 데이터를 집계하고 있어요...",
    "OpenWebUI가 원인을 분석하고 있어요...",
    "분석 결과를 정리하고 있어요...",
  ],
  openwebui: [
    "OpenWebUI가 답변을 작성하고 있어요...",
    "답변을 정리하고 있어요...",
  ],
}

// 짧은 간격으로 단계를 넘기면 RAG → LLM 순서가 눈에 띄게 표시된다.
const STEP_INTERVAL_MS = 700

export function useAssistantStatusSteps(isActive, mode = "openwebui") {
  const [stepIndex, setStepIndex] = useState(0)
  const statusSequence = STATUS_SEQUENCES[mode] || STATUS_SEQUENCES.openwebui

  useEffect(() => {
    if (!isActive) {
      setStepIndex(0)
      return
    }

    setStepIndex(0)

    const timers = statusSequence.slice(1).map((_, index) =>
      setTimeout(() => setStepIndex(index + 1), STEP_INTERVAL_MS * (index + 1)),
    )

    return () => {
      timers.forEach((timerId) => clearTimeout(timerId))
    }
  }, [isActive, statusSequence])

  const statusText = statusSequence[stepIndex] || statusSequence[0]

  return {
    statusText,
    stepIndex,
    totalSteps: statusSequence.length,
  }
}
