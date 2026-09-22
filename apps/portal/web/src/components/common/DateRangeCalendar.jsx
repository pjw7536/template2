// 파일 경로: src/components/common/DateRangeCalendar.jsx
import { Calendar } from "@/components/ui/calendar"

export function DateRangeCalendar({
  selected,
  defaultMonth,
  onSelect,
  numberOfMonths = 2,
  disabled,
  disableAfter,
  classNames,
  ...props
}) {
  const disabledConfig =
    disabled ?? (disableAfter ? { after: disableAfter } : undefined)

  return (
    <Calendar
      mode="range"
      captionLayout="dropdown"
      selected={selected}
      defaultMonth={defaultMonth}
      onSelect={onSelect}
      numberOfMonths={numberOfMonths}
      disabled={disabledConfig}
      classNames={{
        today:
          "!bg-transparent !text-foreground data-[selected=true]:!bg-primary data-[selected=true]:!text-primary-foreground",
        ...classNames,
      }}
      {...props}
    />
  )
}
