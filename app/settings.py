

from pathlib import Path
import os 
BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = 'django-insecure-yu1ljz+30n)pg+xy!abtngnhzo6(_u8vubzu=jjru6gw$21=@u'

DEBUG = True

ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = ['http://apexfx.info', 'https://apexfx.info', 'https://apexfx.net', 'http://apexfx.net', 'https://tspfxb.com', 'https://api.directpay.click']
SITE_ID = 2
CORS_ORIGIN_ALLOW_ALL = True


# ============================================================================
#  درگاه‌های پرداخت ریالی (Rial payment gateways)
# ----------------------------------------------------------------------------
#  دو درگاه پشتیبانی می‌شود: «دایرکت پی» (DirectPay) و «پی‌استار» (PayStar).
#  درگاه فعال از طریق پنل ادمین قابل انتخاب است
#  (admin_panel -> «تنظیمات درگاه پرداخت»). مدل PaymentGatewaySetting مقدار
#  درگاه فعال را نگه می‌دارد.
#
#  ⚠️ امنیت: مقادیر حساس (sign_key و gateway_id) ترجیحاً باید از طریق متغیرهای
#  محیطی (environment variables) تنظیم شوند. مقادیر پیش‌فرض زیر صرفاً برای
#  راه‌اندازی سریع است. حتماً کلید پی‌استار را که قبلاً به‌صورت عمومی منتشر شده
#  از پنل پی‌استار باطل و کلید جدید بسازید و آن را در ENV قرار دهید.
# ============================================================================

DEFAULT_RIAL_GATEWAY = os.environ.get('DEFAULT_RIAL_GATEWAY', 'directpay')

PAYMENT_GATEWAYS = {
    'directpay': {
        'label': 'دایرکت پی',
        'base_url': os.environ.get(
            'DIRECTPAY_BASE_URL', 'https://api.directpay.finance/api/pardakht'
        ),
        'gateway_id': os.environ.get('DIRECTPAY_GATEWAY_ID', '6y63e4oex3q822'),
        'sign_key': os.environ.get(
            'DIRECTPAY_SIGN_KEY',
            'B3D7A776EC4BF4FB24CAF4F7A5C301600CB8B23489330669BB5B7B9AB1F1B153'
            '276D789EC123E8F0984DC3DA1A507329C23A9FB86237D1F6823FDF69D1F29FA8D'
            '21CB2A78DA3CDB5A748C062B1DFD2CABE4EE2BD4F778E45F992A17FA1064D4AF8'
            'D7B5961964E94DD1FBE8EAA205F56F6AFB6F93C7BA05A64C94218291927147',
        ),
        # آدرس برگشت باید با دامنه‌ای که درگاه با آن ساخته شده مطابقت داشته باشد.
        'callback_url': os.environ.get(
            'DIRECTPAY_CALLBACK_URL', 'https://apexfx.net/payment-callback/'
        ),
        'referer': os.environ.get('DIRECTPAY_REFERER', 'https://apexfx.net'),
        # فیلدهای اختصاصی دایرکت‌پی
        'wallet': os.environ.get('DIRECTPAY_WALLET', 'AJKVW4'),
        'send_products': True,
    },
    'paystar': {
        'label': 'پی‌استار',
        'base_url': os.environ.get(
            'PAYSTAR_BASE_URL', 'https://core.paystar.ir/api/pardakht'
        ),
        'gateway_id': os.environ.get('PAYSTAR_GATEWAY_ID', '9v982vy4o0owy'),
        'sign_key': os.environ.get(
            'PAYSTAR_SIGN_KEY',
            '16F391BC7E7DE9DDE697174B8F0A83F5CEC32D4AA629F1F6097D921E050080CA'
            'EE051286346F9CF258E240210FE8853E241EBD54E4347EC608D1E2C46B6CB3F7'
            '6E51501D1C636FFC7CCC417787187766BFF8177C1AF68044C1D0C9CE66B9E3A4'
            '8439CD5C8C7B3051FF1B384EC48C22FBEC21698F7B1FD1153F96BCAA99951B41',
        ),
        # ⚠️ این دامنه باید دقیقاً همان دامنه‌ای باشد که هنگام ساخت درگاه پی‌استار
        # ثبت کرده‌اید. اگر درگاه با apexfx.info ثبت شده، این مقدار را تغییر دهید.
        'callback_url': os.environ.get(
            'PAYSTAR_CALLBACK_URL', 'https://apexfx.net/payment-callback/'
        ),
        'referer': os.environ.get('PAYSTAR_REFERER', 'https://apexfx.net'),
        # پی‌استار به wallet/products نیاز ندارد
        'wallet': os.environ.get('PAYSTAR_WALLET', ''),
        'send_products': False,
    },
}


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
    'admin_panel.middleware.AdminActionLogMiddleware',
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



# لاگ‌گیری: نمایش لاگ‌های اپ trading (از جمله پاسخ کامل درگاه پرداخت) روی کنسول
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '[{asctime}] {levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'loggers': {
        'trading': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
