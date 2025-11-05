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
"[project]/tailwind/src/app/api/mock-oidc/token/route.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/app/api/mock-oidc/token/route.js
__turbopack_context__.s([
    "GET",
    ()=>GET,
    "POST",
    ()=>POST
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$node$3a$crypto__$5b$external$5d$__$28$node$3a$crypto$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/node:crypto [external] (node:crypto, cjs)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$app$2f$api$2f$mock$2d$oidc$2f$store$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/app/api/mock-oidc/store.js [app-route] (ecmascript)");
;
;
const DEFAULT_USER = {
    sub: "demo-user",
    name: "Demo User",
    preferred_username: "demo",
    email: "demo.user@example.com",
    picture: "https://avatars.githubusercontent.com/u/9919?v=4"
};
const DEFAULT_SCOPE = "openid profile email";
function resolveIssuer() {
    const envIssuer = process.env.AUTH_OIDC_ISSUER?.trim();
    if (envIssuer) return envIssuer.replace(/\/$/, "");
    const url = process.env.NEXTAUTH_URL?.replace(/\/$/, "");
    if (url) return `${url}/api/mock-oidc`;
    return "http://localhost:3000/api/mock-oidc";
}
async function parseBody(request) {
    const contentType = request.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
        return request.json();
    }
    const formData = await request.formData();
    const result = {};
    for (const [key, value] of formData.entries()){
        result[key] = value;
    }
    return result;
}
function base64UrlEncode(input) {
    const buffer = typeof input === "string" || input instanceof Buffer ? Buffer.from(input) : Buffer.from(JSON.stringify(input));
    return buffer.toString("base64").replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}
function createIdToken({ issuer, audience, nonce, now, clientSecret }) {
    const payload = {
        iss: issuer,
        aud: audience,
        sub: DEFAULT_USER.sub,
        name: DEFAULT_USER.name,
        email: DEFAULT_USER.email,
        email_verified: true,
        preferred_username: DEFAULT_USER.preferred_username,
        picture: DEFAULT_USER.picture,
        iat: now,
        exp: now + 3600,
        auth_time: now
    };
    if (nonce) {
        payload.nonce = nonce;
    }
    const headerSegment = base64UrlEncode({
        alg: "HS256",
        typ: "JWT"
    });
    const payloadSegment = base64UrlEncode(payload);
    const signingInput = `${headerSegment}.${payloadSegment}`;
    const signature = __TURBOPACK__imported__module__$5b$externals$5d2f$node$3a$crypto__$5b$external$5d$__$28$node$3a$crypto$2c$__cjs$29$__["default"].createHmac("sha256", clientSecret).update(signingInput).digest("base64");
    const signatureSegment = signature.replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
    return `${signingInput}.${signatureSegment}`;
}
function parseClientCredentials(request, body, fallbackClientId) {
    const defaultClientId = process.env.AUTH_OIDC_ID ?? "demo-client";
    const defaultClientSecret = process.env.AUTH_OIDC_SECRET ?? "demo-secret";
    const header = request.headers.get("authorization") || "";
    if (header.startsWith("Basic ")) {
        const encoded = header.slice("Basic ".length);
        const decoded = Buffer.from(encoded, "base64").toString("utf8");
        const separatorIndex = decoded.indexOf(":");
        if (separatorIndex >= 0) {
            const clientId = decoded.slice(0, separatorIndex) || defaultClientId;
            const clientSecret = decoded.slice(separatorIndex + 1) || defaultClientSecret;
            return {
                clientId,
                clientSecret
            };
        }
    }
    return {
        clientId: body.client_id || fallbackClientId || defaultClientId,
        clientSecret: body.client_secret || defaultClientSecret
    };
}
async function POST(request) {
    const body = await parseBody(request);
    const issuedCode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$app$2f$api$2f$mock$2d$oidc$2f$store$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["consumeAuthCode"])(body.code);
    const { clientId, clientSecret } = parseClientCredentials(request, body, issuedCode?.clientId);
    const issuer = resolveIssuer();
    const now = Math.floor(Date.now() / 1000);
    const idToken = createIdToken({
        issuer,
        audience: clientId,
        nonce: issuedCode?.nonce || null,
        now,
        clientSecret
    });
    return Response.json({
        access_token: "mock-access-token",
        token_type: "Bearer",
        expires_in: 3600,
        refresh_token: "mock-refresh-token",
        scope: issuedCode?.scope || body.scope || DEFAULT_SCOPE,
        issued_at: now,
        id_token: idToken
    });
}
const GET = POST;
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__fe2fd1d0._.js.map