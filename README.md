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
