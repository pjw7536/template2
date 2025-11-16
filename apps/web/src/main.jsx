import React from "react"
import ReactDOM from "react-dom/client"
import { RouterProvider } from "react-router-dom"

import { AppProviders } from "@/components/providers/app-providers"
import { router } from "@/routes/router"

import "@/styles/globals.css"

const rootElement = document.getElementById("root")

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </React.StrictMode>,
)
