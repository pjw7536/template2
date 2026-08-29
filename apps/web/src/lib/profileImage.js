import { readEnvValue } from "@/lib/runtimeEnv"

const DEFAULT_MINIO_BASE_URL = "http://localhost:9000"

function removeTrailingSlash(value) {
  return value.replace(/\/+$/, "")
}

function normalizeAvatarId(value) {
  if (typeof value === "string") return value.trim()
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  return ""
}

function normalizeAvatarIdString(value) {
  return typeof value === "string" ? value.trim() : ""
}

export function getMinioBaseUrl() {
  const envValue =
    readEnvValue("VITE_MINIO_ENDPOINT", "VITE_MINIO_BASE_URL", "MINIO_ENDPOINT") ??
    DEFAULT_MINIO_BASE_URL

  return removeTrailingSlash(envValue.trim())
}

export function resolveProfileAvatarId(source) {
  if (!source || typeof source !== "object") return ""

  return (
    normalizeAvatarIdString(source.avatarId) ||
    normalizeAvatarIdString(source.avatarid) ||
    normalizeAvatarIdString(source.avatar_id) ||
    normalizeAvatarIdString(source.userid) ||
    normalizeAvatarIdString(source.userId) ||
    normalizeAvatarIdString(source.user_id)
  )
}

export function buildProfileImageUrl(avatarId) {
  const normalized = normalizeAvatarId(avatarId)
  if (!normalized) return ""

  const base = getMinioBaseUrl()
  return `${base}/profile/${encodeURIComponent(normalized)}.png`
}
