import CredentialsProvider from "next-auth/providers/credentials"
import OAuthProvider from "next-auth/providers/oauth"


const oidcIssuer = process.env.AUTH_OIDC_ISSUER
const oidcClientId = process.env.AUTH_OIDC_ID
const oidcClientSecret = process.env.AUTH_OIDC_SECRET

const providers = []

if (oidcIssuer && oidcClientId && oidcClientSecret) {
  providers.push(
    OAuthProvider({
      id: "oidc",
      name: "OIDC",
      issuer: oidcIssuer,
      clientId: oidcClientId,
      clientSecret: oidcClientSecret,
      checks: ["pkce", "state"],
      authorization: {
        params: {
          scope: "openid profile email",
        },
      },
      profile(profile) {
        return {
          id: profile.sub ?? profile.id ?? profile.email ?? profile.preferred_username ?? "oidc-user",
          name:
            profile.name ??
            profile.preferred_username ??
            profile.given_name ??
            profile.family_name ??
            profile.email ??
            "OIDC User",
          email: profile.email ?? null,
          image: profile.picture ?? null,
        }
      },
    }),
  )
}

const dummyName = process.env.AUTH_DUMMY_NAME ?? "Demo User"
const dummyEmail = process.env.AUTH_DUMMY_EMAIL ?? "demo@example.com"

providers.push(
  CredentialsProvider({
    id: "dummy",
    name: "SSO", // surfaced in debug logs only
    credentials: {},
    async authorize() {
      return {
        id: "dummy-user",
        name: dummyName,
        email: dummyEmail,
      }
    },
  }),
)

export const authOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  session: {
    strategy: "jwt",
  },
  providers,
  pages: {
    signIn: "/login",
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.user = {
          id: user.id ?? token.sub ?? "user",
          name: user.name ?? null,
          email: user.email ?? null,
          image: user.image ?? null,
        }
      }
      return token
    },
    async session({ session, token }) {
      if (token?.user) {
        session.user = token.user
      }
      return session
    },
  },
  // Allow credentials provider without HTTPS in dev
  useSecureCookies: process.env.NODE_ENV === "production",
}
