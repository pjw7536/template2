export function parseAssistantSseBlock(block) {
  const lines = block.replace(/\r\n/g, "\n").split("\n")
  let event = "message"
  const dataLines = []
  lines.forEach((line) => {
    if (line.startsWith("event:")) event = line.slice(6).trim() || "message"
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart())
  })
  const rawData = dataLines.join("\n")
  if (!rawData) return { event, payload: {} }
  try {
    return { event, payload: JSON.parse(rawData) }
  } catch {
    throw new Error("Assistant 스트리밍 응답 형식이 올바르지 않습니다.")
  }
}

export async function readAssistantSse(response, { onEvent } = {}) {
  const reader = response.body?.getReader?.()
  if (!reader) throw new Error("브라우저가 스트리밍 응답을 지원하지 않습니다.")
  const decoder = new TextDecoder()
  const events = []
  let buffer = ""

  const consumeBlock = (block) => {
    const parsed = parseAssistantSseBlock(block)
    events.push(parsed)
    onEvent?.(parsed)
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
      buffer = buffer.replace(/\r\n/g, "\n")
      let boundary = buffer.indexOf("\n\n")
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary).trim()
        buffer = buffer.slice(boundary + 2)
        if (block) consumeBlock(block)
        boundary = buffer.indexOf("\n\n")
      }
      if (done) break
    }
    if (buffer.trim()) consumeBlock(buffer.trim())
  } finally {
    reader.releaseLock?.()
  }
  return events
}
