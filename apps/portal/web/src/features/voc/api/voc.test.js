import { afterEach, describe, expect, it, vi } from "vitest"

import { createVocPost, fetchVocPosts, parseVocPost } from "./voc"

function buildPost(overrides = {}) {
  return {
    id: 10,
    title: "문의",
    content: "<p>내용</p>",
    status: "접수",
    createdAt: "2026-08-01T00:00:00+00:00",
    updatedAt: "2026-08-01T00:00:00+00:00",
    author: { id: 3, name: "사용자(knox)" },
    replies: [],
    ...overrides,
  }
}

function jsonResponse(payload, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(payload),
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("VOC API contract", () => {
  it("canonical camelCase 게시글을 파싱한다", () => {
    expect(parseVocPost(buildPost())).toMatchObject({
      id: 10,
      createdAt: "2026-08-01T00:00:00+00:00",
      author: { id: 3 },
    })
  })

  it("legacy pk와 snake_case 날짜만 있는 응답을 거부한다", () => {
    const legacyPost = buildPost({ id: undefined, pk: 10, createdAt: undefined })
    legacyPost.created_at = "2026-08-01T00:00:00+00:00"

    expect(() => parseVocPost(legacyPost)).toThrow("post.id must be an integer")
  })

  it("목록 요청은 사용하지 않는 status query 없이 전체 목록만 조회한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ results: [buildPost()] }))
    vi.stubGlobal("fetch", fetchMock)

    const posts = await fetchVocPosts()

    expect(posts).toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/voc/posts",
      expect.objectContaining({ credentials: "include" }),
    )
  })

  it("생성 요청과 응답은 canonical 필드만 사용한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ post: buildPost() }, { status: 201 }),
    )
    vi.stubGlobal("fetch", fetchMock)

    const result = await createVocPost({
      title: "문의",
      content: "내용",
      status: "접수",
      app: "기타",
    })

    expect(result.post.id).toBe(10)
    const request = fetchMock.mock.calls[0][1]
    expect(JSON.parse(request.body)).toEqual({
      title: "문의",
      content: "내용",
      status: "접수",
    })
  })
})
