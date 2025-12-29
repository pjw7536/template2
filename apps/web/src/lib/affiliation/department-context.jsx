import * as React from "react"

import { useAuth } from "@/lib/auth"

const DepartmentContext = React.createContext(null)

export function DepartmentProvider({ children, department }) {
  const { user } = useAuth()
  const resolvedDepartment =
    typeof department === "string" ? department : user?.department ?? ""

  return (
    <DepartmentContext.Provider value={{ department: resolvedDepartment }}>
      {children}
    </DepartmentContext.Provider>
  )
}

export function useDepartment() {
  const context = React.useContext(DepartmentContext)
  if (!context) {
    throw new Error("useDepartment must be used within a DepartmentProvider")
  }
  return context
}
