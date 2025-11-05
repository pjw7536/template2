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
"[project]/tailwind/src/app/api/mock-oidc/mock-keys.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// Shared RSA key pair used by the mock OIDC implementation. The public
// portion is served through the JWKS endpoint while the private portion is
// used to sign the id_token that NextAuth consumes.
__turbopack_context__.s([
    "MOCK_JWT_ALG",
    ()=>MOCK_JWT_ALG,
    "MOCK_JWT_KID",
    ()=>MOCK_JWT_KID,
    "privateJwk",
    ()=>privateJwk,
    "publicJwk",
    ()=>publicJwk
]);
const MOCK_JWT_KID = "mock-key";
const MOCK_JWT_ALG = "RS256";
const publicJwk = {
    kty: "RSA",
    n: "oma7G9Ls5H5vjY0f3kzESb0_5Bbsd-GTp-Uy1C9OgN2NN-tJnTEj6Y4DdsT8-plLCTFu5uEe6PEUFJEQqVqVkxn3Fr5U-dnbBPsEUSbD4XCifNF5yjt2-x3_8_01xCyb_df960LZEXUZq5Zjuy5JctvDUwjlVCxWkG2OXNhVOLKj8aQiuqlDSupYP-gSZzIi59NLRLDJGx5iaTVRoL38Yk2aVJEv5VQtRZq2QQMWawi1JWnQHADE2Ss6k_haTraFrjOXaAlQ_oOGiBeJ0SJgjkkzb0n69G2Id2MhSBOLM2DFgfkuydAy8sUQnQsqIgnHxHTBggFnsUax33Soktf-eQ",
    e: "AQAB",
    kid: MOCK_JWT_KID,
    use: "sig",
    alg: MOCK_JWT_ALG
};
const privateJwk = {
    ...publicJwk,
    d: "Ox9xUPDaI1lQXVUaXADQmRPX1b7uuboa2k3b0lmil9GQnuH-u8ZvD5EO-8c9XjI-mgswF8evTBiwOciSK0V6HMKgLNx_7TH9xXNpH-4f88vgq9ZLI2_Aoi1KyFXPpCqlY6WloGeGxQ8_mDM4_aUdQj51fp5HdvxpS01HPc_YPrpdZ7QX6O4PrHONJKVSs_PMDDVurQpvvJehwdndTUhXc9wglF7f9MxFQ1k47Nv6_JdwZXzFNY2gU3J6d96ZG5VKjnRjeQzTVTpes6S66DDGPYpSja-Sx_DTTH1iYPucVoR4HJzHi6cqSeQCOk4jQra7RjF9L0u-3wfJaJl8CJSiHQ",
    p: "3jtde7gqfWJEUsiGV8vdXpVY3eTlLftJVRtU2z5aChMZ7IHJIZNdSvgrpsc9Z_8gMUX2PIJHCD4D1xIpU2H53uyqklgEYqsysdR_hsTi2oVWysS3wUdAYYyLwBTVTTKVV9Qs4hlGAyMH1kVEBoIVmg32PZWJl_eFrUsi8vrU9g8",
    q: "uxQBXTXpibLsJ7ElPen2uJV1aC_KGG-twYwc9zFexxPGSPK1TAI9gZmIzw28Xp5a0Zw_4lTisX1DVGrYrxxk3AVed2-_GRJvuPGTHP49EpR4TccOpFW-hrVxZ-86R40ZK0sYvzw7n981TYC1MWoBRNjPcgdju_7_FaKtOhgeCvc",
    dp: "whuCRN0Qp-HcIZ6q0SbtHX8_VtlmYGpbnC26SaHFjYUvoIegQWZxF1l67zqZ5StPWBpuwF1eY9GfEwz28bDjSpbXSen9Mp2sMu2T0ghIyWur6oI2qmhs0IetTUIlKT-keEmIRpiisXy4jKyFhVW8PooxaYsi2ozFwx6c0TTMLHs",
    dq: "FRkRelCdMOFTzrokqBHduD1qy0Awe4cEwoIpthsERFFPmGR-276Y7yfAjRFQgB89wMvtTHokQr4MvNV78Gu0WDfmynN4yrwQi3v7ClcFzjWeR68-UHw3C3wk-QK6wN0BzKcgeFizpLkIiuAMDzGUSQ5mfsakkcwVOnxpKtcTdEs",
    qi: "Uf9qsNjuSZ2COsxoSEhHb594GpwnD-ew1fcpPGzliVv2FlkSsQrsNqGCoR2pOBpVdylgEQOr04VnXSwQtV01hbvp0ZDL0dcjvvnwziJrRzpiiItwvnVdfdr0qyjfD1plQgK0FUqj_uAV0ze7k31jLsRJ6p15TrYzH9JsdgFmLYs"
};
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
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_react-dom@19.2.0_react@19.2.0__react@19.2.0/node_modules/next/server.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$jose$40$6$2e$1$2e$0$2f$node_modules$2f$jose$2f$dist$2f$webapi$2f$jwt$2f$sign$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/jose@6.1.0/node_modules/jose/dist/webapi/jwt/sign.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$jose$40$6$2e$1$2e$0$2f$node_modules$2f$jose$2f$dist$2f$webapi$2f$key$2f$import$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/jose@6.1.0/node_modules/jose/dist/webapi/key/import.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$app$2f$api$2f$mock$2d$oidc$2f$mock$2d$keys$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/app/api/mock-oidc/mock-keys.js [app-route] (ecmascript)");
;
;
;
let signingKeyPromise;
function buildIssuer(request) {
    const url = new URL(request.url);
    const basePath = url.pathname.replace(/\/token$/, "");
    return `${url.origin}${basePath.replace(/\/$/, "")}`;
}
async function getSigningKey() {
    if (!signingKeyPromise) {
        signingKeyPromise = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$jose$40$6$2e$1$2e$0$2f$node_modules$2f$jose$2f$dist$2f$webapi$2f$key$2f$import$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["importJWK"])(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$app$2f$api$2f$mock$2d$oidc$2f$mock$2d$keys$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["privateJwk"], __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$app$2f$api$2f$mock$2d$oidc$2f$mock$2d$keys$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["MOCK_JWT_ALG"]);
    }
    return signingKeyPromise;
}
async function createIdToken({ request, clientId }) {
    const issuer = buildIssuer(request);
    const subject = "mock-user";
    const jwt = await new __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$jose$40$6$2e$1$2e$0$2f$node_modules$2f$jose$2f$dist$2f$webapi$2f$jwt$2f$sign$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["SignJWT"]({
        name: "Demo User",
        preferred_username: "demo.user",
        email: "demo.user@example.com",
        picture: "https://avatars.dicebear.com/api/initials/Demo%20User.svg"
    }).setProtectedHeader({
        alg: __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$app$2f$api$2f$mock$2d$oidc$2f$mock$2d$keys$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["MOCK_JWT_ALG"],
        kid: __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$app$2f$api$2f$mock$2d$oidc$2f$mock$2d$keys$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["MOCK_JWT_KID"],
        typ: "JWT"
    }).setIssuer(issuer).setSubject(subject).setAudience(clientId).setIssuedAt().setExpirationTime("1h").sign(await getSigningKey());
    return jwt;
}
async function handle(request) {
    const url = new URL(request.url);
    let clientId = url.searchParams.get("client_id") || "";
    if (!clientId && request.method === "POST") {
        try {
            const formData = await request.formData();
            clientId = formData.get("client_id") || "";
        } catch (error) {
        // no-op, fall back to defaults
        }
    }
    if (!clientId) {
        clientId = "demo-client";
    }
    const accessToken = `mock-access-token-${Date.now()}`;
    const idToken = await createIdToken({
        request,
        clientId
    });
    return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
        access_token: accessToken,
        token_type: "Bearer",
        expires_in: 3600,
        refresh_token: `mock-refresh-token-${Date.now()}`,
        id_token: idToken
    });
}
const POST = handle;
const GET = handle;
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__869bde52._.js.map