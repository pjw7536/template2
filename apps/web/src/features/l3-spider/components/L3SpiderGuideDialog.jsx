import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  CircleHelp,
  ExternalLink,
  Filter,
  ImageIcon,
  Mail,
  Radar,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

import { AlgorithmGuideContent } from "./L3SpiderAlgorithmGuide"

const ASSET_ROOT = "/l3-spider/l3-spider-guide-assets"

const GUIDE_META = {
  page: {
    title: "L3 Spider 페이지 설명서",
    description: "실제 화면 기준으로 Summary, Chart, 메일 설정, 제외 필터의 사용 흐름을 확인합니다.",
    icon: BookOpen,
  },
  algorithm: {
    title: "L3 Spider 알고리즘 설명서",
    description: "이상 챔버 자동 감지의 판정 흐름과 운영 기준을 확인합니다.",
    icon: CircleHelp,
  },
}

const PAGE_SECTIONS = [
  { id: "summary", label: "Summary", icon: BarChart3 },
  { id: "chart", label: "Chart", icon: Activity },
  { id: "mail-list", label: "메일 목록", icon: Mail },
  { id: "mail-form", label: "메일 Rule", icon: Bell },
  { id: "exclusion", label: "제외 필터", icon: Filter },
]

const ALGORITHM_SECTIONS = [
  { id: "intro", label: "왜 필요한가", icon: Sparkles },
  { id: "phase1", label: "1단계 스파이크", icon: Activity },
  { id: "phase2", label: "2단계 교차검증", icon: Radar },
  { id: "fadeout", label: "중복 알람 방지", icon: ShieldCheck },
  { id: "read", label: "화면 읽는 법", icon: BarChart3 },
  { id: "faq", label: "FAQ", icon: CircleHelp },
  { id: "glossary", label: "용어집", icon: BookOpen },
]

const PAGE_SCREENSHOTS = [
  {
    id: "summary",
    eyebrow: "01 Summary",
    title: "날짜 하나로 전체 이상 현황을 먼저 본다",
    image: "summary-overview.png",
    alt: "L3 Spider Summary 탭 실제 화면 캡처",
    caption: "Summary 탭 실제 캡처. 번호는 날짜, 관리 버튼, 탭, 6개 Total 지표, 라인별 집계, 라인별 세부 요약을 가리킵니다.",
    points: [
      ["Date 선택", "조회 기준 날짜입니다. 날짜를 바꾸면 Summary 집계와 Chart 선택 후보가 같은 날짜 기준으로 다시 계산됩니다."],
      ["운영 버튼", "메일 설정은 자동 알림 rule을 관리하고, 제외 필터는 노이즈 조합을 집계에서 빼며, 새로고침은 최신 메타데이터를 다시 불러옵니다."],
      ["Summary / Chart 탭", "Summary는 날짜 전체 집계, Chart는 선택 조건별 scatter trellis 분석 화면입니다."],
      ["하단 Total 지표", "기존 3개에서 6개로 확장되어 분석 ROWS, 분석 그룹수, 이상 EQPCH, Warning, High Risk, 이상 건수를 2행 3열로 보여줍니다."],
      ["라인별 현황", "Line별 HR/WN/합계를 비교합니다. 이상이 없는 라인도 흐리게 표시되어 전체 커버리지와 이상 집중 라인을 같이 볼 수 있습니다."],
      ["라인별 세부 요약", "Line, Process, EDS Step별 High Risk/Warning 건수를 보여줍니다. 셀을 클릭하면 같은 조건으로 Chart 탭이 열립니다."],
    ],
  },
  {
    id: "chart",
    eyebrow: "02 Chart",
    title: "Line에서 EQPCH까지 좁혀 scatter trellis로 확인한다",
    image: "chart-workflow.png",
    alt: "L3 Spider Chart 탭 실제 화면 캡처",
    caption: "Chart 탭 실제 캡처. 선택 패널과 하단 조절 핸들, scatter trellis, chart order, axis mode, export 도구를 함께 보여줍니다.",
    points: [
      ["Date 선택", "현재 차트가 어떤 날짜 데이터인지 고정합니다. 선택 완료 시 날짜 옆 체크 표시가 보입니다."],
      ["상위 선택축", "Line Name, Process ID, EDS Step을 고릅니다. 각 컬럼 상단 숫자는 현재 날짜에서 선택 가능한 후보 수입니다."],
      ["상세 선택축", "Step Seq, PPID, EQPCH, Bin Name을 순서대로 선택합니다. PPID 칼럼의 시간은 해당 조합의 마지막 TKin Time입니다."],
      ["선택 패널 조절", "하단 핸들을 클릭하면 선택 패널을 접거나 펼칩니다. 펼친 상태에서 위아래로 드래그하거나 키보드 ↑/↓ 키를 누르면 패널 높이를 조절할 수 있습니다."],
      ["Scatter Plot trellis", "선택된 EQPCH의 이상 Bin을 작은 차트로 나눠 보여줍니다. 빨간 점은 High Risk, 주황 점은 Warning, 회색 점은 정상 기준입니다."],
      ["Chart Order", "기본 순서 또는 High Risk가 있는 차트를 앞쪽에 배치하는 순서를 선택합니다."],
      ["X Axis", "시간 기준, 시간+Wafer 기준, EQPCH+Time 기준으로 X축을 바꿉니다."],
      ["Raw Data", "현재 선택 조건의 원천 row를 CSV로 내려받아 별도 분석이나 공유에 사용합니다."],
      ["All Charts", "현재 trellis 전체 차트를 이미지로 캡처합니다. 보고서 첨부용 전체 차트 묶음을 만들 때 사용합니다."],
    ],
  },
  {
    id: "mail-list",
    eyebrow: "03 Mail settings",
    title: "자동 알림 rule을 한 곳에서 관리한다",
    image: "mail-settings.png",
    alt: "L3 Spider 메일 설정 목록 실제 화면 캡처",
    caption: "메일 설정 목록 실제 캡처. rule 이름, 발송 조건, 수신자, 권한, 작업 버튼을 확인합니다.",
    points: [
      ["메일 발송 설정", "메일 rule을 조회, 추가, 수정, 삭제하는 시트입니다. 사용자가 등록한 rule은 지정 시각 이후 한 번 처리됩니다."],
      ["Rule 추가", "새 메일 rule 입력 창을 엽니다. 아래 Rule form 화면과 연결됩니다."],
      ["Rule / 접근", "Rule 이름과 공유 권한을 관리합니다. 접근 권한은 owner/read/write 레벨로 분리됩니다."],
      ["조건 / 주기", "High Risk만 보낼지, Warning까지 포함할지와 발송 주기를 확인합니다."],
      ["수신자 / 패턴", "수신 이메일과 Line/Process/EDS/Step/PPID/EQPCH/Bin 패턴을 요약 표시합니다."],
      ["작업", "기존 rule을 수정, 삭제, 테스트 발송하거나 권한을 조정하는 영역입니다."],
    ],
  },
  {
    id: "mail-form",
    eyebrow: "04 Mail rule form",
    title: "메일 rule은 조건과 수신자, 발송 시각으로 구성한다",
    image: "mail-rule-form.png",
    alt: "L3 Spider 메일 rule 추가 창 실제 화면 캡처",
    caption: "메일 rule 추가 모달 실제 캡처. 필수값, severity, 수신자, 패턴 필드, 활성 상태를 저장합니다.",
    points: [
      ["메일 rule 추가", "새 rule 생성 모달입니다. 수정 모드에서는 제목이 메일 rule 수정으로 바뀝니다."],
      ["Rule 이름", "목록에서 식별할 이름입니다. 예: 특정 Line의 High Risk 알림."],
      ["메일 조건", "High Risk만 또는 Warning + High Risk 중 발송 대상 severity를 고릅니다."],
      ["발송 시각", "Asia/Seoul 기준 발송 기준 시각입니다. rule 처리는 이 시각 이후의 대상 결과를 확인합니다."],
      ["수신자", "쉼표, 세미콜론, 줄바꿈으로 여러 이메일을 입력할 수 있습니다."],
      ["패턴 필드", "Line ID, Process ID, EDS Step, Step Seq, PPID, EQPCH, Bin Name, 발송 종료일을 지정합니다."],
      ["활성", "rule을 켜고 끄는 스위치입니다. 비활성 rule은 저장되어 있어도 발송 대상에서 제외됩니다."],
      ["저장", "입력한 조건을 저장합니다. 수신자 형식이나 필수값 문제가 있으면 저장 전에 오류가 표시됩니다."],
    ],
  },
  {
    id: "exclusion",
    eyebrow: "05 Exclusion filters",
    title: "노이즈 조합은 집계에서 제외해 신호를 선명하게 만든다",
    image: "exclusion-filters.png",
    alt: "L3 Spider 제외 필터 관리 실제 화면 캡처",
    caption: "제외 필터 관리 시트 실제 캡처. 기존 필터 1건이 흐리게 보이는 상태입니다.",
    points: [
      ["제외 필터 관리", "집계에서 제외할 조합을 관리하는 시트입니다. 적용된 필터는 날짜별 메타와 요약 계산에 반영됩니다."],
      ["필터 추가", "새 제외 규칙 행을 추가합니다. 추가 후 저장 아이콘으로 확정합니다."],
      ["활성", "필터를 즉시 켜거나 끕니다. 비활성 필터는 목록에는 남지만 계산에는 적용되지 않습니다."],
      ["대상 패턴", "Line ID부터 Bin Name까지 제외 조건을 적습니다. 메일 rule과 동일하게 *와 와일드카드를 사용할 수 있습니다."],
      ["날짜 시작 / 종료", "필터 적용 기간입니다. 특정 이벤트 기간만 제외하려면 시작과 종료를 함께 넣습니다."],
      ["메모", "제외 사유, 요청자, 이슈 번호 등을 남깁니다. 나중에 필터를 검토할 때 기준이 됩니다."],
      ["작업", "필터 행을 수정하거나 삭제합니다. 삭제는 적용 이력 관리 기준에 맞춰 신중하게 처리합니다."],
    ],
  },
]


function GuideShell({ sections, activeSection, onSectionClick, scrollRef, children }) {
  return (
    <div className="grid h-full min-h-0 grid-rows-[auto,minmax(0,1fr)] bg-background">
      <nav className="shrink-0 border-b bg-muted/30 px-4 py-3" aria-label="가이드 섹션">
        <div className="flex flex-nowrap items-center gap-2 overflow-x-auto">
          {sections.map((section) => {
            const Icon = section.icon
            const isActive = activeSection === section.id
            return (
              <button
                key={section.id}
                type="button"
                onClick={() => onSectionClick(section.id)}
                className={cn(
                  "flex h-9 shrink-0 items-center gap-2 rounded-md px-3 text-left text-sm transition",
                  "hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isActive ? "bg-background font-semibold text-foreground shadow-sm" : "text-muted-foreground",
                )}
              >
                <Icon className="size-4 shrink-0" aria-hidden="true" />
                <span className="truncate">{section.label}</span>
              </button>
            )
          })}
        </div>
      </nav>
      <main ref={scrollRef} className="min-h-0 min-w-0 overflow-y-auto" data-guide-scroll>
        {children}
      </main>
    </div>
  )
}

function GuideHero({ eyebrow, title, description, badges, variant = "default" }) {
  return (
    <section
      className={cn(
        "border-b px-8 py-10",
        variant === "algorithm" ? "bg-primary/5" : "bg-card",
      )}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">{eyebrow}</p>
      <h2 className="mt-3 max-w-4xl text-3xl font-semibold tracking-tight text-foreground">{title}</h2>
      <p className="mt-4 max-w-4xl text-sm leading-6 text-muted-foreground">{description}</p>
      {badges?.length ? (
        <div className="mt-5 flex flex-wrap gap-2">
          {badges.map((badge) => (
            <Badge key={badge} variant="secondary" className="rounded-md px-2.5 py-1">
              {badge}
            </Badge>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function ScreenshotFigure({ image, alt, caption }) {
  const src = `${ASSET_ROOT}/${image}`
  return (
    <figure className="overflow-hidden rounded-lg border bg-card">
      <button
        type="button"
        onClick={() => window.open(src, "_blank", "noopener,noreferrer")}
          className="group block w-full bg-muted/30 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`${alt} 원본 이미지 열기`}
      >
        <img
          src={src}
          alt={alt}
          className="block w-full max-w-full transition group-hover:opacity-95"
        />
      </button>
      <figcaption className="flex items-center gap-2 border-t px-4 py-2 text-xs text-muted-foreground">
        <ImageIcon className="size-3.5" aria-hidden="true" />
        <span className="min-w-0 flex-1">{caption}</span>
        <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
      </figcaption>
    </figure>
  )
}

function NumberedCallouts({ points }) {
  return (
    <ol className="grid gap-3 md:grid-cols-2">
      {points.map(([title, body], index) => (
        <li key={title} className="grid grid-cols-[2rem,minmax(0,1fr)] gap-3 rounded-lg border bg-card p-3">
          <span className="grid size-8 place-items-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
            {index + 1}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground">{title}</p>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{body}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

function PageGuideContent() {
  return (
    <div>
      <GuideHero
        eyebrow="Actual page capture guide"
        title="L3 Spider 실제 화면 기준 사용 설명서"
        description="L3 Spider는 날짜별 이상감지 결과를 Summary에서 빠르게 훑고, Chart에서 Line/Process/EDS/Step/PPID/EQPCH 단위로 파고드는 화면입니다. 각 캡처의 번호는 실제 UI 영역을 가리키며, 아래 설명은 그 영역이 무엇을 하는지 정리합니다."
        badges={["캡처 경로 /l3_spider", "캡처 실행일 2026-07-14", "화면 데이터 날짜 2026-06-20"]}
      />
      <div className="grid gap-10 px-8 py-8">
        {PAGE_SCREENSHOTS.map((section) => (
          <section key={section.id} id={section.id} className="scroll-mt-6 space-y-5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">{section.eyebrow}</p>
              <h3 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{section.title}</h3>
            </div>
            <ScreenshotFigure image={section.image} alt={section.alt} caption={section.caption} />
            <NumberedCallouts points={section.points} />
          </section>
        ))}
      </div>
    </div>
  )
}


export function L3SpiderGuideDialog({ guideKey, onGuideKeyChange }) {
  const scrollRef = useRef(null)
  const [activeSection, setActiveSection] = useState("")
  const activeMeta = guideKey ? GUIDE_META[guideKey] : null
  const sections = guideKey === "algorithm" ? ALGORITHM_SECTIONS : PAGE_SECTIONS
  const Icon = activeMeta?.icon ?? BookOpen

  useEffect(() => {
    setActiveSection(sections[0]?.id ?? "")
    scrollRef.current?.scrollTo({ top: 0 })
  }, [guideKey, sections])

  useEffect(() => {
    const container = scrollRef.current
    if (!container || !guideKey) return undefined

    const handleScroll = () => {
      const current = sections.reduce((selected, section) => {
        const element = container.querySelector(`#${section.id}`)
        if (!element) return selected
        const offset = element.getBoundingClientRect().top - container.getBoundingClientRect().top
        return offset <= 120 ? section.id : selected
      }, sections[0]?.id ?? "")
      setActiveSection(current)
    }

    handleScroll()
    container.addEventListener("scroll", handleScroll, { passive: true })
    return () => container.removeEventListener("scroll", handleScroll)
  }, [guideKey, sections])

  const handleOpenChange = (open) => {
    if (!open) onGuideKeyChange(null)
  }

  const scrollToSection = (sectionId) => {
    const container = scrollRef.current
    const element = container?.querySelector(`#${sectionId}`)
    if (!container || !element) return
    const top = element.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop - 16
    container.scrollTo({ top, behavior: "smooth" })
    setActiveSection(sectionId)
  }

  return (
    <Dialog open={Boolean(activeMeta)} onOpenChange={handleOpenChange}>
      <DialogContent className="grid h-[90dvh] max-h-[90dvh] w-[80vw] max-w-[80vw] grid-rows-[auto,minmax(0,1fr)] gap-0 overflow-hidden p-0 sm:w-[80vw] sm:max-w-[80vw]">
        <DialogHeader className="shrink-0 border-b px-5 py-3 pr-14 text-left">
          <div className="flex flex-nowrap items-center justify-between gap-4">
            <div className="min-w-0 flex-1">
              <DialogTitle className="flex min-w-0 items-center gap-2">
                <Icon className="size-5 shrink-0 text-primary" aria-hidden="true" />
                <span className="truncate">{activeMeta?.title}</span>
              </DialogTitle>
              <DialogDescription className="mt-1">
                {activeMeta?.description}
              </DialogDescription>
            </div>
            <Tabs value={guideKey ?? "page"} onValueChange={onGuideKeyChange} className="shrink-0">
              <TabsList className="flex-nowrap">
                <TabsTrigger value="page" className="whitespace-nowrap">페이지 설명서</TabsTrigger>
                <TabsTrigger value="algorithm" className="whitespace-nowrap">알고리즘 설명서</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </DialogHeader>
        <div className="min-h-0 overflow-hidden">
          <GuideShell
            sections={sections}
            activeSection={activeSection}
            onSectionClick={scrollToSection}
            scrollRef={scrollRef}
          >
            {guideKey === "algorithm" ? <AlgorithmGuideContent /> : <PageGuideContent />}
          </GuideShell>
        </div>
      </DialogContent>
    </Dialog>
  )
}
