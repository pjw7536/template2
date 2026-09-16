import { STATUS_OPTIONS } from "./constants"

export const EMPTY_POSTS = []

const EMPTY_STATUS_COUNTS = STATUS_OPTIONS.reduce(
  (acc, option) => ({ ...acc, [option.value]: 0 }),
  {},
)

export function buildVocStatusCounts(posts) {
  return posts.reduce((acc, post) => {
    if (post?.status && typeof acc[post.status] === "number") {
      acc[post.status] += 1
    }
    return acc
  }, { ...EMPTY_STATUS_COUNTS })
}

export function getVocPostAuthorKey(post) {
  return post?.author?.id ?? null
}
