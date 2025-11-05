# Django API Service

This directory contains the Django backend that replaces the former Next.js API routes. The project is preconfigured with Django REST Framework and CORS support so the frontend can communicate over HTTP.

## Available commands

```bash
python manage.py runserver           # Start the local development server
python manage.py migrate             # Apply database migrations
python manage.py createsuperuser     # Create an admin user
```

The default database is SQLite, but you can override the engine and connection settings via the `DJANGO_DB_*` environment variables defined in `config/settings.py`.

A simple `GET /health/` endpoint is provided for monitoring and for wiring up the frontend during the migration period.
