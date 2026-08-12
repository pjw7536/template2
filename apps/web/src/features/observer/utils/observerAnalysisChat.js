const MAX_ANALYSIS_QUESTION_CHARS = 2400;
const MAX_HISTORY_MESSAGE_CHARS = 500;

function normalizeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeList(values, limit) {
  return Array.isArray(values)
    ? values.map(normalizeText).filter(Boolean).slice(0, limit)
    : [];
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
    ? `\n\n같은 대화방의 이전 대화(질문 의도 파악용 배경 문맥):\n${previousMessages
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

export function formatObserverAnalysisStreamItem(item) {
  const itemType = normalizeText(item?.type);
  if (itemType === "headline") {
    const text = normalizeText(item?.text);
    return text ? `### ${text}\n\n` : "";
  }
  if (itemType === "summary") {
    const text = normalizeText(item?.text);
    return text ? `${text}\n\n#### 주요 분석\n\n` : "";
  }

  if (itemType === "finding") {
    const label = [normalizeText(item?.category), normalizeText(item?.target)]
      .filter(Boolean)
      .join(" · ");
    const assessment = normalizeText(item?.assessment);
    return assessment
      ? `- ${label ? `**${label}**: ` : ""}${assessment}\n`
      : "";
  }
  if (itemType === "limitations") {
    const limitations = normalizeList(item?.values, 3);
    return limitations.length
      ? `\n> 분석 한계: ${limitations.join(" ")}\n\n`
      : "";
  }

  return "";
}

export function formatObserverAnalysisChatReply(payload) {
  const analysis = payload?.analysis || {};
  const lines = [
    `### ${normalizeText(analysis.headline) || "Observer 종합 분석"}`,
    "",
  ];

  if (normalizeText(analysis.summary)) {
    lines.push(normalizeText(analysis.summary), "");
  }

  const findings = (Array.isArray(analysis.findings) ? analysis.findings : [])
    .map((finding) => ({
      label: [normalizeText(finding?.category), normalizeText(finding?.target)]
        .filter(Boolean)
        .join(" · "),
      assessment: normalizeText(finding?.assessment),
    }))
    .filter((finding) => finding.assessment)
    .slice(0, 5);
  if (findings.length) {
    lines.push("#### 주요 분석", "");
    findings.forEach(({ label, assessment }) => {
      lines.push(`- ${label ? `**${label}**: ` : ""}${assessment}`);
    });
    lines.push("");
  }

  const limitations = normalizeList(analysis.limitations, 3);
  if (limitations.length) {
    lines.push(`> 분석 한계: ${limitations.join(" ")}`);
  }

  return lines.join("\n").trim();
}
