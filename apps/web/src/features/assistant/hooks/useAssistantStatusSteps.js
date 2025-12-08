import { useEffect, useState } from "react"

const STATUS_SEQUENCE = [
  "RAG 배경지식을 찾는 중이에요...",
  "LLM이 답변을 작성하고 있어요...",
  "답변을 정리하고 있어요...",
]

// 짧은 간격으로 단계를 넘기면 RAG → LLM 순서가 눈에 띄게 표시된다.
const STEP_INTERVAL_MS = 700

export function useAssistantStatusSteps(isActive) {
  const [stepIndex, setStepIndex] = useState(0)

  useEffect(() => {
    if (!isActive) {
      setStepIndex(0)
      return
    }

    setStepIndex(0)

    const timers = STATUS_SEQUENCE.slice(1).map((_, index) =>
      setTimeout(() => setStepIndex(index + 1), STEP_INTERVAL_MS * (index + 1)),
    )

    return () => {
      timers.forEach((timerId) => clearTimeout(timerId))
    }
  }, [isActive])

  const statusText = STATUS_SEQUENCE[stepIndex] || STATUS_SEQUENCE[0]

  return {
    statusText,
    stepIndex,
    totalSteps: STATUS_SEQUENCE.length,
  }
}
