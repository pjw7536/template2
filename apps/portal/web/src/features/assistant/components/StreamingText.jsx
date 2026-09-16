import { useEffect, useState } from "react"

const STREAM_DURATION_MS = 500
const STREAM_START_DELAY_MS = 1_000

export function StreamingText({ content, streamId }) {
  const characters = Array.from(typeof content === "string" ? content : "")
  const [visibleCount, setVisibleCount] = useState(() =>
    streamId ? 0 : characters.length,
  )
  const [hasStarted, setHasStarted] = useState(() => !streamId)

  useEffect(() => {
    if (!streamId) {
      setVisibleCount(characters.length)
      setHasStarted(true)
      return undefined
    }
    setVisibleCount(0)
    setHasStarted(false)
    if (!characters.length) return undefined

    let nextVisibleCount = 0
    let intervalId
    const characterIntervalMs = STREAM_DURATION_MS / characters.length
    const startTimeoutId = window.setTimeout(() => {
      setHasStarted(true)
      intervalId = window.setInterval(() => {
        nextVisibleCount += 1
        setVisibleCount(nextVisibleCount)
        if (nextVisibleCount >= characters.length) window.clearInterval(intervalId)
      }, characterIntervalMs)
    }, STREAM_START_DELAY_MS)
    return () => {
      window.clearTimeout(startTimeoutId)
      if (intervalId) window.clearInterval(intervalId)
    }
  }, [characters.length, streamId])

  const isComplete = visibleCount >= characters.length

  return (
    <span className="inline-flex min-h-6 items-center">
      <span className="sr-only">{content}</span>
      <span aria-hidden="true" className="inline-flex items-center">
        {characters.slice(0, visibleCount).join("")}
        {hasStarted && !isComplete ? (
          <span
            data-streaming-cursor
            className="ml-0.5 inline-block h-4 w-0.5 shrink-0 bg-muted-foreground motion-safe:animate-pulse"
          />
        ) : null}
      </span>
    </span>
  )
}
