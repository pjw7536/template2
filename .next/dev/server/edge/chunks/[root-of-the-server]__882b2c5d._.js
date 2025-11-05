(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push(["chunks/[root-of-the-server]__882b2c5d._.js",
"[externals]/node:buffer [external] (node:buffer, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:buffer", () => require("node:buffer"));

module.exports = mod;
}),
"[externals]/node:async_hooks [external] (node:async_hooks, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:async_hooks", () => require("node:async_hooks"));

module.exports = mod;
}),
"[externals]/node:util [external] (node:util, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:util", () => require("node:util"));

module.exports = mod;
}),
"[project]/ [middleware-edge] (unsupported edge import 'http', ecmascript)", ((__turbopack_context__, module, exports) => {

__turbopack_context__.n(__import_unsupported(`http`));
}),
"[project]/ [middleware-edge] (unsupported edge import 'crypto', ecmascript)", ((__turbopack_context__, module, exports) => {

__turbopack_context__.n(__import_unsupported(`crypto`));
}),
"[externals]/node:assert [external] (node:assert, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:assert", () => require("node:assert"));

module.exports = mod;
}),
"[project]/ [middleware-edge] (unsupported edge import 'querystring', ecmascript)", ((__turbopack_context__, module, exports) => {

__turbopack_context__.n(__import_unsupported(`querystring`));
}),
"[project]/ [middleware-edge] (unsupported edge import 'https', ecmascript)", ((__turbopack_context__, module, exports) => {

__turbopack_context__.n(__import_unsupported(`https`));
}),
"[externals]/node:events [external] (node:events, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:events", () => require("node:events"));

module.exports = mod;
}),
"[project]/tailwind/src/lib/auth.js [middleware-edge] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/lib/auth.js
__turbopack_context__.s([
    "GET",
    ()=>GET,
    "POST",
    ()=>POST,
    "auth",
    ()=>auth,
    "authOptions",
    ()=>authOptions,
    "signIn",
    ()=>signIn,
    "signOut",
    ()=>signOut
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$2d$auth$40$4$2e$24$2e$13_next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_reac_8f9846f6a87b9d618d7a1404ae6a854b$2f$node_modules$2f$next$2d$auth$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next-auth@4.24.13_next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_reac_8f9846f6a87b9d618d7a1404ae6a854b/node_modules/next-auth/index.js [middleware-edge] (ecmascript)");
(()=>{
    const e = new Error("Cannot find module 'next-auth/providers/oidc'");
    e.code = 'MODULE_NOT_FOUND';
    throw e;
})();
;
;
function resolveAppUrl() {
    const explicitUrl = process.env.NEXTAUTH_URL || process.env.NEXT_PUBLIC_APP_URL;
    if (explicitUrl) {
        return explicitUrl.replace(/\/$/, "");
    }
    return "http://localhost:3000";
}
function resolveIssuer() {
    if (process.env.AUTH_OIDC_ISSUER) {
        return process.env.AUTH_OIDC_ISSUER.replace(/\/$/, "");
    }
    return `${resolveAppUrl()}/api/mock-oidc`;
}
const authOptions = {
    providers: [
        OIDCProvider({
            clientId: process.env.AUTH_OIDC_ID || "demo-client-id",
            clientSecret: process.env.AUTH_OIDC_SECRET || "demo-client-secret",
            issuer: resolveIssuer(),
            authorization: {
                params: {
                    scope: "openid profile email"
                }
            },
            profile (profile) {
                return {
                    id: profile.sub || "demo-user",
                    name: profile.name || profile.preferred_username || "Demo User",
                    email: profile.email || "demo@example.com",
                    image: profile.picture || null
                };
            }
        })
    ],
    session: {
        strategy: "jwt"
    },
    pages: {
        signIn: "/login"
    },
    callbacks: {
        jwt ({ token, profile }) {
            if (profile?.sub) {
                token.sub = profile.sub;
            }
            return token;
        },
        session ({ session, token }) {
            if (session.user && token?.sub) {
                session.user.id = token.sub;
            }
            return session;
        }
    },
    secret: process.env.NEXTAUTH_SECRET || "development-secret"
};
const { handlers, auth, signIn, signOut } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$2d$auth$40$4$2e$24$2e$13_next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_reac_8f9846f6a87b9d618d7a1404ae6a854b$2f$node_modules$2f$next$2d$auth$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["default"])(authOptions);
const { GET, POST } = handlers;
;
}),
"[project]/tailwind/middleware.js [middleware-edge] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

// middleware.js
__turbopack_context__.s([
    "config",
    ()=>config
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$auth$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/auth.js [middleware-edge] (ecmascript)");
;
const config = {
    matcher: [
        "/((?!api|_next/static|_next/image|favicon.ico|login).*)"
    ]
};
}),
"[project]/tailwind/middleware.js [middleware-edge] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "config",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$middleware$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__$3c$locals$3e$__["config"],
    "middleware",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$auth$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["auth"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$middleware$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/middleware.js [middleware-edge] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$auth$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/auth.js [middleware-edge] (ecmascript)");
}),
]);

//# sourceMappingURL=%5Broot-of-the-server%5D__882b2c5d._.js.map