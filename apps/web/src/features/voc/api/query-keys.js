// src/features/voc/api/query-keys.js
// VOC(Q&A) 데이터의 React Query 키를 한곳에서 관리합니다.

export const vocQueryKeys = {
  all: ["voc"],
  posts: () => ["voc", "posts"],
}
