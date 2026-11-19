import * as React from "react"

import { cn } from "@/lib/utils"
import {
  Table as UiTable,
  TableBody as UiTableBody,
  TableCell as UiTableCell,
  TableHead as UiTableHead,
  TableHeader as UiTableHeader,
  TableRow as UiTableRow,
} from "@/components/ui/table"

/** Portal components/common/table.jsx와 같은 sticky header 표입니다. */
const StickyHeaderContext = React.createContext(false)

export function Table({ stickyHeader = false, className, ...props }) {
  return (
    <StickyHeaderContext.Provider value={Boolean(stickyHeader)}>
      <UiTable className={className} {...props} />
    </StickyHeaderContext.Provider>
  )
}

export const TableHeader = UiTableHeader
export const TableBody = UiTableBody
export const TableRow = UiTableRow
export const TableCell = UiTableCell

export function TableHead({ className, ...props }) {
  const stickyHeader = React.useContext(StickyHeaderContext)
  return <UiTableHead className={cn(stickyHeader && "sticky top-0 z-10 bg-background", className)} {...props} />
}
