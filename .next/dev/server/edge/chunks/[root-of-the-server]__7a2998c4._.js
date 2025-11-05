(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push(["chunks/[root-of-the-server]__7a2998c4._.js",
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
"[project]/tailwind/src/auth.js [middleware-edge] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "auth",
    ()=>auth,
    "authConfig",
    ()=>authConfig,
    "handlers",
    ()=>handlers,
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
const appUrl = process.env.AUTH_BASE_URL || process.env.NEXTAUTH_URL || (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");
const issuer = process.env.AUTH_OIDC_ISSUER || `${appUrl}/api/mock-oidc`;
const authConfig = {
    providers: [
        OIDC({
            id: "oidc",
            name: "Single Sign-On",
            clientId: process.env.AUTH_OIDC_ID || "demo-client-id",
            clientSecret: process.env.AUTH_OIDC_SECRET || "demo-client-secret",
            issuer,
            checks: [
                "none"
            ],
            authorization: {
                params: {
                    scope: "openid profile email"
                }
            },
            profile (profile) {
                const fallbackName = profile.name || profile.preferred_username || "Demo User";
                return {
                    id: profile.sub || profile.id || "demo-user",
                    name: fallbackName,
                    email: profile.email || `${fallbackName.replace(/\s+/g, ".").toLowerCase()}@example.com`,
                    image: profile.picture || null
                };
            }
        })
    ],
    pages: {
        signIn: "/login"
    },
    session: {
        strategy: "jwt"
    },
    callbacks: {
        async jwt ({ token, profile }) {
            if (profile) {
                token.sub = profile.sub || token.sub;
                token.name = profile.name || token.name;
                token.email = profile.email || token.email;
                token.picture = profile.picture || token.picture;
            }
            return token;
        },
        async session ({ session, token }) {
            if (token && session.user) {
                session.user.id = token.sub;
                session.user.name = token.name || session.user.name;
                session.user.email = token.email || session.user.email;
                session.user.image = token.picture || session.user.image;
            }
            return session;
        }
    },
    trustHost: true
};
const { handlers, auth, signIn, signOut } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$2d$auth$40$4$2e$24$2e$13_next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_reac_8f9846f6a87b9d618d7a1404ae6a854b$2f$node_modules$2f$next$2d$auth$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["default"])(authConfig);
}),
"[project]/tailwind/src/middleware.js [middleware-edge] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "config",
    ()=>config,
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$api$2f$server$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_react-dom@19.2.0_react@19.2.0__react@19.2.0/node_modules/next/dist/esm/api/server.js [middleware-edge] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_react-dom@19.2.0_react@19.2.0__react@19.2.0/node_modules/next/dist/esm/server/web/exports/index.js [middleware-edge] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$auth$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/auth.js [middleware-edge] (ecmascript)");
;
;
const PUBLIC_PATHS = [
    "/login",
    "/api/mock-oidc"
];
const __TURBOPACK__default__export__ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$auth$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["auth"])((req)=>{
    const { nextUrl } = req;
    const isLoggedIn = Boolean(req.auth);
    const pathname = nextUrl.pathname;
    const isPublicRoute = PUBLIC_PATHS.some((route)=>pathname === route || pathname.startsWith(`${route}/`)) || pathname.startsWith("/api/auth") || pathname.startsWith("/api/health") || pathname.startsWith("/favicon") || pathname.startsWith("/assets") || pathname.startsWith("/_next");
    if (!isLoggedIn && !isPublicRoute) {
        const loginUrl = new URL("/login", nextUrl.origin);
        loginUrl.searchParams.set("callbackUrl", nextUrl.pathname + nextUrl.search);
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].redirect(loginUrl);
    }
    if (isLoggedIn && pathname === "/login") {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].redirect(new URL("/", nextUrl.origin));
    }
    return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].next();
});
const config = {
    matcher: [
        "/((?!_next/static|_next/image|favicon.ico).*)"
    ]
};
}),
]);

//# sourceMappingURL=%5Broot-of-the-server%5D__7a2998c4._.js.map