(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push(["chunks/[root-of-the-server]__59a50805._.js",
"[externals]/node:buffer [external] (node:buffer, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:buffer", () => require("node:buffer"));

module.exports = mod;
}),
"[externals]/node:async_hooks [external] (node:async_hooks, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:async_hooks", () => require("node:async_hooks"));

module.exports = mod;
}),
"[project]/tailwind/src/lib/auth-session.js [middleware-edge] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/lib/auth-session.js
// 간단한 세션 인코딩/디코딩 유틸리티 (추후 실제 인증 연동 시 교체 용이)
__turbopack_context__.s([
    "AUTH_COOKIE_NAME",
    ()=>AUTH_COOKIE_NAME,
    "DUMMY_SSO_USER",
    ()=>DUMMY_SSO_USER,
    "decodeUserSession",
    ()=>decodeUserSession,
    "encodeUserSession",
    ()=>encodeUserSession,
    "getSessionUserFromCookies",
    ()=>getSessionUserFromCookies
]);
const AUTH_SESSION_COOKIE = "app_session_v1";
function encodeUserSession(user) {
    if (!user || typeof user !== "object") return "";
    try {
        const payload = JSON.stringify({
            user
        });
        return encodeURIComponent(payload);
    } catch  {
        return "";
    }
}
function decodeUserSession(value) {
    if (!value || typeof value !== "string") return null;
    try {
        const decoded = decodeURIComponent(value);
        const parsed = JSON.parse(decoded);
        if (parsed && typeof parsed === "object" && parsed.user && typeof parsed.user === "object") {
            const { name = "", email = "", avatar = "" } = parsed.user;
            if (!name && !email) return null;
            return {
                name,
                email,
                avatar
            };
        }
    } catch  {
        return null;
    }
    return null;
}
function getSessionUserFromCookies(cookieStore) {
    if (!cookieStore || typeof cookieStore.get !== "function") return null;
    const stored = cookieStore.get(AUTH_SESSION_COOKIE);
    if (!stored || !stored.value) return null;
    return decodeUserSession(stored.value);
}
const AUTH_COOKIE_NAME = AUTH_SESSION_COOKIE;
const DUMMY_SSO_USER = Object.freeze({
    name: "Demo SSO User",
    email: "sso.user@example.com",
    avatar: "https://www.gravatar.com/avatar/?d=mp"
});
}),
"[project]/tailwind/middleware.js [middleware-edge] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "config",
    ()=>config,
    "middleware",
    ()=>middleware
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$api$2f$server$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_react-dom@19.2.0_react@19.2.0__react@19.2.0/node_modules/next/dist/esm/api/server.js [middleware-edge] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_react-dom@19.2.0_react@19.2.0__react@19.2.0/node_modules/next/dist/esm/server/web/exports/index.js [middleware-edge] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$auth$2d$session$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/auth-session.js [middleware-edge] (ecmascript)");
;
;
const PUBLIC_PATHS = new Set([
    "/login"
]);
const STATIC_EXTENSION_REGEX = /\.[a-zA-Z0-9]+$/;
function isPublicPath(pathname) {
    return PUBLIC_PATHS.has(pathname);
}
function resolveRedirectTarget(request, fallback = "/") {
    const candidate = request.nextUrl.searchParams.get("redirectTo");
    if (candidate && candidate.startsWith("/")) {
        try {
            const targetUrl = new URL(candidate, request.nextUrl.origin);
            return {
                pathname: targetUrl.pathname,
                search: targetUrl.search
            };
        } catch  {
            return {
                pathname: fallback,
                search: ""
            };
        }
    }
    return {
        pathname: fallback,
        search: ""
    };
}
function middleware(request) {
    const { pathname } = request.nextUrl;
    if (pathname.startsWith("/_next") || pathname.startsWith("/favicon")) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].next();
    }
    if (pathname.startsWith("/api")) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].next();
    }
    if (STATIC_EXTENSION_REGEX.test(pathname)) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].next();
    }
    const sessionCookie = request.cookies.get(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$auth$2d$session$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["AUTH_COOKIE_NAME"]);
    if (isPublicPath(pathname)) {
        if (sessionCookie) {
            const redirectUrl = request.nextUrl.clone();
            const target = resolveRedirectTarget(request);
            redirectUrl.pathname = target.pathname;
            redirectUrl.search = target.search;
            return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].redirect(redirectUrl);
        }
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].next();
    }
    if (!sessionCookie) {
        const loginUrl = request.nextUrl.clone();
        loginUrl.pathname = "/login";
        const search = request.nextUrl.search ?? "";
        loginUrl.searchParams.set("redirectTo", `${pathname}${search}`);
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].redirect(loginUrl);
    }
    return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].next();
}
const config = {
    matcher: [
        "/((?!_next/static|_next/image|favicon.ico).*)"
    ]
};
}),
]);

//# sourceMappingURL=%5Broot-of-the-server%5D__59a50805._.js.map