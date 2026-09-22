// 파일 경로: src/features/appstore/api/queryKeys.js
// Appstore React Query 키 정의

export const appstoreQueryKeys = {
  all: ["appstore"],
  apps: () => ["appstore", "apps"],
  app: (appId) => ["appstore", "apps", appId],
  comments: (appId) => ["appstore", "apps", appId, "comments"],
}
