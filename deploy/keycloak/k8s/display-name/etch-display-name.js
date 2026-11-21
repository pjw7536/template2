// 사용자 표시용 클레임을 만듭니다. Keycloak 계정 이름에는 쓰지 않습니다.
var displayName = String(user.getFirstAttribute("display_name") || "").trim();
var loginId = String(user.getFirstAttribute("loginid") || "").trim();
displayName && loginId ? displayName + "(" + loginId + ")" : displayName || loginId || null;
