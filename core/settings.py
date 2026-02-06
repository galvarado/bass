# core/settings.py
from pathlib import Path
import os
from dotenv import load_dotenv

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

# ==== Sentry ====

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[
        DjangoIntegration(),
        LoggingIntegration(
            level="ERROR",
            event_level="ERROR",
        ),
    ],
    environment=os.getenv("ENVIRONMENT", "production"),
    send_default_pii=True,    # incluye user.id, ip, etc
)

# ==== Paths & env ====
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ==== Seguridad / Entorno ====
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-cambia-esto")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
BANXICO_SIE_TOKEN = os.getenv(
    "BANXICO_SIE_TOKEN",
    "ac2bdbef4b2aaa29af891d4619537a50f2dd88b107587ba8bcd221e33eac3b7b",
)
# ==== Apps ====
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_postalcodes_mexico.apps.DjangoPostalcodesMexicoConfig",
    # Tus apps
    "accounts",
    "collection",
    "ctpat",
    "finance",
    "operators",
    "customers",
    "locations",
    "settlement",
    "trips",
    "trucks",
    "warehouse",
    "workshop",
    "suppliers",
    "common",
    "goods",
    "audit.apps.AuditConfig",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "audit.middleware.StoreRequestMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

]

ROOT_URLCONF = "core.urls"

# ==== Templates ====
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],   # <— tu carpeta global de templates
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# ==== Base de datos ====
# Cambia DB_ENGINE a 'sqlite' si prefieres SQLite.
DB_ENGINE = os.getenv("DB_ENGINE", "postgres")  # "postgres" | "sqlite"

if DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "transporte"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }

# ==== Password validation ====
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Audit (Bitacora)
AUDIT_EXCLUDE = {"audit.AuditLog", "contenttypes.ContentType", "sessions.Session", "common.ExchangeRate"}
AUDIT_FIELDS_EXCLUDE = {
    "auth.User": ["password"],
}

# ==== Internacionalización ====
LANGUAGE_CODE = "es"                   # español
TIME_ZONE = "America/Mexico_City"      # zona horaria México
USE_I18N = True
USE_TZ = True

# ==== Archivos estáticos / media ====
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]      # para desarrollo
STATIC_ROOT = BASE_DIR / "staticfiles"        # para collectstatic en prod
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==== Email (placeholder, ajusta según tu proveedor) ====
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")

# ==== Seguridad (cuando pases a producción) ====
# CSRF_TRUSTED_ORIGINS = ["https://tu-dominio.com"]
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True

# Auth flow
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "post_login_redirect"   # o "trip_list" si prefieres
LOGOUT_REDIRECT_URL = "login"
OPENEXCHANGE_APP_ID = "c98896f4617b43779470c2d5170f285f"
OPENEXCHANGE_BASE_URL = "https://openexchangerates.org/api/latest.json"
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

LOG_DIR = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": f"{LOG_DIR}/django.log",
            "maxBytes": 50 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
            "level": "INFO",
        },
    },
    "loggers": {
        # 👇 Este es el que escribe los 500 (traceback incluido)
        "django.request": {
            "handlers": ["console", "file"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
}

FACTURAPI_API_KEY = os.getenv("FACTURAPI_API_KEY", "")
FACTURAPI_BASE_URL = os.getenv("FACTURAPI_BASE_URL", "https://www.facturapi.io/v2")
FACTURAPI_TIMEOUT_SECONDS = int(os.getenv("FACTURAPI_TIMEOUT_SECONDS", "30"))

# Defaults para “producto/servicio” si aún no guardas claves SAT en tu modelo Item
FACTURAPI_DEFAULT_PRODUCT_KEY = os.getenv("FACTURAPI_DEFAULT_PRODUCT_KEY", "78101800")  # transporte/flete (ajústalo)
FACTURAPI_DEFAULT_UNIT_KEY = os.getenv("FACTURAPI_DEFAULT_UNIT_KEY", "E48")             # servicio :contentReference[oaicite:1]{index=1}

# Recomendación: crear como draft para evitar timbrar “por accidente”
FACTURAPI_CREATE_AS_DRAFT = os.getenv("FACTURAPI_CREATE_AS_DRAFT", "true").lower() == "true"