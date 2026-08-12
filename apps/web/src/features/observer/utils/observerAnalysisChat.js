const MAX_ANALYSIS_QUESTION_CHARS = 2400;
const MAX_HISTORY_MESSAGE_CHARS = 500;

function normalizeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function appendList(lines, title, values) {
  const items = Array.isArray(values) ? values.map(normalizeText).filter(Boolean) : [];
  if (!items.length) return;
  lines.push(`**${title}**`);
  items.forEach((item) => lines.push(`- ${item}`));
  lines.push("");
}

function formatDate(value) {
  const normalized = normalizeText(value);
  return normalized ? normalized.slice(0, 10) : "";
}

export function buildObserverAnalysisQuestion(prompt, history = []) {
  const currentPrompt = normalizeText(prompt);
  const previousMessages = (Array.isArray(history) ? history : [])
    .filter((message) => ["user", "assistant"].includes(message?.role))
    .map((message) => ({
      role: message.role,
      content: normalizeText(message?.content),
    }))
    .filter(
      (message) =>
        message.content &&
        !(message.role === "user" && message.content === currentPrompt)
    )
    .slice(-4);
  const historySuffix = previousMessages.length
    ? `\n\n현재 조회 조건에서의 이전 대화:\n${previousMessages
        .map(
          (message) =>
            `- ${message.role === "user" ? "사용자" : "Assistant"}: ${message.content.slice(
              0,
              MAX_HISTORY_MESSAGE_CHARS
            )}`
        )
        .join("\n")}`
    : "";
  return `${currentPrompt}${historySuffix}`.slice(0, MAX_ANALYSIS_QUESTION_CHARS);
}

export function formatObserverAnalysisChatReply(payload) {
  const analysis = payload?.analysis || {};
  const meta = payload?.meta || {};
  const scope = payload?.scope || {};
  const lines = [
    `### ${normalizeText(analysis.headline) || "Observer 종합 분석"}`,
    "",
  ];

  if (normalizeText(analysis.summary)) {
    lines.push(normalizeText(analysis.summary), "");
  }

  const findings = Array.isArray(analysis.findings) ? analysis.findings : [];
  findings.forEach((finding) => {
    const category = normalizeText(finding?.category) || "분석";
    const target = normalizeText(finding?.target) || "주요 발견";
    lines.push(`#### ${category} · ${target}`, "");
    if (normalizeText(finding?.assessment)) {
      lines.push(normalizeText(finding.assessment), "");
    }
    appendList(lines, "기록된 원인", finding?.recordedCauses);
    appendList(lines, "주변 로그 기반 원인 후보", finding?.inferredCauses);
    appendList(lines, "근거 로그", finding?.evidenceIds);
  });

  appendList(lines, "추가 확인 항목", analysis.recommendedChecks);
  appendList(lines, "분석 한계", analysis.limitations);

  const period = [formatDate(scope.from), formatDate(scope.to)].filter(Boolean).join(" ~ ");
  const coverage = [
    `EQP 관심 상태 ${Number(meta.eqpTargetCount || 0).toLocaleString()}건`,
    `TIP 관심 상태 ${Number(meta.tipTargetCount || 0).toLocaleString()}건`,
    `주변 로그 ${Number(meta.contextIncludedCount || 0).toLocaleString()}건`,
  ].join(" · ");
  lines.push("---", `분석 범위: ${normalizeText(scope.eqpId) || "EQP 미상"}${period ? ` · ${period}` : ""}`);
  lines.push(`분석 입력: ${coverage}`);
  const version = [
    normalizeText(meta.analysisModel),
    normalizeText(meta.promptVersion),
  ].filter(Boolean).join(" · ");
  if (version) lines.push(`분석 버전: ${version}`);

  return lines.join("\n").trim();
}
