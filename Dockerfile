# ReleaseGuard production image.
FROM python:3.12-slim

# Do not write .pyc files, flush logs immediately and keep pip quiet and cache-free.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=development \
    APP_VERSION=0.0.0-dev

WORKDIR /app

# Create an unprivileged system user with no login shell and no home directory.
RUN groupadd --system app && \
    useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app

# Install dependencies first so this layer is cached when only the source code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only what the application needs at runtime; files stay owned by root (read-only for the app user).
COPY app.py .
COPY templates/ templates/

USER app

EXPOSE 8000

# Use Python for the health check because the slim image does not include curl.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "app:app"]
