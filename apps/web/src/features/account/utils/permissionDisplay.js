export const PERMISSION_PAGE_SIZE = 20

export const ACCESS_ROLE_OPTIONS = [
  { value: "user", label: "일반 사용자" },
  { value: "admin", label: "관리자" },
]

export const ACCESS_ACTION_LABELS = {
  request: "승인 요청",
  approve: "승인",
  reject: "거절",
  grant: "직접 부여",
  revoke: "회수",
  reset_to_policy: "수동 설정 해제",
  change_role: "역할 변경",
  policy_create: "자동 규칙 추가",
  policy_update: "자동 규칙 수정",
  policy_delete: "자동 규칙 삭제",
  scope_create: "권한 범위 생성",
  scope_update: "권한 범위 수정",
  scope_delete: "권한 범위 삭제",
  data_scope_grant: "소속 데이터 범위 부여",
  data_scope_revoke: "소속 데이터 범위 회수",
  data_scope_change: "소속 데이터 범위 방식 변경",
  affiliation_role_grant: "소속 역할 부여",
  affiliation_role_change: "소속 역할 변경",
  affiliation_role_revoke: "소속 역할 회수",
  affiliation_create: "소속 생성",
  affiliation_update: "소속 정보 변경",
  affiliation_activate: "소속 활성화",
  affiliation_deactivate: "소속 비활성화",
}

export const ACCESS_STATUS_LABELS = {
  allowed: "허용",
  pending: "대기",
  denied: "차단",
  not_requested: "미요청",
  inactive: "비활성",
}

export const ACCESS_SOURCE_LABELS = {
  portal_access_required: "Portal 차단 우선",
  explicit_allowed: "개별 허용",
  explicit_denied: "개별 차단",
  explicit_pending: "개별 승인 대기",
  policy_department: "부서 자동 규칙",
  superuser_bypass: "슈퍼유저 우회",
  none: "결정 기준 없음",
  scope_inactive: "권한 범위 비활성",
  scope_not_found: "권한 범위 없음",
}

export const ACCESS_ROLE_LABELS = {
  ...Object.fromEntries(
    ACCESS_ROLE_OPTIONS.map((option) => [option.value, option.label]),
  ),
  viewer: "조회자",
  member: "구성원",
  manager: "관리자",
}

export const ACCESS_RULE_TYPE_LABELS = {
  department: "부서 일치",
}

const MUTATION_ERROR_LABELS = {
  duplicate_policy_rule: "동일한 자동 접근 규칙이 이미 등록되어 있습니다.",
  forbidden: "권한 관리 권한이 없습니다.",
  invalid_policy_rule: "적용 조건 형식을 확인해 주세요.",
  invalid_request: "요청 형식을 확인해 주세요.",
  invalid_role: "지원하지 않는 권한입니다.",
  invalid_scope: "적용할 권한 범위를 확인해 주세요.",
  invalid_status_transition: "이미 상태가 변경되었습니다. 목록을 새로고침해 주세요.",
  immutable_access_bypass: "슈퍼유저의 접근 권한은 변경할 수 없습니다.",
  affiliation_scope_not_supported: "이 앱은 소속 데이터 범위를 사용하지 않습니다.",
  allowed_app_access_required_for_all: "전체 범위는 앱 접근을 먼저 직접 허용해야 합니다.",
  invalid_affiliation_ids: "선택한 소속을 다시 확인해 주세요.",
  non_manual_affiliation_grants_immutable: "자동 부여된 소속 범위는 이 화면에서 변경할 수 없습니다.",
  reason_required_for_all: "전체 소속 범위에는 변경 사유가 필요합니다.",
  reason_required: "권한 변경 사유가 필요합니다.",
  scope_required: "적용할 권한 범위를 선택해 주세요.",
}

export function getPermissionMutationErrorMessage(error, fallback) {
  const message = error?.message || ""
  if (MUTATION_ERROR_LABELS[message]) return MUTATION_ERROR_LABELS[message]
  if (!message || message.startsWith("Failed to") || /failed to fetch|networkerror/i.test(message)) {
    return fallback
  }
  return message
}

export function formatPermissionCount(value) {
  return Number(value || 0).toLocaleString("ko-KR")
}

export function buildAccessScopeOptions(scopes) {
  return (Array.isArray(scopes) ? scopes : []).map((scope) => ({
    value: scope.key,
    label: scope.name || scope.key,
  }))
}

export function getAuditIdentity(user) {
  return user?.knoxId || user?.username || user?.email || (user?.id ? `#${user.id}` : "-")
}

function formatAuditValue(field, value) {
  if (value === undefined || value === null || value === "") return "-"
  if (field === "explicitStatus") return ACCESS_STATUS_LABELS[value] || value
  if (field === "role") return ACCESS_ROLE_LABELS[value] || value
  if (field === "ruleType") return ACCESS_RULE_TYPE_LABELS[value] || value
  if (field === "isActive") return value ? "사용" : "사용 안 함"
  if (field === "requestable") return value ? "가능" : "불가"
  if (field === "source") return ACCESS_SOURCE_LABELS[value] || value
  if (field === "dataScopeMode") {
    return { default: "현재 소속 + 선택 소속", all: "모든 활성 소속" }[value] || value
  }
  return String(value)
}

export function getAuditChanges(row) {
  const fields = [
    "explicitStatus",
    "role",
    "isActive",
    "ruleType",
    "value",
    "source",
    "key",
    "name",
    "scopeType",
    "requestable",
    "dataScopeMode",
    "affiliationId",
    "grantedBy",
  ]
  return fields.flatMap((field) => {
    const before = row.before?.[field]
    const after = row.after?.[field]
    if (before === undefined && after === undefined) return []
    if (before === after) return []
    const label = {
      explicitStatus: "명시 상태",
      role: "접근 역할",
      isActive: "사용 여부",
      ruleType: "적용 기준",
      value: "적용 조건",
      source: "결정 기준",
      key: "키",
      name: "이름",
      scopeType: "권한 범위 유형",
      requestable: "요청 가능",
      dataScopeMode: "소속 데이터 범위",
      affiliationId: "소속 ID",
      grantedBy: "부여자 ID",
    }[field]
    return [`${label}: ${formatAuditValue(field, before)} -> ${formatAuditValue(field, after)}`]
  })
}
