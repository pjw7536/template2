/** 조직·업로드 화면용 묶음입니다. Portal과 같은 shadcn 컴포넌트·토큰 위에 만듭니다. */
import { Badge as UiBadge } from "@/components/ui/badge"
import { Button as UiButton } from "@/components/ui/button"
import { Card as UiCard, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input as UiInput } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { NativeSelect } from "./NativeSelect"

export const cx = cn
export const Input = UiInput
export const Select = NativeSelect

const BUTTON = { primary: "default", outline: "outline", ghost: "ghost", danger: "outline" }

export function Button({ variant = "primary", className, ...props }) {
  return (
    <UiButton
      type="button"
      variant={BUTTON[variant]}
      className={cn(variant === "danger" && "text-destructive hover:text-destructive", className)}
      {...props}
    />
  )
}

export function Card({ title, description, actions, className, contentClassName, children }) {
  return (
    <UiCard className={cn("gap-0 py-0", className)}>
      {title || actions ? (
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 border-b py-3">
          <div className="grid gap-1">
            <CardTitle className="text-sm">{title}</CardTitle>
            {description ? <CardDescription className="text-xs">{description}</CardDescription> : null}
          </div>
          {actions}
        </CardHeader>
      ) : null}
      <CardContent className={cn("py-4", contentClassName)}>{children}</CardContent>
    </UiCard>
  )
}

const TONE = {
  gray: "",
  blue: "border-chart-2/40 text-chart-2",
  green: "border-chart-2/40 bg-chart-2/10 text-chart-2",
  amber: "border-chart-4/50 text-chart-4",
  red: "border-destructive/40 text-destructive",
}

export function Badge({ tone = "gray", children }) {
  return <UiBadge variant={tone === "gray" ? "secondary" : "outline"} className={TONE[tone]}>{children}</UiBadge>
}

export function Alert({ tone = "red", children }) {
  return (
    <div role={tone === "red" ? "alert" : "status"}
      className={cn("rounded-md border px-3 py-2 text-sm", tone === "red" ? "border-destructive/30 text-destructive" : "bg-muted/40")}>
      {children}
    </div>
  )
}

/** CSV 파일을 텍스트로 읽어 onText에 넘깁니다. 같은 파일을 다시 고를 수 있게 값을 비웁니다. */
export function FilePicker({ label, onText }) {
  return (
    <label className="inline-flex h-9 cursor-pointer items-center rounded-md border bg-background px-4 text-sm font-medium shadow-xs hover:bg-accent hover:text-accent-foreground">
      {label}
      <input
        type="file"
        accept=".csv,text/csv"
        className="sr-only"
        onChange={async (event) => {
          const file = event.target.files?.[0]
          event.target.value = ""
          if (file) onText(await file.text(), file.name)
        }}
      />
    </label>
  )
}
