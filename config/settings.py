import os, secrets
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
if os.environ.get("RENDER") == "true" and not os.environ.get("DJANGO_SECRET_KEY"):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be configured privately on Render."
    )
key_file = BASE_DIR / ".secret-key"
if not os.environ.get("DJANGO_SECRET_KEY") and not key_file.exists():
    try:
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_urlsafe(64))
    except FileExistsError:
        pass
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or key_file.read_text().strip()
DEBUG = (
    os.environ.get("DJANGO_DEBUG", "0" if os.environ.get("RENDER") == "true" else "1")
    == "1"
)
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
).split(",")
INSTALLED_APPS = [
    "shop.admin_site.OwnerAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "shop",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "shop.middleware.StoreLanguageMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "shop.context.store",
            ]
        },
    }
]
DATA_DIR = Path(os.environ.get("FARMCART_DATA_DIR", BASE_DIR))
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "az"
TIME_ZONE = "Asia/Baku"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = DATA_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/account/"
LOGOUT_REDIRECT_URL = "/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True

CSRF_TRUSTED_ORIGINS = [
    origin
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin
]

# Render provides this hostname and terminates TLS at its trusted proxy.
render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_host:
    ALLOWED_HOSTS.append(render_host)
    CSRF_TRUSTED_ORIGINS.append("https://" + render_host)
if os.environ.get("RENDER") == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# Configure these only in the hosting provider's private environment settings.
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "").strip().lower()
ADMIN_SETUP_SECRET = os.environ.get("ADMIN_SETUP_SECRET", "")
EMAIL_BACKEND = "shop.email_backend.ResendBackend"
EMAIL_API_KEY = os.environ.get("EMAIL_API_KEY", "")
DEFAULT_FROM_EMAIL = os.environ.get("EMAIL_FROM", "")
OWNER_AUTH_TEST_MODE = False
# Ephemeral Render SQLite may never store one-time ownership state.
OWNER_AUTH_DURABLE = os.environ.get("RENDER") != "true" or bool(
    os.environ.get("DATABASE_URL")
)
if os.environ.get("DATABASE_URL"):
    import dj_database_url
    from urllib.parse import urlsplit

    if urlsplit(os.environ["DATABASE_URL"]).scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL must be a PostgreSQL connection URL.")
    DATABASES["default"] = dj_database_url.parse(
        os.environ["DATABASE_URL"], conn_max_age=60, ssl_require=True
    )

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    "API_KEY": os.environ.get("CLOUDINARY_API_KEY", ""),
    "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET", ""),
    "SECURE": True,
}
CLOUD_MEDIA_ENABLED = all(
    CLOUDINARY_STORAGE[key] for key in ["CLOUD_NAME", "API_KEY", "API_SECRET"]
)
MEDIA_DURABLE = os.environ.get("RENDER") != "true" or CLOUD_MEDIA_ENABLED
if CLOUD_MEDIA_ENABLED:
    STORAGES["default"] = {"BACKEND": "shop.storage.CatalogCloudinaryStorage"}
