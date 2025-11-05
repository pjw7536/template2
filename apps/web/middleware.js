import { NextResponse } from "next/server"

const PUBLIC_PATH_PREFIXES = ["/login", "/api", "/_next", "/favicon.ico", "/assets", "/public"]
const SESSION_COOKIE_NAME = "sessionid"

function isPublicPath(pathname) {
  return PUBLIC_PATH_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))
}

export function middleware(request) {
  const { pathname } = request.nextUrl

  if (isPublicPath(pathname)) {
    return NextResponse.next()
  }

  const sessionCookie = request.cookies.get(SESSION_COOKIE_NAME)
  if (!sessionCookie) {
    const loginUrl = new URL("/login", request.url)
    if (pathname && pathname !== "/") {
      loginUrl.searchParams.set("next", pathname)
    }
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!_next/|favicon.ico|assets/|public/|.*\\.(?:js|css|png|jpg|jpeg|gif|svg|ico)$).*)"],
}
