"""ReleaseGuard: a small Flask service that reports whether an application is ready for release."""

import os
import re
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template
from werkzeug.exceptions import HTTPException

APP_NAME = "ReleaseGuard"
DEFAULT_ENVIRONMENT = "development"
DEFAULT_VERSION = "0.0.0-dev"
ALLOWED_ENVIRONMENTS = ("development", "staging", "production")

# Semantic version: MAJOR.MINOR.PATCH with an optional pre-release suffix (e.g. 1.4.2 or 1.4.2-rc.1).
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")

app = Flask(__name__)


def get_settings():
    """Read settings from environment variables at request time, falling back to safe defaults."""
    environment = os.environ.get("APP_ENV", "").strip().lower() or DEFAULT_ENVIRONMENT
    version = os.environ.get("APP_VERSION", "").strip() or DEFAULT_VERSION
    return environment, version


def evaluate_readiness(environment, version):
    """Run the release checks and return (ready, checks)."""
    is_semver = bool(SEMVER_PATTERN.match(version))
    is_prerelease = "-" in version

    checks = [
        {
            "name": "environment_is_known",
            "passed": environment in ALLOWED_ENVIRONMENTS,
            "detail": f"Environment '{environment}' must be one of: {', '.join(ALLOWED_ENVIRONMENTS)}.",
        },
        {
            "name": "version_is_semantic",
            "passed": is_semver,
            "detail": f"Version '{version}' must follow MAJOR.MINOR.PATCH (optionally -prerelease).",
        },
        {
            "name": "production_uses_stable_version",
            "passed": environment != "production" or (is_semver and not is_prerelease),
            "detail": "Production releases must use a stable version without a pre-release suffix.",
        },
    ]
    ready = all(check["passed"] for check in checks)
    return ready, checks


@app.get("/")
def dashboard():
    environment, version = get_settings()
    ready, checks = evaluate_readiness(environment, version)
    return render_template(
        "index.html",
        app_name=APP_NAME,
        environment=environment,
        version=version,
        ready=ready,
        checks=checks,
    )


@app.get("/health")
def health():
    return jsonify(
        status="ok",
        service=APP_NAME,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/release")
def release():
    environment, version = get_settings()
    ready, checks = evaluate_readiness(environment, version)
    return jsonify(
        application=APP_NAME,
        version=version,
        environment=environment,
        release_ready=ready,
        checks=checks,
    )


@app.errorhandler(HTTPException)
def handle_http_error(error):
    """Return JSON instead of HTML for HTTP errors such as 404 and 405."""
    return jsonify(error=error.name, message=error.description, status=error.code), error.code


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """Log unexpected errors and return a generic message without leaking internals."""
    app.logger.exception("Unhandled error: %s", error)
    return jsonify(error="Internal Server Error", message="An unexpected error occurred.", status=500), 500


if __name__ == "__main__":
    # Local development only. In containers the app is served by gunicorn (see Dockerfile).
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False)
