from django.apps import AppConfig


class AdminPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_panel'

    def ready(self):
        # اتصالِ سیگنال‌های ثبتِ تغییرات (قبل/بعد) برای لاگِ ادمین
        try:
            from . import audit
            audit.connect()
        except Exception:
            pass
