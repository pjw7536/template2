# Template2 Monorepo

This repository hosts a mono-repo that separates the customer-facing Next.js frontend from a new Django-powered backend. Each application lives under the `apps/` directory and can be developed independently while sharing a single source control and deployment pipeline.

## Structure

- `apps/web` – existing Next.js frontend (moved unchanged from the project root)
- `apps/api` – Django backend scaffold configured for REST development
- `package.json` – npm workspace definition with helper scripts for the frontend workspace

## Getting Started

### Frontend (Next.js)

```bash
npm install
npm run web:dev
```

The commands above install dependencies in workspace mode and start the Next.js development server within `apps/web`.

### Backend (Django)

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

The Django project ships with a basic configuration, REST framework, and a `/health/` endpoint you can call from the frontend or monitoring tools. Environment variables can be stored in `.env` files loaded with `python-dotenv` or another mechanism if desired.

## Next Steps

- Connect Django authentication endpoints to the Next.js client.
- Move any remaining API routes out of Next.js and replace them with requests to Django.
- Expand shared tooling (ESLint, Prettier, CI) at the repository root for both apps.

## Docker Deployment

The repository ships with a production-ready Docker Compose stack that builds the Django API, the Next.js frontend, and an Nginx reverse proxy on a shared Docker network. The proxy exposes port `80` on the host while routing `/<api|static>` requests to the backend container and all other traffic to the frontend server.

```bash
docker compose up --build
```

The command above builds the application images, runs database migrations, collects static files, and starts all three containers. Static assets collected from Django are shared with Nginx through a named volume so they can be served directly. The frontend is compiled with `NEXT_PUBLIC_BACKEND_URL=/api`, allowing browser requests to flow through the proxy without additional configuration.

### Hot-reload Development Stack

For local development with automatic reloads inside the containers, combine the new override file with the production stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

This command keeps the production build definitions while swapping in development-friendly entrypoints. Django runs via `python manage.py runserver` with your source mounted into the container, and Next.js executes `npm run dev` after installing/updating dependencies in a dedicated `node_modules` volume. Port `8000` exposes the API with live code reloads, and port `3000` serves the Next.js dev server pointing at the API container.

Nginx is also part of the override stack, so `http://localhost:8080` proxies both services (including `/static` assets) while preserving HMR and websocket upgrades from the Next.js process.

## Environment configuration

Reverse proxy deployments often become hard to reason about because multiple services need to agree on the same host names. The repository now provides curated environment files under `env/` that separate shared Django defaults from stage-specific overrides and align the Next.js app with the proxy setup:

- `env/api.common.env` – database, proxy, and login defaults that apply everywhere.
- `env/api.dev.env` / `env/api.prod.env` – values that differ per environment (debug toggles, allowed hosts, and HTTPS enforcement).
- `env/web.dev.env` / `env/web.prod.env` – frontend-specific variables such as `NEXTAUTH_URL` and the backend URL that Next.js should call.

Both `docker-compose.yml` and `docker-compose.dev.yml` automatically load the correct combination of files, so switching between development and production only requires editing the stage-specific files. Update the placeholder domain (`example.com`) in the production files to match your public host and rotate `NEXTAUTH_SECRET`/`DJANGO_SECRET_KEY` with strong values before deploying.
