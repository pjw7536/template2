# Dockerfile의 구문 버전을 지정
# (1.7 이상을 사용하면 최신 기능 지원 — 예: heredoc, 캐시 관리 등)

###############################################
# 1️⃣ 의존성 설치 단계 (deps)
###############################################
FROM node:20-alpine AS deps
# - Node.js 20 버전, Alpine 리눅스 기반 (가볍고 빠름)
# - "AS deps" → 이 단계를 나중에 참조할 수 있도록 이름 지정

WORKDIR /app
# 컨테이너 안의 작업 디렉토리를 /app으로 설정

COPY package.json package-lock.json ./
# 패키지 정보 파일만 먼저 복사 (빌드 캐시 최적화용)

RUN npm install

###############################################
# 2️⃣ 빌드 단계 (builder)
###############################################
FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# Next.js의 텔레메트리(사용 통계 전송) 비활성화

COPY --from=deps /app/node_modules ./node_modules
# 1단계에서 설치한 node_modules를 그대로 복사
# → 다시 npm install 하지 않아도 됨

COPY . .
# 전체 프로젝트 복사 (소스 코드 포함)

ARG NEXT_PUBLIC_BACKEND_URL=/api
ENV NEXT_PUBLIC_BACKEND_URL=${NEXT_PUBLIC_BACKEND_URL}
# 빌드 시점 환경변수 설정
# - 예: 백엔드 API 주소를 프론트엔드 빌드 시에 삽입

RUN npm run build
# Next.js 프로젝트를 빌드하여 `.next` 폴더 생성
# (정적 리소스 및 서버 렌더링 코드가 여기 저장됨)

###############################################
# 3️⃣ 실행 단계 (runner)
###############################################
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# 실행 시에도 텔레메트리 비활성화

ARG NEXT_PUBLIC_BACKEND_URL=/api
ENV NEXT_PUBLIC_BACKEND_URL=${NEXT_PUBLIC_BACKEND_URL}
# 런타임 환경에서도 동일한 환경변수 적용

COPY package.json package-lock.json ./
RUN npm install --omit=dev
# 실행 환경에서는 devDependencies 제외
# → 빌드 도구 등 불필요한 패키지 제거로 이미지 경량화

COPY --from=builder /app/.next ./.next
# 빌드 결과물(.next)을 복사

COPY --from=builder /app/public ./public
# 정적 리소스(public 폴더) 복사

EXPOSE 3000
# 컨테이너 외부에서 접근할 포트 설정 (Next.js 기본 포트)

CMD ["npm", "run", "start"]
# 컨테이너 시작 시 실행할 명령
# Next.js 프로덕션 서버를 실행 (next start)
