# ReleaseGuard

ReleaseGuard is a small Flask service that helps a DevOps team answer one question before deploying: **is this application ready for release?**

It reads the target environment and application version from environment variables, runs a few release checks, and reports the result as JSON and as an HTML dashboard.

## Endpoints

| Method | Path       | Description |
|--------|------------|-------------|
| GET    | `/`        | HTML dashboard that explains ReleaseGuard and shows the current release status. |
| GET    | `/health`  | Liveness check: `{"status": "ok", "service": "ReleaseGuard", "timestamp": "..."}` |
| GET    | `/release` | Application name, version, environment, `release_ready` flag and individual check results. |

Unknown routes and unsupported methods return JSON errors (for example `404` and `405`). Unexpected server errors are logged and return a generic JSON `500` without internal details.

## Configuration

| Variable      | Default       | Notes |
|---------------|---------------|-------|
| `APP_ENV`     | `development` | One of `development`, `staging`, `production` (case-insensitive). |
| `APP_VERSION` | `0.0.0-dev`   | Semantic version, e.g. `1.4.2` or `1.5.0-rc.1`. |
| `PORT`        | `5000`        | Only used by `python app.py` for local development. |

Blank values fall back to the defaults.

### Release checks

A release is ready only when **all** checks pass:

1. `environment_is_known`: `APP_ENV` is one of the allowed environments.
2. `version_is_semantic`: `APP_VERSION` matches `MAJOR.MINOR.PATCH` with an optional `-prerelease` suffix.
3. `production_uses_stable_version`: production must not use a pre-release version such as `1.5.0-rc.1`.

## Project layout

```
app.py                     Flask application (routes, settings, readiness checks, error handlers)
templates/index.html       HTML dashboard rendered at GET /
tests/test_app.py          pytest tests for every endpoint and the error handlers
pytest.ini                 pytest configuration (test path and import path)
requirements.txt           Pinned runtime dependencies (Flask, gunicorn)
requirements-dev.txt       Runtime dependencies plus pytest and pip-audit
Dockerfile                 Production image running gunicorn as a non-root user
.dockerignore              Keeps tests, venvs, git data and secrets out of the build context
.gitignore                 Ignores virtualenvs, caches and secret files such as .env
.github/workflows/ci.yml   GitHub Actions pipeline: test, audit, build, smoke test
```

## Installation

Requires Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

## Run locally

```bash
APP_ENV=staging APP_VERSION=1.4.2 python app.py
```

Then open http://127.0.0.1:5000/ or:

```bash
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:5000/release
```

## Testing

```bash
python -m pytest
```

Dependency vulnerability audit:

```bash
pip-audit -r requirements.txt -r requirements-dev.txt
```

## Docker

Build the image:

```bash
docker build -t releaseguard:local .
```

Run it (gunicorn listens on port 8000 inside the container):

```bash
docker run --rm -p 8000:8000 -e APP_ENV=production -e APP_VERSION=1.4.2 releaseguard:local
```

The image:

- uses `python:3.12-slim` and installs only runtime dependencies,
- runs as the unprivileged `app` user (application files are owned by root and are read-only for that user),
- serves the app with gunicorn instead of the Flask development server,
- defines a `HEALTHCHECK` against `/health`.

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main` and pull requests that target `main`. It:

1. checks out the code without persisting the GitHub token,
2. sets up Python 3.12 and installs application and test dependencies,
3. runs `pytest`,
4. runs `pip-audit` against both requirements files,
5. builds the Docker image (it is **not** pushed anywhere),
6. starts the container, calls `/health` and confirms the process is not running as root.

Any failing step fails the job. The workflow token only has `contents: read` permission, and the workflow uses no secrets.

## Security notes

- Credentials do not belong in this repository. Pass configuration through environment variables or your platform's secret store. `.env` files are ignored by git and Docker.
- Keep dependencies pinned and let CI's `pip-audit` step flag known vulnerabilities.
