// 개발 PC 기본값입니다. 배포 이미지는 이 파일을 env로 다시 만듭니다.
// 앱 열은 Keycloak /iam 그룹의 카탈로그(make keycloak-access-apply가 저장)에서 읽습니다.
window.__IAM_CONFIG__ = {
  keycloakUrl: "http://localhost:8180",
  realm: "portal",
  clientId: "iam",
}
