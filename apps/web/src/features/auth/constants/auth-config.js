// src/features/auth/constants/auth-config.js
// 인증 기능에서 공통으로 사용하는 기본 설정 값입니다.
// - 로그인/로그아웃 엔드포인트와 세션 만료 시간 등의 초기값을 정의합니다.

/**
 * @typedef {Object} AuthConfig
 * @property {string} loginUrl
 * @property {string} logoutUrl
 * @property {string} frontendRedirect
 * @property {number | null | undefined} [sessionMaxAgeSeconds]
 * @property {boolean | undefined} [providerConfigured]
 */

/**
 * 서버 응답과 병합될 기본 인증 설정.
 * 초보자 Tip: "config" 상태는 서버에서 받아온 값을 덮어쓰는데,
 *             서버에서 내려주지 않는 속성은 여기 값이 그대로 사용됩니다.
 * @type {AuthConfig}
 */
export const DEFAULT_AUTH_CONFIG = {
  loginUrl: "/auth/login",
  logoutUrl: "/auth/logout",
  frontendRedirect: "",
  sessionMaxAgeSeconds: 60 * 30,
}
