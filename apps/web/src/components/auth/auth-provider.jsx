"use client";

// ✅ AuthProvider (리팩토링 + 한글주석)
// - 목적: 인증 상태(user), 로딩 상태, 로그인/로그아웃 함수, 서버 설정(config)을 전역 Context 로 제공
// - 특징:
//   1) fetchJson 유틸: JSON/텍스트 응답 모두 안전 처리, 오류 메시지 보존
//   2) URL 빌딩 로직 정리: next 리다이렉트 처리 안정화
//   3) 마운트 여부 체크로 언마운트 후 setState 방지
//   4) 창 포커스 시 사용자 정보 자동 새로고침(선택적)
//   5) JSDoc 타입 주석으로 IDE 자동완성 도움 (JS 그대로 유지)

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { buildBackendUrl } from "@/lib/api";

/**
 * @template T
 * @typedef {Object} FetchResult
 * @property {boolean} ok - HTTP ok 여부(response.ok)
 * @property {number} status - HTTP 상태 코드
 * @property {T|null} data - 파싱된 데이터(JSON 또는 null)
 * @property {string | null} [error] - 오류 메시지(있을 경우)
 */

/** JSON/텍스트 응답을 안전하게 처리하는 fetch 유틸 */
async function fetchJson(url, options = {}) {
  /** @type {FetchResult<any>} */
  const base = { ok: false, status: 0, data: null, error: null };
  let response;
  try {
    response = await fetch(url, {
      credentials: "include", // 쿠키 기반 세션 포함
      ...options,
    });
  } catch (networkError) {
    return { ...base, error: String(networkError) };
  }

  const contentType = response.headers.get("content-type") || "";
  let data = null;
  try {
    if (contentType.includes("application/json")) {
      data = await response.json();
    } else {
      const text = await response.text();
      try {
        data = text ? JSON.parse(text) : null; // 혹시 JSON 문자열인 텍스트일 수 있음
      } catch {
        data = text || null; // 순수 텍스트면 그대로 보존
      }
    }
  } catch (parseError) {
    // 파싱 오류는 data=null 유지
  }
  return { ok: response.ok, status: response.status, data, error: response.ok ? null : (typeof data === "string" ? data : null) };
}

/**
 * @typedef {Object} AuthUser
 * @property {string} id
 * @property {string} [email]
 * @property {string} [name]
 * @property {string[]} [roles]
 */

/**
 * @typedef {Object} AuthConfig
 * @property {boolean} devLoginEnabled
 * @property {string} loginUrl
 * @property {string} frontendRedirect
 * @property {number | null | undefined} [sessionMaxAgeSeconds]
 */

/**
 * @typedef {Object} AuthContextValue
 * @property {AuthUser | null} user
 * @property {boolean} isLoading
 * @property {(options?: { next?: string }) => Promise<{ method: "dev" | "redirect"; url?: string; next?: string }>} login
 * @property {() => Promise<void>} logout
 * @property {() => Promise<void>} refresh
 * @property {AuthConfig} config
 */

// 기본 설정(백엔드가 내려주는 값으로 병합됨)
const DEFAULT_CONFIG = /** @type {AuthConfig} */ ({
  devLoginEnabled: false,
  loginUrl: "/oidc/authenticate/",
  frontendRedirect: "http://localhost:3000",
  sessionMaxAgeSeconds: 60 * 30,
});

// Context 생성: 초기값은 undefined로 두고, 훅에서 가드
/** @type {React.Context<AuthContextValue | undefined>} */
const AuthContext = createContext(undefined);

/** 안전한 next URL 생성 (절대/상대 경로 모두 지원) */
function buildNextUrl(nextPath, base) {
  if (!nextPath) return undefined;
  const trimmed = String(nextPath).trim();
  if (!trimmed) return undefined;

  const baseUrl = base && base.trim() ? base.trim() : (typeof window !== "undefined" ? window.location.origin : "");
  if (!baseUrl) return trimmed; // SSR 환경 등에서 base 가 없으면 원문 유지

  try {
    return new URL(trimmed, baseUrl).toString();
  } catch {
    if (trimmed.startsWith("/")) {
      return `${baseUrl.replace(/\/+$/, "")}${trimmed}`;
    }
    return trimmed;
  }
}

/** 로그인 URL에 next 파라미터를 안전하게 추가 */
function appendNextParam(url, nextUrl) {
  if (!nextUrl) return url;
  try {
    const u = new URL(url);
    u.searchParams.set("next", nextUrl);
    return u.toString();
  } catch {
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}next=${encodeURIComponent(nextUrl)}`;
  }
}

/**
 * AuthProvider: 앱 최상단에 배치하여 하위에서 useAuth() 사용
 * - 초기 마운트 시: 서버 config 및 현재 사용자(/auth/me) 로드
 * - window focus 시: 사용자 정보 재검증(신뢰도 ↑, UX 개선)
 */
export function AuthProvider({ children }) {
  /** @type {[AuthUser|null, React.Dispatch<React.SetStateAction<AuthUser|null>>]} */
  const [user, setUser] = useState(null);
  /** @type {[AuthConfig, React.Dispatch<React.SetStateAction<AuthConfig>>]} */
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [isLoading, setIsLoading] = useState(true);
  const mountedRef = useRef(false);
  const lastRefreshRef = useRef(0);

  const sessionRefreshIntervalMs = useMemo(() => {
    const rawSeconds = Number(config.sessionMaxAgeSeconds);
    if (!Number.isFinite(rawSeconds) || rawSeconds <= 0) {
      return 0;
    }
    const halfLifeMs = Math.floor(rawSeconds * 1000 * 0.5);
    return Math.max(60_000, halfLifeMs);
  }, [config.sessionMaxAgeSeconds]);

  const focusCooldownMs = useMemo(() => {
    if (sessionRefreshIntervalMs > 0) {
      return Math.max(30_000, Math.min(sessionRefreshIntervalMs / 2, 300_000));
    }
    return 30_000;
  }, [sessionRefreshIntervalMs]);

  // 컴포넌트 마운트/언마운트 추적 (언마운트 후 setState 방지)
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  /** 서버에서 Auth 설정 로드 (/auth/config) */
  const loadConfig = useCallback(async () => {
    try {
      const endpoint = buildBackendUrl("/auth/config");
      const result = await fetchJson(endpoint, { cache: "no-store" });
      if (result.ok && result.data) {
        if (!mountedRef.current) return;
        setConfig((prev) => ({ ...prev, ...(/** @type {Partial<AuthConfig>} */(result.data)) }));
      }
    } catch {
      // 설정 로드 실패 시 기본값 유지(조용히 무시)
    }
  }, []);

  /** 현재 사용자 정보 로드 (/auth/me) */
  const loadUser = useCallback(async () => {
    if (mountedRef.current) setIsLoading(true);
    try {
      const endpoint = buildBackendUrl("/auth/me");
      const result = await fetchJson(endpoint, { cache: "no-store" });
      if (!mountedRef.current) return;
      if (result.ok && result.data) {
        setUser(/** @type {AuthUser} */(result.data));
      } else {
        setUser(null);
      }
    } catch {
      if (mountedRef.current) setUser(null);
    } finally {
      if (mountedRef.current) setIsLoading(false);
      lastRefreshRef.current = Date.now();
    }
  }, []);

  // 최초 로드
  useEffect(() => {
    // 순서는 크게 중요하진 않지만, config 먼저 시도
    loadConfig();
    loadUser();
  }, [loadConfig, loadUser]);

  // UX 향상: 탭 포커스 복귀 시 사용자 정보 자동 새로고침(세션 만료/갱신 대응)
  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const onFocus = () => {
      const now = Date.now();
      if (now - lastRefreshRef.current < focusCooldownMs) {
        return;
      }
      lastRefreshRef.current = now;
      loadUser();
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [focusCooldownMs, loadUser]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    if (!sessionRefreshIntervalMs) return undefined;
    const timer = window.setInterval(() => {
      loadUser();
    }, sessionRefreshIntervalMs);
    return () => window.clearInterval(timer);
  }, [loadUser, sessionRefreshIntervalMs]);

  /** 로그인 함수 */
  const login = useCallback(
    async (options = {}) => {
      const nextPath = typeof options?.next === "string" ? options.next : undefined;
      const nextAbsolute = buildNextUrl(nextPath, config.frontendRedirect);

      // 1) 개발용 로그인 (백엔드가 dev-login 허용 시)
      if (config.devLoginEnabled) {
        try {
          const endpoint = buildBackendUrl("/auth/dev-login");
          const result = await fetchJson(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          });
          if (result.ok) {
            await loadUser();
            return { method: "dev", next: nextPath };
          }
        } catch {
          // 실패 시 리다이렉트 로그인으로 폴백
        }
      }

      // 2) OIDC 등 실제 로그인 페이지로 리다이렉트
      const rawLoginUrl = config.loginUrl || "/oidc/authenticate/";
      const absoluteLoginUrl = rawLoginUrl.startsWith("http")
        ? rawLoginUrl
        : buildBackendUrl(rawLoginUrl);
      const target = appendNextParam(absoluteLoginUrl, nextAbsolute);

      if (typeof window !== "undefined") {
        window.location.href = target; // 즉시 이동
      }
      return { method: "redirect", url: target };
    },
    [config, loadUser]
  );

  /** 로그아웃 함수 */
  const logout = useCallback(async () => {
    try {
      const endpoint = buildBackendUrl("/auth/logout");
      await fetchJson(endpoint, { method: "POST" });
    } finally {
      if (mountedRef.current) setUser(null);
    }
  }, []);

  /** Context value 메모이제이션 */
  const value = useMemo(
    () => ({
      user,
      isLoading,
      login,
      logout,
      refresh: loadUser,
      config,
    }),
    [user, isLoading, login, logout, loadUser, config]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * useAuth 훅: Provider 내부에서만 사용 가능
 * - 사용 예: const { user, login, logout, isLoading } = useAuth();
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    // 개발 단계에서 문제를 빨리 발견하기 위해 명확한 에러 메시지 제공
    throw new Error("useAuth는 AuthProvider 내부에서만 사용할 수 있습니다.");
  }
  return ctx;
}
