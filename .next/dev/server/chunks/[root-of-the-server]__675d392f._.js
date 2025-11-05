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
"[project]/tailwind/src/app/api/mock-oidc/.well-known/openid-configuration/route.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/app/api/mock-oidc/.well-known/openid-configuration/route.js
__turbopack_context__.s([
    "GET",
    ()=>GET
]);
function getBaseUrl() {
    const envIssuer = process.env.AUTH_OIDC_ISSUER?.trim();
    if (envIssuer) return envIssuer.replace(/\/$/, "");
    const url = process.env.NEXTAUTH_URL?.replace(/\/$/, "");
    if (url) return `${url}/api/mock-oidc`;
    return "http://localhost:3000/api/mock-oidc";
}
function GET() {
    const issuer = getBaseUrl();
    const json = {
        issuer,
        authorization_endpoint: `${issuer}/authorize`,
        token_endpoint: `${issuer}/token`,
        userinfo_endpoint: `${issuer}/userinfo`,
        response_types_supported: [
            "code"
        ],
        grant_types_supported: [
            "authorization_code",
            "refresh_token"
        ],
        scopes_supported: [
            "openid",
            "profile",
            "email"
        ],
        id_token_signing_alg_values_supported: [
            "HS256"
        ],
        token_endpoint_auth_methods_supported: [
            "client_secret_basic",
            "client_secret_post"
        ]
    };
    return Response.json(json, {
        headers: {
            "Cache-Control": "no-store"
        }
    });
}
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__675d392f._.js.map