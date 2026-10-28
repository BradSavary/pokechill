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

# Shared secret of the Vercel Crons: Vercel sends it in the Authorization
# header of each scheduled call (ranch/internal_views.py). Empty (locally):
# the internal URLs refuse every request.
CRON_SECRET = os.environ.get("CRON_SECRET", "")
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
    "pokedex",  # reference catalogue: species, types, moves
    "accounts",  # guest mode, sign up, log in (no model: uses Django's User)
    "ranch",  # the player's game state: Player, collection, Welcome area
]

MIDDLEWARE = [
    # First, so that its timing covers the whole request
    "config.timing.ServerTimingMiddleware",
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
                # Adds `is_guest` to every template (account box of the sidebar)
                "accounts.context_processors.account",
            ],
            # {% load assets %}: versioned URLs of the CSS and scripts (config/assets.py)
            "libraries": {"assets": "config.assets"},
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
        # Keep the connection for up to 60 s and reuse it for the next
        # requests: a Vercel function stays warm between close visits, and
        # opening a connection to Neon (TCP, TLS, login) costs more than a few
        # queries. Health checks test a reused connection first (Neon may
        # have closed it while the function slept) and reopen it if needed.
        conn_max_age=60,
        conn_health_checks=True,
    )
}

if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    # Neon's pooled connection (PgBouncer, transaction mode) can't keep the
    # server-side cursors Django uses for .iterator(): disable them.
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Authentication -------------------------------------------------------

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "ranch:index"
LOGOUT_REDIRECT_URL = "pokedex:index"

# Sessions last one year (default: two weeks). For a guest, the session cookie
# IS the game: losing it means losing the save. An idle game is played over
# months, so registered players also stay logged in.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365

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
# Destination of `collectstatic`, served by Vercel's CDN in production.
# Vercel runs collectstatic itself during the build when STATIC_ROOT is set.
STATIC_ROOT = BASE_DIR / "staticfiles"


# --- Production security ---------------------------------------------------

if not DEBUG:
    # Vercel terminates HTTPS and forwards requests over HTTP with this header:
    # trusting it lets Django know the original request was secure.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Cookies are only sent over HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Tell browsers to always use HTTPS for this site (one year, HSTS)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365

# Deployment checks (`manage.py check --deploy`) that don't apply here:
SILENCED_SYSTEM_CHECKS = [
    "security.W008",  # HTTP -> HTTPS redirect: already done by Vercel's edge
    "security.W005",  # HSTS on subdomains: we don't own the vercel.app domain
    "security.W021",  # HSTS preload list: same reason
]
