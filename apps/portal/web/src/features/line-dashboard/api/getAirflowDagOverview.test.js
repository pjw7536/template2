import { afterEach, describe, expect, it, vi } from "vitest"

import { getAirflowDagOverview } from "./getAirflowDagOverview"

describe("getAirflowDagOverview", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("Django session endpoint에서 overview를 조회합니다", async () => {
    const payload = {
      baseUrl: "/airflow",
      totals: { total: 0, active: 0, paused: 0, failed: 0 },
      dags: [],
    }
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(payload),
    })

    await expect(getAirflowDagOverview()).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/line-dashboard/airflow/dag-overview",
      expect.objectContaining({
        credentials: "include",
        headers: { Accept: "application/json" },
      }),
    )
  })

  it("backend 오류를 기존 overview error 형태로 변환합니다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: vi.fn().mockResolvedValue({ error: "Airflow API 정보를 불러오지 못했습니다." }),
    })

    await expect(getAirflowDagOverview()).resolves.toEqual({
      baseUrl: "/airflow",
      error: "Airflow API 정보를 불러오지 못했습니다.",
    })
  })
})
