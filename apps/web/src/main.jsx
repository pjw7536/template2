import React, { Suspense } from "react"
import ReactDOM from "react-dom/client"
import { RouterProvider } from "react-router-dom"

import { AppProviders, RouteLoadingFallback } from "@/components/common"
import { router } from "./routes/router"

import "./styles/globals.css"

const rootElement = document.getElementById("root")

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <AppProviders>
      <Suspense fallback={<RouteLoadingFallback />}>
        <RouterProvider router={router} />
      </Suspense>
    </AppProviders>
  </React.StrictMode>,
)
