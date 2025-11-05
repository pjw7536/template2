module.exports = [
"[externals]/next/dist/compiled/next-server/app-route-turbo.runtime.dev.js [external] (next/dist/compiled/next-server/app-route-turbo.runtime.dev.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/compiled/next-server/app-route-turbo.runtime.dev.js", () => require("next/dist/compiled/next-server/app-route-turbo.runtime.dev.js"));

module.exports = mod;
}),
"[externals]/next/dist/compiled/@opentelemetry/api [external] (next/dist/compiled/@opentelemetry/api, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/compiled/@opentelemetry/api", () => require("next/dist/compiled/@opentelemetry/api"));

module.exports = mod;
}),
"[externals]/next/dist/compiled/next-server/app-page-turbo.runtime.dev.js [external] (next/dist/compiled/next-server/app-page-turbo.runtime.dev.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/compiled/next-server/app-page-turbo.runtime.dev.js", () => require("next/dist/compiled/next-server/app-page-turbo.runtime.dev.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/work-unit-async-storage.external.js [external] (next/dist/server/app-render/work-unit-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/server/app-render/work-unit-async-storage.external.js", () => require("next/dist/server/app-render/work-unit-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/work-async-storage.external.js [external] (next/dist/server/app-render/work-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/server/app-render/work-async-storage.external.js", () => require("next/dist/server/app-render/work-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/shared/lib/no-fallback-error.external.js [external] (next/dist/shared/lib/no-fallback-error.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/shared/lib/no-fallback-error.external.js", () => require("next/dist/shared/lib/no-fallback-error.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/after-task-async-storage.external.js [external] (next/dist/server/app-render/after-task-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/server/app-render/after-task-async-storage.external.js", () => require("next/dist/server/app-render/after-task-async-storage.external.js"));

module.exports = mod;
}),
"[project]/tailwind/src/lib/auth-session.js [app-route] (ecmascript)", ((__turbopack_context__) => {
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
"[project]/tailwind/src/app/api/auth/login/route.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/app/api/auth/login/route.js
__turbopack_context__.s([
    "POST",
    ()=>POST
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_react-dom@19.2.0_react@19.2.0__react@19.2.0/node_modules/next/server.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$auth$2d$session$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/auth-session.js [app-route] (ecmascript)");
;
;
async function POST(request) {
    let redirectTo = "/";
    try {
        const body = await request.json();
        if (body && typeof body.redirectTo === "string" && body.redirectTo.startsWith("/")) {
            redirectTo = body.redirectTo;
        }
    } catch  {
    // body가 없거나 JSON 파싱 실패 시 기본값 유지
    }
    const sessionValue = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$auth$2d$session$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["encodeUserSession"])(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$auth$2d$session$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["DUMMY_SSO_USER"]);
    const response = __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
        success: true,
        user: __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$auth$2d$session$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["DUMMY_SSO_USER"],
        redirectTo
    });
    response.cookies.set({
        name: __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$auth$2d$session$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["AUTH_COOKIE_NAME"],
        value: sessionValue,
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: ("TURBOPACK compile-time value", "development") === "production",
        maxAge: 60 * 60 * 24 * 7
    });
    return response;
}
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__e1cd24d2._.js.map