(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push(["chunks/[root-of-the-server]__fa7ac236._.js",
"[externals]/node:buffer [external] (node:buffer, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:buffer", () => require("node:buffer"));

module.exports = mod;
}),
"[externals]/node:async_hooks [external] (node:async_hooks, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("node:async_hooks", () => require("node:async_hooks"));

module.exports = mod;
}),
"[project]/tailwind/src/auth.js [middleware-edge] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "auth",
    ()=>auth,
    "authOptions",
    ()=>authOptions,
    "handlers",
    ()=>handlers,
    "signIn",
    ()=>signIn,
    "signOut",
    ()=>signOut
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$2d$auth$40$5$2e$0$2e$0$2d$beta$2e$30_next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$_fd9190ec192ec33eaed1abc30047308a$2f$node_modules$2f$next$2d$auth$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next-auth@5.0.0-beta.30_next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0._fd9190ec192ec33eaed1abc30047308a/node_modules/next-auth/index.js [middleware-edge] (ecmascript) <locals>");
(()=>{
    const e = new Error("Cannot find module 'next-auth/providers/oidc'");
    e.code = 'MODULE_NOT_FOUND';
    throw e;
})();
;
;
const defaultBaseUrl = process.env.NEXTAUTH_URL ?? "http://localhost:3000";
const fallbackIssuer = `${defaultBaseUrl.replace(/\/$/, "")}/api/mock-oidc`;
const authOptions = {
    trustHost: true,
    secret: process.env.AUTH_SECRET,
    session: {
        strategy: "jwt"
    },
    pages: {
        signIn: "/login"
    },
    providers: [
        OIDCProvider({
            id: "oidc",
            name: "SSO",
            issuer: process.env.AUTH_OIDC_ISSUER || fallbackIssuer,
            clientId: process.env.AUTH_OIDC_ID || "mock-client-id",
            clientSecret: process.env.AUTH_OIDC_SECRET || "mock-client-secret",
            profile (profile) {
                return {
                    id: profile.sub ?? "mock-user",
                    name: profile.name ?? profile.preferred_username ?? "Mock User",
                    email: profile.email ?? "mock.user@example.com",
                    image: profile.picture ?? null
                };
            }
        })
    ],
    callbacks: {
        async jwt ({ token, profile, account }) {
            if (profile) {
                token.sub = profile.sub ?? token.sub;
                token.name = profile.name ?? token.name;
                token.email = profile.email ?? token.email;
                token.picture = profile.picture ?? token.picture;
            }
            if (account?.id_token) {
                token.idToken = account.id_token;
            }
            return token;
        },
        async session ({ session, token }) {
            if (!session.user) {
                session.user = {};
            }
            session.user.id = token.sub ?? session.user.id;
            session.user.name = token.name ?? session.user.name;
            session.user.email = token.email ?? session.user.email;
            session.user.image = token.picture ?? session.user.image;
            return session;
        }
    }
};
const { auth, signIn, signOut, handlers } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$2d$auth$40$5$2e$0$2e$0$2d$beta$2e$30_next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$_fd9190ec192ec33eaed1abc30047308a$2f$node_modules$2f$next$2d$auth$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__$3c$locals$3e$__["default"])(authOptions);
}),
"[project]/tailwind/middleware.js [middleware-edge] (ecmascript)", ((__turbopack_context__) => {
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
    const { auth: session, nextUrl } = req;
    const { pathname } = nextUrl;
    const isPublic = PUBLIC_PATHS.some((path)=>pathname.startsWith(path));
    if (!session && !isPublic && !pathname.startsWith("/api/auth")) {
        const loginUrl = new URL("/login", nextUrl);
        loginUrl.searchParams.set("callbackUrl", nextUrl.pathname + nextUrl.search);
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].redirect(loginUrl);
    }
    if (session && pathname === "/login") {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$esm$2f$server$2f$web$2f$exports$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["NextResponse"].redirect(new URL("/", nextUrl));
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

//# sourceMappingURL=%5Broot-of-the-server%5D__fa7ac236._.js.map