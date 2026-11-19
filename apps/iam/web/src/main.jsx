import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import App from "./App.jsx"
import { initLogin } from "./lib/keycloak.js"

const root = createRoot(document.getElementById("root"))

initLogin()
  .then(() => root.render(<StrictMode><App /></StrictMode>))
  .catch(() => {
    root.render(<p style={{ padding: 16 }}>Keycloak에 연결하지 못했습니다. public/config.js의 주소·realm·client를 확인하세요.</p>)
  })
