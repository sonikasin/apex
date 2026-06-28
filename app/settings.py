

from pathlib import Path
import os 
BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = 'django-insecure-yu1ljz+30n)pg+xy!abtngnhzo6(_u8vubzu=jjru6gw$21=@u'

DEBUG = True

ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = ['http://apexfx.info', 'https://apexfx.info', 'https://tspfxb.com', 'https://api.directpay.click']
SITE_ID = 2
CORS_ORIGIN_ALLOW_ALL = True


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'trading',
    'admin_panel',

]
AUTH_USER_MODEL = 'trading.CustomUser'

MIDDLEWARE = [
    'trading.middleware.Custom404Middleware',
    'trading.middleware.ErrorHandlingMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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


WSGI_APPLICATION = 'app.wsgi.application'


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.hostinger.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = 'info@apexfx.net'  # آدرس ایمیل تنظیم‌شده در هاستینگر
EMAIL_HOST_PASSWORD = 'Sin@1831'  # رمز عبور ایمیل
EMAIL_USE_TLS = False  # برای پورت 465 نیازی به TLS نیست
EMAIL_USE_SSL = False  # برای پورت 465 که از SSL استفاده می‌کند
DEFAULT_FROM_EMAIL = 'info@apexfx.net'  # ایمیل پیش‌فرض برای ارسال


import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        'OPTIONS': {
            'timeout': 40,  # افزایش زمان انتظار برای قفل دیتابیس (ثانیه)
            'init_command': (
                'PRAGMA journal_mode=WAL;'  # فعال‌سازی حالت Write-Ahead Logging
                'PRAGMA synchronous=NORMAL;'  # بهینه‌سازی همگام‌سازی
              
            ),
        },
        'CONN_MAX_AGE': 0,  # جلوگیری از نگه‌داری طولانی‌مدت اتصالات
    }
}
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'



AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]




LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


import os

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

if DEBUG:
    STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
