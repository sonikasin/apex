import requests
from requests.auth import HTTPBasicAuth
import logging
from django.shortcuts import render, redirect
from .models import PropAccount, PropOrder,FreeAccountQuota, Ticket,Wallet,WalletTransaction, CustomUser,DiscountCode, PlanStage,PropPlan,Referral,Wallet,StageUpgradeRequest
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import random
import string
from django.urls import reverse
from django.conf import settings
from django.db import transaction
import requests
from django.http import JsonResponse
from datetime import datetime

logger = logging.getLogger(__name__)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import PropPlan, PropOrder, BlogPost
import uuid


def index(request):
    plans = PropPlan.objects.all().order_by('account_size', 'name')
    account_sizes = plans.values_list('account_size', flat=True).distinct().order_by('account_size')
    plan_types = PropPlan.PLAN_TYPES  # استفاده از انتخاب‌های مدل

    # انتخاب پلن پیش‌فرض (دو مرحله‌ای با 1000 دلار)
    selected_plan = None
    if request.GET.get('plan_type') and request.GET.get('account_size'):
        selected_plan = plans.filter(
            name=request.GET.get('plan_type'),
            account_size=request.GET.get('account_size')
        ).first()
    if not selected_plan:
        selected_plan = plans.filter(name='two_stage', account_size=1000).first()

    # دریافت آخرین پست‌های بلاگ
    latest_posts = BlogPost.objects.order_by('-created_at')[:3]

    return render(request, 'index.html', {
        'plans': plans,
        'account_sizes': account_sizes,
        'plan_types': plan_types,
        'selected_plan': selected_plan,
        'latest_posts': latest_posts,
    })

def get_plan_details(request):
    plan_type = request.GET.get('plan_type')
    account_size = request.GET.get('account_size')
    
    try:
        plan = PropPlan.objects.get(name=plan_type, account_size=account_size)
        stages = plan.stages.all()
        stages_data = [
            {
                'stage_type': stage.get_stage_type_display(),
                'profit_target': float(stage.profit_target) if stage.profit_target else None,
                'profit_target_percent': float(stage.profit_target_percent) if stage.profit_target_percent else None,
                'max_loss_percent': float(stage.max_loss_percent),
                'max_daily_loss_percent': float(stage.max_daily_loss_percent),
                'min_trading_days': stage.min_trading_days if stage.min_trading_days else '-',
                'floating_risk_percent': float(stage.floating_risk_percent) if stage.floating_risk_percent else None,
            }
            for stage in stages
        ]
        data = {
            'id': plan.id,
            'name': plan.get_name_display(),
            'account_size': float(plan.account_size),
            'price': float(plan.price),
            'leverage': plan.leverage,
            'stages': stages_data,
        }
        return JsonResponse({'success': True, 'plan': data})
    except PropPlan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'پلن یافت نشد.'})


from decimal import Decimal

# نرخ تبدیل تتر به تومان (می‌توانید این را از تنظیمات یا API دریافت کنید)
TETHER_TO_TOMAN_RATE = Decimal('166100')
FIXED_DOLLAR_RATE = Decimal('99000')



@login_required
def order_view(request, plan_id):
    plan = get_object_or_404(PropPlan, id=plan_id)
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    brokers = ['LiteFinance-MT5-Demo' , 'GlobalPrime-Demo']
    
    # Calculate initial price
    original_price_usd = plan.price
    final_price_usd = original_price_usd
    final_price_toman = original_price_usd * TETHER_TO_TOMAN_RATE
    
    discount_amount_usd = Decimal('0')
    discount_code = None
    discount_code_str = request.POST.get('discount_code', '').strip() if request.method == 'POST' else ''
    
    if request.method == 'POST':
        server = request.POST.get('server')
        payment_method = request.POST.get('payment_method')
        use_wallet = request.POST.get('use_wallet') == 'on'
        use_fixed_dollar = request.POST.get('fixed_dollar') == 'on'
        if use_fixed_dollar:
            dollar_rate = FIXED_DOLLAR_RATE
        else:
            dollar_rate = TETHER_TO_TOMAN_RATE

        final_price_toman = original_price_usd * dollar_rate
        # Validate discount code
        if discount_code_str:
            try:
                discount_code = DiscountCode.objects.get(code=discount_code_str, active=True)
                
                # Check expiration
                if discount_code.expiration_date and discount_code.expiration_date < timezone.now():
                    messages.error(request, 'کد تخفیف منقضی شده است.')
                    return render(request, 'order.html', {
                        'plan': plan,
                        'brokers': brokers,
                        'original_price_usd': original_price_usd,
                        'final_price_usd': final_price_usd,
                        'final_price_toman': final_price_toman,
                        'discount_code': discount_code_str
                    })
                # Check usage limit
                if discount_code.max_uses_active and discount_code.max_uses <= 0:
 
                    messages.error(request, 'کد تخفیف به حداکثر استفاده رسیده است.')
                    return render(request, 'order.html', {
                        'plan': plan,
                        'brokers': brokers,
                        'original_price_usd': original_price_usd,
                        'final_price_usd': final_price_usd,
                        'final_price_toman': final_price_toman,
                        'discount_code': discount_code_str
                    })
                # Check first purchase only
                if (
                    discount_code.first_purchase_only 
                    and not PropOrder.objects.filter(
                    user=request.user, 
                    status='completed'
                    ).exists()
                ):
                    messages.error(request, 'این کد تخفیف فقط برای خرید اول قابل استفاده است.')
                    return render(request, 'order.html', {
                        'plan': plan,
                        'brokers': brokers,
                        'original_price_usd': original_price_usd,
                        'final_price_usd': final_price_usd,
                        'final_price_toman': final_price_toman,
                        'discount_code': discount_code_str
                    })
                # Check allowed users
                if discount_code.users.exists() and request.user not in discount_code.users.all():
                    messages.error(request, 'شما مجاز به استفاده از این کد تخفیف نیستید.')
                    return render(request, 'order.html', {
                        'plan': plan,
                        'brokers': brokers,
                        'original_price_usd': original_price_usd,
                        'final_price_usd': final_price_usd,
                        'final_price_toman': final_price_toman,
                        'discount_code': discount_code_str
                    })
                # Check allowed plans
                if discount_code.plans.exists() and plan not in discount_code.plans.all():
                    messages.error(request, 'این کد تخفیف برای این پلن قابل استفاده نیست.')
                    return render(request, 'order.html', {
                        'plan': plan,
                        'brokers': brokers,
                        'original_price_usd': original_price_usd,
                        'final_price_usd': final_price_usd,
                        'final_price_toman': final_price_toman,
                        'discount_code': discount_code_str
                    })
                # Calculate discount
                if discount_code.discount_type == 'percent':
                    discount_amount_usd = original_price_usd * (Decimal(str(discount_code.discount_value)) / Decimal('100'))
                else:  # amount
                    discount_amount_usd = Decimal(str(discount_code.discount_value))
                final_price_usd = max(original_price_usd - discount_amount_usd, Decimal('0'))
                final_price_toman = final_price_usd * dollar_rate

            except DiscountCode.DoesNotExist:
                messages.error(request, 'کد تخفیف نامعتبر است.')
                return render(request, 'order.html', {
                    'plan': plan,
                    'brokers': brokers,
                    'original_price_usd': original_price_usd,
                    'final_price_usd': final_price_usd,
                    'final_price_toman': final_price_toman,
                    'discount_code': discount_code_str
                })
        
        if not server:
            messages.error(request, 'لطفاً یک بروکر انتخاب کنید.')
            return render(request, 'order.html', {
                'plan': plan,
                'brokers': brokers,
                'original_price_usd': original_price_usd,
                'final_price_usd': final_price_usd,
                'final_price_toman': final_price_toman,
                'discount_code': discount_code_str
            })
        
        # Validate wallet balance if use_wallet is selected
        wallet_deduction_usd = Decimal('0')
        if use_wallet and payment_method == 'rial':
            if wallet.balance_usd >= final_price_usd:
                wallet_deduction_usd = final_price_usd
                remaining_price_usd = Decimal('0')
                remaining_price_toman = Decimal('0')
            else:
                wallet_deduction_usd = wallet.balance_usd
                remaining_price_usd = final_price_usd - wallet_deduction_usd
                remaining_price_toman = remaining_price_usd * dollar_rate
                if wallet.balance_usd < final_price_usd and remaining_price_usd > 0:
                    messages.error(request, f'موجودی کیف پول ({wallet.balance_usd} دلار) کافی نیست.  از صفحه داشبورد شارژ کنید مبلغ مورد نیاز: {final_price_usd} دلار.')
                    return render(request, 'order.html', {
                        'plan': plan,
                        'brokers': brokers,
                        'original_price_usd': original_price_usd,
                        'final_price_usd': final_price_usd,
                        'final_price_toman': final_price_toman,
                        'discount_code': discount_code_str
                    })
        else:
            remaining_price_usd = final_price_usd
            remaining_price_toman = final_price_toman
        
        # Create order

        order = PropOrder(
            order_number=str(uuid.uuid4())[:20],
            plan=plan,
            user=request.user,
            status='pending',
            server=server,
            payment_method=payment_method,
            discount_code=discount_code,
            original_price_usd=original_price_usd,
            final_price_usd=remaining_price_usd,
            final_price_toman=remaining_price_toman,
            dollar_price=dollar_rate,
            used_wallet=use_wallet
        )
        order.save()
        
        # Deduct wallet balance if applicable
        if use_wallet and wallet_deduction_usd > 0:
            wallet.balance_usd -= wallet_deduction_usd
            wallet.save()
            logger.info(f"Deducted {wallet_deduction_usd} USD from wallet for order {order.id}")
        
        # Use discount code
        if discount_code:
            discount_code.use_code()
        
        # Handle payment
        if payment_method == 'rial':
            if use_wallet and wallet_deduction_usd >= final_price_usd:
                # Full payment via wallet
                order.status = 'completed'
                order.save()
                
                # Assign account
                account = PropAccount.objects.filter(
                    user__isnull=True,
                    order__isnull=True,
                    plan__isnull=True,
                    server=order.server,
                    balance=order.plan.account_size
                ).first()
                if account:
                    account.user = order.user
                    account.order = order
                    account.plan = order.plan
                    plan_stage = PlanStage.objects.filter(
                        plan=order.plan,
                        stage_type=order.plan.level
                    ).first()
                    if plan_stage:
                        account.daily_draw_percent = plan_stage.max_daily_loss_percent
                        account.total_draw_percent = plan_stage.max_loss_percent
                        account.floating_risk_percent = plan_stage.floating_risk_percent
                        account.profit_percent = plan_stage.profit_target_percent
                        if account.plan.name in ["ریل", "zero"]:
                            account.level = "Real"
                        else:
                            account.level = "level1"
                    account.save()
                    
                    # Handle referral bonus
                    
                    
                    
                    
                    messages.success(request, 'پرداخت با کیف پول موفق بود و حساب به شما اختصاص یافت.')
                    success_url = f"{reverse('payment_success')}?{urlencode({'msg': 'پرداخت با کیف پول موفق بود و حساب به شما اختصاص یافت.'})}"
                    try:
            
                        FLASK_API_URL = "http://194.62.43.229:800/api/create_user"
                
                        account_number = getattr(account, 'login', None) or \
                                        getattr(account, 'account_number', None) or \
                                        getattr(account, 'mt5_login', None) or \
                                        f"prop_{account.id}"

                        username = str(account_number).strip()
                        password = username                    # رمز = شماره حساب (طبق درخواست شما)

                        payload = {
                            "username": username,
                            "password": password,
                            "days": 30,
                            "max_volume_mb": 2048              # حجم دلخواه (۲ گیگ) - میتونی تغییر بدی
                        }

                        response = requests.post(
                            FLASK_API_URL,
                            json=payload,
                            auth=HTTPBasicAuth("admin", "admin123"),   # ←←← حتماً این رمز ادمین رو تغییر بده!
                            timeout=15
                        )

                        if response.status_code == 201:
                            logger.info(f"✅ کاربر ApexFX ساخته شد | Username: {username} | Password: {password}")
                        elif response.status_code == 409:
                            logger.warning(f"کاربر ApexFX قبلاً وجود داشته: {username}")
                        else:
                            logger.error(f"❌ خطا در ساخت کاربر ApexFX: {response.status_code} - {response.text}")

                    except Exception as e:
                        logger.error(f"Exception در ساخت کاربر ApexFX برای سفارش {order.id}: {str(e)}", exc_info=True)
                        return redirect(success_url)
                else:
                    # Refund wallet if no account is available
                    if wallet_deduction_usd > 0:
                        wallet.balance_usd += wallet_deduction_usd
                        wallet.save()
                        logger.info(f"Refunded {wallet_deduction_usd} USD to wallet for order {order.id}")
                    messages.warning(request, 'پرداخت با کیف پول موفق بود، اما حساب مناسب یافت نشد. با پشتیبانی تماس بگیرید.')
                    success_url = f"{reverse('payment_success')}?{urlencode({'msg': 'پرداخت با کیف پول موفق بود، اما حساب مناسب یافت نشد. با پشتیبانی تماس بگیرید.'})}"
                    return redirect(success_url)
            else:
                # Partial wallet payment or no wallet, proceed to payment gateway
                logger.info(f"Order {order.id} created: wallet_deduction={wallet_deduction_usd} USD, remaining={remaining_price_usd} USD via gateway")
                messages.info(request, f'موجودی کیف پول ({wallet_deduction_usd} دلار) برای سفارش استفاده شد. لطفاً مابقی ({remaining_price_usd} دلار) را از طریق درگاه پرداخت کنید.')
                return redirect('payment_gateway', order_id=order.id)
        else:
            messages.info(request, 'پرداخت با تتر در حال حاضر غیرفعال است.')
            return redirect('order', plan_id=plan_id)
    
    return render(request, 'order.html', {
        'plan': plan,
        'brokers': brokers,
        'original_price_usd': original_price_usd,
        'final_price_usd': final_price_usd,
        'final_price_toman': final_price_toman,
        'discount_code': discount_code_str
    })
    
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
import hmac
import hashlib
import requests
import logging
def generate_paystar_sign(amount, order_id, callback_url, sign_key):
    sign_data = f"{amount}#{order_id}#{callback_url}"
    return hmac.new(sign_key.encode(), sign_data.encode(), hashlib.sha512).hexdigest()
@login_required
def payment_gateway(request, order_id):
    order = get_object_or_404(PropOrder, id=order_id, user=request.user)
    
    # Use the updated final price after any wallet deduction
    final_price_toman = order.final_price_toman
    final_price_usd = order.final_price_usd
    
    if request.method == 'POST':
        # PayStar configurations
        token = "6y63e4oex3q822"
        sign_key = "B3D7A776EC4BF4FB24CAF4F7A5C301600CB8B23489330669BB5B7B9AB1F1B153276D789EC123E8F0984DC3DA1A507329C23A9FB86237D1F6823FDF69D1F29FA8D21CB2A78DA3CDB5A748C062B1DFD2CABE4EE2BD4F778E45F992A17FA1064D4AF8D7B5961964E94DD1FBE8EAA205F56F6AFB6F93C7BA05A64C94218291927147"
        callback_url = 'https://apexfx.info/payment-callback/'  # Update to your actual callback URL

        # Split user's full name
      
        first_name = request.user.first_name
        last_name = request.user.last_name

        try:
            # Generate PayStar sign
            amount = int(final_price_toman * 10)  # Convert to Rial
            order_id_str = str(order.id)
            sign = generate_paystar_sign(amount, order_id_str, callback_url, sign_key)

            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }
            payload = {
                "amount": amount,
                "order_id": order_id_str,
                "callback": callback_url,
                "first_name": first_name,
                "last_name": last_name,
                "products": [
                    {
                        "code": "2323",
                        "price": str(amount),
                        "quantity": 1000000
                    }
                ],
                "sign": sign,
                "wallet": "AJKVW4",
                "description": f'order id: {order.id} product: {order.plan.name}',
            }

            proxies = {
                'http': 'http://81.12.93.154:8888',
                'https': 'https://81.12.93.154:8888',
            }
            proxy_url = "https://api.directpay.finance/api/pardakht/create"
            # Send request to PayStar API
            response = requests.post(
                proxy_url,
                json=payload,
                headers=headers,
                timeout=60
            )
            logger.info(f"PayStar create transaction response: {response.status_code} - {response.text}")

            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == 1:
                    pay_token = response_data['data']['token']
                    return redirect(f"https://api.directpay.finance/api/pardakht/payment?token={pay_token}&referer=https://apexfx.net")
                else:
                    print(request, f"خطا در ایجاد تراکنش: {response_data.get('message', 'Unknown error')}")
                    error_url = f"{reverse('payment_error')}?{urlencode({'msg': response_data.get('message', 'Unknown error')})}"
                    return redirect(error_url)
            else:
                print(request, "ارتباط با درگاه پرداخت ناموفق بود.")
                return redirect(error_url)
        except requests.exceptions.RequestException as e:
            logger.error(f"PayStar create transaction exception: {str(e)}")
            messages.error(request, "خطا در ارتباط با درگاه پرداخت.")
            return redirect(error_url)
    
    return render(request, 'payment.html', {
        'order': order,
        'original_price_usd': order.original_price_usd,
        'final_price_usd': final_price_usd,
        'final_price_toman': final_price_toman
    })
import json
from django.views.decorators.csrf import csrf_exempt

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import redirect, reverse
from django.contrib import messages
from decimal import Decimal
import hmac
import hashlib
import requests
import logging

logger = logging.getLogger(__name__)
def generate_paystar_verify_sign(amount, ref_num, card_number, tracking_code):
    sign_key = "B3D7A776EC4BF4FB24CAF4F7A5C301600CB8B23489330669BB5B7B9AB1F1B153276D789EC123E8F0984DC3DA1A507329C23A9FB86237D1F6823FDF69D1F29FA8D21CB2A78DA3CDB5A748C062B1DFD2CABE4EE2BD4F778E45F992A17FA1064D4AF8D7B5961964E94DD1FBE8EAA205F56F6AFB6F93C7BA05A64C94218291927147"
    sign_data = f"{int(amount)}#{str(ref_num)}#{str(card_number)}#{str(tracking_code)}"
    return hmac.new(sign_key.encode(), sign_data.encode(), hashlib.sha512).hexdigest()
import json
import requests
import random
import string
from decimal import Decimal
from django.urls import reverse
from urllib.parse import urlencode
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def payment_callback(request):
    if request.method != 'POST':
        logger.error("Invalid request method for payment callback")
        error_url = f"{reverse('payment_error')}?{urlencode({'msg': 'درخواست نامعتبر است.'})}"
        return redirect(error_url)

    logger.info(f"Raw POST data: {request.POST}")
    logger.info(f"Raw request body: {request.body}")

    data = request.POST
    status = data.get('status')
    ref_num = data.get('ref_num')
    order_id = data.get('order_id')
    card_number = data.get('card_number')
    tracking_code = data.get('tracking_code')
    transaction_id = data.get('transaction_id')
    logger.info(f"Callback data: status={status}, ref_num={ref_num}, order_id={order_id}")

    is_wallet_transaction = str(order_id).startswith('1831')

    if is_wallet_transaction:
        try:
            wallet_transaction_id = int(str(order_id)[4:])
            transaction = WalletTransaction.objects.get(id=wallet_transaction_id)
            order = None
        except WalletTransaction.DoesNotExist:
            logger.error(f"No wallet transaction found for {order_id}")
            return redirect(f"{reverse('wallet_error')}?{urlencode({'msg': 'تراکنش کیف پول یافت نشد.'})}")
    else:
        try:
            order = PropOrder.objects.get(id=order_id)
            transaction = None
        except PropOrder.DoesNotExist:
            logger.error(f"No order found for {order_id}")
            return redirect(f"{reverse('payment_error')}?{urlencode({'msg': 'سفارش یافت نشد.'})}")

    if status != '1':
        logger.error(f"Transaction failed: status={status}")
        if order and order.used_wallet:
            wallet = Wallet.objects.get(user=order.user)
            wallet.balance_usd += (order.original_price_usd - order.final_price_usd)
            wallet.save()
        if order:
            order.status = 'failed'
            order.save()
        if transaction:
            transaction.status = 'failed'
            transaction.save()
        return redirect(f"{reverse('payment_error' if not is_wallet_transaction else 'wallet_error')}?{urlencode({'msg': 'تراکنش ناموفق بود.'})}")

    expected_amount = int((order.final_price_toman if order else transaction.amount_toman) * 10)
    sign = generate_paystar_verify_sign(expected_amount, ref_num, card_number, tracking_code)

    verify_data = {
        "ref_num": ref_num,
        "amount": expected_amount,
        "sign": sign,
    }
    headers = {
        'Authorization': 'Bearer 6y63e4oex3q822',
        'Content-Type': 'application/json',
    }

    try:
        session = requests.Session()
        response = session.post(
            "https://api.directpay.finance/api/pardakht/verify",
            json=verify_data,
            headers=headers,
            timeout=25,
            verify=False
        )
        logger.info(f"Verify response: {response.status_code} - {response.text[:300]}")

        if response.status_code == 200 and response.json().get('status') == 1:
            if is_wallet_transaction:
                transaction.status = 'completed'
                transaction.save()
                wallet = transaction.user.wallet
                wallet.balance_usd += transaction.amount_usd * Decimal('1.12')
                wallet.save()

                try:
                    referral = Referral.objects.get(referred=transaction.user)
                    referrer = referral.referrer
                    referral_bonus_usd = (expected_amount / TETHER_TO_TOMAN_RATE) * Decimal('0.05')
                    referral.earnings += referral_bonus_usd
                    referral.save()
                except Referral.DoesNotExist:
                    logger.info(f"No referral found for user {transaction.user.email}")

                messages.success(request, 'واریز به کیف پول با موفقیت انجام شد.')

                session_key = f'wallet_transaction_id_{wallet_transaction_id}'
                if request.session.get(session_key):
                    del request.session[session_key]
                    request.session.modified = True

                success_url = f"{reverse('wallet_success')}?{urlencode({'msg': 'واریز به کیف پول با موفقیت انجام شد.'})}"
                return redirect(success_url)
            order.transaction_id = transaction_id
            order.status = 'completed'
            order.save()

            account = PropAccount.objects.filter(
                user__isnull=True,
                order__isnull=True,
                plan__isnull=True,
                server=order.server,
                balance=order.plan.account_size
            ).first()

            if account:
                account.user = order.user
                account.order = order
                account.plan = order.plan
                plan_stage = PlanStage.objects.filter(
                    plan=order.plan,
                    stage_type=order.plan.level
                ).first()

                if plan_stage:
                    account.daily_draw_percent = plan_stage.max_daily_loss_percent
                    account.total_draw_percent = plan_stage.max_loss_percent
                    account.floating_risk_percent = plan_stage.floating_risk_percent
                    account.profit_percent = plan_stage.profit_target_percent
                    account.level = "Real" if order.plan.name in ["ریل", "zero"] else "level1"
                account.save()
                order.accnum = int(account.account_number)
                order.save()
                try:
                    referral = Referral.objects.get(referred=order.user)
                    referrer = referral.referrer
                    referral_bonus_usd = order.original_price_usd * Decimal('0.05')
                    referral.earnings += referral_bonus_usd
                    referral.save()
                except Referral.DoesNotExist:
                    logger.info(f"No referral found for user {order.user.email}")

                wallet_deduction_usd = order.original_price_usd - order.final_price_usd if order.used_wallet else Decimal('0')
                

                messages.success(request, 'پرداخت موفق بود و حساب به شما اختصاص یافت.')
                success_url = f"{reverse('payment_success')}?{urlencode({'msg': 'پرداخت موفق بود و حساب به شما اختصاص یافت.'})}"
            try:
                # آدرس API فلاسک (اگر روی همون سرور هست از 127.0.0.1 استفاده کن)
                FLASK_API_URL = "http://194.62.43.229:800/api/create_user"
                
                account_number = getattr(account, 'login', None) or \
                                 getattr(account, 'account_number', None) or \
                                 getattr(account, 'mt5_login', None) or \
                                 f"prop_{account.id}"

                username = str(account_number).strip()
                password = username                    # رمز = شماره حساب (طبق درخواست شما)

                payload = {
                    "username": username,
                    "password": password,
                    "days": 30,
                    "max_volume_mb": 2048              # حجم دلخواه (۲ گیگ) - میتونی تغییر بدی
                }

                response = requests.post(
                    FLASK_API_URL,
                    json=payload,
                    auth=HTTPBasicAuth("admin", "admin123"),   # ←←← حتماً این رمز ادمین رو تغییر بده!
                    timeout=15
                )

                if response.status_code == 201:
                    logger.info(f"✅ کاربر ApexFX ساخته شد | Username: {username} | Password: {password}")
                elif response.status_code == 409:
                    logger.warning(f"کاربر ApexFX قبلاً وجود داشته: {username}")
                else:
                    logger.error(f"❌ خطا در ساخت کاربر ApexFX: {response.status_code} - {response.text}")

            except Exception as e:
                logger.error(f"Exception در ساخت کاربر ApexFX برای سفارش {order.id}: {str(e)}", exc_info=True)
            # ================================================================
                return redirect(success_url)
            else:
                if order.used_wallet:
                    wallet = Wallet.objects.get(user=order.user)
                    wallet_deduction_usd = order.original_price_usd - order.final_price_usd
                    wallet.balance_usd += wallet_deduction_usd
                    wallet.save()
                    logger.info(f"Refunded {wallet_deduction_usd} USD to wallet for order {order.id} due to no available account")
                messages.warning(request, 'پرداخت موفق بود، اما حساب مناسب یافت نشد. با پشتیبانی تماس بگیرید.')
                success_url = f"{reverse('payment_success')}?{urlencode({'msg': 'پرداخت موفق بود، اما حساب مناسب یافت نشد. با پشتیبانی تماس بگیرید.'})}"
                return redirect(success_url)
        else:
            if order and order.used_wallet:
                wallet = Wallet.objects.get(user=order.user)
                wallet_deduction_usd = order.original_price_usd - order.final_price_usd
                wallet.balance_usd += wallet_deduction_usd
                wallet.save()
                logger.info(f"Refunded {wallet_deduction_usd} USD to wallet for failed order {order.id}")
            if order:
                order.status = 'failed'
                order.save()
            if transaction:
                transaction.status = 'failed'
                transaction.save()
            error_message = f'پرداخت ناموفق بود: {response.json().get("message", "Unknown error")}'
            logger.error(f"Order {order_id} verification failed: {response.text}")
            error_url = f"{reverse('payment_error' if not is_wallet_transaction else 'wallet_error')}?{urlencode({'msg': error_message})}"
            return redirect(error_url)
    except requests.exceptions.RequestException as e:
        logger.error(f"PayStar verify request exception: {str(e)}")
        if order and order.used_wallet:
            wallet = Wallet.objects.get(user=order.user)
            wallet_deduction_usd = order.original_price_usd - order.final_price_usd
            wallet.balance_usd += wallet_deduction_usd
            wallet.save()
            logger.info(f"Refunded {wallet_deduction_usd} USD to wallet for failed order {order.id}")
        if order:
            order.status = 'failed'
            order.save()
        if transaction:
            transaction.status = 'failed'
            transaction.save()
        error_url = f"{reverse('payment_error' if not is_wallet_transaction else 'wallet_error')}?{urlencode({'msg': 'خطا در تأیید پرداخت.'})}"
        return redirect(error_url)
token = "7704037388:AAGBGS0zyoJUHQoeOr2jGsFuPYDP_xvVMq0"
chat_id = "-1002871104747"
def send_telegram_message(message):
    """ارسال پیام به تاپیک خاص در گروه تلگرام"""
    telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML',  # برای فرمت بهتر
    }
    try:
        response = requests.post(telegram_url, json=payload)
        response.raise_for_status()  # خطا در صورت عدم موفقیت درخواست
    except requests.RequestException as e:
        # لاگ کردن خطا
        print(f"خطا در ارسال پیام به تلگرام: {e}")
from django.db.models import Sum
@login_required
def dashboard(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    # ایجاد خودکار Referral فقط اگر مدلی با ایمیل معرفی‌شده (referred) وجود نداشته باشه
    if not hasattr(request.user, 'referral_received'):
        Referral.objects.create(
            referred=request.user,
            referrer=None,
            earnings=Decimal('0.00')
        )
        messages.info(request, 'رفرال پیش‌فرض برای شما ایجاد شد.')
    
    # درآمد رفرال
    total_referral_earnings = Decimal('0.00')
    if hasattr(request.user, 'referral_received'):
        total_referral_earnings = request.user.referral_received.earnings or Decimal('0.00')

    # مدیریت ظرفیت اکانت رایگان
    today = timezone.now().date()
    quota, created = FreeAccountQuota.objects.get_or_create(
        date=today,
        defaults={'total_capacity': 500, 'allocated_count': 0}
    )

    # محاسبه ظرفیت باقیمانده
    remaining_quota = quota.total_capacity - quota.allocated_count

    if request.method == 'POST' and 'request_free_account' in request.POST:
        # بررسی ظرفیت
        if not quota.is_capacity_available():
            return JsonResponse({
                'status': 'error',
                'message': 'ظرفیت اکانت‌های رایگان امروز تکمیل شده است. لطفاً فردا تلاش کنید.'
            })

        # بررسی احراز هویت
        

        # بررسی عدم وجود حساب پراپ
        if PropAccount.objects.filter(user=request.user).exists():
            return JsonResponse({
                'status': 'error',
                'message': 'شما قبلاً یک حساب پراپ دارید. هر کاربر فقط می‌تواند یک اکانت رایگان دریافت کند.'
            })

        # یافتن حساب مناسب
        account = PropAccount.objects.filter(
            user__isnull=True,
            order__isnull=True,
            plan__isnull=True,
            server__startswith='Global',
            balance=Decimal('1000.00')
        ).first()

        if not account:
            return JsonResponse({
                'status': 'error',
                'message': 'در حال حاضر حساب رایگانی با مشخصات مورد نظر موجود نیست. لطفاً بعداً تلاش کنید.'
            })

        # یافتن پلن دو مرحله‌ای (قرعه‌کشی)
        plan = PropPlan.objects.filter(name='two_stage_lottery', account_size=Decimal('1000.00')).first()
        if not plan:
            return JsonResponse({
                'status': 'error',
                'message': 'پلن "دو مرحله‌ای (قرعه‌کشی)" با موجودی 1000 دلار یافت نشد. با پشتیبانی تماس بگیرید.'
            })

        try:
            with transaction.atomic():
                # تخصیص حساب به کاربر و پلن
                account.user = request.user
                account.plan = plan
                plan_stage = PlanStage.objects.filter(
                    plan=plan,
                    stage_type=plan.level
                ).first()
                if plan_stage:
                    account.daily_draw_percent = plan_stage.max_daily_loss_percent
                    account.total_draw_percent = plan_stage.max_loss_percent
                    account.floating_risk_percent = plan_stage.floating_risk_percent
                    account.profit_percent = plan_stage.profit_target_percent
                    account.level = 'level1'
                account.status = 'active'
                account.save()

                # افزایش تعداد تخصیص‌یافته
                quota.allocate_account()

                # ارسال اعلان تلگرام
                telegram_message = (
                    f"اکانت رایگان تخصیص یافت!\n"
                    f"کاربر: {request.user.email}\n"
                    f"نوع پلن: {plan.get_name_display()}\n"
                    f"شماره حساب: {account.account_number}\n"
                    f"سرور: {account.server}\n"
                    f"رمز سرمایه‌گذار: {account.investor_password}\n"
                )
                send_telegram_message(telegram_message)

                return JsonResponse({
                    'status': 'success',
                    'message': 'اکانت رایگان با موفقیت به شما تخصیص یافت.',
                    'redirect_url': reverse('payment_success') + '?' + urlencode({'msg': 'اکانت رایگان با موفقیت به شما تخصیص یافت.'})
                })

        except Exception as e:
            logger.error(f"خطا در تخصیص اکانت رایگان برای کاربر {request.user.email}: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'خطایی در تخصیص اکانت رایگان رخ داد. لطفاً با پشتیبانی تماس بگیرید.'
            })

    return render(request, 'dashboard.html', {
        'wallet': wallet,
        'total_referral_earnings': total_referral_earnings,
        'free_account_quota': quota.total_capacity,
        'free_account_allocated': quota.allocated_count,
        'remaining_quota': remaining_quota  # اضافه کردن ظرفیت باقیمانده
    })

import uuid
@login_required
def wallet_deposit(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    amount_toman = request.POST.get('amount_toman', '').strip() if request.method == 'POST' else ''
    if request.method == 'POST':
        try:
            amount_toman = Decimal(amount_toman)
            if amount_toman <= 0:
                messages.error(request, 'مبلغ باید بیشتر از صفر باشد.')
                return render(request, 'wallet_deposit.html', {
                    'wallet': wallet,
                    'amount_toman': amount_toman
                })
            amount_usd = amount_toman / TETHER_TO_TOMAN_RATE
            transaction = WalletTransaction(
                user=request.user,
                transaction_type='deposit',
                amount_toman=amount_toman,
                amount_usd=amount_usd,
                status='pending',
                transaction_id=f"WALLET-{str(uuid.uuid4())[:20]}"  # Convert UUID to string before slicing
            )
            transaction.save()
            return redirect('wallet_payment_gateway', transaction_id=transaction.id)
        except ValueError:
            messages.error(request, 'لطفاً یک مبلغ معتبر وارد کنید.')
            return render(request, 'wallet_deposit.html', {
                'wallet': wallet,
                'amount_toman': amount_toman
            })
    return render(request, 'wallet_deposit.html', {
        'wallet': wallet,
        'amount_toman': amount_toman
    })
from urllib.parse import urlencode
def generate_paystar_sign(amount, order_id, callback_url, sign_key):
    sign_data = f"{amount}#{order_id}#{callback_url}"
    return hmac.new(sign_key.encode(), sign_data.encode(), hashlib.sha512).hexdigest()

@login_required
def wallet_payment_gateway(request, transaction_id):
    transaction = get_object_or_404(WalletTransaction, id=transaction_id, user=request.user)
    
    if request.method == 'POST':
        # Prevent infinite redirect loop by checking if already attempted
        if request.session.get(f'payment_attempt_{transaction_id}', False):
            messages.error(request, "خطا: تلاش برای پرداخت مجدد ناموفق بود. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.")
            logger.error(f"Multiple payment attempts for transaction {transaction_id}")
            error_url = f"{reverse('wallet_error')}?{urlencode({'msg': 'تلاش برای پرداخت مجدد ناموفق بود.'})}"
            return redirect(error_url)
        
        # Mark payment attempt in session and store transaction ID
        request.session[f'payment_attempt_{transaction_id}'] = True
        request.session[f'wallet_transaction_id_{transaction_id}'] = transaction.id
        request.session.modified = True
        
        # PayStar configurations
        token = "6y63e4oex3q822"
        sign_key = "B3D7A776EC4BF4FB24CAF4F7A5C301600CB8B23489330669BB5B7B9AB1F1B153276D789EC123E8F0984DC3DA1A507329C23A9FB86237D1F6823FDF69D1F29FA8D21CB2A78DA3CDB5A748C062B1DFD2CABE4EE2BD4F778E45F992A17FA1064D4AF8D7B5961964E94DD1FBE8EAA205F56F6AFB6F93C7BA05A64C94218291927147"
        callback_url = 'https://apexfx.info/payment-callback/'  # Update to your actual callback URL

        # Split user's full name
        first_name = request.user.first_name
        last_name = request.user.last_name

        try:
            # Generate PayStar sign
            amount = int(transaction.amount_toman * 10)  # Convert to Rial
            wallet_order_id = f"1831{transaction.id}"  # Prefix with 1831 for wallet transactions
            sign = generate_paystar_sign(amount, wallet_order_id, callback_url, sign_key)

            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }
            payload = {
                "amount": amount,
                "order_id": wallet_order_id,
                "callback": callback_url,
                "first_name": first_name,
                "last_name": last_name,
                "products": [
                    {
                        "code": "2323",
                        "price": str(amount),
                        "quantity": 1000000
                    }
                ],
                "sign": sign,
                "wallet": "AJKVW4",
                "description": f'wallet transaction id: {transaction.id}',
            }

            proxies = {
                'http': 'http://81.12.93.154:2172',
                'https': 'http://81.12.93.154:2172',
            }
            proxy_url = "https://api.directpay.finance/api/pardakht/create"
            # Send request to PayStar API
            response = requests.post(
                proxy_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            logger.info(f"PayStar create transaction response for wallet: {response.status_code} - {response.text}")

            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == 1:
                    pay_token = response_data['data']['token']
                    # Clear session flags after successful redirect
                    del request.session[f'payment_attempt_{transaction_id}']
                    del request.session[f'wallet_transaction_id_{transaction_id}']
                    request.session.modified = True
                    logger.info(f"Redirecting to PayStar payment: https://api.directpay.finance/api/pardakht/payment?token={pay_token}")
                    return redirect(f"https://api.directpay.finance/api/pardakht/payment?token={pay_token}&referer=https://apexfx.net")
                else:
                    error_message = response_data.get('message', 'خطا در ایجاد تراکنش.')
                    messages.error(request, f"خطا در ایجاد تراکنش: {error_message}")
                    logger.error(f"PayStar error: {error_message}")
                    error_url = f"{reverse('wallet_error')}?{urlencode({'msg': f'خطا در ایجاد تراکنش: {error_message}'})}"
                    return redirect(error_url)
            else:
                messages.error(request, "ارتباط با درگاه پرداخت ناموفق بود.")
                logger.error(f"PayStar failed with status {response.status_code}")
                error_url = f"{reverse('wallet_error')}?{urlencode({'msg': 'ارتباط با درگاه پرداخت ناموفق بود.'})}"
                return redirect(error_url)
        except requests.exceptions.RequestException as e:
            messages.error(request, "خطا در ارتباط با درگاه پرداخت.")
            logger.error(f"PayStar request exception: {str(e)}")
            error_url = f"{reverse('wallet_error')}?{urlencode({'msg': 'خطا در ارتباط با درگاه پرداخت.'})}"
            return redirect(error_url)
    
    return render(request, 'wallet_payment.html', {
        'transaction': transaction
    })
@login_required
def wallet_success(request):
    msg = request.GET.get('msg', 'واریز به کیف پول با موفقیت انجام شد.')
    msg = unquote(msg)
    wallet = Wallet.objects.get(user=request.user)
    return render(request, 'wallet_success.html', {'message': msg, 'wallet': wallet})

@login_required
def wallet_error(request):
    msg = request.GET.get('msg', 'خطایی در واریز به کیف پول رخ داد.')
    msg = unquote(msg)
    wallet = Wallet.objects.get(user=request.user)
    return render(request, 'wallet_error.html', {'message': msg, 'wallet': wallet})
def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        messages.success(request, 'پیام شما با موفقیت دریافت شد!')
        return redirect('contact')
    return render(request, 'contact.html')
def about(request):
    return render(request, 'about.html')
@login_required
def prop_accounts(request):
    accounts = PropAccount.objects.filter(user=request.user)
    print(f"User {request.user.id} ({request.user.email}) - Found {accounts.count()} accounts")
    if accounts.exists():
        print(f"Accounts: {[acc.account_number for acc in accounts]}")  # لیست حساب‌ها در لاگ
    return render(request, 'prop-accounts.html', {'accounts': accounts})
@login_required
def prop_orders(request):
    orders = PropOrder.objects.filter(user=request.user, status='completed')
    return render(request, 'prop-orders.html', {'orders': orders})
@login_required
def ticket_list(request):
    # فقط تیکت‌های کاربر لاگین‌شده را نمایش بده
    tickets = Ticket.objects.filter(user=request.user)
    return render(request, 'ticket-list.html', {'tickets': tickets})


logger = logging.getLogger(__name__)





# ====================== تابع ارسال پیام به روبیکا ======================
def send_rubika_message(text: str, chat_id: str):
    """
    ارسال پیام به گروه یا چت روبیکا
    """
    TOKEN = "BABCDC0HLDGSWXQWGDUWRMFLBVDURFPMGGTJSPIHUOQJHXJXCIZPWIFQHDTSOQKQ"
    url = f"https://botapi.rubika.ir/v3/{TOKEN}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        # "disable_notification": False,   # اگر نمی‌خوای نوتیفیکیشن بیاد True کن
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            # بسته به ساختار پاسخ روبیکا (معمولاً status یا ok)
            if result.get("status") == "OK" or result.get("ok") is True:
                logger.info(f"پیام با موفقیت به روبیکا ارسال شد | chat_id: {chat_id}")
                return True
            else:
                logger.error(f"خطای API روبیکا: {result}")
                return False
        else:
            logger.error(f"خطای HTTP {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"خطای شبکه در ارسال به روبیکا: {e}")
        return False
    except Exception as e:
        logger.error(f"خطای غیرمنتظره در send_rubika_message: {e}")
        return False
# ====================== ویوی جزئیات تیکت ======================
@login_required
def ticket_detail(request, ticket_number):
    ticket = get_object_or_404(Ticket, ticket_number=ticket_number, user=request.user)
    
    if request.method == 'POST':
        # بررسی اینکه تیکت بسته نباشد
        if ticket.status == 'closed':
            messages.error(request, 'این تیکت بسته شده است و نمی‌توانید پاسخ دهید.')
            return redirect('ticket_detail', ticket_number=ticket_number)
        
        message = request.POST.get('message')
        if message:
            # تبدیل زمان جاری به زمان محلی سیستم (آسیا/تهران)
            local_time = timezone.localtime(timezone.now())
            
            # اضافه کردن پیام کاربر به تیکت
            ticket.messages.append({
                'text': message,
                'timestamp': local_time.strftime('%H:%M - %Y/%m/%d'),  # نمایش به صورت (ساعت - تاریخ میلادی محلی)
                'sender': 'user'
            })
            ticket.save()

            # ==================== ساخت پیام برای روبیکا ====================
            rubika_message = (
                f"📩 پاسخ جدید به تیکت!\n\n"
                f"شماره تیکت: {ticket.ticket_number}\n"
                f"پیام:\n{message}\n"
            )

            # اگر بخوای اطلاعات بیشتری مثل موضوع یا دپارتمان هم بفرستی:
            rubika_message += (
                f"\nموضوع: {ticket.subject}\n"
                f"دپارتمان: {ticket.department}\n"
            )

            # ارسال به گروه روبیکا
            RUBIKA_GROUP_CHAT_ID = "g0HQxMb0848e3c655fad25b4d642b31f"
            
            success = send_rubika_message(rubika_message, RUBIKA_GROUP_CHAT_ID)
            
            if success:
                messages.success(request, 'پاسخ شما ثبت شد و به گروه روبیکا اطلاع‌رسانی گردید ✅')
            else:
                messages.warning(request, 'پاسخ ثبت شد اما ارسال به گروه روبیکا با مشکل مواجه شد.')

            return redirect('ticket_detail', ticket_number=ticket_number)
    
    return render(request, 'ticket-detail.html', {'ticket': ticket})
from django.db import transaction
from django.db.models import Max, F
from django.utils import timezone
import logging  # برای لاگ خطاها (اختیاری)



@login_required
def create_ticket(request):
    if request.method == 'POST':
        department = request.POST.get('department')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        account_id = request.POST.get('account')
        
        account = None
        if account_id:
            try:
                account = request.user.prop_accounts.get(id=account_id)
            except PropAccount.DoesNotExist:
                messages.error(request, 'حساب انتخاب‌شده معتبر نیست.')
                return redirect('create_ticket')

        ticket = None
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    ticket = Ticket.objects.create(
                        subject=subject,
                        department=department,
                        status='open',
                        user=request.user,
                        account=account,
                        messages=[{
                            'text': message,
                            'timestamp': timezone.now().strftime('%Y/%m/%d - %H:%M'),
                            'sender': 'user'
                        }]
                    )
                    
                    # تولید شماره تیکت
                    proposed_number = f"#{ticket.id}"
                    if Ticket.objects.filter(ticket_number=proposed_number).exclude(id=ticket.id).exists():
                        proposed_number = f"#{uuid.uuid4().hex[:8].upper()}"
                    
                    ticket.ticket_number = proposed_number
                    ticket.save(update_fields=['ticket_number'])
                    break
                    
            except IntegrityError as e:
                if 'ticket_number' in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Retry {attempt+1} for ticket creation: {e}")
                    continue
                else:
                    logger.error(f"Ticket creation failed after {max_retries} retries: {e}")
                    messages.error(request, 'خطا در ایجاد تیکت. لطفاً دوباره تلاش کنید.')
                    return redirect('create_ticket')
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                messages.error(request, 'خطای غیرمنتظره رخ داد.')
                return redirect('create_ticket')

        if not ticket:
            return redirect('create_ticket')

        # ==================== ساخت پیام برای روبیکا ====================
        rubika_message = (
            f"🆕 تیکت جدید ایجاد شد!\n\n"
            f"شماره تیکت: {ticket.ticket_number}\n"
            f"دپارتمان: {department}\n"
            f"موضوع: {subject}\n"
            f"پیام کاربر:\n{message}\n"
        )
        
        if account:
            order_line = f"شماره سفارش: {account.order.id}\n" if hasattr(account, "order") and account.order and account.order.id else ""
            
            rubika_message += (
                f"\n{order_line}"
                f"\n**اطلاعات حساب:**\n"
                f"شماره حساب: {account.account_number or 'نامشخص'}\n"
                f"سرور: {account.server or 'نامشخص'}\n"
                f"رمز سرمایه‌گذار: {account.main_password or 'نامشخص'}\n"
                f"سطح: {account.get_level_display() or 'نامشخص'}\n"
                f"موجودی: {account.balance or 'نامشخص'} دلار\n"
                f"پلن: {account.plan.get_name_display() if getattr(account, 'plan', None) else 'نامشخص'}\n"
            )

        # ارسال پیام به گروه روبیکا
        RUBIKA_GROUP_CHAT_ID = "g0HQxMb0848e3c655fad25b4d642b31f"
        
        success = send_rubika_message(rubika_message, RUBIKA_GROUP_CHAT_ID)
        
        if success:
            messages.success(request, 'تیکت با موفقیت ایجاد شد و به گروه روبیکا اطلاع‌رسانی گردید ✅')
        else:
            messages.warning(request, 'تیکت ایجاد شد اما ارسال پیام به گروه روبیکا با مشکل مواجه شد.')

        return redirect('ticket_list')

    # GET request
    return render(request, 'create-ticket.html')

def send_telegram_message2(message):
    """ارسال پیام به تاپیک خاص در گروه‌های تلگرام (دو گروه)"""
    telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # لیست چت‌آیدی‌ها (دو گروه)
    chat_ids = [
        "-1002771003890",   # گروه قبلی
        "-1003804550499"    # گروه جدید
    ]
    
    for chat_id in chat_ids:
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
        }
        try:
            response = requests.post(telegram_url, json=payload)
            response.raise_for_status()
            print(f"✅ پیام با موفقیت به چت {chat_id} ارسال شد")
        except requests.RequestException as e:
            print(f"❌ خطا در ارسال به چت {chat_id}: {e}")
from .models import Rule  

def rules(request):
    rules = Rule.objects.all()
    return render(request, 'rules.html', {'rules': rules})


from django.shortcuts import render, redirect
from django.contrib import messages
import requests
import logging
from .models import PropAccount

logger = logging.getLogger(__name__)

from django.shortcuts import render, redirect
from django.contrib import messages
import requests
import logging
from .models import PropAccount

logger = logging.getLogger(__name__)
from django.shortcuts import render, redirect
from django.contrib import messages
import requests
import logging
from .models import PropAccount
from django.core.paginator import Paginator

logger = logging.getLogger(__name__)
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
import requests
import logging
from datetime import datetime
from .models import PropAccount
@login_required
def analytics(request):
    if not request.user.is_authenticated:
        messages.error(request, 'برای دسترسی به آنالیز حساب، لطفاً وارد شوید.')
        return redirect('login')

    accounts = PropAccount.objects.filter(user=request.user)
    selected_account = None
    metrics = None
    current_profit_percent = 0.0
    daily_drawdown_value = 0.0
    daily_drawdown_result = 0.0
    total_drawdown_value = 0.0
    total_drawdown_result = 0.0
    profit_target_value = 0.0
    profit_target_progress = 0.0
    daily_drawdown_chart_percent = 0.0
    total_drawdown_chart_percent = 0.0
    trades_paginated = None
    account_status = "در انتظار انتخاب حساب"
    trading_days_count = 0

    if request.method == 'POST':
        account_number = request.POST.get('account_number')
        if account_number:
            try:
                current_time = timezone.now()
                formatted_time = current_time.strftime("%Y-%m-%dT23:59:59")
                selected_account = accounts.get(account_number=account_number)
                
                # درخواست به API
                api_url = 'http://91.107.144.126:80/metrics'
                payload = {
                    'login': int(account_number),
                    'password': selected_account.investor_password,
                    'server': selected_account.server,
                    'from_date': '2025-06-27',
                    'to_date': formatted_time,
                    'daily_drawdown_threshold': float(selected_account.daily_draw_percent or 5.0),
                    'overall_drawdown_threshold': float(selected_account.total_draw_percent or 20.0),
                    'floating_risk_threshold': float(selected_account.floating_risk_percent or 2.0),
                    'profit_target_percent': float(selected_account.profit_percent or 10.0)
                }
                response = requests.post(api_url, json=payload, timeout=60)
                response.raise_for_status()
                metrics = response.json()

                # محاسبه تعداد روزهای معاملاتی
                if metrics.get('daily_metrics'):
                    trading_days_count = len(metrics['daily_metrics'])

                # محاسبه سود کوتاه‌مدت
                short_profitable_trades = 0
                short_profit_value = 0.0
                if metrics.get('trades'):
                    for trade in metrics['trades']:
                        duration = trade.get('duration_seconds', 0)
                        profit_loss = trade.get('profit_loss', 0.0)
                        if duration < 30 and profit_loss > 0:
                            short_profitable_trades += 1
                            short_profit_value += float(profit_loss)
                metrics['short_profitable_trades'] = short_profitable_trades
                metrics['short_profit_value'] = short_profit_value

                # محاسبه درصد سود فعلی
                initial_balance = float(metrics.get('initial_balance', 0))
                current_balance = float(metrics.get('current_balance', 0))
                if initial_balance != 0:
                    current_profit_percent = ((current_balance - initial_balance) / initial_balance) * 100

                # محاسبه دراوداون روزانه
                daily_draw_percent = float(selected_account.daily_draw_percent or 5.0)
                if metrics.get('daily_metrics'):
                    last_metric = metrics['daily_metrics'][-1]
                    day_balance = float(last_metric['start_balance'])
                else:
                    day_balance = initial_balance
                daily_drawdown_value = day_balance * (daily_draw_percent / 100)
                daily_drawdown_result = day_balance - daily_drawdown_value

                # محاسبه دراوداون کل
                total_draw_percent = float(selected_account.total_draw_percent or 20.0)
                total_drawdown_value = initial_balance * (total_draw_percent / 100)
                total_drawdown_result = initial_balance - total_drawdown_value

                # محاسبه درصد دراوداون برای نمودارها
                daily_drawdown_chart_percent = float(metrics.get('daily_drawdown_last_day', 0.0))
                total_drawdown_chart_percent = float(metrics.get('max_drawdown_percent', 0.0))

                # محاسبه تارگت سود بر اساس نوع پلن و سطح
                plan = selected_account.plan
                level = selected_account.level
                profit_percent = 0.0  # مقدار پیش‌فرض

                if plan:
                    plan_type = plan.name
                    if plan_type in ['two_stage', 'two_stage_lottery', 'weekly']:
                        if level == 'level1':
                            profit_percent = 8.0
                        elif level == 'level2':
                            profit_percent = 4.0
                        elif level == 'Real':
                            profit_percent = 0.0  # بدون تارگت
                    elif plan_type == 'single_stage':
                        if level == 'level1':
                            profit_percent = 6.0
                        elif level == 'Real':
                            profit_percent = 0.0  # بدون تارگت
                    elif plan_type == 'zero':
                        profit_percent = 0.0  # بدون تارگت

                # محاسبه مقدار تارگت سود
                profit_target_value = initial_balance * (profit_percent / 100) + initial_balance if profit_percent > 0 else 0.0
                profit_target_progress = (current_profit_percent / profit_percent) * 100 if profit_percent > 0 and current_profit_percent >= 0 else 0.0

                # تعیین وضعیت حساب
                is_violated = metrics.get('daily_drawdown_violated', False) or \
                              metrics.get('overall_drawdown_violated', False) or \
                              metrics.get('floating_risk_violated', False)
                
                if is_violated:
                    account_status = "حساب از دست رفته"
                elif profit_percent > 0 and current_balance >= profit_target_value:
                    account_status = "پاس شده"
                else:
                    account_status = "در حال بررسی"

                # صفحه‌بندی معاملات
                if metrics.get('trades'):
                    paginator = Paginator(metrics['trades'], 10)
                    page_number = request.POST.get('page', 1)
                    trades_paginated = paginator.get_page(page_number)

            except PropAccount.DoesNotExist:
                messages.error(request, 'حساب انتخاب‌شده یافت نشد.')
            except requests.exceptions.HTTPError as http_err:
                logger.error(f"API HTTP Error: {http_err}")
                messages.error(request, 'خطا در دریافت اطلاعات از API. لطفاً دوباره تلاش کنید.')
            except requests.exceptions.RequestException as req_err:
                logger.error(f"API Request Error: {req_err}")
                messages.error(request, 'خطا در اتصال به API. لطفاً دوباره تلاش کنید.')
            except ValueError as json_err:
                logger.error(f"API JSON Error: {json_err}")
                messages.error(request, 'داده‌های دریافتی از API نامعتبر است.')

    return render(request, 'analytics.html', {
        'accounts': accounts,
        'selected_account': selected_account,
        'metrics': metrics,
        'current_profit_percent': current_profit_percent,
        'daily_drawdown_value': daily_drawdown_value,
        'daily_drawdown_result': daily_drawdown_result,
        'total_drawdown_value': total_drawdown_value,
        'total_drawdown_result': total_drawdown_result,
        'profit_target_value': profit_target_value,
        'profit_target_progress': profit_target_progress,
        'daily_drawdown_chart_percent': daily_drawdown_chart_percent,
        'total_drawdown_chart_percent': total_drawdown_chart_percent,
        'trades_paginated': trades_paginated,
        'account_status': account_status,
        'trading_days_count': trading_days_count,
    })

def user_register(request):
    referral_code = request.GET.get('referral_code') or request.POST.get('referral_code')
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        logger.info(f"Starting registration for email: {email}")

        if password != password_confirm:
            messages.error(request, 'رمزهای واردشده مطابقت ندارند.')
            return render(request, 'register.html', {'referral_code': referral_code})

        if CustomUser.objects.filter(email=email).exists():
            user = CustomUser.objects.get(email=email)
            if user.is_active:
                messages.error(request, 'ایمیل قبلاً ثبت و تأیید شده است.')
                return render(request, 'register.html', {'referral_code': referral_code})
            else:
                # Activate the user directly without verification
                try:
                    with transaction.atomic():
                        user.is_active = True
                        user.is_email_verified = True
                        user.verification_code = ''
                        user.save()

                        wallet, created = Wallet.objects.get_or_create(
                            user=user,
                            defaults={'balance_usd': Decimal('1.00')}
                        )
                        if not created:
                            wallet.balance_usd += Decimal('1.00')
                            wallet.save()

                        # Create transaction record
                        WalletTransaction.objects.create(
                            user=user,
                            transaction_type='deposit',
                            amount_toman=0,  # Assuming no toman conversion for welcome bonus
                            amount_usd=Decimal('1.00'),
                            status='completed',
                            transaction_id=f"WELCOME_{timezone.now().strftime('%Y%m%d%H%M%S')}_{user.id}",
                        )

                        messages.success(request, 'ایمیل شما با موفقیت تأیید شد. اکنون می‌توانید وارد شوید.')
                        return redirect('login')
                except Exception as e:
                    logger.error(f"Activation failed: {str(e)}")
                    messages.error(request, 'خطا در فعال‌سازی. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.')
                    return render(request, 'register.html', {'referral_code': referral_code})

        try:
            with transaction.atomic():
                logger.info("Creating user...")
                user = CustomUser.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                )
                logger.info(f"User created with ID: {user.id}")

                # بررسی و ثبت رفرال (اختیاری)
                if referral_code:
                    try:
                        referrer = CustomUser.objects.get(id=referral_code)  # کد رفرال همان id کاربر است
                        Referral.objects.create(referrer=referrer, referred=user, earnings=Decimal('0.00'))
                    except CustomUser.DoesNotExist:
                        logger.warning(f"Invalid referral code: {referral_code}")

                # Activate the user directly without verification
                user.is_active = True
                user.is_email_verified = True
                user.verification_code = ''
                user.save()

                wallet, created = Wallet.objects.get_or_create(
                    user=user,
                    defaults={'balance_usd': Decimal('1.00')}
                )
                if not created:
                    wallet.balance_usd += Decimal('1.00')
                    wallet.save()

                # Create transaction record
                WalletTransaction.objects.create(
                    user=user,
                    transaction_type='deposit',
                    amount_toman=0,  # Assuming no toman conversion for welcome bonus
                    amount_usd=Decimal('1.00'),
                    status='completed',
                    transaction_id=f"WELCOME_{timezone.now().strftime('%Y%m%d%H%M%S')}_{user.id}",
                )

                messages.success(request, 'ثبت‌نام شما با موفقیت انجام شد. اکنون می‌توانید وارد شوید.')
                return redirect('login')
        except Exception as e:
            logger.error(f"Registration failed: {str(e)}")
            messages.error(request, 'خطا در ثبت‌نام. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.')
            return render(request, 'register.html', {'referral_code': referral_code})

    return render(request, 'register.html', {'referral_code': referral_code})


def verify_email(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        stored_code = request.session.get('verification_code')
        user_id = request.session.get('user_id')
        email = request.session.get('user_email')

        if not user_id or not stored_code or not email:
            messages.error(request, 'جلسه تأیید منقضی شده است. لطفاً دوباره ثبت‌نام کنید.')
            return redirect('register')

        try:
            user = CustomUser.objects.get(id=user_id, email=email)
        except CustomUser.DoesNotExist:
            messages.error(request, 'کاربر یافت نشد. لطفاً دوباره ثبت‌نام کنید.')
            return redirect('register')

        if code == stored_code:
            user.is_active = True
            user.is_email_verified = True
            user.verification_code = ''
            user.save()
            wallet, created = Wallet.objects.get_or_create(
                    user=user,
                    defaults={'balance_usd': Decimal('1.00')}
                )
            if not created:
                wallet.balance_usd += Decimal('1.00')
                wallet.save()

                # Create transaction record
            WalletTransaction.objects.create(
                    user=user,
                    transaction_type='deposit',
                    amount_toman=0,  # Assuming no toman conversion for welcome bonus
                    amount_usd=Decimal('1.00'),
                    status='completed',
                    transaction_id=f"WELCOME_{timezone.now().strftime('%Y%m%d%H%M%S')}_{user.id}",
            )
            # Clean up session
            del request.session['verification_code']
            del request.session['user_email']
            del request.session['user_id']
            messages.success(request, 'ایمیل شما با موفقیت تأیید شد. اکنون می‌توانید وارد شوید.')
            return redirect('login')
        else:
            messages.error(request, 'کد واردشده اشتباه است.')

    return render(request, 'verify_email.html')

def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            if user.is_active and user.is_email_verified:
                login(request, user)
                return redirect('dashboard')
            else:
                verification_code = ''.join(random.choices(string.digits, k=6))
                request.session['verification_code'] = verification_code
                request.session['user_email'] = email
                request.session['user_id'] = user.id

                html_message = render_to_string('emails/verification_email.html', {
                    'code': verification_code,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                })
                plain_message = strip_tags(html_message)
                try:
                    send_mail(
                        'کد تأیید ایمیل - کی آر جی اف ایکس',
                        plain_message,
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    messages.info(request, 'ایمیل شما تأیید نشده است. کد تأیید جدید به ایمیل‌تان ارسال شد.')
                    return redirect('verify_email')
                except Exception as e:
                    logger.error(f"Failed to send verification email: {str(e)}")
                    messages.error(request, 'خطا در ارسال ایمیل. لطفاً دوباره تلاش کنید.')
                    return render(request, 'login.html')
        else:
            messages.error(request, 'ایمیل یا رمز عبور اشتباه است.')
    return render(request, 'login.html')

def user_logout(request):
    logout(request)
    return redirect('index')


import random
import string
import requests
import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.cache import cache
# فراموش نکنید مدل CustomUser ایمپورت شود

logger = logging.getLogger(__name__)

def clean_phone_number(phone):
    """
    این تابع شماره موبایل را گرفته و به فرمت استاندارد 11 رقمی (09xxxxxxxxx) تبدیل می‌کند.
    """
    if not phone:
        return ""
        
    # ۱. تبدیل اعداد فارسی و عربی به انگلیسی
    persian_to_eng = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
    phone = str(phone).translate(persian_to_eng)
    
    # ۲. حذف تمام کاراکترهای غیر عددی (مثل +، فاصله، خط تیره)
    phone = ''.join(filter(str.isdigit, phone))
    
    # ۳. استخراج 10 رقم اصلی و اضافه کردن صفر به ابتدای آن
    # مهم نیست شماره 0098 داشته باشد یا +98 یا 09، ما 10 رقم آخر که با 9 شروع می‌شود را می‌گیریم
    if len(phone) >= 10 and phone[-10:].startswith('9'):
        return '0' + phone[-10:]
        
    return phone

def password_reset_request(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        
        # منطق محدودیت درخواست (Rate limiting)
        cache_key = f"password_reset_{email}"
        request_count = cache.get(cache_key, 0)
        
        if request_count >= 5:
            messages.error(request, 'تعداد درخواست‌های شما بیش از حد مجاز است. لطفاً ۵ دقیقه صبر کنید.')
            return render(request, 'password_reset_request.html')
        
        try:
            user = CustomUser.objects.get(email=email)
            
            if not user.phone_number:
                messages.error(request, 'شماره تماسی برای این حساب کاربری ثبت نشده است. لطفاً با پشتیبانی تماس بگیرید.')
                return render(request, 'password_reset_request.html')
            
            # تبدیل شماره دیتابیس به فرمت استاندارد
            normalized_phone = clean_phone_number(user.phone_number)
            
            verification_code = ''.join(random.choices(string.digits, k=6))
            
            request.session['verification_code'] = verification_code
            request.session['user_email'] = email
            request.session['user_id'] = user.id
            
            # تنظیمات API پیامک
            api_key = "9VzI6eC8vpNkGzAqyYv0vLxbeFIz3l4nBFqgSdj8lghEjbG3"
            template_id = 112673
            sms_url = "https://api.sms.ir/v1/send/verify"
            
            payload = {
                "mobile": normalized_phone,
                "templateId": template_id,
                "parameters": [
                    {
                        "name": "Code",  # اگر در پنل sms.ir با حروف بزرگ است، اینجا هم CODE بنویسید
                        "value": verification_code
                    }
                ]
            }
            
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "text/plain"
            }
            
            try:
                response = requests.post(sms_url, json=payload, headers=headers, timeout=10)
                response.raise_for_status() 
                
                cache.set(cache_key, request_count + 1, timeout=300)
                messages.success(request, 'کد بازیابی به شماره موبایل شما ارسال شد.')
                return redirect('password_reset_verify')
                
            except requests.exceptions.RequestException as e:
                # این خط متن دقیق ارور را در لاگ (ترمینال) چاپ می‌کند تا اگر مشکل از جای دیگری بود متوجه شوید
                error_detail = e.response.text if e.response is not None else str(e)
                logger.error(f"SMS API Error: {error_detail} | Attempted Phone: {normalized_phone}")
                
                messages.error(request, 'خطا در ارتباط با سرویس پیامک. لطفاً دوباره تلاش کنید.')
                return render(request, 'password_reset_request.html')
                
        except CustomUser.DoesNotExist:
            messages.success(request, 'کد بازیابی به شماره موبایل شما ارسال شد.')
            return render(request, 'password_reset_request.html')
    
    return render(request, 'password_reset_request.html')

def password_reset_verify(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        stored_code = request.session.get('verification_code')
        user_id = request.session.get('user_id')
        email = request.session.get('user_email')

        if not user_id or not stored_code or not email:
            messages.error(request, 'جلسه تأیید منقضی شده است. لطفاً دوباره درخواست بازیابی کنید.')
            return redirect('password_reset_request')

        # Rate limiting logic
        cache_key = f"password_verify_{email}"
        attempt_count = cache.get(cache_key, 0)

        if attempt_count >= 5:
            # Invalidate the verification code
            if 'verification_code' in request.session:
                del request.session['verification_code']
            messages.error(request, 'تعداد تلاش‌های شما بیش از حد مجاز است. کد منقضی شد. لطفاً دوباره درخواست بازیابی کنید.')
            return redirect('password_reset_request')

        try:
            user = CustomUser.objects.get(id=user_id, email=email)
        except CustomUser.DoesNotExist:
            messages.error(request, 'کاربر یافت نشد. لطفاً دوباره درخواست بازیابی کنید.')
            return redirect('password_reset_request')

        if code == stored_code:
            if password != password_confirm:
                messages.error(request, 'رمزهای واردشده مطابقت ندارند.')
                return render(request, 'password_reset_verify.html')
            user.set_password(password)
            user.is_active = True
            user.is_email_verified = True
            user.verification_code = ''
            user.save()
            # Clean up session
            del request.session['verification_code']
            del request.session['user_email']
            del request.session['user_id']
            # Clear cache on success
            cache.delete(cache_key)
            messages.success(request, 'رمز عبور شما با موفقیت تغییر کرد. حالا می‌توانید لاگین کنید.')
            return redirect('login')
        else:
            # Increment attempt count and set expiry for 5 minutes (300 seconds)
            cache.set(cache_key, attempt_count + 1, timeout=300)
            messages.error(request, 'کد تأیید اشتباه است.')
    return render(request, 'password_reset_verify.html')



from django.shortcuts import render, get_object_or_404
from .models import BlogPost

def blog_list(request):
    blogs = BlogPost.objects.all()
    return render(request, 'blog_list.html', {'blogs': blogs})

def blog_detail(request, slug):
    blog = get_object_or_404(BlogPost, slug=slug)
    return render(request, 'blog_detail.html', {'blog': blog})





from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import IdentityVerification
from .forms import IdentityVerificationForm

@login_required
def identity_verification(request):
    try:
        verification = request.user.identity_verification
    except IdentityVerification.DoesNotExist:
        verification = None

    if request.method == 'POST':
        form = IdentityVerificationForm(request.POST, request.FILES, instance=verification)
        if form.is_valid():
            verification = form.save(commit=False)
            verification.user = request.user
            verification.status = 'pending'
            verification.save()
            messages.success(request, 'مدارک شما با موفقیت ارسال شد و در انتظار بررسی است.')
            return redirect('identity_verification')
        else:
            messages.error(request, 'لطفاً خطاهای فرم را بررسی کنید.')
    else:
        form = IdentityVerificationForm(instance=verification)

    return render(request, 'identity_verification.html', {
        'form': form,
        'verification': verification,
    })
    
    
    
from django.shortcuts import render
from urllib.parse import unquote

def payment_success(request):
    msg = request.GET.get('msg', 'پرداخت با موفقیت انجام شد.')
    msg = unquote(msg)
    return render(request, 'payment_success.html', {'message': msg})



def payment_error(request):
    msg = request.GET.get('msg', 'خطایی در پرداخت رخ داد.')
    msg = unquote(msg)
    order_id = request.GET.get('order_id')
    
    # Check if this is a wallet transaction
    if order_id and str(order_id).startswith('1831'):
        try:
            transaction_id = int(str(order_id)[4:])
            transaction = WalletTransaction.objects.get(id=transaction_id)
            transaction.status = 'failed'
            transaction.save()
            logger.info(f"Wallet transaction {transaction_id} marked as failed")
            error_url = f"{reverse('wallet_error')}?{urlencode({'msg': msg})}"
            return redirect(error_url)
        except WalletTransaction.DoesNotExist:
            logger.error(f"No wallet transaction found for order_id {order_id}")
            messages.error(request, 'تراکنش کیف پول یافت نشد.')
    
    # Check if this is an order with wallet usage
    if order_id:
        try:
            order = PropOrder.objects.get(id=order_id)
            if order.used_wallet:
                wallet = Wallet.objects.get(user=order.user)
                wallet_deduction_usd = min(wallet.balance_usd, order.original_price_usd - order.final_price_usd)
                if wallet_deduction_usd > 0:
                    wallet.balance_usd += wallet_deduction_usd
                    wallet.save()
                    logger.info(f"Refunded {wallet_deduction_usd} USD to wallet for failed order {order.id}")
            order.status = 'failed'
            order.save()
        except PropOrder.DoesNotExist:
            logger.error(f"No order found for order_id {order_id}")
    
    return render(request, 'payment_error.html', {'message': msg})

from datetime import datetime, date



@login_required
def personal_analytics(request):
    # بررسی وجود حساب پراپ فعال
    if not PropAccount.objects.filter(user=request.user, status='active').exists():
        messages.error(request, 'برای دسترسی به آنالیز شخصی، باید حداقل یک حساب پراپ فعال داشته باشید.')
        return redirect('analytics')

    # مدیریت محدودیت درخواست‌های روزانه با استفاده از سشن
    today = date.today().isoformat()
    session_key = f'personal_analytics_requests_{request.user.id}_{today}'
    request_count = request.session.get(session_key, 0)

    if request_count >= 10:
        messages.error(request, 'شما به حداکثر تعداد درخواست‌های روزانه (10) رسیده‌اید. لطفاً فردا دوباره تلاش کنید.')
        return render(request, 'personal_analytics.html', {
            'servers': ['FIBOGroup-MT5 Server', 'LiteFinance-MT5-Demo'],
            'metrics': None,
            'current_profit_percent': 0.0,
            'daily_drawdown_value': 0.0,
            'daily_drawdown_result': 0.0,
            'total_drawdown_value': 0.0,
            'total_drawdown_result': 0.0,
            'profit_target_value': 0.0,
            'profit_target_progress': 0.0,
            'daily_drawdown_chart_percent': 0.0,
            'total_drawdown_chart_percent': 0.0,
            'trades_paginated': None,
            'account_status': 'در انتظار وارد کردن اطلاعات',
            'login_number': '',
            'investor_password': '',
            'server': '',
            'daily_draw_percent': '5.0',
            'total_draw_percent': '20.0',
            'floating_risk_percent': '2.0',
            'profit_percent': '10.0',
        })

    metrics = None
    current_profit_percent = 0.0
    daily_drawdown_value = 0.0
    daily_drawdown_result = 0.0
    total_drawdown_value = 0.0
    total_drawdown_result = 0.0
    profit_target_value = 0.0
    profit_target_progress = 0.0
    daily_drawdown_chart_percent = 0.0
    total_drawdown_chart_percent = 0.0
    trades_paginated = None
    account_status = "در انتظار وارد کردن اطلاعات"
    servers = ['FIBOGroup-MT5 Server', 'LiteFinance-MT5-Demo']

    if request.method == 'POST':
        # افزایش تعداد درخواست‌ها
        request_count += 1
        request.session[session_key] = request_count
        request.session.modified = True

        login_number = request.POST.get('login_number')
        investor_password = request.POST.get('investor_password')
        server = request.POST.get('server')
        daily_draw_percent = request.POST.get('daily_draw_percent')
        total_draw_percent = request.POST.get('total_draw_percent')
        floating_risk_percent = request.POST.get('floating_risk_percent')
        profit_percent = request.POST.get('profit_percent')

        # اعتبارسنجی ورودی‌ها
        try:
            login_number = int(login_number)
            daily_draw_percent = float(daily_draw_percent) if daily_draw_percent else 5.0
            total_draw_percent = float(total_draw_percent) if total_draw_percent else 20.0
            floating_risk_percent = float(floating_risk_percent) if floating_risk_percent else 2.0
            profit_percent = float(profit_percent) if profit_percent else 10.0

            if not investor_password or not server:
                messages.error(request, 'لطفاً تمام فیلدها را پر کنید.')
                return render(request, 'personal_analytics.html', {
                    'servers': servers,
                    'metrics': metrics,
                    'current_profit_percent': current_profit_percent,
                    'daily_drawdown_value': daily_drawdown_value,
                    'daily_drawdown_result': daily_drawdown_result,
                    'total_drawdown_value': total_drawdown_value,
                    'total_drawdown_result': total_drawdown_result,
                    'profit_target_value': profit_target_value,
                    'profit_target_progress': profit_target_progress,
                    'daily_drawdown_chart_percent': daily_drawdown_chart_percent,
                    'total_drawdown_chart_percent': total_drawdown_chart_percent,
                    'trades_paginated': trades_paginated,
                    'account_status': account_status,
                    'login_number': login_number,
                    'investor_password': investor_password,
                    'server': server,
                    'daily_draw_percent': daily_draw_percent,
                    'total_draw_percent': total_draw_percent,
                    'floating_risk_percent': floating_risk_percent,
                    'profit_percent': profit_percent,
                })

            current_time = datetime.now()
            formatted_time = current_time.strftime("%Y-%m-%dT23:59:59")

            # درخواست به API
            api_url = 'http://91.107.144.126:80/metrics'
            payload = {
                'login': login_number,
                'password': investor_password,
                'server': server,
                'from_date': '2025-06-27',
                'to_date': formatted_time,
                'daily_drawdown_threshold': daily_draw_percent,
                'overall_drawdown_threshold': total_draw_percent,
                'floating_risk_threshold': floating_risk_percent,
                'profit_target_percent': profit_percent
            }

            try:
                response = requests.post(api_url, json=payload, timeout=60)
                response.raise_for_status()
                metrics = response.json()

                # محاسبه سود کوتاه‌مدت
                metrics['short_profit_value'] = metrics.get('short_profitable_trades', 0) * 50

                # محاسبه درصد سود فعلی
                initial_balance = float(metrics.get('initial_balance', 0))
                current_balance = float(metrics.get('current_balance', 0))
                if initial_balance != 0:
                    current_profit_percent = ((current_balance - initial_balance) / initial_balance) * 100

                # محاسبه دراوداون روزانه
                if metrics.get('daily_metrics'):
                    last_metric = metrics['daily_metrics'][-1]
                    day_balance = float(last_metric['start_balance'])
                else:
                    day_balance = initial_balance

                daily_drawdown_value = day_balance * (daily_draw_percent / 100)
                daily_drawdown_result = day_balance - daily_drawdown_value

                # محاسبه دراوداون کل
                total_drawdown_value = initial_balance * (total_draw_percent / 100)
                total_drawdown_result = initial_balance - total_drawdown_value

                # محاسبه درصد دراوداون برای نمودارها
                daily_drawdown_chart_percent = float(metrics.get('daily_drawdown_last_day', 0.0))
                total_drawdown_chart_percent = float(metrics.get('max_drawdown_percent', 0.0))

                # محاسبه تارگت سود
                profit_value = initial_balance * (profit_percent / 100)
                profit_target_value = initial_balance + profit_value
                if profit_percent != 0:
                    profit_target_progress = (current_profit_percent / profit_percent) * 100 if current_profit_percent >= 0 else 0.0

                # تعیین وضعیت حساب
                is_violated = metrics.get('daily_drawdown_violated', False) or \
                              metrics.get('overall_drawdown_violated', False) or \
                              metrics.get('floating_risk_violated', False)
                
                if is_violated:
                    account_status = "حساب از دست رفته"
                elif current_balance >= profit_target_value:
                    account_status = "پاس شده"
                else:
                    account_status = "در حال بررسی"

                # صفحه‌بندی معاملات
                if metrics.get('trades'):
                    paginator = Paginator(metrics['trades'], 10)
                    page_number = request.POST.get('page', 1)
                    trades_paginated = paginator.get_page(page_number)

                messages.success(request, f'آنالیز با موفقیت انجام شد. تعداد درخواست‌های باقی‌مانده امروز: {10 - request_count}')

            except requests.exceptions.HTTPError as http_err:
                logger.error(f"API HTTP Error: {http_err}")
                messages.error(request, 'خطا در دریافت اطلاعات از API. لطفاً دوباره تلاش کنید.')
            except requests.exceptions.RequestException as req_err:
                logger.error(f"API Request Error: {req_err}")
                messages.error(request, 'خطا در اتصال به API. لطفاً دوباره تلاش کنید.')
            except ValueError as json_err:
                logger.error(f"API JSON Error: {json_err}")
                messages.error(request, 'داده‌های دریافتی از API نامعتبر است.')

        except ValueError:
            messages.error(request, 'لطفاً مقادیر معتبر عددی وارد کنید.')

    return render(request, 'personal_analytics.html', {
        'servers': servers,
        'metrics': metrics,
        'current_profit_percent': current_profit_percent,
        'daily_drawdown_value': daily_drawdown_value,
        'daily_drawdown_result': daily_drawdown_result,
        'total_drawdown_value': total_drawdown_value,
        'total_drawdown_result': total_drawdown_result,
        'profit_target_value': profit_target_value,
        'profit_target_progress': profit_target_progress,
        'daily_drawdown_chart_percent': daily_drawdown_chart_percent,
        'total_drawdown_chart_percent': total_drawdown_chart_percent,
        'trades_paginated': trades_paginated,
        'account_status': account_status,
        'login_number': request.POST.get('login_number', ''),
        'investor_password': request.POST.get('investor_password', ''),
        'server': request.POST.get('server', ''),
        'daily_draw_percent': request.POST.get('daily_draw_percent', '5.0'),
        'total_draw_percent': request.POST.get('total_draw_percent', '20.0'),
        'floating_risk_percent': request.POST.get('floating_risk_percent', '2.0'),
        'profit_percent': request.POST.get('profit_percent', '10.0'),
    })
    
    
    

@login_required
def affiliate_panel(request):
    user = request.user
    # دریافت رفرال‌های کاربر
    referrals = Referral.objects.filter(referrer=user)
    referral_count = referrals.count()
    
    # دریافت سفارش‌های موفق رفرال‌ها
    referred_users = [referral.referred for referral in referrals]
    successful_orders = PropOrder.objects.filter(user__in=referred_users, status='completed')
    order_count = successful_orders.count()
    
    # محاسبه درآمد رفرال
    total_earnings = Decimal('0.00')
    orders_with_earnings = []
    for order in successful_orders:
        earnings = order.final_price_usd * (Decimal(user.affiliate_percentage) / Decimal(100))
        total_earnings += earnings
        orders_with_earnings.append({
            'order': order,
            'earnings': earnings
        })
    
    # محاسبه تعداد خریدهای موفق برای هر رفرال
    referrals_with_counts = []
    for referral in referrals:
        successful_order_count = PropOrder.objects.filter(user=referral.referred, status='completed').count()
        referrals_with_counts.append({
            'referral': referral,
            'successful_order_count': successful_order_count
        })
    
    # دریافت موجودی کیف پول
    wallet, created = Wallet.objects.get_or_create(user=user)
    
    # لینک رفرال
    referral_link = f"{request.build_absolute_uri('/')[:-1]}?referral_code={user.id}"
    
    return render(request, 'affiliate_panel.html', {
        'referral_count': referral_count,
        'order_count': order_count,
        'total_earnings': total_earnings,
        'wallet_balance': wallet.balance_usd,
        'referral_code': user.id,
        'affiliate_percentage': user.affiliate_percentage,
        'referrals': referrals_with_counts,
        'successful_orders': orders_with_earnings,
        'referral_link': referral_link,
        'home_url': '/',  # لینک دستی برای بازگشت به صفحه اصلی (لطفاً لینک دقیق را ارائه دهید)
    })
    
    

from django.shortcuts import render, redirect
from django.contrib import messages
from admin_panel.models import UserSubmission, SubmissionAttempt
from django.utils import timezone
from django.db import IntegrityError

def get_client_ip(request):
    """استخراج IP آدرس کاربر"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def user_submission_form(request):
    if request.method == 'POST':
        try:
            instagram_id = request.POST.get('instagram_id')
            telegram_id = request.POST.get('telegram_id')
            email = request.POST.get('email')

            if not instagram_id or not telegram_id or not email:
                raise ValueError('همه فیلدها باید پر شوند.')

            client_ip = get_client_ip(request)
            attempt, created = SubmissionAttempt.objects.get_or_create(
                ip_address=client_ip,
                defaults={'attempt_count': 0, 'last_attempt': timezone.now()}
            )

            if attempt.attempt_count >= 3:
                raise ValueError('شما بیش از حد مجاز (3 بار) درخواست ارسال کرده‌اید.')

            attempt.attempt_count += 1
            attempt.last_attempt = timezone.now()
            attempt.save()

            UserSubmission.objects.create(
                instagram_id=instagram_id,
                telegram_id=telegram_id,
                email=email
            )
            messages.success(request, 'اطلاعات شما با موفقیت ارسال شد.')
            return redirect('user_submission_form')
        except IntegrityError:
            messages.error(request, 'ایمیل واردشده قبلاً ثبت شده است.')
        except ValueError as e:
            messages.error(request, f'خطا: {str(e)}')
        except Exception as e:
            messages.error(request, f'خطا در ارسال اطلاعات: {str(e)}')

    return render(request, 'user_submission_form.html', {
        'instagram_id': request.POST.get('instagram_id', ''),
        'telegram_id': request.POST.get('telegram_id', ''),
        'email': request.POST.get('email', '')
    })



from django.contrib.auth.decorators import login_required   


@login_required
def stage_upgrade_request(request):
    # دریافت حساب‌های پراپ کاربر
    accounts = PropAccount.objects.filter(user=request.user, status='active')
    
    # دریافت درخواست‌های ارتقاء قبلی
    upgrade_requests = StageUpgradeRequest.objects.filter(user=request.user).order_by('-requested_at')
    
    # صفحه‌بندی درخواست‌ها
    paginator = Paginator(upgrade_requests, 10)
    page_number = request.GET.get('page', 1)
    requests_paginated = paginator.get_page(page_number)
    
    if request.method == 'POST':
        account_number = request.POST.get('account_number')
        try:
            selected_account = accounts.get(account_number=account_number)
            
            # بررسی وجود درخواست قبلی برای این حساب
                        
            if StageUpgradeRequest.objects.filter(account=selected_account, user=request.user, status__in=['pending', 'approved']).exists():
                messages.error(request, 'شما قبلاً برای این حساب درخواست ارتقاء ثبت کرده‌اید.')
                return redirect('stage_upgrade_request')
            
            # بررسی وجود پلن برای حساب
            if not selected_account.plan:
                messages.error(request, 'این حساب به هیچ پلنی مرتبط نیست. لطفاً با پشتیبانی تماس بگیرید.')
                return redirect('stage_upgrade_request')
            
            # دریافت اطلاعات پلن و مرحله
            plan = selected_account.plan
            plan_stage = PlanStage.objects.filter(plan=plan, stage_type=plan.level).first()
            
            # بررسی وجود مرحله مرتبط
            if not plan_stage:
                messages.error(request, f'مرحله مرتبط برای پلن {plan.get_name_display()} یافت نشد.')
                return redirect('stage_upgrade_request')
            
            # تنظیم مقادیر پیش‌فرض
            current_time = datetime.now()
            formatted_time = current_time.strftime("%Y-%m-%dT23:59:59")
            
            # تنظیم تارگت سود و روزهای معاملاتی بر اساس نوع پلن
            if plan.name == 'two_stage':
                min_trading_days = 5
                profit_target_percent = 8.0 if selected_account.level == 'level1' else 4.0
            elif plan.name == 'weekly':
                min_trading_days = 3
                profit_target_percent = 8.0 if selected_account.level == 'level1' else 4.0
            elif plan.name == 'single_stage':
                min_trading_days = 5
                profit_target_percent = 6.0
            else:  # zero or real
                messages.error(request, 'این حساب قابل ارتقاء نیست.')
                return redirect('stage_upgrade_request')
            
            # درخواست به API برای بررسی شرایط
            api_url = 'http://91.107.144.126:80/metrics'
            payload = {
                'login': int(account_number),
                'password': selected_account.investor_password,
                'server': selected_account.server,
                'from_date': '2025-06-27',
                'to_date': formatted_time,
                'daily_drawdown_threshold': float(selected_account.daily_draw_percent or 5.0),
                'overall_drawdown_threshold': float(selected_account.total_draw_percent or 20.0),
                'floating_risk_threshold': float(selected_account.floating_risk_percent or 2.0),
                'profit_target_percent': profit_target_percent
            }
            
            try:
                response = requests.post(api_url, json=payload, timeout=60)
                response.raise_for_status()
                metrics = response.json()
                
                # بررسی نقض قوانین
                is_violated = metrics.get('daily_drawdown_violated', False) or \
                              metrics.get('overall_drawdown_violated', False) or \
                              metrics.get('floating_risk_violated', False)
                
                if is_violated:
                    rejection_reason = "نقض قوانین دراو‌دان (روزانه، کلی یا ریسک شناور)"
                    StageUpgradeRequest.objects.create(
                        account=selected_account,
                        user=request.user,
                        status='rejected',
                        rejection_reason=rejection_reason
                    )
                    messages.error(request, f'درخواست رد شد: {rejection_reason}')
                    return redirect('stage_upgrade_request')
                
                # بررسی تعداد روزهای معاملاتی
                trading_days = metrics.get('trading_days', 0)
                if trading_days < min_trading_days:
                    rejection_reason = f"تعداد روزهای معاملاتی ({trading_days}) کمتر از حداقل مورد نیاز ({min_trading_days}) است."
                    StageUpgradeRequest.objects.create(
                        account=selected_account,
                        user=request.user,
                        status='rejected',
                        rejection_reason=rejection_reason
                    )
                    messages.error(request, rejection_reason)
                    return redirect('stage_upgrade_request')
                
                # بررسی تارگت سود
                initial_balance = float(metrics.get('initial_balance', 0))
                current_balance = float(metrics.get('current_balance', 0))
                current_profit_percent = ((current_balance - initial_balance) / initial_balance * 100) if initial_balance != 0 else 0.0
                
                if current_profit_percent < profit_target_percent:
                    rejection_reason = f"سود فعلی ({current_profit_percent:.2f}%) کمتر از تارگت سود ({profit_target_percent}%) است."
                    StageUpgradeRequest.objects.create(
                        account=selected_account,
                        user=request.user,
                        status='rejected',
                        rejection_reason=rejection_reason
                    )
                    messages.error(request, rejection_reason)
                    return redirect('stage_upgrade_request')
                
                # اگر همه شرایط برآورده شده، تخصیص حساب جدید
                new_level = 'Real' if plan.name == 'single_stage' or selected_account.level == 'level2' else 'level2'
                new_account = PropAccount.objects.filter(
                    user__isnull=True,
                    order__isnull=True,
                    plan__isnull=True,
                    server=selected_account.server,
                    balance=selected_account.balance
                ).first()
                
                if not new_account:
                    rejection_reason = "حساب جدیدی با مشخصات مشابه یافت نشد."
                    StageUpgradeRequest.objects.create(
                        account=selected_account,
                        user=request.user,
                        status='rejected',
                        rejection_reason=rejection_reason
                    )
                    messages.error(request, rejection_reason)
                    return redirect('stage_upgrade_request')
                
                # تخصیص حساب جدید
                new_account.user = request.user
                new_account.plan = plan
                new_account.level = new_level
                new_account.daily_draw_percent = plan_stage.max_daily_loss_percent
                new_account.total_draw_percent = plan_stage.max_loss_percent
                new_account.floating_risk_percent = plan_stage.floating_risk_percent
                new_account.profit_percent = plan_stage.profit_target_percent
                new_account.status = 'active'
                new_account.save()
                
                # غیرفعال کردن حساب قدیمی
                selected_account.status = 'frozen'
                selected_account.save()
                
                # ثبت درخواست موفق
                StageUpgradeRequest.objects.create(
                    account=selected_account,
                    user=request.user,
                    status='approved'
                )
                
                # ارسال پیام به تلگرام
                telegram_message = (
                    f"درخواست ارتقاء مرحله تأیید شد!\n"
                    f"کاربر: {request.user.email}\n"
                    f"حساب قدیمی: {selected_account.account_number}\n"
                    f"حساب جدید: {new_account.account_number}\n"
                    f"مرحله جدید: {new_account.get_level_display()}\n"
                )
                send_telegram_message(telegram_message)
                
                messages.success(request, f'درخواست ارتقاء به مرحله {new_account.get_level_display()} با موفقیت انجام شد.')
                return redirect('stage_upgrade_request')
                
            except requests.exceptions.HTTPError as http_err:
                logger.error(f"API HTTP Error: {http_err}")
                messages.error(request, 'خطا در دریافت اطلاعات از API. لطفاً دوباره تلاش کنید.')
            except requests.exceptions.RequestException as req_err:
                logger.error(f"API Request Error: {req_err}")
                messages.error(request, 'خطا در اتصال به API. لطفاً دوباره تلاش کنید.')
            except ValueError as json_err:
                logger.error(f"API JSON Error: {json_err}")
                messages.error(request, 'داده‌های دریافتی از API نامعتبر است.')
            except IntegrityError:
                messages.error(request, 'شما قبلاً برای این حساب درخواست ارتقاء ثبت کرده‌اید.')
                
        except PropAccount.DoesNotExist:
            messages.error(request, 'حساب انتخاب‌شده یافت نشد.')
    
    return render(request, 'stage_upgrade_request.html', {
        'accounts': accounts,
        'requests_paginated': requests_paginated
    })
    
    
    




import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import PropAccount, Certificate
from PIL import Image, ImageDraw, ImageFont
import datetime
import os
from django.conf import settings
from django.http import FileResponse
import uuid

logger = logging.getLogger(__name__)

@login_required
def generate_certificate(request):
    # Get eligible accounts (stage_two or real) that don't have a certificate yet
    eligible_accounts = PropAccount.objects.filter(
        user=request.user,
        level__in=['level2', 'Real'],
        certificate__isnull=True
    )
    
    # Get all certificates for the user
    certificates = Certificate.objects.filter(user=request.user).order_by('-created_at')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        account_id = request.POST.get('account')
        
        # Validate name (English letters and spaces only)
        if not name or not all(c.isalpha() or c.isspace() for c in name):
            messages.error(request, 'نام باید فقط شامل حروف انگلیسی و فاصله باشد.')
            return render(request, 'generate_certificate.html', {
                'eligible_accounts': eligible_accounts,
                'certificates': certificates
            })
        
        # Validate account
        try:
            account = PropAccount.objects.get(
                id=account_id,
                user=request.user,
                level__in=['level2', 'Real'],
                certificate__isnull=True
            )
        except PropAccount.DoesNotExist:
            messages.error(request, 'حساب انتخاب‌شده نامعتبر است یا قبلاً برای آن سرتیفیکیت صادر شده است.')
            return render(request, 'generate_certificate.html', {
                'eligible_accounts': eligible_accounts,
                'certificates': certificates
            })
        
        try:
            # Generate certificate
            img = Image.open(os.path.join(settings.MEDIA_ROOT, 'blank_certificate.jpg'))
            draw = ImageDraw.Draw(img)
            
            name_length = len(name)
            if 1 <= name_length <= 13:
                name_position = (130, 525)
                font = ImageFont.truetype(os.path.join(settings.MEDIA_ROOT, 'arialbd.ttf'), 140)
            elif 14 <= name_length <= 18:
                name_position = (130, 536)
                font = ImageFont.truetype(os.path.join(settings.MEDIA_ROOT, 'arialbd.ttf'), 120)
            else:  # name_length >= 19
                name_position = (130, 596)
                font = ImageFont.truetype(os.path.join(settings.MEDIA_ROOT, 'arialbd.ttf'), 70)
            
            date_font = ImageFont.truetype(os.path.join(settings.MEDIA_ROOT, 'arial.ttf'), 25)
            current_date = datetime.datetime.now().strftime("%d %B %Y")
            date_position = (130, 1020)
            
            draw.text(name_position, name, fill=(21, 133, 98), font=font)
            draw.text(date_position, current_date, fill="black", font=date_font)
            
            # Save certificate
            certificate_filename = f'certificates/{timezone.now().strftime("%Y/%m/%d")}/{uuid.uuid4()}.jpg'
            certificate_path = os.path.join(settings.MEDIA_ROOT, certificate_filename)
            os.makedirs(os.path.dirname(certificate_path), exist_ok=True)
            img.save(certificate_path)
            
            # Create certificate record
            Certificate.objects.create(
                user=request.user,
                account=account,
                name=name,
                file=certificate_filename,
                created_at=timezone.now()
            )
            
            messages.success(request, 'سرتیفیکیت با موفقیت صادر شد.')
            return redirect('generate_certificate')
            
        except Exception as e:
            logger.error(f"Error generating certificate: {e}")
            messages.error(request, 'خطایی در تولید سرتیفیکیت رخ داد. لطفاً دوباره تلاش کنید.')
        
    return render(request, 'generate_certificate.html', {
        'eligible_accounts': eligible_accounts,
        'certificates': certificates
    })

@login_required
def download_certificate(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id, user=request.user)
    file_path = certificate.file.path  # Use .path to get the string path of the file
    
    if os.path.exists(file_path):
        try:
            return FileResponse(open(file_path, 'rb'), content_type='image/jpeg', as_attachment=True, filename=f"certificate_{certificate.account.account_number}.jpg")
        except Exception as e:
            logger.error(f"Error serving certificate file: {e}")
            messages.error(request, 'خطایی در دانلود فایل سرتیفیکیت رخ داد.')
            return redirect('generate_certificate')
    else:
        messages.error(request, 'فایل سرتیفیکیت یافت نشد.')
        return redirect('generate_certificate')
    
from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import requests
from django.utils import timezone
from trading.models import AccountSimulationLog
from trading.models import PropAccount


def send_rubika_message2(text: str):
    TOKEN = "BABCDC0HLDGSWXQWGDUWRMFLBVDURFPMGGTJSPIHUOQJHXJXCIZPWIFQHDTSOQKQ"
    url = f"https://botapi.rubika.ir/v3/{TOKEN}/sendMessage"
    payload = {
        "chat_id": "g0Hnukg099e6f5bc5f9b1f8e4ce0cb05",
        "text": text
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass


@login_required
def request_transfer_to_mt4(request):
    # فقط حساب‌های کاربر با سرور trader.apexfx.info
    user_accounts = PropAccount.objects.filter(
        user=request.user,
        server__icontains="trader.apexfx.info"
    ).order_by('-account_number')

    if request.method == 'POST':
        account_number = request.POST.get('account_number', '').strip()
        broker = request.POST.get('broker', 'LiteFinance')

        if not account_number:
            messages.error(request, 'لطفاً یک حساب انتخاب کنید')
            return render(request, 'admin_panel/request_transfer.html', {'accounts': user_accounts})

        # جلوگیری از درخواست تکراری
        if AccountSimulationLog.objects.filter(account_number=account_number).exists():
            messages.error(request, 'این حساب قبلاً بررسی شده است.')
            return render(request, 'admin_panel/request_transfer.html', {'accounts': user_accounts})

        # ==================== درخواست به API ====================
        try:
            api_url = f"http://185.243.48.250/api/account_balance_and_history/{account_number}/"
            api_res = requests.get(
                api_url,
                headers={'X-API-Key': 'sina1831'},
                timeout=15
            )
            data = api_res.json()

            if not data.get('success'):
                messages.error(request, data.get('error', 'حساب یافت نشد'))
                return render(request, 'admin_panel/request_transfer.html', {'accounts': user_accounts})

        except Exception as e:
            messages.error(request, f'خطا در ارتباط با سرور تریدینگ: {str(e)}')
            return render(request, 'admin_panel/request_transfer.html', {'accounts': user_accounts})

        account_info = data['account']

        # چک وضعیت حساب
        if not account_info.get('is_active') or account_info.get('status') != 'active':
            status_display = account_info.get('status_display', account_info.get('status', 'نامشخص'))
            messages.error(request, f'حساب غیرفعال است! وضعیت: {status_display}')
            return render(request, 'admin_panel/request_transfer.html', {'accounts': user_accounts})

        # پردازش تریدها
        initial_balance = float(account_info.get('balance', 0))
        balance = initial_balance
        trade_history = data.get('trade_history', [])
        adjusted_count = 0

        for h in trade_history:
            pl = h.get('pl', 0)
            if pl > 0:
                balance -= abs(pl)
            else:
                balance += abs(pl)
            adjusted_count += 1

        final_balance = round(balance, 2)

        # ==================== اطلاعات کامل حساب (پلن + لول + پسورد) ====================
        prop_account = PropAccount.objects.filter(account_number=account_number).first()

        email = prop_account.user.email if prop_account and prop_account.user else "نامشخص"
        order_number = prop_account.order.order_number if prop_account and prop_account.order else None
        plan_name = prop_account.plan.name if prop_account and getattr(prop_account, 'plan', None) else "نامشخص"
        level = getattr(prop_account, 'level', 'نامشخص')
        investor_password = getattr(prop_account, 'investor_password', 'نامشخص')
        main_password = getattr(prop_account, 'main_password', 'نامشخص')

        # ==================== ذخیره لاگ ====================
        AccountSimulationLog.objects.create(
            account_number=account_number,
            broker=broker,
            email=email,
            order_number=order_number,
            plan=plan_name,
            level=level,
            initial_balance=initial_balance,
            final_balance=final_balance,
            ip_address=request.META.get('REMOTE_ADDR')
        )

        # ==================== ارسال به روبیکا (با پلن، لول و پسورد) ====================
        rubika_text = f"""
✅ درخواست انتقال به متاتریدر ثبت شد

🔹 شماره حساب: {account_number}
🔹 بروکر: {broker}
🔹 ایمیل: {email}
🔹 پلن: {plan_name}
🔹 لول: {level}
🔹 پسورد سرمایه‌گذار: {investor_password}
🔹 پسورد اصلی: {main_password}

📊 وضعیت: فعال ✓
📈 تعداد ترید اعمال‌شده: {adjusted_count}
💰 بالانس اولیه: ${initial_balance}
💰 بالانس نهایی: ${final_balance}

⏰ زمان: {timezone.now().strftime('%Y-%m-%d %H:%M')}
        """.strip()

        send_rubika_message2(rubika_text)

        return render(request, 'admin_panel/request_transfer.html', {
            'success': True,
            'account_number': account_number,
            'broker': broker
        })

    # GET request
    return render(request, 'admin_panel/request_transfer.html', {
        'accounts': user_accounts
    })