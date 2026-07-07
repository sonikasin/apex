"""
ثبتِ دقیقِ تغییراتِ مدل‌ها (قبل/بعد) برای پنل ادمین.

با استفاده از سیگنال‌های pre_save/post_save/post_delete و یک ذخیره‌سازِ thread-local،
هر تغییری که در طولِ یک درخواستِ پنل ادمین روی مدل‌های مهم رخ دهد جمع‌آوری می‌شود.
میدل‌ور در پایانِ درخواست این تغییرات را در AdminActionLog.changes ذخیره می‌کند.
این‌طور در جزئیاتِ لاگ می‌توان دید چه چیزی ویرایش/حذف/اضافه شده و مقدارِ قبل و بعدِ هر فیلد چه بوده.
"""
import threading
from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_save

_local = threading.local()

# مدل‌هایی که تغییراتشان ثبت می‌شود (نام کلاس → برچسبِ فارسی)
MODEL_LABELS = {
    'PropAccount': 'حساب پراپ',
    'PropOrder': 'سفارش',
    'CustomUser': 'کاربر',
    'Ticket': 'تیکت',
    'Employee': 'کارمند',
    'PropPlan': 'پلن پراپ',
    'PlanStage': 'مرحله پلن',
    'Rule': 'قانون',
    'DiscountCode': 'کد تخفیف',
    'Referral': 'رفرال',
    'Wallet': 'کیف پول',
    'WalletTransaction': 'تراکنش کیف پول',
    'IdentityVerification': 'احراز هویت',
    'StageUpgradeRequest': 'درخواست ارتقاء',
    'FreeAccountQuota': 'سهمیه حساب رایگان',
    'Certificate': 'سرتیفیکیت',
    'PaymentGatewaySetting': 'تنظیمات درگاه',
    'BlogPost': 'پست وبلاگ',
    'UserSubmission': 'ارسال کاربر',
}

# فیلدهای حساس که مقدارشان ثبت نمی‌شود
MASK_FIELDS = {'password'}


# ---------------------------------------------------------------------------
# مدیریت وضعیتِ درخواست (thread-local)
# ---------------------------------------------------------------------------
def start(request=None):
    _local.active = True
    _local.changes = []


def stop():
    _local.active = False
    _local.changes = []


def collected():
    return getattr(_local, 'changes', [])


def _active():
    return getattr(_local, 'active', False)


# ---------------------------------------------------------------------------
# کمکی‌ها
# ---------------------------------------------------------------------------
def _fmt(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    s = str(value)
    return s if len(s) <= 500 else (s[:500] + '…')


def _snapshot(instance):
    data = {}
    try:
        fields = instance._meta.concrete_fields
    except Exception:
        return data
    for field in fields:
        name = field.name
        if name in MASK_FIELDS or 'password' in name.lower():
            continue
        try:
            data[name] = _fmt(getattr(instance, field.attname))
        except Exception:
            continue
    return data


def _label(instance):
    return MODEL_LABELS.get(type(instance).__name__, type(instance).__name__)


# ---------------------------------------------------------------------------
# سیگنال‌ها
# ---------------------------------------------------------------------------
def _pre_save(sender, instance, **kwargs):
    if not _active():
        return
    if not instance.pk:
        instance._audit_old = None
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._audit_old = _snapshot(old)
    except Exception:
        instance._audit_old = None


def _post_save(sender, instance, created, **kwargs):
    if not _active():
        return
    new = _snapshot(instance)
    old = getattr(instance, '_audit_old', None)
    if created or old is None:
        _local.changes.append({
            'model': _label(instance), 'pk': str(instance.pk),
            'repr': str(instance)[:200], 'action': 'create', 'fields': new,
        })
    else:
        diff = {}
        for key, new_val in new.items():
            old_val = old.get(key)
            if old_val != new_val:
                diff[key] = {'before': old_val, 'after': new_val}
        if diff:
            _local.changes.append({
                'model': _label(instance), 'pk': str(instance.pk),
                'repr': str(instance)[:200], 'action': 'update', 'changes': diff,
            })


def _post_delete(sender, instance, **kwargs):
    if not _active():
        return
    _local.changes.append({
        'model': _label(instance), 'pk': str(instance.pk),
        'repr': str(instance)[:200], 'action': 'delete', 'fields': _snapshot(instance),
    })


def connect():
    """اتصالِ سیگنال‌ها به مدل‌های ردیابی‌شده (یک‌بار در startup)."""
    try:
        from trading import models as tm
    except Exception:
        tm = None
    try:
        from admin_panel import models as am
    except Exception:
        am = None

    for name in MODEL_LABELS:
        model = None
        if tm is not None:
            model = getattr(tm, name, None)
        if model is None and am is not None:
            model = getattr(am, name, None)
        if model is None:
            continue
        pre_save.connect(_pre_save, sender=model, dispatch_uid='audit_pre_%s' % name)
        post_save.connect(_post_save, sender=model, dispatch_uid='audit_post_%s' % name)
        post_delete.connect(_post_delete, sender=model, dispatch_uid='audit_del_%s' % name)
