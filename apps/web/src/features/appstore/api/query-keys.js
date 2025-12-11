// src/features/appstore/api/query-keys.js
// Appstore React Query 키 정의

export const appstoreQueryKeys = {
  all: ["appstore"],
  apps: () => ["appstore", "apps"],
  app: (appId) => ["appstore", "apps", appId],
  comments: (appId) => ["appstore", "apps", appId, "comments"],
}
