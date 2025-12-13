// src/features/appstore/components/AppFormDialog.jsx
import { useEffect, useMemo, useState } from "react"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

function toTags(value) {
  if (!value?.trim()) return []
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

function getFirstClipboardImageFile(clipboardData) {
  const items = Array.from(clipboardData?.items ?? [])
  const imageItem = items.find((item) => item.kind === "file" && item.type?.startsWith("image/"))
  return imageItem ? imageItem.getAsFile() : null
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "")
    reader.onerror = () => reject(reader.error || new Error("Failed to read file"))
    reader.readAsDataURL(file)
  })
}

export function AppFormDialog({
  open,
  onOpenChange,
  onSubmit,
  initialData,
  isSubmitting,
  defaultContactName = "",
  defaultContactKnoxid = "",
}) {
  const [name, setName] = useState("")
  const [category, setCategory] = useState("")
  const [url, setUrl] = useState("")
  const [description, setDescription] = useState("")
  const [tagsText, setTagsText] = useState("")
  const [badge, setBadge] = useState("")
  const [contactName, setContactName] = useState("")
  const [contactKnoxid, setContactKnoxid] = useState("")
  const [screenshotUrl, setScreenshotUrl] = useState("")
  const [screenshotError, setScreenshotError] = useState("")

  useEffect(() => {
    if (!open) return
    if (initialData) {
      setName(initialData.name || "")
      setCategory(initialData.category || "")
      setUrl(initialData.url || "")
      setDescription(initialData.description || "")
      setTagsText(initialData.tags?.join(", ") || "")
      setBadge(initialData.badge || "")
      setContactName(initialData.contactName || "")
      setContactKnoxid(initialData.contactKnoxid || "")
      setScreenshotUrl(initialData.screenshotUrl || "")
      setScreenshotError("")
    } else {
      setName("")
      setCategory("")
      setUrl("")
      setDescription("")
      setTagsText("")
      setBadge("")
      setContactName("")
      setContactKnoxid("")
      setScreenshotUrl("")
      setScreenshotError("")
    }
  }, [initialData, open])

  useEffect(() => {
    if (!open || initialData) return
    setContactName((prev) => (prev ? prev : defaultContactName || ""))
    setContactKnoxid((prev) => (prev ? prev : defaultContactKnoxid || ""))
  }, [defaultContactName, defaultContactKnoxid, initialData, open])

  const title = useMemo(
    () => (initialData ? "앱 정보 수정" : "새 앱 등록"),
    [initialData],
  )

  const handleSubmit = async () => {
    if (!name.trim() || !category.trim() || !url.trim()) return
    const payload = {
      name: name.trim(),
      category: category.trim(),
      url: url.trim(),
      description: description.trim(),
      tags: toTags(tagsText),
      badge: badge.trim(),
      contactName: contactName.trim(),
      contactKnoxid: contactKnoxid.trim(),
      screenshotUrl: screenshotUrl.trim(),
    }
    await onSubmit(payload)
  }

  const handleScreenshotPaste = async (event) => {
    const file = getFirstClipboardImageFile(event.clipboardData)
    if (!file) {
      setScreenshotError("이미지(스크린샷)만 붙여넣을 수 있어요.")
      return
    }

    event.preventDefault()
    setScreenshotError("")

    try {
      const dataUrl = await fileToDataUrl(file)
      setScreenshotUrl(dataUrl)
    } catch {
      setScreenshotError("스크린샷을 읽지 못했습니다. 다시 시도해 주세요.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="app-name">앱 이름</Label>
            <Input
              id="app-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="예: Slack Platform"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="app-category">카테고리</Label>
            <Input
              id="app-category"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              placeholder="예: Collaboration"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="app-url">URL</Label>
            <Input
              id="app-url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.com"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="app-description">설명</Label>
            <textarea
              id="app-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="앱의 주요 기능과 사용 목적을 입력하세요."
              className="min-h-[140px] w-full resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="app-tags">태그 (쉼표 구분)</Label>
            <Input
              id="app-tags"
              value={tagsText}
              onChange={(event) => setTagsText(event.target.value)}
              placeholder="예: Messaging, Collaboration"
            />
          </div>

          <div className="grid gap-2 sm:grid-cols-2 sm:gap-3">
            <div className="grid gap-2">
              <Label htmlFor="app-badge">배지</Label>
              <Input
                id="app-badge"
                value={badge}
                onChange={(event) => setBadge(event.target.value)}
                placeholder="예: Popular, Beta"
              />
            </div>
            <div className="grid gap-2">
              <Label id="app-screenshot-label">스크린샷 (클립보드 붙여넣기)</Label>
              <div className="grid gap-2">
                <div
                  id="app-screenshot"
                  aria-labelledby="app-screenshot-label"
                  tabIndex={0}
                  onPaste={handleScreenshotPaste}
                  className="grid min-h-[140px] place-items-center rounded-md border bg-muted/40 p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                >
                  {screenshotUrl ? (
                    <img
                      src={screenshotUrl}
                      alt="스크린샷 미리보기"
                      className="max-h-56 w-full rounded-md object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <div className="grid gap-2 text-center">
                      <p className="text-sm font-medium text-foreground">여기에 스크린샷을 붙여넣어 주세요</p>
                      <p className="text-xs text-muted-foreground">Ctrl+V / ⌘V</p>
                    </div>
                  )}
                </div>

                {screenshotError ? (
                  <p className="text-xs text-destructive">{screenshotError}</p>
                ) : null}

                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs text-muted-foreground">
                    {screenshotUrl ? "붙여넣은 이미지가 저장됩니다." : "클릭 후 붙여넣기(Ctrl+V)를 사용하세요."}
                  </p>
                  {screenshotUrl ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setScreenshotUrl("")
                        setScreenshotError("")
                      }}
                      type="button"
                    >
                      삭제
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="app-contact-name">담당자 이름</Label>
              <Input
                id="app-contact-name"
                value={contactName}
                onChange={(event) => setContactName(event.target.value)}
                placeholder="홍길동"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="app-contact-knoxid">담당자 Knox ID</Label>
              <Input
                id="app-contact-knoxid"
                value={contactKnoxid}
                onChange={(event) => setContactKnoxid(event.target.value)}
                placeholder="이메일 @ 앞부분"
              />
            </div>
          </div>
        </div>

        <DialogFooter className="pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)} type="button">
            취소
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting || !name || !category || !url} type="button">
            {initialData ? "수정 완료" : "등록"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
