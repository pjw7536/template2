ARG PYTHON_BASE_IMAGE=python:3.12-slim
FROM ${PYTHON_BASE_IMAGE}
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN PIP_INDEX_URL="$PIP_INDEX_URL" PIP_TRUSTED_HOST="$PIP_TRUSTED_HOST" pip install --no-cache-dir -r requirements.txt
COPY workload.py ./
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--threads", "4", "--access-logfile", "-", "workload:application_from_env()"]
