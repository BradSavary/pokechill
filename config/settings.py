"""
Django settings for PokéChill.

All environment-specific values are read from environment variables, so the
same code runs locally (SQLite, debug on) and on Vercel (Neon PostgreSQL,
debug off) without any separate settings file.

Reference: https://docs.djangoproject.com/en/5.2/ref/settings/
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable ("1", "true", "yes" are truthy)."""
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes"}


# --- Security -------------------------------------------------------------

# Debug is on by default for local development; Vercel sets DJANGO_DEBUG=0.
DEBUG = env_bool("DJANGO_DEBUG", default=True)

# In production the secret key MUST come from the environment. A hard-coded
# fallback is only acceptable while debugging locally.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")
    SECRET_KEY = "dev-only-insecure-key"

# Comma-separated list, e.g. "pokechill.vercel.app,.vercel.app"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
if DEBUG:
    ALLOWED_HOSTS += ["localhost", "127.0.0.1"]


# --- Applications ---------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Project apps
    "pokedex",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Project-wide templates (base layout, footer...) live in /templates
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Database -------------------------------------------------------------

# DATABASE_URL selects the database: absent -> local SQLite file,
# set (e.g. "postgresql://...neon.tech/db") -> Neon PostgreSQL in production.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        # Serverless functions are short-lived: don't keep connections open.
        conn_max_age=0,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Authentication -------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Internationalization -------------------------------------------------

LANGUAGE_CODE = "en-us"

# All dates are stored in UTC. Paris time is only used by game rules
# (day/night cycle, daily quest reset), which will convert explicitly.
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# --- Static files ---------------------------------------------------------

STATIC_URL = "static/"
# Source static files (CSS, sprites, cries) committed in the repository
STATICFILES_DIRS = [BASE_DIR / "static"]
# Destination of `collectstatic`, served by Vercel's CDN in production
STATIC_ROOT = BASE_DIR / "staticfiles"
