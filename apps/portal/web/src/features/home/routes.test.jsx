import { matchRoutes } from "react-router-dom"
import { describe, expect, it } from "vitest"

import { homeRoutes } from "./routes"

describe("Home route 계약", () => {
  it("Portal home은 유지하고 react logo preview는 등록하지 않는다", () => {
    expect(matchRoutes(homeRoutes, "/")).not.toBeNull()
    expect(matchRoutes(homeRoutes, "/react-logo-preview")).toBeNull()
  })
})
