import os
from pathlib import Path
import environ

env = environ.Env(
    DEBUG=(bool, False)
)

BASE_DIR = Path(__file__).resolve().parent.parent

# Lee .env si existe
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('DJANGO_SECRET_KEY', default='change-me-in-production')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])

CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=[
        'https://lyvio.io',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        "https://ibex-daring-molly.ngrok-free.app"
    ]
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    
    # Third party (antes de tus apps)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'crispy_forms',
    'crispy_bootstrap5',
    # Form rendering with Tailwind (django-formify)
    'django_viewcomponent',
    'django_formify',
    
    # Local apps - accounts PRIMERO porque otros dependen de él
    'accounts',  # DEBE IR PRIMERO
    'activation',
    'subscriptions',
    'onboarding',
    'bots',
    'bot_builder',
    'landing',
    'dashboard',
    'sso',  # SSO Authentication
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Auto-logout middleware: checks inactivity and expires sessions server-side
    'accounts.middleware.AutoLogoutMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'lyvio.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'loaders': [(
                'django.template.loaders.cached.Loader', [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                    'django_viewcomponent.loaders.ComponentLoader',
                ]
            )],
        },
    },
]

WSGI_APPLICATION = 'lyvio.wsgi.application'

# Database
DATABASES = {
    'default': env.db('DATABASE_URL', default='postgresql://botuser:password@localhost:5432/botdb')
}

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379'),
    }
}

# Auth
AUTH_USER_MODEL = 'accounts.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Django-allauth
SITE_ID = 1
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = 'none'  # Temporal: desactivar verificación
LOGIN_REDIRECT_URL = '/dashboard/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

# Debug: Verificar flujo de login
ACCOUNT_LOGIN_REDIRECT_URL = '/bot-builder/'

# Internationalization
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Servicios externos
CHATWOOT_API_URL = env('CHATWOOT_API_URL', default='https://app.lyvio.io')
CHATWOOT_PLATFORM_TOKEN = env('CHATWOOT_PLATFORM_TOKEN', default='')
LYVIO_PLATFORM_TOKEN = env('LYVIO_PLATFORM_TOKEN', default='')
# lyvio/settings.py configuration

# Webhook configuration
N8N_WEBHOOK_URL = os.getenv('NEW_ACCOUNT_N8N_WEBHOOK_URL', 'https://n8n.2asoft.tech/webhook/lyvio/account-activation')
ADD_DOCUMENT_N8N_WEBHOOK_URL = os.getenv('ADD_DOCUMENT_N8N_WEBHOOK_URL', 'https://n8n.2asoft.tech/webhook-test/lyvio/vectorize-document')
DELETE_DOCUMENT_N8N_WEBHOOK_URL = os.getenv('DELETE_DOCUMENT_N8N_WEBHOOK_URL', 'https://n8n.2asoft.tech/webhook/lyvio/delete-document-vectors')

# MinIO configuration
MINIO_ENDPOINT = env('MINIO_ENDPOINT', default='central-minio:9000')
MINIO_ACCESS_KEY = env('MINIO_ACCESS_KEY', default='')
MINIO_SECRET_KEY = env('MINIO_SECRET_KEY', default='')
MINIO_BUCKET = env('MINIO_BUCKET', default='lyvio-bot-documents')
STRIPE_PUBLIC_KEY = env('STRIPE_PUBLIC_KEY', default='')
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='')

# Wompi
WOMPI_PUBLIC_KEY = env('WOMPI_PUBLIC_KEY', default='')
WOMPI_PRIVATE_KEY = env('WOMPI_PRIVATE_KEY', default='')
WOMPI_EVENTS_SECRET = env('WOMPI_EVENTS_SECRET', default='')
WOMPI_INTEGRITY_SECRET = env('WOMPI_INTEGRITY_SECRET', default='')
WOMPI_TEST_MODE = env.bool('WOMPI_TEST_MODE', default=True)


# Site URL para callbacks
SITE_URL = env('SITE_URL', default='http://localhost:8000')

# Email settings
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@lyvio.io')
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.dummy.EmailBackend')
# EMAIL_FILE_PATH = '/tmp/app-messages'  # Para development, guardar emails en archivos
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=False)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',   # Login estándar de Django
]

# Login URLs
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Webhook Security - API Key para autenticar webhooks salientes hacia N8N
LYVIO_WEBHOOK_API_KEY = env('LYVIO_WEBHOOK_API_KEY', default='lyvio-secret-api-key-2024')

# ================================
# SSO (Single Sign-On) Configuration
# ================================
# Secreto compartido entre n8n y Django para validar requests de generación de tokens
SSO_SHARED_SECRET = env('SSO_SHARED_SECRET', default='change-me-in-production-use-strong-random-value')

# Tiempo de validez del token SSO en minutos (por defecto 5 minutos)
SSO_TOKEN_EXPIRY_MINUTES = env.int('SSO_TOKEN_EXPIRY_MINUTES', default=5)

# URL a donde redirigir después de un login SSO exitoso
SSO_REDIRECT_URL = env('SSO_REDIRECT_URL', default='/dashboard')

# Antigüedad máxima del timestamp permitida en segundos (previene replay attacks)
SSO_MAX_TIMESTAMP_AGE_SECONDS = env.int('SSO_MAX_TIMESTAMP_AGE_SECONDS', default=30)

SITE_URL = env('SITE_URL', default='https://platform.lyvio.io')

# -------------------------------
# Session / Auto-logout settings
# -------------------------------
# Expira la sesión cuando el usuario cierre el navegador
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Tiempo máximo de inactividad (en segundos) antes de forzar logout por el servidor.
# AutoLogoutMiddleware usará esta variable. Por defecto 30 minutos.
AUTO_LOGOUT_DELAY = env.int('AUTO_LOGOUT_DELAY', default=30 * 60)

# Si se desea que cada petición renueve el tiempo de sesión en el servidor,
# habilitar SESSION_SAVE_EVERY_REQUEST. Lo dejamos en False para que el
# middleware controle la expiración basada en la última actividad registrada.
SESSION_SAVE_EVERY_REQUEST = False
