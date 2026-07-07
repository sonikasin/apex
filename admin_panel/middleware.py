"""
Middleware برای ثبت خودکار لاگ ممیزی پنل ادمین.

هر درخواستی که به ویوهای namespace «admin_panel» می‌رسد و توسط یک کاربر
احراز هویت‌شده انجام می‌شود، در مدل AdminActionLog ثبت می‌گردد (به‌جز خودِ
صفحه‌ی لاگ‌ها برای جلوگیری از نویز).
"""

import json
import logging

logger = logging.getLogger('admin_panel')

# نام ویوهایی که نباید لاگ شوند (برای جلوگیری از نویز/بازگشت)
EXCLUDED_VIEW_NAMES = {
    'admin_action_log_list',
    'admin_action_log_detail',
}

# کلیدهای حساس که در داده‌های POST ذخیره نمی‌شوند
SENSITIVE_KEYS = {'csrfmiddlewaretoken', 'password', 'password1', 'password2',
                  'new_password', 'old_password', 'confirm_password'}

# نگاشت برخی نام‌ویوها به شرح فارسی خوانا
VIEW_LABELS = {
    'dashboard': 'مشاهده داشبورد',
    'customuser_list': 'مشاهده لیست کاربران',
    'customuser_add': 'افزودن کاربر',
    'customuser_edit': 'ویرایش کاربر',
    'customuser_delete': 'حذف کاربر',
    'propaccount_list': 'مشاهده حساب‌های پراپ',
    'propaccount_assign': 'تخصیص حساب پراپ',
    'propaccount_review': 'بررسی حساب پراپ',
    'create_account_via_api': 'ایجاد حساب از طریق API',
    'bulk_assign_accounts': 'تخصیص گروهی حساب‌ها',
    'proporder_list': 'مشاهده سفارش‌ها',
    'ticket_list': 'مشاهده تیکت‌ها',
    'ticket_reply': 'پاسخ به تیکت',
    'employee_list': 'مشاهده کارمندان',
    'employee_add': 'افزودن کارمند',
    'employee_edit': 'ویرایش کارمند',
    'identity_verification_list': 'مشاهده احراز هویت‌ها',
    'identity_verification_review': 'بررسی احراز هویت',
    'propplan_list': 'مشاهده پلن‌های پراپ',
    'wallet_list': 'مشاهده کیف پول‌ها',
    'wallet_edit': 'ویرایش کیف پول',
    'wallet_transactions': 'مشاهده تراکنش‌های کیف پول',
    'bulk_update_wallets': 'به‌روزرسانی گروهی کیف پول‌ها',
    'rule_list': 'مشاهده قوانین',
    'discount_code_list': 'مشاهده کدهای تخفیف',
    'discount_code_edit': 'ویرایش کد تخفیف',
    'referral_list': 'مشاهده رفرال‌ها',
    'referral_edit': 'ویرایش رفرال',
    'send_gift_email': 'ارسال ایمیل هدیه',
    'blog_list_admin': 'مشاهده وبلاگ‌ها',
    'user_submission_list': 'مشاهده ارسال‌های کاربران',
    'password_generator': 'تولید رمز عبور',
    'free_account_quota_list': 'مشاهده سهمیه حساب رایگان',
    'payment_gateway_settings': 'تنظیمات درگاه پرداخت',
}


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _categorize(url_name, method):
    name = (url_name or '').lower()
    if 'delete' in name:
        return 'delete'
    if 'add' in name or 'create' in name or 'generat' in name:
        return 'create'
    if 'edit' in name or 'update' in name or 'review' in name or 'assign' in name or 'reply' in name:
        return 'update'
    if method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return 'action'
    return 'view'


def _sanitize_post(request):
    if request.method not in ('POST', 'PUT', 'PATCH'):
        return ''
    try:
        data = {}
        for key in request.POST.keys():
            if key.lower() in SENSITIVE_KEYS or 'password' in key.lower():
                data[key] = '***'
            else:
                values = request.POST.getlist(key)
                data[key] = values if len(values) > 1 else (values[0] if values else '')
        if request.FILES:
            data['_files'] = list(request.FILES.keys())
        text = json.dumps(data, ensure_ascii=False)
        return text[:8000]
    except Exception:
        return ''


class AdminActionLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # داده‌های POST را قبل از اجرای ویو نگه می‌داریم (بعضی ویوها request را مصرف می‌کنند)
        post_snapshot = None
        if request.method in ('POST', 'PUT', 'PATCH'):
            post_snapshot = _sanitize_post(request)

        response = self.get_response(request)

        try:
            self._log(request, response, post_snapshot)
        except Exception as exc:  # pragma: no cover - لاگ نباید هرگز ریکوئست را خراب کند
            logger.warning("AdminActionLog failed: %s", exc)

        return response

    def _log(self, request, response, post_snapshot):
        match = getattr(request, 'resolver_match', None)
        if not match or match.namespace != 'admin_panel':
            return

        url_name = match.url_name or ''
        if url_name in EXCLUDED_VIEW_NAMES:
            return

        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return

        # import داخل تابع برای جلوگیری از مشکلات بارگذاری اپ‌ها
        from .models import AdminActionLog

        kwargs = match.kwargs or {}
        object_id = str(kwargs.get('pk') or kwargs.get('id') or kwargs.get('wallet_id') or '')

        label = VIEW_LABELS.get(url_name, url_name or request.path)
        if object_id:
            label = f"{label} (#{object_id})"

        AdminActionLog.objects.create(
            user=user,
            user_email=getattr(user, 'email', '') or str(user),
            is_superuser=bool(getattr(user, 'is_superuser', False)),
            category=_categorize(url_name, request.method),
            action_description=label,
            method=request.method,
            path=request.path[:500],
            view_name=url_name,
            query_string=request.META.get('QUERY_STRING', '')[:2000],
            post_data=post_snapshot or '',
            object_id=object_id[:100],
            status_code=getattr(response, 'status_code', None),
            ip_address=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
        )
