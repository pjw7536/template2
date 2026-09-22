// src/features/errors/routes.jsx
// 에러/404 페이지 라우트 정의를 제공합니다.
import { lazyNamed } from "@/lib/react/lazyNamed"

const NotFoundPage = lazyNamed(() => import("./pages/NotFoundPage"), "NotFoundPage")

export const notFoundRoute = {
  path: "*",
  element: <NotFoundPage />,
}

export const errorRoutes = [notFoundRoute]
