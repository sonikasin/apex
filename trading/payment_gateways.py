"""
ماژول مرکزی مدیریت درگاه‌های پرداخت ریالی (DirectPay / PayStar).

هر دو درگاه از یک ساختار API یکسان (PayStar-compatible) استفاده می‌کنند:
    - POST {base_url}/create   -> دریافت توکن یکبارمصرف
    - GET  {base_url}/payment?token=...  -> هدایت کاربر به درگاه
    - POST {base_url}/verify   -> تأیید نهایی تراکنش

امضا (sign) با الگوریتم HMAC-SHA512 ساخته می‌شود:
    - create:  amount#order_id#callback
    - verify:  amount#ref_num#card_number#tracking_code

پیکربندی هر درگاه در settings.PAYMENT_GATEWAYS قرار دارد و درگاه فعال از طریق
مدل PaymentGatewaySetting (قابل تغییر از پنل ادمین) انتخاب می‌شود.
"""

import hmac
import hashlib
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def get_gateway_choices():
    """لیست (نام, برچسب) درگاه‌ها برای استفاده در choices مدل/فرم."""
    return [(name, cfg.get('label', name)) for name, cfg in settings.PAYMENT_GATEWAYS.items()]


def get_gateway(name):
    """
    پیکربندی درگاه را بر اساس نام برمی‌گرداند. اگر نام نامعتبر باشد،
    به درگاه پیش‌فرض برمی‌گردد.
    """
    gateways = settings.PAYMENT_GATEWAYS
    if name not in gateways:
        name = settings.DEFAULT_RIAL_GATEWAY
    cfg = dict(gateways[name])
    cfg['name'] = name
    return cfg


def get_active_gateway_name():
    """نام درگاه فعالِ انتخاب‌شده در پنل ادمین."""
    # import داخل تابع برای جلوگیری از circular import
    from .models import PaymentGatewaySetting
    try:
        return PaymentGatewaySetting.get_active_gateway()
    except Exception as exc:  # pragma: no cover - در زمان migration ممکن است جدول نباشد
        logger.warning("Falling back to default gateway: %s", exc)
        return settings.DEFAULT_RIAL_GATEWAY


def get_active_gateway():
    """پیکربندی کامل درگاه فعال."""
    return get_gateway(get_active_gateway_name())


def _create_sign(sign_key, amount, order_id, callback):
    sign_data = f"{amount}#{order_id}#{callback}"
    return hmac.new(sign_key.encode(), sign_data.encode(), hashlib.sha512).hexdigest()


def _verify_sign(sign_key, amount, ref_num, card_number, tracking_code):
    sign_data = f"{int(amount)}#{ref_num}#{card_number}#{tracking_code}"
    return hmac.new(sign_key.encode(), sign_data.encode(), hashlib.sha512).hexdigest()


def _headers(gateway):
    return {
        'Authorization': f"Bearer {gateway['gateway_id']}",
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        # بعضی WAFها درخواست بدون User-Agent را با 401/403 رد می‌کنند
        'User-Agent': 'ApexFX/1.0 (+https://apexfx.net)',
    }


def create_transaction(gateway, amount, order_id, *, first_name='', last_name='',
                       description='', timeout=60):
    """
    ایجاد تراکنش در درگاه و برگرداندن آبجکت response (requests.Response).
    amount باید به ریال و عدد صحیح باشد.
    """
    callback = gateway['callback_url']
    sign = _create_sign(gateway['sign_key'], amount, order_id, callback)

    payload = {
        'amount': amount,
        'order_id': order_id,
        'callback': callback,
        'sign': sign,
        'description': description,
    }

    full_name = f"{first_name or ''} {last_name or ''}".strip()
    if full_name:
        payload['name'] = full_name

    # فیلدهای اختصاصی دایرکت‌پی (پی‌استار به این‌ها نیاز ندارد)
    if gateway.get('send_products'):
        payload['first_name'] = first_name
        payload['last_name'] = last_name
        payload['products'] = [{
            'code': '2323',
            'price': str(amount),
            'quantity': 1000000,
        }]
    if gateway.get('wallet'):
        payload['wallet'] = gateway['wallet']

    url = f"{gateway['base_url'].rstrip('/')}/create"
    logger.info("[%s] create transaction -> %s | order_id=%s amount=%s",
                gateway['name'], url, order_id, amount)
    return requests.post(url, json=payload, headers=_headers(gateway), timeout=timeout)


def payment_redirect_url(gateway, token):
    """آدرس هدایت کاربر به صفحه‌ی پرداخت درگاه."""
    url = f"{gateway['base_url'].rstrip('/')}/payment?token={token}"
    if gateway.get('referer'):
        url += f"&referer={gateway['referer']}"
    return url


def verify_transaction(gateway, amount, ref_num, card_number, tracking_code, timeout=25):
    """
    تأیید نهایی تراکنش. amount باید به ریال و عدد صحیح باشد.
    برگرداندن آبجکت response (requests.Response).
    """
    sign = _verify_sign(gateway['sign_key'], amount, ref_num, card_number, tracking_code)
    data = {
        'ref_num': ref_num,
        'amount': amount,
        'sign': sign,
    }
    url = f"{gateway['base_url'].rstrip('/')}/verify"
    logger.info("[%s] verify transaction -> %s | ref_num=%s amount=%s",
                gateway['name'], url, ref_num, amount)
    return requests.post(url, json=data, headers=_headers(gateway), timeout=timeout, verify=False)
