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
"[externals]/node:crypto [external] (node:crypto, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:crypto", () => require("node:crypto"));

module.exports = mod;
}),
"[project]/tailwind/src/app/api/mock-oidc/store.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/app/api/mock-oidc/store.js
__turbopack_context__.s([
    "consumeAuthCode",
    ()=>consumeAuthCode,
    "saveAuthCode",
    ()=>saveAuthCode
]);
const issuedCodes = new Map();
function saveAuthCode(code, payload) {
    if (!code) return;
    issuedCodes.set(code, {
        ...payload,
        createdAt: Date.now()
    });
}
function consumeAuthCode(code) {
    if (!code) return null;
    const payload = issuedCodes.get(code);
    issuedCodes.delete(code);
    return payload ?? null;
}
}),
"[project]/tailwind/src/app/api/mock-oidc/authorize/route.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/app/api/mock-oidc/authorize/route.js
__turbopack_context__.s([
    "GET",
    ()=>GET
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$node$3a$crypto__$5b$external$5d$__$28$node$3a$crypto$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/node:crypto [external] (node:crypto, cjs)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$app$2f$api$2f$mock$2d$oidc$2f$store$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/app/api/mock-oidc/store.js [app-route] (ecmascript)");
;
;
const DEFAULT_SCOPE = "openid profile email";
function GET(request) {
    const url = new URL(request.url);
    const redirectUri = url.searchParams.get("redirect_uri");
    const state = url.searchParams.get("state");
    const nonce = url.searchParams.get("nonce");
    const scope = url.searchParams.get("scope") || DEFAULT_SCOPE;
    const clientId = url.searchParams.get("client_id") || "demo-client";
    if (!redirectUri) {
        return Response.json({
            error: "invalid_request",
            error_description: "redirect_uri is required"
        }, {
            status: 400
        });
    }
    const code = __TURBOPACK__imported__module__$5b$externals$5d2f$node$3a$crypto__$5b$external$5d$__$28$node$3a$crypto$2c$__cjs$29$__["default"].randomUUID();
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$app$2f$api$2f$mock$2d$oidc$2f$store$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["saveAuthCode"])(code, {
        nonce,
        scope,
        clientId
    });
    const callbackUrl = new URL(redirectUri);
    callbackUrl.searchParams.set("code", code);
    if (state) {
        callbackUrl.searchParams.set("state", state);
    }
    return Response.redirect(callbackUrl.toString());
}
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__e8b26719._.js.map