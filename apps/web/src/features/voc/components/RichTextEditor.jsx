import * as React from "react"
import { useQuill } from "react-quilljs"

export function RichTextEditor({
  id,
  value,
  onChange,
  placeholder,
  modules,
  formats,
  readOnly = false,
  className = "",
  ariaLabelledby,
  ariaLabel,
}) {
  const { quill, quillRef } = useQuill({
    theme: "snow",
    placeholder,
    modules,
    formats,
    readOnly,
  })

  const normalizeHtml = React.useCallback((html) => {
    if (!html || html === "<p><br></p>") return ""
    return html
  }, [])

  const handleWrapperPointerDown = (event) => {
    if (readOnly || !quill) return
    if (event.pointerType === "mouse" && event.button !== 0) return

    const target = event.target
    if (target && typeof target.closest === "function") {
      if (target.closest(".ql-toolbar")) return
      const clickedEditor = target.closest(".ql-editor")
      quill.focus()
      if (!clickedEditor) {
        quill.setSelection(quill.getLength(), 0, "silent")
      }
      return
    }

    quill.focus()
  }

  React.useEffect(() => {
    if (!quill) return undefined
    const handleChange = () => {
      if (!onChange) return
      const html = normalizeHtml(quill.root.innerHTML)
      onChange(html)
    }
    quill.on("text-change", handleChange)
    return () => {
      quill.off("text-change", handleChange)
    }
  }, [normalizeHtml, onChange, quill])

  React.useEffect(() => {
    if (!quill) return
    const nextValue = normalizeHtml(value || "")
    const currentValue = normalizeHtml(quill.root.innerHTML)
    if (nextValue === currentValue) return
    quill.clipboard.dangerouslyPasteHTML(nextValue)
    quill.setSelection(quill.getLength(), 0)
  }, [normalizeHtml, quill, value])

  React.useEffect(() => {
    if (!quill) return
    quill.enable(!readOnly)
  }, [quill, readOnly])

  return (
    <div
      className={["voc-quill", className].filter(Boolean).join(" ")}
      onPointerDownCapture={handleWrapperPointerDown}
    >
      <div
        id={id}
        ref={quillRef}
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledby}
        aria-readonly={readOnly ? "true" : "false"}
      />
    </div>
  )
}
