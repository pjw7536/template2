import { afterEach, describe, expect, it } from "vitest"

import { readEnvValue } from "@/lib/runtimeEnv"

describe("readEnvValue", () => {
  afterEach(() => {
    delete globalThis.__APP_CONFIG__
    delete process.env.RUNTIME_ENV_FALLBACK_TEST
  })

  it("runtime config 값을 우선합니다", () => {
    globalThis.__APP_CONFIG__ = {
      VITE_BACKEND_URL: "https://runtime.example.test",
    }

    expect(readEnvValue("VITE_BACKEND_URL")).toBe("https://runtime.example.test")
  })

  it("빈 runtime 값은 다음 fallback으로 넘깁니다", () => {
    globalThis.__APP_CONFIG__ = {
      RUNTIME_ENV_FALLBACK_TEST: "  ",
    }
    process.env.RUNTIME_ENV_FALLBACK_TEST = "process-fallback"

    expect(readEnvValue("RUNTIME_ENV_FALLBACK_TEST")).toBe("process-fallback")
  })

  it("설정되지 않은 key는 undefined를 반환합니다", () => {
    globalThis.__APP_CONFIG__ = {}

    expect(readEnvValue("UNKNOWN_RUNTIME_KEY")).toBeUndefined()
  })
})
