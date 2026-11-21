import Keycloak from "keycloak-js"

import { displayProfile } from "./users"

/** 런타임 설정(public/config.js)을 읽어 Keycloak 로그인과 Admin API 호출을 제공합니다. */
const config = window.__IAM_CONFIG__ ?? {}

export const realm = config.realm
export const keycloak = new Keycloak({
  url: config.keycloakUrl,
  realm: config.realm,
  clientId: config.clientId,
})

export function initLogin() {
  return keycloak.init({ onLoad: "login-required", pkceMethod: "S256", checkLoginIframe: false })
}

/** Etch Members를 쓰려면 realm-management의 manage-users role이 필요합니다. */
export function canManageUsers() {
  return keycloak.hasResourceRole("manage-users", "realm-management")
}

/** 이전 토큰에 비어 있는 표시 속성을 자기 프로필에서 확인합니다. */
export async function loadDisplayProfile(initial) {
  const profile = displayProfile(initial, await keycloak.loadUserInfo().catch(() => null))
  if ((profile.display_name && profile.loginid) || !canManageUsers() || !keycloak.subject) return profile
  const ownUser = await admin(`/users/${encodeURIComponent(keycloak.subject)}`).catch(() => null)
  return displayProfile(profile, ownUser)
}

export class AdminError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

/** 대상 realm의 Admin API를 호출합니다. path는 `/admin/realms/<realm>` 뒤의 경로입니다. */
export async function admin(path, { method = "GET", body, query } = {}) {
  await keycloak.updateToken(30)
  const url = new URL(`${config.keycloakUrl}/admin/realms/${encodeURIComponent(realm)}${path}`)
  for (const [key, value] of Object.entries(query ?? {})) url.searchParams.set(key, value)
  const response = await fetch(url, {
    method,
    headers: {
      Authorization: `Bearer ${keycloak.token}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    let detail = ""
    try {
      const data = await response.json()
      detail = data.errorMessage || data.error || ""
    } catch {
      // 본문이 없는 오류 응답은 상태 코드만 표시합니다.
    }
    throw new AdminError(response.status, `Keycloak ${method} ${path} 실패 (HTTP ${response.status}) ${detail}`.trim())
  }
  const text = await response.text()
  return text ? JSON.parse(text) : null
}
