from datetime import timedelta
import os
from pathlib import Path
import environ  # type: ignore
USE_TZ = True



env = environ.Env()
environ.Env.read_env()
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
env_file = BASE_DIR / '.env'
if not env_file.exists():
    raise RuntimeError(f"⛔️ could not find .env at {env_file!r}")
env.read_env(str(env_file))
# 🔐 Security
SECRET_KEY = "i4lz)ec6yzw1#$wis03=o@kasdfasdfaseaFEBbfgFFDEgdsGGDGGVdsdfdewqA3egvbarna9t%+8^&t#yd=(c@(_havg*wi=6^"
DEBUG = env.bool('DEBUG', default=True)
ALLOWED_HOSTS = [
    "backendlms.thevista365.com",
    "kfgc.schoolcare.pk",
    "kfgc.online",
    "testing-lms.schoolcare.pk",
    "127.0.0.1",
    "localhost",
]

CSRF_TRUSTED_ORIGINS = [
    "https://backendlms.thevista365.com",
    "https://kfgc.schoolcare.pk",
    "https://kfgc.online/"
    "https://testing-lms.schoolcare.pk",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]
CORS_ALLOWED_ORIGINS = [
    "https://backendlms.thevista365.com",
    "https://kfgc.schoolcare.pk",
    "https://kfgc.online",
    "https://testing-lms.schoolcare.pk",
    "http://localhost:3000",      # if your React runs on 3000 in dev
    "http://127.0.0.1:3000",
]

# ALLOWED_HOSTS = "ALLOWED_HOSTS=127.0.0.1,localhost,yourdomain.com"
# CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')
# CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "False") == "True"


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'corsheaders',
    'core',
    'notifications',
    'rest_framework_simplejwt',
    'django_celery_beat',
    "django_apscheduler",
]




MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'lms.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        "DIRS": [BASE_DIR / "core" / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'lms.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# DB will be used in Production
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': env('DB_NAME'),
#         'USER': env('DB_USER'),
#         'PASSWORD': env('DB_PASSWORD'),
#         'HOST': env('DB_HOST'),   # or IP address of your DB server
#         'PORT': env('DB_PORT'),   # default PostgreSQL port
#     }
# }


PROVISION_CALLBACK_TOKEN = os.getenv('PROVISION_CALLBACK_TOKEN', None)


TIME_ZONE = 'Asia/Karachi'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


AUTH_USER_MODEL = 'core.User'

# 📬 Email Settings (SMTP)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'moinuldinc@gmail.com'
EMAIL_HOST_PASSWORD = 'lekg bbec tlka qalq'
DEFAULT_FROM_EMAIL = 'moinuldinc@gmail.com'


CELERY_BROKER_URL = env(
    'CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'


CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers.DatabaseScheduler'

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env('REDIS_URL', default='redis://127.0.0.1:6379/1'),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
     'DEFAULT_PERMISSION_CLASSES': [
        'core.permissions.RoleBasedPermission',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
SPECTACULAR_SETTINGS = {
    'TITLE': 'Library Management System API',
    'DESCRIPTION': 'Zubair Hassan',
    'VERSION': '1.0.0',
}


FRONTEND_URL = "https://kfgc.online/"

CORS_ALLOW_CREDENTIALS = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

