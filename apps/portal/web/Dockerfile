# Vite 빌드 + 정적 프리뷰를 위한 멀티 스테이지 Dockerfile

ARG NODE_BASE_IMAGE=node:20-alpine
FROM ${NODE_BASE_IMAGE} AS deps
ARG ALPINE_REPOSITORY_MIRROR=
ARG NPM_REGISTRY=
ARG NPM_STRICT_SSL=true
WORKDIR /app
RUN if [ -n "$ALPINE_REPOSITORY_MIRROR" ]; then \
        sed -i "s@https://dl-cdn.alpinelinux.org/alpine@${ALPINE_REPOSITORY_MIRROR}@g" /etc/apk/repositories; \
    fi
RUN if [ -n "$NPM_REGISTRY" ]; then \
        npm config set registry "$NPM_REGISTRY"; \
    fi \
    && npm config set strict-ssl "$NPM_STRICT_SSL"
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps

FROM ${NODE_BASE_IMAGE} AS builder
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM ${NODE_BASE_IMAGE} AS runner
ARG ALPINE_REPOSITORY_MIRROR=
ARG NPM_REGISTRY=
ARG NPM_STRICT_SSL=true
WORKDIR /app
ENV NODE_ENV=production
RUN if [ -n "$ALPINE_REPOSITORY_MIRROR" ]; then \
        sed -i "s@https://dl-cdn.alpinelinux.org/alpine@${ALPINE_REPOSITORY_MIRROR}@g" /etc/apk/repositories; \
    fi
RUN if [ -n "$NPM_REGISTRY" ]; then \
        npm config set registry "$NPM_REGISTRY"; \
    fi \
    && npm config set strict-ssl "$NPM_STRICT_SSL"
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/scripts/write-runtime-env.mjs ./scripts/write-runtime-env.mjs
RUN npm install -g serve
EXPOSE 3000
CMD ["sh", "-c", "node /app/scripts/write-runtime-env.mjs && exec serve -s dist -l 3000"]
