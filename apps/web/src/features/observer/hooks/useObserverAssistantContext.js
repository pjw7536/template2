import { useEffect, useMemo } from "react";

import { usePageAssistantContext } from "@/lib/assistant/pageContext";

import { observerApi } from "../api/observerApi";
import {
  buildObserverAnalysisQuestion,
  formatObserverAnalysisChatReply,
} from "../utils/observerAnalysisChat";
import { buildObserverAssistantContextKey } from "../utils/observerAssistantContext";
import { buildObserverEvidenceHref } from "../utils/observerEvidence";

const DEFAULT_OBSERVER_ANALYSIS_PROMPT =
  "현재 조회 데이터의 반복·집중 패턴, 시간적 연관성, 원인 일관성, 운영상 의미를 중요도순으로 종합 분석해줘.";

function formatScopeDescription(scope) {
  const from = String(scope?.from || "").slice(0, 10);
  const to = String(scope?.to || "").slice(0, 10);
  const period = [from, to].filter(Boolean).join(" ~ ");
  const typeCount = Array.isArray(scope?.logTypes) ? scope.logTypes.length : 0;
  return [period, `로그 유형 ${typeCount}개`].filter(Boolean).join(" · ");
}

export function useObserverAssistantContext(scope) {
  const { registerPageContext, clearPageContext } = usePageAssistantContext();
  const scopeKey = useMemo(() => buildObserverAssistantContextKey(scope), [scope]);
  const context = useMemo(() => {
    const canAnalyze = Boolean(
      scope?.eqpId && scope?.from && scope?.to && scope?.logTypes?.length
    );
    if (!canAnalyze) return null;

    return {
      key: scopeKey,
      kind: "observer",
      label: `Observer · ${scope.eqpId}`,
      description: formatScopeDescription(scope),
      placeholder: "현재 Observer 조회 데이터에 대해 질문하세요.",
      footer: "Observer · OpenWebUI",
      scope,
      defaultPrompt: DEFAULT_OBSERVER_ANALYSIS_PROMPT,
      sendMessage: async ({ prompt, history, roomId, contextKey, signal, onDelta }) => {
        const payload = await observerApi.analyzeLogsStream({
          ...scope,
          question: buildObserverAnalysisQuestion(prompt, history),
          roomId,
          contextKey,
          signal,
          onDelta,
        });
        return {
          reply: formatObserverAnalysisChatReply(payload),
          sources: [],
          segments: [],
          raw: payload,
          contextSnapshot: {
            kind: "observer",
            scope: payload?.scope || scope,
            coverage: payload?.meta || {},
            evidence: (Array.isArray(payload?.analysis?.findings)
              ? payload.analysis.findings
              : []
            ).map((finding) => {
              const evidenceIds = Array.isArray(finding?.evidenceIds)
                ? finding.evidenceIds.slice(0, 50)
                : [];
              return {
                category: finding?.category || "",
                target: finding?.target || "",
                evidenceIds,
                evidenceTargets: evidenceIds.map((evidenceId) => ({
                  id: evidenceId,
                  href: buildObserverEvidenceHref(payload?.scope || scope, evidenceId),
                })),
              };
            }),
          },
        };
      },
    };
  }, [scope, scopeKey]);

  useEffect(() => {
    if (!context) return undefined;
    registerPageContext(context);
    return () => clearPageContext(context.key);
  }, [clearPageContext, context, registerPageContext]);
}
