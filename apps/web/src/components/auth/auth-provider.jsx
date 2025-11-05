"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

import { buildBackendUrl } from "@/lib/api"

const AuthContext = createContext(undefined)

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: "include",
    ...options,
  })
  const text = await response.text()
  try {
    const data = text ? JSON.parse(text) : null
    return { ok: response.ok, status: response.status, data }
  } catch (error) {
    return { ok: response.ok, status: response.status, data: null }
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [config, setConfig] = useState({
    devLoginEnabled: false,
    loginUrl: "/oidc/authenticate/",
    frontendRedirect: "http://localhost:3000",
  })
  const [isLoading, setIsLoading] = useState(true)

  const loadConfig = useCallback(async () => {
    try {
      const endpoint = buildBackendUrl("/auth/config")
      const result = await fetchJson(endpoint, { cache: "no-store" })
      if (result.ok && result.data) {
        setConfig((previous) => ({ ...previous, ...result.data }))
      }
    } catch (error) {
      // Ignore config errors and keep defaults
    }
  }, [])

  const loadUser = useCallback(async () => {
    setIsLoading(true)
    try {
      const endpoint = buildBackendUrl("/auth/me")
      const result = await fetchJson(endpoint, { cache: "no-store" })
      if (result.ok && result.data) {
        setUser(result.data)
      } else {
        setUser(null)
      }
    } catch (error) {
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConfig()
    loadUser()
  }, [loadConfig, loadUser])

  const login = useCallback(async (options = {}) => {
    const nextPath = typeof options?.next === "string" ? options.next : undefined
    if (config.devLoginEnabled) {
      try {
        const endpoint = buildBackendUrl("/auth/dev-login")
        const result = await fetchJson(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        })
        if (result.ok) {
          await loadUser()
          return { method: "dev", next: nextPath }
        }
      } catch (error) {
        // fall through to redirect
      }
    }

    const loginUrl = config.loginUrl || "/oidc/authenticate/"
    let target = loginUrl.startsWith("http") ? loginUrl : buildBackendUrl(loginUrl)
    if (nextPath) {
      try {
        const url = new URL(target)
        url.searchParams.set("next", nextPath)
        target = url.toString()
      } catch (error) {
        const separator = target.includes("?") ? "&" : "?"
        target = `${target}${separator}next=${encodeURIComponent(nextPath)}`
      }
    }
    if (typeof window !== "undefined") {
      window.location.href = target
    }
    return { method: "redirect", url: target }
  }, [config, loadUser])

  const logout = useCallback(async () => {
    try {
      const endpoint = buildBackendUrl("/auth/logout")
      await fetchJson(endpoint, { method: "POST" })
    } finally {
      setUser(null)
    }
  }, [])

  const value = useMemo(
    () => ({
      user,
      isLoading,
      login,
      logout,
      refresh: loadUser,
      config,
    }),
    [user, isLoading, login, logout, loadUser, config],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
