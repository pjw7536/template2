# Web

React 19 + React Router + Vite 기반의 프론트엔드 앱입니다. SPA 빌드로 일관된 개발 경험을 제공합니다.

## 개발 서버 실행

```bash
npm install
npm run dev
```

- 기본 포트: [http://localhost:3000](http://localhost:3000)
- 환경 변수는 `.env` 또는 `.env.local` 파일에 `VITE_` 접두사로 정의합니다. (예: `VITE_BACKEND_URL`)

## 프로덕션 빌드

```bash
npm run build
```

생성된 정적 자산은 `dist/` 디렉터리에 위치하며, `npm run preview`로 간단히 확인할 수 있습니다.

## 코드 품질

```bash
npm run lint
```

ESLint flat config 기반으로 React/JSX 규칙과 Hooks 검사 규칙을 수행합니다.
