import { buildBackendUrl, safeParseJson } from "@/lib/api"

import { sanitizeContentHtml } from "../utils"

function buildApiError(response, payload, fallbackMessage) {
  const apiMessage =
    payload && typeof payload === "object" && typeof payload.error === "string"
      ? payload.error
      : ""
  const error = new Error(apiMessage || fallbackMessage)
  error.status = response.status
  return error
}

function buildContractError(message) {
  const error = new Error(`Invalid VOC API response: ${message}`)
  error.code = "VOC_API_CONTRACT_ERROR"
  return error
}

function requireObject(value, field) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw buildContractError(`${field} must be an object`)
  }
  return value
}

function requireInteger(value, field) {
  if (!Number.isInteger(value)) {
    throw buildContractError(`${field} must be an integer`)
  }
  return value
}

function requireString(value, field) {
  if (typeof value !== "string") {
    throw buildContractError(`${field} must be a string`)
  }
  return value
}

export function parseVocAuthor(raw) {
  if (raw === null) return null
  const author = requireObject(raw, "author")
  return {
    id: requireInteger(author.id, "author.id"),
    name: requireString(author.name, "author.name"),
  }
}

export function parseVocReply(raw) {
  const reply = requireObject(raw, "reply")
  return {
    id: requireInteger(reply.id, "reply.id"),
    postId: requireInteger(reply.postId, "reply.postId"),
    content: requireString(reply.content, "reply.content").trim(),
    createdAt: requireString(reply.createdAt, "reply.createdAt"),
    author: parseVocAuthor(reply.author),
  }
}

export function parseVocPost(raw) {
  const post = requireObject(raw, "post")
  if (!Array.isArray(post.replies)) {
    throw buildContractError("post.replies must be an array")
  }

  return {
    id: requireInteger(post.id, "post.id"),
    title: requireString(post.title, "post.title"),
    content: sanitizeContentHtml(requireString(post.content, "post.content")),
    status: requireString(post.status, "post.status"),
    app: requireString(post.app, "post.app"),
    createdAt: requireString(post.createdAt, "post.createdAt"),
    updatedAt: requireString(post.updatedAt, "post.updatedAt"),
    author: parseVocAuthor(post.author),
    replies: post.replies.map(parseVocReply),
  }
}

function parsePostEnvelope(payload) {
  const envelope = requireObject(payload, "payload")
  return { post: parseVocPost(envelope.post) }
}

export async function fetchVocPosts() {
  const endpoint = buildBackendUrl("/api/v1/voc/posts")
  const response = await fetch(endpoint, {
    cache: "no-store",
    credentials: "include",
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(response, payload, `Failed to load posts (status ${response.status})`)
  }

  const envelope = requireObject(payload, "payload")
  if (!Array.isArray(envelope.results)) {
    throw buildContractError("results must be an array")
  }
  return envelope.results.map(parseVocPost)
}

export async function createVocPost({ title, content, status, app }) {
  const endpoint = buildBackendUrl("/api/v1/voc/posts")
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ title, content, status, app }),
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(response, payload, "Failed to create post")
  }
  return parsePostEnvelope(payload)
}

export async function updateVocPost(postId, updates = {}) {
  const endpoint = buildBackendUrl(`/api/v1/voc/posts/${postId}`)
  const body = {}
  if ("title" in updates) body.title = updates.title
  if ("content" in updates) body.content = updates.content
  if ("status" in updates) body.status = updates.status
  if ("app" in updates) body.app = updates.app

  const response = await fetch(endpoint, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(response, payload, "Failed to update post")
  }
  return parsePostEnvelope(payload)
}

export async function deleteVocPost(postId) {
  const endpoint = buildBackendUrl(`/api/v1/voc/posts/${postId}`)
  const response = await fetch(endpoint, {
    method: "DELETE",
    credentials: "include",
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(response, payload, "Failed to delete post")
  }
  if (requireObject(payload, "payload").success !== true) {
    throw buildContractError("success must be true")
  }
  return { success: true }
}

export async function createVocReply({ postId, content }) {
  const endpoint = buildBackendUrl(`/api/v1/voc/posts/${postId}/replies`)
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ content }),
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(response, payload, "Failed to add reply")
  }
  const envelope = requireObject(payload, "payload")
  return {
    reply: parseVocReply(envelope.reply),
    post: parseVocPost(envelope.post),
  }
}
