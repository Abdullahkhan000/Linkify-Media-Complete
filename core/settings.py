import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

DEBUG = os.getenv("DEBUG", "True").lower() in {"1", "true", "yes", "on"}

# SECURITY WARNING: keep the secret key used in production secret.
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SECRET_KEY must be configured when DEBUG=False.")
    SECRET_KEY = "django-insecure-local-development-only"

# ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host.strip()]
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",  # required for allauth
]

OTHER_APPS = [
    'rest_framework',
    'allauth',
    'allauth.account',
    'allauth.headless',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
    'api',
]

INSTALLED_APPS += OTHER_APPS

SITE_ID = 1

FRONTEND_URL = os.getenv(
    'FRONTEND_URL',
    'http://localhost:3000' if DEBUG else '',
).strip().rstrip('/')
if FRONTEND_URL and urlparse(FRONTEND_URL).scheme not in {'http', 'https'}:
    raise ImproperlyConfigured('FRONTEND_URL must be an http or https URL.')
if FRONTEND_URL and FRONTEND_URL not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(FRONTEND_URL)

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# allauth config
ACCOUNT_LOGIN_METHODS = {'email', 'username'}
# Verification is deliberately disabled for the initial launch. Set this to
# "mandatory" when transactional email and a public site domain are ready.
ACCOUNT_EMAIL_VERIFICATION = os.getenv('ACCOUNT_EMAIL_VERIFICATION', 'none').strip().lower()
if ACCOUNT_EMAIL_VERIFICATION not in {'none', 'optional', 'mandatory'}:
    raise ImproperlyConfigured(
        'ACCOUNT_EMAIL_VERIFICATION must be none, optional, or mandatory.'
    )
ACCOUNT_CONFIRM_EMAIL_ON_GET = False
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_SIGNUP_FIELDS = ['username*', 'email*', 'password1*', 'password2*']
ACCOUNT_FORMS = {'signup': 'api.forms.LinkifySignupForm'}
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_MIN_LENGTH = 3
ACCOUNT_ADAPTER = 'api.adapters.CustomAccountAdapter'
HEADLESS_ONLY = False
HEADLESS_FRONTEND_URLS = {
    'account_confirm_email': f'{FRONTEND_URL}/verify-email/{{key}}',
    'account_reset_password': f'{FRONTEND_URL}/forgot-password',
    'account_reset_password_from_key': f'{FRONTEND_URL}/reset-password/{{key}}',
    'account_signup': f'{FRONTEND_URL}/signup',
    'socialaccount_login_error': f'{FRONTEND_URL}/login?social=error',
} if FRONTEND_URL else {}
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'github': {
        'SCOPE': ['user:email'],
    },
}

# Resend Email Config
RESEND_API_KEY = os.getenv('RESEND_API_KEY')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'support@linkifymedia.com')

# Fallback during dev if RESEND_API_KEY is missing
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "api.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "api.middleware.APIKeyMiddleware",  # custom middleware for API key auth
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates", 
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "api.context_processors.social_auth_providers",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

database_url = os.getenv("DATABASE_URL", "").strip()
if database_url:
    parsed_database_url = urlparse(database_url)
    if parsed_database_url.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must use the postgres or postgresql scheme.")
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed_database_url.path.lstrip("/"),
        "USER": unquote(parsed_database_url.username or ""),
        "PASSWORD": unquote(parsed_database_url.password or ""),
        "HOST": parsed_database_url.hostname or "",
        "PORT": parsed_database_url.port or 5432,
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"sslmode": os.getenv("DATABASE_SSLMODE", "require")},
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()

# External services
LEMONSQUEEZY_API_KEY = os.getenv("LEMONSQUEEZY_API_KEY", "").strip()
LEMONSQUEEZY_STORE_ID = os.getenv("LEMONSQUEEZY_STORE_ID", "").strip()
LEMONSQUEEZY_VARIANT_PRO = os.getenv("LEMONSQUEEZY_VARIANT_PRO", "").strip()
LEMONSQUEEZY_VARIANT_BIZ = os.getenv("LEMONSQUEEZY_VARIANT_BIZ", "").strip()
LEMONSQUEEZY_WEBHOOK_SECRET = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET", "").strip()

# Abuse controls. Redis is used automatically when REDIS_URL is configured.
REDIS_URL = os.getenv("REDIS_URL", "").strip()
CACHES = {
    "default": (
        {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}
        if REDIS_URL
        else {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "linkify-local-cache",
        }
    )
}
DEMO_API_ENABLED = os.getenv("DEMO_API_ENABLED", str(DEBUG)).lower() in {"1", "true", "yes", "on"}
DEMO_RATE_LIMIT = int(os.getenv("DEMO_RATE_LIMIT", "30"))
DEMO_TOKEN_MAX_AGE = int(os.getenv("DEMO_TOKEN_MAX_AGE", "3600"))
BATCH_LIMITS = {"demo": 3, "pro": 25, "business": 100}
API_REQUEST_TIMEOUT = int(os.getenv("API_REQUEST_TIMEOUT", "30"))
SUPPORT_RATE_LIMIT = int(os.getenv("SUPPORT_RATE_LIMIT", "20"))

# Production-safe defaults can be overridden when TLS terminates elsewhere.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", str(not DEBUG)).lower() in {"1", "true", "yes", "on"}
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", str(not DEBUG)).lower() in {"1", "true", "yes", "on"}
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", str(not DEBUG)).lower() in {"1", "true", "yes", "on"}
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "standard"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
