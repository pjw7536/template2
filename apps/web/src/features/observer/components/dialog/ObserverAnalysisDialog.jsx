import React from "react";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

function AnalysisLoading() {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center gap-3 text-center">
      <Loader2 className="size-7 animate-spin text-primary" aria-hidden="true" />
      <div>
        <p className="text-sm font-semibold text-foreground">Observer 로그를 종합 분석하고 있습니다.</p>
        <p className="mt-1 text-xs text-muted-foreground">
          관심 상태 통계와 주변 로그를 현재 OpenWebUI 모델이 확인합니다.
        </p>
      </div>
    </div>
  );
}

function AnalysisError({ error, onRetry }) {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center gap-3 text-center">
      <AlertTriangle className="size-7 text-destructive" aria-hidden="true" />
      <div>
        <p className="text-sm font-semibold text-foreground">AI 분석을 완료하지 못했습니다.</p>
        <p className="mt-1 text-xs text-muted-foreground">
          {error?.message || "잠시 후 다시 시도해 주세요."}
        </p>
      </div>
      <Button type="button" variant="outline" size="sm" onClick={onRetry}>
        <RefreshCw className="size-4" aria-hidden="true" />
        다시 분석
      </Button>
    </div>
  );
}

function FindingSection({ finding }) {
  const hasRecordedCauses = finding.recordedCauses?.length > 0;
  const hasInferredCauses = finding.inferredCauses?.length > 0;

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{finding.category || "분석"}</Badge>
        <h3 className="text-sm font-semibold text-foreground">
          {finding.target || "주요 발견"}
        </h3>
      </div>
      {finding.assessment ? (
        <p className="mt-2 text-sm leading-6 text-foreground">{finding.assessment}</p>
      ) : null}
      {hasRecordedCauses ? (
        <div className="mt-3">
          <p className="text-xs font-semibold text-foreground">기록된 원인</p>
          <ul className="mt-1 space-y-1 text-sm text-muted-foreground">
            {finding.recordedCauses.map((cause) => (
              <li key={cause}>• {cause}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {hasInferredCauses ? (
        <div className="mt-3">
          <p className="text-xs font-semibold text-foreground">주변 로그 기반 원인 후보</p>
          <ul className="mt-1 space-y-1 text-sm text-muted-foreground">
            {finding.inferredCauses.map((cause) => (
              <li key={cause}>• {cause}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {finding.evidenceIds?.length ? (
        <div className="mt-3 flex flex-wrap gap-1.5" aria-label="분석 근거 로그">
          {finding.evidenceIds.map((eventId) => (
            <Badge key={eventId} variant="secondary" className="font-mono font-normal">
              {eventId}
            </Badge>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function AnalysisResult({ payload }) {
  const analysis = payload?.analysis || {};
  const meta = payload?.meta || {};
  const sourceCounts = meta.sourceCounts || {};

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-primary/20 bg-primary/5 p-4">
        <div className="flex items-start gap-3">
          <Sparkles className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-foreground">
              {analysis.headline || "Observer 종합 분석"}
            </h2>
            {analysis.summary ? (
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground">
                {analysis.summary}
              </p>
            ) : null}
          </div>
        </div>
      </section>

      {analysis.findings?.length ? (
        <div className="space-y-3">
          {analysis.findings.map((finding, index) => (
            <FindingSection
              key={`${finding.category}-${finding.target}-${index}`}
              finding={finding}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-border p-4 text-sm text-muted-foreground">
          조회 범위에서 별도로 표시할 주요 발견이 없습니다.
        </div>
      )}

      {analysis.recommendedChecks?.length ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-foreground">추가 확인 항목</h3>
          </div>
          <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
            {analysis.recommendedChecks.map((item) => (
              <li key={item}>• {item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {analysis.limitations?.length ? (
        <section className="rounded-xl border border-border bg-muted/40 p-4">
          <h3 className="text-xs font-semibold text-foreground">분석 한계</h3>
          <ul className="mt-1 space-y-1 text-xs text-muted-foreground">
            {analysis.limitations.map((item) => (
              <li key={item}>• {item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-3 text-xs text-muted-foreground">
        <span>EQP 관심 상태 {meta.eqpTargetCount || 0}건</span>
        <span>TIP 관심 상태 {meta.tipTargetCount || 0}건</span>
        <span>주변 로그 {meta.contextIncludedCount || 0}건</span>
        <span>
          조회 source {Object.values(sourceCounts).reduce((total, count) => total + Number(count || 0), 0).toLocaleString()}건
        </span>
        {meta.promptTruncated ? <span>입력 크기에 맞춰 주변 로그를 축소했습니다.</span> : null}
      </div>
    </div>
  );
}

export default function ObserverAnalysisDialog({
  open,
  onOpenChange,
  isPending,
  error,
  data,
  onRetry,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid max-h-[88dvh] w-[min(920px,calc(100vw-2rem))] max-w-[min(920px,calc(100vw-2rem))] grid-rows-[auto_minmax(0,1fr)] overflow-hidden p-0 sm:max-w-[min(920px,calc(100vw-2rem))]">
        <DialogHeader className="border-b border-border px-5 py-4 pr-12">
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="size-4 text-primary" aria-hidden="true" />
            AI 종합 분석
          </DialogTitle>
          <DialogDescription>
            현재 EQP와 조회 기간의 관심 상태 및 주변 로그를 분석합니다.
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 overflow-y-auto p-5">
          {isPending ? <AnalysisLoading /> : null}
          {!isPending && error ? <AnalysisError error={error} onRetry={onRetry} /> : null}
          {!isPending && !error && data ? <AnalysisResult payload={data} /> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
