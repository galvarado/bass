# core/settings.py
from pathlib import Path
import os
from dotenv import load_dotenv
import os

# ==== Paths & env ====
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ==== Seguridad / Entorno ====
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-cambia-esto")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# ==== Apps ====
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Tus apps
    "accounts",
    "collection",
    "ctpat",
    "finance",
    "operators",
    "settlement",
    "trips",
    "trucks",
    "warehouse",
    "workshop",
    "common",
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
LOGIN_REDIRECT_URL = "dashboard"   # o "trip_list" si prefieres
LOGOUT_REDIRECT_URL = "login"
OPENEXCHANGE_APP_ID = "c98896f4617b43779470c2d5170f285f"
OPENEXCHANGE_BASE_URL = "https://openexchangerates.org/api/latest.json"
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
