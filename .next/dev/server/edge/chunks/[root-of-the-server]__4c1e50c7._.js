(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push(["chunks/[root-of-the-server]__4c1e50c7._.js",
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
    "handlers",
    ()=>handlers,
    "signIn",
    ()=>signIn,
    "signOut",
    ()=>signOut
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$2d$auth$40$4$2e$24$2e$13_next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_reac_8f9846f6a87b9d618d7a1404ae6a854b$2f$node_modules$2f$next$2d$auth$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next-auth@4.24.13_next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_reac_8f9846f6a87b9d618d7a1404ae6a854b/node_modules/next-auth/index.js [middleware-edge] (ecmascript)");
;
const providerName = process.env.OPENID_PROVIDER_NAME ?? "Single Sign-On";
const openIdScope = process.env.OPENID_SCOPE ?? "openid profile email";
const openIdPrompt = process.env.OPENID_PROMPT;
function assertEnv(value, message) {
    if (!value) {
        throw new Error(message);
    }
}
const { OPENID_WELL_KNOWN, OPENID_ISSUER, OPENID_CLIENT_ID, OPENID_CLIENT_SECRET, NEXTAUTH_SECRET } = process.env;
assertEnv(OPENID_WELL_KNOWN || OPENID_ISSUER, "Set either OPENID_WELL_KNOWN or OPENID_ISSUER in your environment to configure the OpenID provider.");
assertEnv(OPENID_CLIENT_ID, "Set OPENID_CLIENT_ID in your environment to configure the OpenID provider.");
assertEnv(OPENID_CLIENT_SECRET, "Set OPENID_CLIENT_SECRET in your environment to configure the OpenID provider.");
assertEnv(NEXTAUTH_SECRET, "Set NEXTAUTH_SECRET in your environment so Auth.js can encrypt sessions.");
const { handlers, auth, signIn, signOut } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$2d$auth$40$4$2e$24$2e$13_next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_reac_8f9846f6a87b9d618d7a1404ae6a854b$2f$node_modules$2f$next$2d$auth$2f$index$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["default"])({
    providers: [
        {
            id: "oidc",
            name: providerName,
            type: "oidc",
            wellKnown: OPENID_WELL_KNOWN,
            issuer: OPENID_ISSUER,
            clientId: OPENID_CLIENT_ID,
            clientSecret: OPENID_CLIENT_SECRET,
            authorization: {
                params: {
                    scope: openIdScope,
                    ...openIdPrompt ? {
                        prompt: openIdPrompt
                    } : {}
                }
            },
            profile (profile) {
                const fallbackName = [
                    profile.given_name,
                    profile.family_name
                ].filter(Boolean).join(" ");
                return {
                    id: profile.sub ?? profile.id ?? profile.user_id,
                    name: profile.name ?? fallbackName ?? "",
                    email: profile.email ?? null,
                    image: profile.picture ?? null
                };
            }
        }
    ],
    session: {
        strategy: "jwt"
    },
    pages: {
        signIn: "/auth/signin"
    },
    trustHost: true,
    secret: NEXTAUTH_SECRET,
    callbacks: {
        authorized ({ request, auth }) {
            const isLoggedIn = !!auth?.user;
            const pathname = request.nextUrl.pathname;
            if (pathname.startsWith("/auth/signin")) {
                return true;
            }
            return isLoggedIn;
        },
        jwt ({ token, account, profile }) {
            if (account) {
                token.accessToken = account.access_token;
                token.id = profile?.sub ?? profile?.id ?? token.sub;
            }
            if (!token.id && token.sub) {
                token.id = token.sub;
            }
            return token;
        },
        session ({ session, token }) {
            if (session.user) {
                session.user.id = token.id;
            }
            if (token.accessToken) {
                session.accessToken = token.accessToken;
            }
            return session;
        }
    }
});
;
}),
"[project]/tailwind/src/middleware.js [middleware-edge] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "config",
    ()=>config
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$auth$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/auth.js [middleware-edge] (ecmascript)");
;
const config = {
    matcher: [
        "/((?!api/auth|auth/signin|_next/static|_next/image|favicon.ico|.*\\..*).*)"
    ]
};
}),
"[project]/tailwind/src/middleware.js [middleware-edge] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "config",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$middleware$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__$3c$locals$3e$__["config"],
    "middleware",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$auth$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__["auth"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$middleware$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/src/middleware.js [middleware-edge] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$auth$2e$js__$5b$middleware$2d$edge$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/auth.js [middleware-edge] (ecmascript)");
}),
]);

//# sourceMappingURL=%5Broot-of-the-server%5D__4c1e50c7._.js.map