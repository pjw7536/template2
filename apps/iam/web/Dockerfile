ARG NODE_BASE_IMAGE=node:22-alpine
ARG NGINX_BASE_IMAGE=nginx:1.30-alpine

FROM ${NODE_BASE_IMAGE} AS build
ARG NPM_REGISTRY=https://registry.npmjs.org/
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --registry "$NPM_REGISTRY" --no-audit --no-fund
COPY . .
RUN npm run build

FROM ${NGINX_BASE_IMAGE}
LABEL org.opencontainers.image.title="Etch Members Web" \
      org.opencontainers.image.description="Etch Members web interface for organization, app access, affiliation imports, and workload reporting."
COPY nginx.conf /etc/nginx/iam.conf
COPY --from=build /app/dist/ /usr/share/nginx/html/
USER 101:101
EXPOSE 8080
ENTRYPOINT ["nginx", "-c", "/etc/nginx/iam.conf", "-g", "daemon off;"]
