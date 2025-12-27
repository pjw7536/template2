import * as React from "react"

import { cn } from "@/lib/utils"
import {
  Table as UiTable,
  TableHeader as UiTableHeader,
  TableBody as UiTableBody,
  TableFooter as UiTableFooter,
  TableHead as UiTableHead,
  TableRow as UiTableRow,
  TableCell as UiTableCell,
  TableCaption as UiTableCaption,
} from "@/components/ui/table"

const StickyHeaderContext = React.createContext(false)

export function Table({ stickyHeader = false, className, ...props }) {
  return (
    <StickyHeaderContext.Provider value={Boolean(stickyHeader)}>
      <UiTable className={className} {...props} />
    </StickyHeaderContext.Provider>
  )
}

export function TableHeader({ className, ...props }) {
  return <UiTableHeader className={className} {...props} />
}

export function TableBody({ className, ...props }) {
  return <UiTableBody className={className} {...props} />
}

export function TableFooter({ className, ...props }) {
  return <UiTableFooter className={className} {...props} />
}

export function TableRow({ className, ...props }) {
  return <UiTableRow className={className} {...props} />
}

export function TableHead({ className, ...props }) {
  const stickyHeader = React.useContext(StickyHeaderContext)

  return (
    <UiTableHead
      className={cn(stickyHeader && "sticky top-0 z-10 bg-background", className)}
      {...props}
    />
  )
}

export function TableCell({ className, ...props }) {
  return <UiTableCell className={className} {...props} />
}

export function TableCaption({ className, ...props }) {
  return <UiTableCaption className={className} {...props} />
}
