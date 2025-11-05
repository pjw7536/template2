(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push(["chunks/[root-of-the-server]__4e791e82._.js",
"[externals]/node:buffer [external] (node:buffer, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:buffer", () => require("node:buffer"));

module.exports = mod;
}),
"[externals]/node:async_hooks [external] (node:async_hooks, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:async_hooks", () => require("node:async_hooks"));

module.exports = mod;
}),
"[project]/tailwind/src/auth.config.js [middleware-edge] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
(()=>{
    const e = new Error("Cannot find module 'next-auth/providers/oauth'");
    e.code = 'MODULE_NOT_FOUND';
    throw e;
})();
;
const issuer = process.env.AUTH_OIDC_ISSUER ?? `${process.env.NEXTAUTH_URL ?? "http://localhost:3000"}/api/mock-oidc`;
const clientId = process.env.AUTH_OIDC_ID ?? "demo-client-id";
const clientSecret = process.env.AUTH_OIDC_SECRET ?? "demo-client-secret";
/** @type {import("next-auth").NextAuthConfig} */ const authConfig = {
    trustHost: true,
    secret: process.env.NEXTAUTH_SECRET ?? "change-me-in-production",
    session: {
        strategy: "jwt"
    },
    providers: [
        OAuthProvider({
            id: "oidc",
            name: "OpenID Connect",
            type: "oauth",
            wellKnown: `${issuer}/.well-known/openid-configuration`,
            clientId,
            clientSecret,
            authorization: {
                params: {
                    scope: "openid profile email"
                }
            },
            checks: [
                "state"
            ],
            profile (profile) {
                return {
                    id: profile.sub ?? "sandbox-user",
                    name: profile.name ?? profile.preferred_username ?? "Sandbox User",
                    email: profile.email ?? "sandbox@example.com",
                    image: profile.picture ?? null
                };
            }
        })
    ],
    callbacks: {
        authorized ({ auth, request }) {
            const isLoggedIn = !!auth?.user;
            const isAuthRoute = request.nextUrl.pathname.startsWith("/login");
            if (isAuthRoute) {
                return true;
            }
            return isLoggedIn;
        },
        async jwt ({ token, account, profile }) {
            if (account?.provider === "oidc" && profile) {
                token.id = profile.sub ?? token.id;
            }
            return token;
        },
        async session ({ session, token }) {
            if (token?.id) {
                session.user = session.user ?? {};
                session.user.id = token.id;
            }
            return session;
        }
    }
};
const __TURBOPACK__default__export__ = authConfig;
}),
"[project]/tailwind/src/auth.js [middleware-edge] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "GET",
    ()=>GET,
    "POST",
    ()=>POST,
    "auth",
    ()=>auth,
    "handlers",
    ()=>handlers,
    "signIn",
    ()=>signIn,
    "signOut",
    ()=>signOut
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$2d$auth$40$5$2e$0$2e$0$2d$beta$2e$30_next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$_fd9190ec192ec33eaed1abc30047308a$2f$node_modules$2f$next$2d$auth$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next-auth@5.0.0-beta.30_next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0._fd9190ec192ec33eaed1abc30047308a/node_modules/next-auth/index.js [middleware-edge] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$auth$2e$config$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/auth.config.js [middleware-edge] (ecmascript)");
;
;
const { auth, handlers, signIn, signOut } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$2d$auth$40$5$2e$0$2e$0$2d$beta$2e$30_next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$_fd9190ec192ec33eaed1abc30047308a$2f$node_modules$2f$next$2d$auth$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__$3c$locals$3e$__["default"])(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$auth$2e$config$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["default"]);
const { GET, POST } = handlers;
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
    "/login"
];
const API_PATHS = [
    "/api/auth",
    "/api/mock-oidc"
];
const __TURBOPACK__default__export__ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$auth$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["auth"])((request)=>{
    const { nextUrl } = request;
    const { pathname } = nextUrl;
    const isPublicRoute = PUBLIC_PATHS.some((path)=>pathname === path) || pathname.startsWith("/_next") || pathname.startsWith("/favicon") || pathname.startsWith("/images") || pathname.startsWith("/public");
    const isAuthApi = API_PATHS.some((path)=>pathname.startsWith(path));
    if (isAuthApi) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].next();
    }
    if (!request.auth && !isPublicRoute) {
        const loginUrl = new URL("/login", nextUrl.origin);
        if (pathname && pathname !== "/") {
            loginUrl.searchParams.set("callbackUrl", `${pathname}${nextUrl.search}`);
        }
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].redirect(loginUrl);
    }
    if (request.auth && pathname === "/login") {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].redirect(new URL("/", nextUrl.origin));
    }
    return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].next();
});
const config = {
    matcher: [
        "/((?!api/mock-oidc|api/auth|_next/static|_next/image|favicon.ico).*)"
    ]
};
}),
]);

//# sourceMappingURL=%5Broot-of-the-server%5D__4e791e82._.js.map