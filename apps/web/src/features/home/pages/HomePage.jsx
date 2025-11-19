// src/features/home/pages/HomePage.jsx
// 홈 화면의 안내 섹션으로, AppShell 아래에서 가장 먼저 보여집니다.
export function HomePage() {
  return (
    <section className="relative h-[600px] overflow-hidden rounded-xl border shadow-sm">
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[url('/images/Wow-gif.gif')] bg-cover bg-center"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-white/70 backdrop-blur-sm dark:bg-slate-950/70"
      />
      <div className="relative z-10 grid gap-4 p-6">
        <h1 className="text-3xl font-semibold tracking-tight">Welcome</h1>
        <p className="mt-2 text-base text-muted-foreground">
          This is a placeholder for the main dashboard content. Replace it with your actual page components.
        </p>
      </div>
    </section>
  )
}
