import { withAuth } from "next-auth/middleware"

const publicPaths = ["/login", "/api/auth"]

export const proxy = withAuth({
  callbacks: {
    authorized: ({ token, req }) => {
      const { pathname } = req.nextUrl
      if (publicPaths.some((path) => pathname.startsWith(path))) {
        return true
      }
      return Boolean(token)
    },
  },
  pages: {
    signIn: "/login",
  },
})

export default proxy

export const config = {
  matcher: ["/((?!_next/|favicon.ico|assets/|.*\\.\w+$).*)"],
}
