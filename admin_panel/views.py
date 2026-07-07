# trading/admin_panel/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from trading.models import CustomUser,BlogPost,FreeAccountQuota, PropAccount,Wallet, WalletTransaction,Referral, PropOrder, Ticket, Employee, IdentityVerification, PropPlan, PlanStage, Rule, DiscountCode
from django.contrib import messages
from .models import UserSubmission
import random
import string
from django.utils import timezone
from django.core.mail import send_mail
import logging
from datetime import datetime
from django.db.models import Q
import json
from decimal import Decimal
from django.db import transaction
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

def is_admin_or_has_permission(user, permission):
    if user.is_superuser or user.email == "sinakrg1831@gmail.com":
        return True
    try:
        employee = Employee.objects.get(user=user)
        return getattr(employee, permission)
    except Employee.DoesNotExist:
        return False

def admin_required(permission=None):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'لطفاً ابتدا وارد شوید.')
                return redirect('admin_panel:dashboard')
            if permission:
                if not is_admin_or_has_permission(request.user, permission):
                    messages.error(request, 'شما دسترسی لازم برای این بخش را ندارید.')
                    return redirect('admin_panel:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

@admin_required('can_manage_tickets')
def dashboard(request):
    empty_accounts = PropAccount.objects.filter(user__isnull=True, order__isnull=True).count()
    return render(request, 'admin_panel/dashboard.html', {'empty_accounts': empty_accounts})

def search_query(queryset, search_term, fields, filters=None):
    query = Q()
    for field in fields:
        query |= Q(**{f"{field}__icontains": search_term})
    if filters:
        for key, value in filters.items():
            if value:
                query &= Q(**{key: value})
    return queryset.filter(query)
@admin_required('can_manage_verifications')
def customuser_list(request):
    search_term = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    user_list = CustomUser.objects.all()
    fields = ['email', 'first_name', 'last_name', 'phone_number', 'verification_code']
    filters = {'is_active': status_filter} if status_filter else None
    if search_term or filters:
        user_list = search_query(user_list, search_term, fields, filters)
    paginator = Paginator(user_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/customuser_list.html', {
        'page_obj': page_obj,
        'search_term': search_term,
        'status_filter': status_filter
    })

@admin_required('can_manage_verifications')
def customuser_add(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number = request.POST.get('phone_number', '')
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        try:
            user = CustomUser.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                password=password
            )
            send_mail(
                'حساب کاربری جدید',
                f'حساب شما ایجاد شد. رمز عبور: {password}',
                'from@example.com',
                [email],
                fail_silently=False,
            )
            messages.success(request, f'کاربر {email} با موفقیت ایجاد شد.')
            return redirect('admin_panel:customuser_list')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد کاربر: {str(e)}')
    return render(request, 'admin_panel/customuser_form.html', {'form_type': 'add'})

# trading/admin_panel/views.py
@admin_required('can_manage_users')
def customuser_edit(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        user.email = request.POST.get('email')
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.phone_number = request.POST.get('phone_number', '')
        user.is_active = request.POST.get('is_active') == 'on'
        user.is_email_verified = request.POST.get('is_email_verified') == 'on'
        user.is_staff = request.POST.get('is_staff') == 'on'
        user.referral_code = request.POST.get('referral_code') or str(user.id)
        user.affiliate_percentage = float(request.POST.get('affiliate_percentage') or 0.0)
        user.save()
        messages.success(request, 'کاربر با موفقیت ویرایش شد.')
        return redirect('admin_panel:customuser_list')
    return render(request, 'admin_panel/customuser_form.html', {
        'form_type': 'edit',
        'user': user
    })

@admin_required('can_manage_users')
def customuser_delete(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    user.delete()
    messages.success(request, 'کاربر با موفقیت حذف شد.')
    return redirect('admin_panel:customuser_list')

@admin_required('can_manage_accounts')
def propaccount_list(request):
    search_term = request.GET.get('search', '')
    plan_filter = request.GET.get('plan_type', '')
    account_list = PropAccount.objects.all()
    fields = ['account_number', 'server', 'order__order_number', 'user__email']  # اضافه کردن جستجو بر اساس email کاربر و شماره سفارش
    filters = {'plan__name': plan_filter} if plan_filter else None
    if search_term or filters:
        account_list = search_query(account_list, search_term, fields, filters)
    paginator = Paginator(account_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/propaccount_list.html', {
        'page_obj': page_obj,
        'search_term': search_term,
        'plan_filter': plan_filter
    })
@admin_required('can_manage_accounts')
def empty_accounts_list(request):
    search_term = request.GET.get('search', '')
    server_filter = request.GET.get('server_filter', '')  # دریافت مقدار سلکت باکس
    
    # فیلتر حساب‌های خالی
    account_list = PropAccount.objects.filter(
        user__isnull=True,
        order__isnull=True
    )

    # اعمال فیلتر سرور
    if server_filter in ['FIBOGroup', 'GlobalPrime-Demo', 'LiteFinance']:
        account_list = account_list.filter(server__icontains=server_filter)
    else:
        # اگر هیچ فیلتری انتخاب نشده، فقط سرورهای موردنظر را نشان بده
        account_list = account_list.filter(
            Q(server__icontains='FIBOGroup') |
            Q(server__icontains='GlobalPrime-Demo') |
            Q(server__icontains='LiteFinance')
        )

    # مرتب‌سازی نزولی بر اساس بالانس
    account_list = account_list.order_by('-balance')

    # اعمال جستجو بر اساس شماره حساب یا سرور
    fields = ['account_number', 'server']
    if search_term:
        account_list = search_query(account_list, search_term, fields)

    paginator = Paginator(account_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin_panel/empty_accounts_list.html', {
        'page_obj': page_obj,
        'search_term': search_term,
        'server_filter': server_filter,
        'title': 'لیست حساب‌های خالی'
    })
@admin_required('can_manage_accounts')
def propaccount_add(request):
    if request.method == 'POST':
        try:
            account = PropAccount.objects.create(
                account_number=request.POST.get('account_number') or None,
                server=request.POST.get('server') or None,
                investor_password=request.POST.get('investor_password') or None,
                main_password=request.POST.get('main_password') or None,
                plan_id=request.POST.get('plan_type') or None,
                balance=request.POST.get('balance') or None,
                daily_draw_percent=request.POST.get('daily_draw_percent') or None,
                total_draw_percent=request.POST.get('total_draw_percent') or None,
                floating_risk_percent=request.POST.get('floating_risk_percent') or None,
            )
            if request.POST.get('user'):
                account.user = CustomUser.objects.get(pk=request.POST.get('user'))
            if request.POST.get('order'):
                account.order = PropOrder.objects.get(pk=request.POST.get('order'))
            account.save()
            messages.success(request, 'حساب با موفقیت ایجاد شد.')
            return redirect('admin_panel:propaccount_list')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد حساب: {str(e)}')
            return render(request, 'admin_panel/propaccount_form.html', {
                'form_type': 'add',
                'users': CustomUser.objects.all(),
                'orders': PropOrder.objects.all(),
                'plans': PropPlan.objects.all(),
                'account': PropAccount(
                    account_number=request.POST.get('account_number'),
                    server=request.POST.get('server'),
                    investor_password=request.POST.get('investor_password'),
                    main_password=request.POST.get('main_password'),
                    balance=request.POST.get('balance'),
                    daily_draw_percent=request.POST.get('daily_draw_percent'),
                    total_draw_percent=request.POST.get('total_draw_percent'),
                    floating_risk_percent=request.POST.get('floating_risk_percent')
                ),
                'selected_user': request.POST.get('user'),
                'selected_order': request.POST.get('order'),
                'selected_plan': request.POST.get('plan_type')
            })
    users = CustomUser.objects.all()
    orders = PropOrder.objects.all()
    plans = PropPlan.objects.all()
    return render(request, 'admin_panel/propaccount_form.html', {
        'form_type': 'add',
        'users': users,
        'orders': orders,
        'plans': plans
    })

@admin_required('can_manage_verifications')
def propaccount_edit(request, pk):
    account = get_object_or_404(PropAccount, pk=pk)
    if request.method == 'POST':
        
        try:
            account.account_number = request.POST.get('account_number') or None
            account.server = request.POST.get('server') or None
            account.investor_password = request.POST.get('investor_password') or None
            account.main_password = request.POST.get('main_password') or None
            account.plan_id = request.POST.get('plan_type') or None
            account.balance = request.POST.get('balance') or None
            account.daily_draw_percent = request.POST.get('daily_draw_percent') or None
            account.total_draw_percent = request.POST.get('total_draw_percent') or None
            account.floating_risk_percent = request.POST.get('floating_risk_percent') or None
            account.user = CustomUser.objects.get(pk=request.POST.get('user')) if request.POST.get('user') else None
            account.order = PropOrder.objects.get(pk=request.POST.get('order')) if request.POST.get('order') else None
            account.save()
            messages.success(request, 'حساب با موفقیت ویرایش شد.')
            return redirect('admin_panel:propaccount_list')
        except Exception as e:
            messages.error(request, f'خطا در ویرایش حساب: {str(e)}')
            return render(request, 'admin_panel/propaccount_form.html', {
                'form_type': 'edit',
                'account': account,
                'users': CustomUser.objects.all(),
                'orders': PropOrder.objects.all(),
                'plans': PropPlan.objects.all(),
                'selected_user': request.POST.get('user'),
                'selected_order': request.POST.get('order'),
                'selected_plan': request.POST.get('plan_type')
            })
    users = CustomUser.objects.all()
    orders = PropOrder.objects.all()
    plans = PropPlan.objects.all()
    return render(request, 'admin_panel/propaccount_form.html', {
        'form_type': 'edit',
        'account': account,
        'users': users,
        'orders': orders,
        'plans': plans,
        'selected_user': account.user.id if account.user else '',
        'selected_order': account.order.id if account.order else '',
        'selected_plan': account.plan.id if account.plan else ''
    })

@admin_required('can_manage_verifications')
def propaccount_delete(request, pk):
    account = get_object_or_404(PropAccount, pk=pk)
    account.delete()
    messages.success(request, 'حساب با موفقیت حذف شد.')
    return redirect('admin_panel:propaccount_list')
@admin_required('can_manage_orders')
def proporder_list(request):
    search_term = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    order_list = PropOrder.objects.all().order_by('-id')
 
    fields = ['id', 'user__email']
    
    filters = {'status': status_filter} if status_filter else None
    
    if search_term or filters:
        order_list = search_query(order_list, search_term, fields, filters)
        
    paginator = Paginator(order_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin_panel/proporder_list.html', {
        'page_obj': page_obj,
        'search_term': search_term,
        'status_filter': status_filter
    })

@admin_required('can_manage_orders')
def proporder_add(request):
    if request.method == 'POST':
        try:
            PropOrder.objects.create(
                order_number=request.POST.get('order_number'),
                plan_id=request.POST.get('plan_type'),
                purchase_date=request.POST.get('purchase_date'),
                status=request.POST.get('status'),
                user=CustomUser.objects.get(pk=request.POST.get('user')) if request.POST.get('user') else None
            )
            messages.success(request, 'سفارش با موفقیت ایجاد شد.')
            return redirect('admin_panel:proporder_list')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد سفارش: {str(e)}')
    users = CustomUser.objects.all()
    plans = PropPlan.objects.all()
    return render(request, 'admin_panel/proporder_form.html', {
        'form_type': 'add',
        'users': users,
        'plans': plans
    })

@admin_required('can_manage_orders')
def proporder_edit(request, pk):
    order = get_object_or_404(PropOrder, pk=pk)
    if request.method == 'POST':
        order.order_number = request.POST.get('order_number')
        order.plan_id = request.POST.get('plan_type')
        order.purchase_date = request.POST.get('purchase_date')
        order.status = request.POST.get('status')
        order.user = CustomUser.objects.get(pk=request.POST.get('user')) if request.POST.get('user') else None
        order.save()
        messages.success(request, 'سفارش با موفقیت ویرایش شد.')
        return redirect('admin_panel:proporder_list')
    users = CustomUser.objects.all()
    plans = PropPlan.objects.all()
    return render(request, 'admin_panel/proporder_form.html', {
        'form_type': 'edit',
        'order': order,
        'users': users,
        'plans': plans
    })

@admin_required('can_manage_verifications')
def proporder_delete(request, pk):
    order = get_object_or_404(PropOrder, pk=pk)
    order.delete()
    messages.success(request, 'سفارش با موفقیت حذف شد.')
    return redirect('admin_panel:proporder_list')

@admin_required('can_manage_tickets')
def ticket_list(request):
    search_term = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    department_filter = request.GET.get('department', '')
    ticket_list = Ticket.objects.all()
    fields = ['ticket_number', 'subject', 'department', 'user__email']  # اضافه کردن جستجو بر اساس email کاربر
    filters = {}
    if status_filter:
        filters['status'] = status_filter
    if department_filter:
        filters['department'] = department_filter
    if search_term or filters:
        ticket_list = search_query(ticket_list, search_term, fields, filters)
    paginator = Paginator(ticket_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/ticket_list.html', {
        'page_obj': page_obj,
        'search_term': search_term,
        'status_filter': status_filter,
        'department_filter': department_filter
    })

@admin_required('can_manage_tickets')
def ticket_add(request):
    if request.method == 'POST':
        try:
            Ticket.objects.create(
                ticket_number=request.POST.get('ticket_number'),
                subject=request.POST.get('subject'),
                department=request.POST.get('department'),
                status=request.POST.get('status'),
                messages=[],
            )
            messages.success(request, 'تیکت با موفقیت ایجاد شد.')
            return redirect('admin_panel:ticket_list')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد تیکت: {str(e)}')
    return render(request, 'admin_panel/ticket_form.html', {'form_type': 'add'})

@admin_required('can_manage_tickets')
def ticket_edit(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == 'POST':
        ticket.ticket_number = request.POST.get('ticket_number')
        ticket.subject = request.POST.get('subject')
        ticket.department = request.POST.get('department')
        ticket.status = request.POST.get('status')
        ticket.save()
        messages.success(request, 'تیکت با موفقیت ویرایش شد.')
        return redirect('admin_panel:ticket_list')
    return render(request, 'admin_panel/ticket_form.html', {'form_type': 'edit', 'ticket': ticket})

@admin_required('can_manage_verifications')
def ticket_delete(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    ticket.delete()
    messages.success(request, 'تیکت با موفقیت حذف شد.')
    return redirect('admin_panel:ticket_list')

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.core.mail import send_mail
from django.utils import timezone
# trading/admin_panel/views.py

@admin_required('can_manage_tickets')
def ticket_reply(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == 'POST':
        message = request.POST.get('message')
        status = request.POST.get('status')
        if message:
            # تبدیل زمان با استفاده از timezone.localtime برای اطمینان از اعمال زمان تهران
            local_time = timezone.localtime(timezone.now())
            ticket.messages.append({
                'text': message,
                'timestamp': local_time.strftime('%H:%M - %Y/%m/%d'), # تغییر ترتیب برای خوانایی بهتر در راست‌چین (ساعت - تاریخ)
                'sender': request.user.email
            })
            if status in ['open', 'closed']:
                ticket.status = status
            ticket.save()
            
            messages.success(request, 'پاسخ با موفقیت ارسال شد.')
            return redirect('admin_panel:ticket_list')
    return render(request, 'admin_panel/ticket_reply.html', {'ticket': ticket})

@admin_required('can_manage_verifications')
def identity_verification_list(request):
    search_term = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    verification_list = IdentityVerification.objects.all()
    fields = ['user__email']
    filters = {'status': status_filter} if status_filter else None
    if search_term or filters:
        verification_list = search_query(verification_list, search_term, fields, filters)
    paginator = Paginator(verification_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/identity_verification_list.html', {
        'page_obj': page_obj,
        'search_term': search_term,
        'status_filter': status_filter
    })

@admin_required('can_manage_verifications')
def identity_verification_review(request, pk):
    verification = get_object_or_404(IdentityVerification, pk=pk)
    if request.method == 'POST':
        status = request.POST.get('status')
        rejection_reason = request.POST.get('rejection_reason', '')
        verification.status = status
        verification.reviewed_at = timezone.now()
        if status == 'rejected':
            verification.rejection_reason = rejection_reason
        else:
            verification.rejection_reason = None
        verification.save()
        messages.success(request, 'وضعیت احراز هویت به‌روزرسانی شد.')
        send_mail(
            'به‌روزرسانی وضعیت احراز هویت',
            f'وضعیت احراز هویت شما: {verification.get_status_display()}\n'
            f'{rejection_reason if status == "rejected" else ""}',
            'from@example.com',
            [verification.user.email],
            fail_silently=True,
        )
        return redirect('admin_panel:identity_verification_list')
    return render(request, 'admin_panel/identity_verification_review.html', {'verification': verification})

@admin_required('can_manage_employees')
def employee_list(request):
    search_term = request.GET.get('search', '')
    employee_list = Employee.objects.all()
    fields = ['user__email', 'user__first_name', 'user__last_name']
    if search_term:
        employee_list = search_query(employee_list, search_term, fields)
    paginator = Paginator(employee_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/employee_list.html', {
        'page_obj': page_obj,
        'search_term': search_term
    })

@admin_required('can_manage_employees')
def employee_add(request):
    if request.method == 'POST':
        try:
            user = CustomUser.objects.get(pk=request.POST.get('user'))
            Employee.objects.create(
                user=user,
                can_manage_users=request.POST.get('can_manage_users') == 'on',
                can_manage_accounts=request.POST.get('can_manage_accounts') == 'on',
                can_manage_orders=request.POST.get('can_manage_orders') == 'on',
                can_manage_tickets=request.POST.get('can_manage_tickets') == 'on',
                can_manage_employees=request.POST.get('can_manage_employees') == 'on',
                can_manage_verifications=request.POST.get('can_manage_verifications') == 'on',
                can_manage_plans=request.POST.get('can_manage_plans') == 'on',
                can_manage_discounts=request.POST.get('can_manage_discounts') == 'on'
            )
            messages.success(request, 'کارمند با موفقیت اضافه شد.')
            return redirect('admin_panel:employee_list')
        except Exception as e:
            messages.error(request, f'خطا در افزودن کارمند: {str(e)}')
    users = CustomUser.objects.all()
    return render(request, 'admin_panel/employee_form.html', {'form_type': 'add', 'users': users})

@admin_required('can_manage_employees')
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        employee.can_manage_users = request.POST.get('can_manage_users') == 'on'
        employee.can_manage_accounts = request.POST.get('can_manage_accounts') == 'on'
        employee.can_manage_orders = request.POST.get('can_manage_orders') == 'on'
        employee.can_manage_tickets = request.POST.get('can_manage_tickets') == 'on'
        employee.can_manage_employees = request.POST.get('can_manage_employees') == 'on'
        employee.can_manage_verifications = request.POST.get('can_manage_verifications') == 'on'
        employee.can_manage_plans = request.POST.get('can_manage_plans') == 'on'
        employee.can_manage_discounts = request.POST.get('can_manage_discounts') == 'on'
        employee.save()
        messages.success(request, 'کارمند با موفقیت ویرایش شد.')
        return redirect('admin_panel:employee_list')
    return render(request, 'admin_panel/employee_form.html', {'form_type': 'edit', 'employee': employee})

@admin_required('can_manage_employees')
def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    employee.delete()
    messages.success(request, 'کارمند با موفقیت حذف شد.')
    return redirect('admin_panel:employee_list')

@admin_required('can_manage_plans')
def propplan_list(request):
    search_term = request.GET.get('search', '')
    plan_list = PropPlan.objects.all()
    fields = ['name', 'account_size', 'price', 'leverage']
    if search_term:
        query = Q()
        for field in fields:
            query |= Q(**{f"{field}__icontains": search_term})
        plan_list = plan_list.filter(query)
    paginator = Paginator(plan_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/propplan_list.html', {
        'page_obj': page_obj,
        'search_term': search_term
    })

@admin_required('can_manage_plans')
def propplan_add(request):
    if request.method == 'POST':
        try:
            plan = PropPlan.objects.create(
                name=request.POST.get('name'),
                account_size=request.POST.get('account_size'),
                price=request.POST.get('price'),
                leverage=request.POST.get('leverage')
            )
            # Handle stages
            stage_types = request.POST.getlist('stage_type')
            profit_targets = request.POST.getlist('profit_target')
            profit_target_percents = request.POST.getlist('profit_target_percent')
            max_loss_percents = request.POST.getlist('max_loss_percent')
            max_daily_loss_percents = request.POST.getlist('max_daily_loss_percent')
            min_trading_days_list = request.POST.getlist('min_trading_days')
            floating_risk_percents = request.POST.getlist('floating_risk_percent')

            for i in range(len(stage_types)):
                if stage_types[i]:
                    PlanStage.objects.create(
                        plan=plan,
                        stage_type=stage_types[i],
                        profit_target=profit_targets[i] or None,
                        profit_target_percent=profit_target_percents[i] or None,
                        max_loss_percent=max_loss_percents[i] or 10.0,
                        max_daily_loss_percent=max_daily_loss_percents[i] or 5.0,
                        min_trading_days=min_trading_days_list[i] or None,
                        floating_risk_percent=floating_risk_percents[i] or None
                    )
            messages.success(request, 'پلن و مراحل آن با موفقیت ایجاد شد.')
            return redirect('admin_panel:propplan_list')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد پلن: {str(e)}')
    return render(request, 'admin_panel/propplan_form.html', {'form_type': 'add'})

@admin_required('can_manage_plans')
def propplan_edit(request, pk):
    plan = get_object_or_404(PropPlan, pk=pk)
    if request.method == 'POST':
        try:
            # Update plan details
            plan.name = request.POST.get('name')
            plan.account_size = request.POST.get('account_size')
            plan.price = request.POST.get('price')
            plan.leverage = request.POST.get('leverage')
            plan.save()

            # Handle stages
            stage_ids = request.POST.getlist('stage_id[]')
            stage_types = request.POST.getlist('stage_type[]')
            profit_targets = request.POST.getlist('profit_target[]')
            profit_target_percents = request.POST.getlist('profit_target_percent[]')
            max_loss_percents = request.POST.getlist('max_loss_percent[]')
            max_daily_loss_percents = request.POST.getlist('max_daily_loss_percent[]')
            min_trading_days_list = request.POST.getlist('min_trading_days[]')
            floating_risk_percents = request.POST.getlist('floating_risk_percent[]')
            delete_stages = request.POST.getlist('delete_stage[]')

            # Delete selected stages
            if delete_stages:
                PlanStage.objects.filter(id__in=delete_stages, plan=plan).delete()

            # Update or create stages
            for i in range(len(stage_types)):
                # Skip if stage_type is empty or all fields are empty/default
                if not stage_types[i]:
                    continue

                # Validate that at least one critical field is provided
                if not (
                    profit_targets[i] or
                    profit_target_percents[i] or
                    max_loss_percents[i] or
                    max_daily_loss_percents[i] or
                    min_trading_days_list[i] or
                    floating_risk_percents[i]
                ):
                    continue  # Skip if all fields are empty

                stage_data = {
                    'plan': plan,
                    'stage_type': stage_types[i],
                    'profit_target': profit_targets[i] or None,
                    'profit_target_percent': profit_target_percents[i] or None,
                    'max_loss_percent': max_loss_percents[i] or 10.0,
                    'max_daily_loss_percent': max_daily_loss_percents[i] or 5.0,
                    'min_trading_days': min_trading_days_list[i] or None,
                    'floating_risk_percent': floating_risk_percents[i] or None
                }

                if i < len(stage_ids) and stage_ids[i]:
                    # Update existing stage
                    PlanStage.objects.filter(id=stage_ids[i], plan=plan).update(**stage_data)
                else:
                    # Create new stage
                    PlanStage.objects.create(**stage_data)

            messages.success(request, 'پلن و مراحل آن با موفقیت ویرایش شد.')
            return redirect('admin_panel:propplan_list')
        except Exception as e:
            messages.error(request, f'خطا در ویرایش پلن: {str(e)}')
    return render(request, 'admin_panel/propplan_form.html', {'form_type': 'edit', 'plan': plan})

@admin_required('can_manage_verifications')
def propplan_delete(request, pk):
    plan = get_object_or_404(PropPlan, pk=pk)
    plan.delete()
    messages.success(request, 'پلن با موفقیت حذف شد.')
    return redirect('admin_panel:propplan_list')

@admin_required('can_manage_plans')
def rule_list(request):
    search_term = request.GET.get('search', '')
    rule_list = Rule.objects.all()
    fields = ['title', 'description']
    if search_term:
        query = Q()
        for field in fields:
            query |= Q(**{f"{field}__icontains": search_term})
        rule_list = rule_list.filter(query)
    paginator = Paginator(rule_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/rule_list.html', {
        'page_obj': page_obj,
        'search_term': search_term
    })

@admin_required('can_manage_plans')
def rule_add(request):
    if request.method == 'POST':
        try:
            Rule.objects.create(
                title=request.POST.get('title'),
                description=request.POST.get('description'),
                order=request.POST.get('order')
            )
            messages.success(request, 'قانون با موفقیت ایجاد شد.')
            return redirect('admin_panel:rule_list')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد قانون: {str(e)}')
    return render(request, 'admin_panel/rule_form.html', {'form_type': 'add'})

@admin_required('can_manage_plans')
def rule_edit(request, pk):
    rule = get_object_or_404(Rule, pk=pk)
    if request.method == 'POST':
        try:
            rule.title = request.POST.get('title')
            rule.description = request.POST.get('description')
            rule.order = request.POST.get('order')
            rule.save()
            messages.success(request, 'قانون با موفقیت ویرایش شد.')
            return redirect('admin_panel:rule_list')
        except Exception as e:
            messages.error(request, f'خطا در ویرایش قانون: {str(e)}')
    return render(request, 'admin_panel/rule_form.html', {'form_type': 'edit', 'rule': rule})

@admin_required('can_manage_plans')
def rule_delete(request, pk):
    rule = get_object_or_404(Rule, pk=pk)
    rule.delete()
    messages.success(request, 'قانون با موفقیت حذف شد.')
    return redirect('admin_panel:rule_list')

@admin_required('can_manage_discounts')
def discount_code_list(request):
    search_term = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    discount_list = DiscountCode.objects.all()
    fields = ['code', 'affiliate_email']
    filters = {'active': status_filter} if status_filter in ['True', 'False'] else None
    if search_term or filters:
        discount_list = search_query(discount_list, search_term, fields, filters)
    paginator = Paginator(discount_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/discount_code_list.html', {
        'page_obj': page_obj,
        'search_term': search_term,
        'status_filter': status_filter
    })

@admin_required('can_manage_discounts')
def discount_code_add(request):
    if request.method == 'POST':
        try:
            # Validate required fields
            required_fields = ['code', 'discount_type', 'discount_value']
            for field in required_fields:
                if not request.POST.get(field):
                    messages.error(request, f'فیلد {field} الزامی است.')
                    return render(request, 'admin_panel/discount_code_form.html', {
                        'form_type': 'add',
                        'plans': PropPlan.objects.all(),
                        'users': CustomUser.objects.all(),
                        'discount_code': DiscountCode(**{k: v for k, v in request.POST.items() if k in ['code', 'discount_type', 'discount_value', 'max_uses', 'affiliate_email', 'affiliate_percentage', 'expiration_date', 'max_uses_active', 'first_purchase_only', 'active']}),
                    })

            discount_code = DiscountCode.objects.create(
                code=request.POST.get('code'),
                discount_type=request.POST.get('discount_type'),
                discount_value=request.POST.get('discount_value'),
                max_uses=request.POST.get('max_uses') or 1,
                max_uses_active=request.POST.get('max_uses_active') == 'on',
                first_purchase_only=request.POST.get('first_purchase_only') == 'on',
                affiliate_email=request.POST.get('affiliate_email') or None,
                affiliate_percentage=request.POST.get('affiliate_percentage') or 0.0,
                active=request.POST.get('active') == 'on',
                expiration_date=request.POST.get('expiration_date') or None
            )
            # Handle ManyToMany fields
            if request.POST.getlist('plans'):
                discount_code.plans.set(PropPlan.objects.filter(id__in=request.POST.getlist('plans')))
            if request.POST.getlist('users'):
                discount_code.users.set(CustomUser.objects.filter(id__in=request.POST.getlist('users')))
            messages.success(request, 'کد تخفیف با موفقیت ایجاد شد.')
            return redirect('admin_panel:discount_code_list')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد کد تخفیف: {str(e)}')
            return render(request, 'admin_panel/discount_code_form.html', {
                'form_type': 'add',
                'plans': PropPlan.objects.all(),
                'users': CustomUser.objects.all(),
                'discount_code': DiscountCode(**{k: v for k, v in request.POST.items() if k in ['code', 'discount_type', 'discount_value', 'max_uses', 'affiliate_email', 'affiliate_percentage', 'expiration_date', 'max_uses_active', 'first_purchase_only', 'active']}),
            })
    return render(request, 'admin_panel/discount_code_form.html', {
        'form_type': 'add',
        'plans': PropPlan.objects.all(),
        'users': CustomUser.objects.all(),
        'discount_code': DiscountCode()  # Empty object for GET request
    })

@admin_required('can_manage_discounts')
def discount_code_edit(request, pk):
    discount_code = get_object_or_404(DiscountCode, pk=pk)
    if request.method == 'POST':
        try:
            # Validate required fields
            required_fields = ['code', 'discount_type', 'discount_value']
            for field in required_fields:
                if not request.POST.get(field):
                    messages.error(request, f'فیلد {field} الزامی است.')
                    return render(request, 'admin_panel/discount_code_form.html', {
                        'form_type': 'edit',
                        'discount_code': discount_code,
                        'plans': PropPlan.objects.all(),
                        'users': CustomUser.objects.all(),
                    })

            discount_code.code = request.POST.get('code')
            discount_code.discount_type = request.POST.get('discount_type')
            discount_code.discount_value = request.POST.get('discount_value')
            discount_code.max_uses = request.POST.get('max_uses') or 1
            discount_code.max_uses_active = request.POST.get('max_uses_active') == 'on'
            discount_code.first_purchase_only = request.POST.get('first_purchase_only') == 'on'
            discount_code.affiliate_email = request.POST.get('affiliate_email') or None
            discount_code.affiliate_percentage = request.POST.get('affiliate_percentage') or 0.0
            discount_code.active = request.POST.get('active') == 'on'
            discount_code.expiration_date = request.POST.get('expiration_date') or None
            discount_code.save()
            # Handle ManyToMany fields
            discount_code.plans.set(PropPlan.objects.filter(id__in=request.POST.getlist('plans')))
            discount_code.users.set(CustomUser.objects.filter(id__in=request.POST.getlist('users')))
            messages.success(request, 'کد تخفیف با موفقیت ویرایش شد.')
            return redirect('admin_panel:discount_code_list')
        except Exception as e:
            messages.error(request, f'خطا در ویرایش کد تخفیف: {str(e)}')
            return render(request, 'admin_panel/discount_code_form.html', {
                'form_type': 'edit',
                'discount_code': discount_code,
                'plans': PropPlan.objects.all(),
                'users': CustomUser.objects.all(),
            })
    return render(request, 'admin_panel/discount_code_form.html', {
        'form_type': 'edit',
        'discount_code': discount_code,
        'plans': PropPlan.objects.all(),
        'users': CustomUser.objects.all()
    })

@admin_required('can_manage_discounts')
def discount_code_delete(request, pk):
    discount_code = get_object_or_404(DiscountCode, pk=pk)
    discount_code.delete()
    messages.success(request, 'کد تخفیف با موفقیت حذف شد.')
    return redirect('admin_panel:discount_code_list')

from django.http import JsonResponse

@admin_required('can_manage_accounts')
def propaccount_assign(request, pk):
    account = get_object_or_404(PropAccount, pk=pk)

    # بررسی اینکه اکانت خالی است
    if account.user or account.order or account.plan:
        messages.error(request, 'این حساب خالی نیست و نمی‌تواند تحویل داده شود.')
        return redirect('admin_panel:propaccount_list')

    if request.method == 'POST':
        try:
            plan_id = request.POST.get('plan_type')
            user_id = request.POST.get('user_id')
            balance = request.POST.get('balance')
            level = request.POST.get('level')
            order_id = request.POST.get('order_id')  # 👈 آیدی سفارش اختیاری

            if not plan_id or not user_id or not balance or not level:
                raise ValueError('پلن، کاربر، موجودی و لِوِل باید مشخص شوند.')

            plan = PropPlan.objects.get(pk=plan_id)
            user = CustomUser.objects.get(pk=user_id)

            # بررسی تطابق موجودی با پلن
            if float(balance) != float(plan.account_size):
                raise ValueError('موجودی حساب با اندازه حساب پلن مطابقت ندارد.')

            # بررسی معتبر بودن لِوِل
            valid_levels = [choice[0] for choice in PropAccount.LEVEL_CHOICES]
            if level not in valid_levels:
                raise ValueError('لِوِل انتخاب‌شده نامعتبر است.')

            # بررسی و اتصال سفارش
            order = None
            if order_id:
                try:
                    order = PropOrder.objects.get(pk=order_id)

                    # سفارش باید متعلق به همین کاربر باشد
                    if order.user != user:
                        raise ValueError('این سفارش متعلق به این کاربر نیست.')

                    
                except PropOrder.DoesNotExist:
                    raise ValueError('سفارشی با این آیدی پیدا نشد.')

            # بروزرسانی اکانت
            account.user = user
            account.plan = plan
            account.balance = balance
            account.level = level
            account.order = order  # اگر وارد نشده باشد، None می‌ماند

            # تنظیم محدودیت‌ها بر اساس پلن و مرحله
            plan_stage = PlanStage.objects.filter(
                plan=plan,
                stage_type=plan.level
            ).first()

            if plan_stage:
                account.daily_draw_percent = plan_stage.max_daily_loss_percent
                account.total_draw_percent = plan_stage.max_loss_percent
                account.floating_risk_percent = plan_stage.floating_risk_percent
                account.profit_percent = plan_stage.profit_target_percent

            account.save()
            messages.success(request, 'حساب با موفقیت تحویل داده شد.')
            return redirect('admin_panel:propaccount_list')

        except Exception as e:
            messages.error(request, f'خطا در تحویل حساب: {str(e)}')
            return render(request, 'admin_panel/propaccount_assign.html', {
                'account': account,
                'plans': PropPlan.objects.all(),
                'level_choices': PropAccount.LEVEL_CHOICES,
                'selected_plan': request.POST.get('plan_type'),
                'selected_user_email': request.POST.get('user_email'),
                'selected_level': request.POST.get('level'),
                'selected_order_id': request.POST.get('order_id'),
                'error': str(e)
            })

    return render(request, 'admin_panel/propaccount_assign.html', {
        'account': account,
        'plans': PropPlan.objects.all(),
        'level_choices': PropAccount.LEVEL_CHOICES,
        'selected_plan': '',
        'selected_user_email': '',
        'selected_level': '',
        'selected_order_id': ''
    })


@admin_required('can_manage_accounts')
def user_search(request):
    query = request.GET.get('q', '')
    users = CustomUser.objects.filter(
        Q(email__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    )[:10]

    users_data = [
        {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
        for user in users
    ]

    return JsonResponse({'users': users_data})

import requests

from datetime import datetime

logger = logging.getLogger(__name__)

@admin_required('can_manage_accounts')
def propaccount_review(request):
    accounts = PropAccount.objects.all()
    search_query = request.POST.get('search_account', '').strip()
    # فیلتر کردن حساب‌ها بر اساس جستجو
    if search_query:
        accounts = accounts.filter(account_number__contains=search_query)
        if not accounts.exists():
            messages.error(request, 'هیچ حسابی با این شماره یافت نشد.')
    
    if request.method == 'POST' and 'account_number' in request.POST:
        account_number = request.POST.get('account_number')
        if account_number:
            try:
                # یافتن حساب برای دریافت اطلاعات سرور و رمز
                account = PropAccount.objects.get(account_number=account_number)
            except PropAccount.DoesNotExist:
                messages.error(request, 'حساب با این شماره یافت نشد.')
                return render(request, 'admin_panel/propaccount_review.html', {
                    'accounts': accounts,
                    'metrics': None,
                    'trades_paginated': None,
                })
            
            try:
                # درخواست به API
                current_time = datetime.now()
                formatted_time = current_time.strftime("%Y-%m-%dT23:59:59")
                
                api_url = 'http://91.107.144.126:80/metrics'
                payload = {
                    'login': int(account_number),
                    'password': account.investor_password,
                    'server': account.server,
                    'from_date': '2025-01-27',
                    'to_date': formatted_time,
                    'daily_drawdown_threshold': float(account.daily_draw_percent or 5.0),
                    'overall_drawdown_threshold': float(account.total_draw_percent or 20.0),
                    'floating_risk_threshold': float(account.floating_risk_percent or 2.0),
                    'profit_target_percent': float(account.profit_percent or 10.0)
                }
                response = requests.post(api_url, json=payload, timeout=60)
                response.raise_for_status()
                metrics = response.json()
                
                # محاسبه معاملات زیر 30 ثانیه با پروفیت مثبت
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
                current_profit_percent = ((current_balance - initial_balance) / initial_balance) * 100 if initial_balance != 0 else 0.0
                
                # تعیین وضعیت حساب
                is_violated = metrics.get('daily_drawdown_violated', False) or \
                              metrics.get('overall_drawdown_violated', False) or \
                              metrics.get('floating_risk_violated', False) or \
                              metrics.get('position_loss_violated', False) or \
                              metrics.get('profit_violated', False)
                
                account_status = "حساب از دست رفته" if is_violated else \
                                 "پاس شده" if current_balance >= metrics.get('profit_target_value', 0) else \
                                 "در حال بررسی"
                
                # صفحه‌بندی معاملات
                trades_paginated = None
                if metrics.get('trades'):
                    paginator = Paginator(metrics['trades'], 10)
                    page_number = request.POST.get('page', 1)
                    trades_paginated = paginator.get_page(page_number)
                
                return render(request, 'admin_panel/propaccount_review.html', {
                    'accounts': accounts,
                    'selected_account': account,
                    'metrics': metrics,
                    'current_profit_percent': current_profit_percent,
                    'trades_paginated': trades_paginated,
                    'account_status': account_status,
                })
            except requests.exceptions.HTTPError as http_err:
                logger.error(f"API HTTP Error: {http_err}")
                messages.error(request, 'خطا در دریافت اطلاعات از API. لطفاً دوباره تلاش کنید.')
            except requests.exceptions.RequestException as req_err:
                logger.error(f"API Request Error: {req_err}")
                messages.error(request, 'خطا در اتصال به API. لطفاً دوباره تلاش کنید.')
            except ValueError as json_err:
                logger.error(f"API JSON Error: {json_err}")
                messages.error(request, 'داده‌های دریافتی از API نامعتبر است.')
    
    return render(request, 'admin_panel/propaccount_review.html', {
        'accounts': accounts,
        'metrics': None,
        'trades_paginated': None,
    })

    
    
@admin_required('can_manage_accounts')
def bulk_assign_accounts(request):
    if request.method == 'POST':
        try:
            user_ids = request.POST.getlist('user_id')
            plan_id = request.POST.get('plan_type')
            balance = request.POST.get('balance')

            if not user_ids or not plan_id or not balance:
                raise ValueError('کاربران، پلن و موجودی باید مشخص شوند.')

            plan = PropPlan.objects.get(pk=plan_id)
            if float(balance) != float(plan.account_size):
                raise ValueError('موجودی با اندازه حساب پلن مطابقت ندارد.')

            empty_accounts = PropAccount.objects.filter(user__isnull=True, order__isnull=True, plan__isnull=True)
            if len(empty_accounts) < len(user_ids):
                raise ValueError(f'تعداد حساب‌های خالی ({len(empty_accounts)}) کمتر از تعداد کاربران انتخاب‌شده ({len(user_ids)}) است.')

            results = []
            selected_users = []
            for index, user_id in enumerate(user_ids):
                try:
                    user = CustomUser.objects.get(pk=user_id)
                    account = empty_accounts[index]
                    account.user = user
                    account.plan = plan
                    account.balance = balance

                    plan_stage = PlanStage.objects.filter(plan=plan, stage_type=plan.level).first()
                    if plan_stage:
                        account.daily_draw_percent = plan_stage.max_daily_loss_percent
                        account.total_draw_percent = plan_stage.max_loss_percent
                        account.floating_risk_percent = plan_stage.floating_risk_percent
                        account.profit_percent = plan_stage.profit_target_percent
                        account.level = "Real" if plan.name in ["zero", "ریل"] else "level1"

                    account.save()
                    results.append({
                        'email': user.email,
                        'status': 'success',
                        'message': f'حساب {account.account_number} با موفقیت به {user.email} تخصیص یافت.'
                    })
                    selected_users.append(user)

                    send_mail(
                        'تخصیص حساب پراپ',
                        f'حساب پراپ شماره {account.account_number} با موجودی {account.balance} دلار و پلن {plan.get_name_display()} به شما تخصیص یافت.',
                        'from@example.com',
                        [user.email],
                        fail_silently=True,
                    )

                except CustomUser.DoesNotExist:
                    results.append({
                        'email': f'کاربر با ID {user_id}',
                        'status': 'error',
                        'message': 'کاربر یافت نشد.'
                    })
                except Exception as e:
                    results.append({
                        'email': f'کاربر با ID {user_id}',
                        'status': 'error',
                        'message': f'خطا: {str(e)}'
                    })

            success_count = sum(1 for result in results if result['status'] == 'success')
            error_count = len(results) - success_count
            messages.success(request, f'{success_count} حساب با موفقیت تخصیص یافت.')
            if error_count > 0:
                messages.error(request, f'{error_count} خطا در تخصیص حساب‌ها رخ داد.')

            return render(request, 'admin_panel/bulk_assign_accounts.html', {
                'plans': PropPlan.objects.all(),
                'results': results,
                'selected_user_ids': user_ids,
                'selected_users': selected_users,
                'selected_plan': plan_id,
                'selected_balance': balance
            })

        except PropPlan.DoesNotExist:
            messages.error(request, 'پلن مشخص شده یافت نشد.')
        except ValueError as e:
            messages.error(request, f'خطا: {str(e)}')
        except Exception as e:
            messages.error(request, f'خطا در پردازش: {str(e)}')

    return render(request, 'admin_panel/bulk_assign_accounts.html', {
        'plans': PropPlan.objects.all(),
        'results': None,
        'selected_user_ids': [],
        'selected_users': [],
        'selected_plan': '',
        'selected_balance': ''
    })


from django.shortcuts import render, redirect
from django.contrib import messages
from .models import UserSubmission, SubmissionAttempt
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
            return redirect('admin_panel:user_submission_form')
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

@admin_required('can_manage_users')
def user_submission_list(request):
    search_term = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    submission_list = UserSubmission.objects.all()
    fields = ['instagram_id', 'telegram_id', 'email']
    filters = {'is_approved': status_filter == 'True'} if status_filter in ['True', 'False'] else None
    if search_term or filters:
        query = Q()
        for field in fields:
            query |= Q(**{f"{field}__icontains": search_term})
        if filters:
            query &= Q(**filters)
        submission_list = submission_list.filter(query)
    paginator = Paginator(submission_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/user_submission_list.html', {
        'page_obj': page_obj,
        'search_term': search_term,
        'status_filter': status_filter
    })

@admin_required('can_manage_users')
def user_submission_approve(request, pk):
    submission = get_object_or_404(UserSubmission, pk=pk)
    if request.method == 'POST':
        submission.is_approved = not submission.is_approved
        submission.save()
        status = 'تأیید' if submission.is_approved else 'لغو تأیید'
        messages.success(request, f'وضعیت ارسال با موفقیت {status} شد.')
        return redirect('admin_panel:user_submission_list')
    return redirect('admin_panel:user_submission_list')

@admin_required('can_manage_users')
def user_submission_delete(request, pk):
    submission = get_object_or_404(UserSubmission, pk=pk)
    if request.method == 'POST':
        submission.delete()
        messages.success(request, 'ارسال با موفقیت حذف شد.')
        return redirect('admin_panel:user_submission_list')
    return redirect('admin_panel:user_submission_list')




def search_query(queryset, search_term, fields, filters=None):
    query = Q()
    for field in fields:
        query |= Q(**{f"{field}__icontains": search_term})
    if filters:
        for key, value in filters.items():
            if value:
                query &= Q(**{key: value})
    return queryset.filter(query)

@admin_required('can_manage_verifications')
def wallet_list(request):
    search_term = request.GET.get('search', '')
    wallet_list = Wallet.objects.all()
    fields = ['user__email', 'balance_usd']
    if search_term:
        wallet_list = search_query(wallet_list, search_term, fields)
    paginator = Paginator(wallet_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/wallet_list.html', {
        'page_obj': page_obj,
        'search_term': search_term
    })

@admin_required('can_manage_verifications')
def wallet_transactions(request, wallet_id):
    wallet = get_object_or_404(Wallet, id=wallet_id)
    search_term = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    transaction_type_filter = request.GET.get('transaction_type', '')
    
    transaction_list = WalletTransaction.objects.filter(user=wallet.user)
    fields = ['transaction_id', 'amount_usd', 'amount_toman']
    filters = {}
    if status_filter:
        filters['status'] = status_filter
    if transaction_type_filter:
        filters['transaction_type'] = transaction_type_filter
    
    if search_term or filters:
        transaction_list = search_query(transaction_list, search_term, fields, filters)
    
    paginator = Paginator(transaction_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin_panel/wallet_transactions.html', {
        'page_obj': page_obj,
        'search_term': search_term,
        'status_filter': status_filter,
        'transaction_type_filter': transaction_type_filter,
        'wallet': wallet
    })

@admin_required('can_manage_verifications')
def wallet_edit(request, pk):
    wallet = get_object_or_404(Wallet, pk=pk)
    if request.method == 'POST':
        try:
            new_balance = request.POST.get('balance_usd')
            if new_balance:
                wallet.balance_usd = Decimal(new_balance)
                wallet.save()
                messages.success(request, 'موجودی کیف پول با موفقیت ویرایش شد.')
                send_mail(
                    'به‌روزرسانی موجودی کیف پول',
                    f'موجودی کیف پول شما به {wallet.balance_usd} دلار به‌روزرسانی شد.',
                    'from@example.com',
                    [wallet.user.email],
                    fail_silently=True,
                )
                return redirect('admin_panel:wallet_list')
            else:
                messages.error(request, 'مقدار موجودی الزامی است.')
        except Exception as e:
            messages.error(request, f'خطا در ویرایش کیف پول: {str(e)}')
    
    return render(request, 'admin_panel/wallet_form.html', {
        'form_type': 'edit',
        'wallet': wallet
    })

@admin_required('can_manage_verifications')
def bulk_update_wallets(request):
    users = CustomUser.objects.all()  # For template
    if request.method == 'POST':
        try:
            amount_usd = request.POST.get('amount_usd')
            all_users = request.POST.get('all_users') == 'on'
            user_ids = request.POST.getlist('user_id') if not all_users else [user.id for user in CustomUser.objects.all()]
            
            if not amount_usd:
                raise ValueError('مقدار برای اضافه کردن به موجودی الزامی است.')
            if not user_ids:
                raise ValueError('حداقل یک کاربر باید انتخاب شود.')
                
            amount_usd = Decimal(amount_usd)
            if amount_usd <= 0:
                raise ValueError('مقدار باید مثبت باشد.')
                
            results = []
            success_count = 0
            current_time = timezone.now().strftime('%Y%m%d%H%M%S')

            with transaction.atomic():
                # Fetch all users and their wallets in one query
                users = CustomUser.objects.filter(id__in=user_ids).select_related('wallet')
                user_ids_set = set(user_ids)
                existing_wallets = {w.user_id: w for w in Wallet.objects.filter(user_id__in=user_ids_set)}
                
                # Prepare lists for bulk operations
                wallets_to_create = []
                wallets_to_update = []
                transactions_to_create = []
                
                for user in users:
                    try:
                        transaction_id = f"ADMIN_{current_time}_{user.id}"
                        if user.id in existing_wallets:
                            # Update existing wallet
                            wallet = existing_wallets[user.id]
                            wallet.balance_usd += amount_usd
                            wallets_to_update.append(wallet)
                        else:
                            # Create new wallet
                            wallets_to_create.append(
                                Wallet(user=user, balance_usd=amount_usd)
                            )
                        
                        # Prepare transaction
                        transactions_to_create.append(
                            WalletTransaction(
                                user=user,
                                transaction_type='deposit',
                                amount_toman=0,  # Assuming no toman conversion
                                amount_usd=amount_usd,
                                status='completed',
                                transaction_id=transaction_id
                            )
                        )
                        
                        results.append({
                            'email': user.email,
                            'status': 'success',
                            'message': f'موجودی کیف پول {user.email} با موفقیت {amount_usd} دلار افزایش یافت.'
                        })
                        success_count += 1
                        
                    except Exception as e:
                        results.append({
                            'email': user.email,
                            'status': 'error',
                            'message': f'خطا: {str(e)}'
                        })

                # Bulk create new wallets
                if wallets_to_create:
                    Wallet.objects.bulk_create(wallets_to_create)
                
                # Bulk update existing wallets
                if wallets_to_update:
                    Wallet.objects.bulk_update(wallets_to_update, ['balance_usd'])
                
                # Bulk create transactions
                if transactions_to_create:
                    WalletTransaction.objects.bulk_create(transactions_to_create)
                
                # Send emails in bulk (asynchronous if possible)
                email_messages = [
                    (
                        'افزایش موجودی کیف پول',
                        f'موجودی کیف پول شما {amount_usd} دلار افزایش یافت. موجودی جدید: {wallet.balance_usd if wallet.user_id in existing_wallets else amount_usd} دلار',
                        'from@example.com',
                        [user.email]
                    )
                    for user, wallet in [(u, existing_wallets.get(u.id)) for u in users]
                ]
                for subject, message, from_email, recipient_list in email_messages:
                    send_mail(subject, message, from_email, recipient_list, fail_silently=True)
            
            messages.success(request, f'{success_count} کیف پول با موفقیت به‌روزرسانی شد.')
            if len(results) - success_count > 0:
                messages.error(request, f'{len(results) - success_count} خطا در به‌روزرسانی کیف پول‌ها رخ داد.')
                
            return render(request, 'admin_panel/bulk_update_wallets.html', {
                'users': users,
                'results': results,
                'selected_user_ids': user_ids,
                'amount_usd': amount_usd,
                'all_users': all_users
            })
            
        except ValueError as e:
            messages.error(request, f'خطا: {str(e)}')
        except Exception as e:
            messages.error(request, f'خطا در پردازش: {str(e)}')
    
    return render(request, 'admin_panel/bulk_update_wallets.html', {
        'users': users,
        'results': None,
        'selected_user_ids': [],
        'amount_usd': '',
        'all_users': False
    })
import time    
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
logger = logging.getLogger(__name__)

@admin_required('can_manage_users')
def send_gift_email(request):
    if request.method == 'POST':
        try:
            all_users = request.POST.get('all_users') == 'on'
            user_ids = request.POST.getlist('user_id') if not all_users else [user.id for user in CustomUser.objects.all()]

            if not user_ids:
                raise ValueError('حداقل یک کاربر باید انتخاب شود.')

            results = []
            success_count = 0

            # Fetch users in one query
            users = CustomUser.objects.filter(id__in=user_ids)
            
            for user in users:
                try:
                    # Prepare email
                    html_content = render_to_string('admin_panel/gift_email_template.html', {
                        'user': user,
                        'amount': '5.00',
                        'dashboard_url': 'https://apexfx.net/dashboard/'
                    })
                    text_content = strip_tags(html_content)

                    email = EmailMultiAlternatives(
                        subject='هدیه ویژه Apex Fx',
                        body=text_content,
                        from_email='info@apexfx.net',
                        to=[user.email]
                    )
                    email.attach_alternative(html_content, "text/html")
                    
                    # ارسال ایمیل
                    email.send(fail_silently=True)
                    
                    # پرینت اطلاعات ایمیل در کنسول
                    print(f"ایمیل به {user.email} با موفقیت ارسال شد. زمان: {time.strftime('%Y-%m-%d %H:%M:%S')}")

                    results.append({
                        'email': user.email,
                        'status': 'success',
                        'message': f'ایمیل برای {user.email} با موفقیت ارسال شد.'
                    })
                    success_count += 1

                    # تأخیر 0.5 ثانیه بین ارسال ایمیل‌ها
                    time.sleep(1)

                except Exception as e:
                    logger.error(f"خطا در ارسال ایمیل به {user.email}: {str(e)}")
                    results.append({
                        'email': user.email,
                        'status': 'error',
                        'message': f'خطا: {str(e)}'
                    })

            messages.success(request, f'{success_count} ایمیل با موفقیت ارسال شد.')
            if len(results) - success_count > 0:
                messages.error(request, f'{len(results) - success_count} خطا در ارسال ایمیل رخ داد.')

            return render(request, 'admin_panel/send_gift_email.html', {
                'users': CustomUser.objects.all(),
                'results': results,
                'selected_user_ids': user_ids,
                'all_users': all_users
            })

        except ValueError as e:
            logger.error(f"خطای ورودی: {str(e)}")
            messages.error(request, f'خطا: {str(e)}')
        except Exception as e:
            logger.error(f"خطا در پردازش: {str(e)}")
            messages.error(request, f'خطا در پردازش: {str(e)}')

    return render(request, 'admin_panel/send_gift_email.html', {
        'users': CustomUser.objects.all(),
        'results': None,
        'selected_user_ids': [],
        'all_users': False
    })
    
    

@admin_required('can_manage_plans')
def blog_list(request):
    search_term = request.GET.get('search', '')
    blog_list = BlogPost.objects.all()
    if search_term:
        blog_list = blog_list.filter(Q(title__icontains=search_term) | Q(content__icontains=search_term))
    paginator = Paginator(blog_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/blog_list.html', {'page_obj': page_obj, 'search_term': search_term})

@admin_required('can_manage_plans')
def blog_add(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        author = request.user if request.user.is_authenticated else None
        slug = request.POST.get('slug', title.lower().replace(' ', '-'))
        blog = BlogPost.objects.create(title=title, content=content, author=author, slug=slug)
        messages.success(request, f'پست "{title}" با موفقیت اضافه شد.')
        return redirect('admin_panel:blog_list_admin')
    return render(request, 'admin_panel/blog_form.html', {'form_type': 'add'})

@admin_required('can_manage_plans')
def blog_edit(request, pk):
    blog = get_object_or_404(BlogPost, pk=pk)
    if request.method == 'POST':
        blog.title = request.POST.get('title')
        blog.content = request.POST.get('content')
        blog.slug = request.POST.get('slug', blog.title.lower().replace(' ', '-'))
        blog.save()
        messages.success(request, f'پست "{blog.title}" با موفقیت ویرایش شد.')
        return redirect('admin_panel:blog_list_admin')
    return render(request, 'admin_panel/blog_form.html', {'form_type': 'edit', 'blog': blog})

@admin_required('can_manage_plans')
def blog_delete(request, pk):
    blog = get_object_or_404(BlogPost, pk=pk)
    if request.method == 'POST':
        blog.delete()
        messages.success(request, f'پست "{blog.title}" با موفقیت حذف شد.')
        return redirect('admin_panel:blog_list_admin')
    return render(request, 'admin_panel/blog_delete_confirm.html', {'blog': blog})

import random
import string


@admin_required('can_manage_users')
def password_generator(request):
    password = ''
    if request.method == 'POST':
        # Define character sets
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special_chars = '#[]()@$&*!?|,./^+-_'
        
        # Ensure at least one of each required type
        password = (
            random.choice(lowercase) +
            random.choice(uppercase) +
            random.choice(digits) +
            random.choice(special_chars)
        )
        
        # Fill the rest to reach exactly 14 characters
        remaining_length = 14 - 4  # 4 characters already used
        all_chars = lowercase + uppercase + digits + special_chars
        password += ''.join(random.choice(all_chars) for _ in range(remaining_length))
        
        # Shuffle the password to randomize character positions
        password = ''.join(random.sample(password, len(password)))
        
        messages.success(request, f'رمز عبور جدید: {password}')
    
    return render(request, 'admin_panel/password_generator.html', {'password': password})



@admin_required('can_manage_plans')
def free_account_quota_list(request):
    quota_list = FreeAccountQuota.objects.all().order_by('-date')
    paginator = Paginator(quota_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/free_account_quota_list.html', {
        'page_obj': page_obj
    })

@admin_required('can_manage_plans')
def free_account_quota_add(request):
    if request.method == 'POST':
        date = request.POST.get('date')
        total_capacity = request.POST.get('total_capacity')
        try:
            total_capacity = int(total_capacity)
            if total_capacity < 0:
                raise ValueError('ظرفیت نمی‌تواند منفی باشد.')
            FreeAccountQuota.objects.create(
                date=date,
                total_capacity=total_capacity,
                allocated_count=0
            )
            messages.success(request, 'ظرفیت قرعه‌کشی با موفقیت اضافه شد.')
            return redirect('admin_panel:free_account_quota_list')
        except Exception as e:
            messages.error(request, f'خطا در افزودن ظرفیت: {str(e)}')
    return render(request, 'admin_panel/free_account_quota_form.html', {
        'form_type': 'add'
    })
@admin_required('can_manage_plans')
def free_account_quota_edit(request, pk=None):
    if pk:
        quota = get_object_or_404(FreeAccountQuota, pk=pk)
    else:
        quota = None  # برای حالت افزودن

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete' and quota:
            quota.delete()
            messages.success(request, 'ظرفیت قرعه‌کشی با موفقیت حذف شد.')
            return redirect('admin_panel:free_account_quota_list')

        elif action == 'reset_allocated' and quota:
            quota.allocated_count = 0
            quota.save()
            messages.success(request, 'تعداد تخصیص‌یافته با موفقیت ریست شد (به صفر بازگشت).')
            return redirect('admin_panel:free_account_quota_edit', pk=quota.pk)

        else:
            # ویرایش یا افزودن
            date = request.POST.get('date')
            total_capacity = request.POST.get('total_capacity')
            try:
                total_capacity = int(total_capacity)
                if quota and total_capacity < quota.allocated_count:
                    raise ValueError('ظرفیت جدید نمی‌تواند کمتر از تعداد تخصیص‌یافته باشد.')

                if quota:
                    quota.date = date
                    quota.total_capacity = total_capacity
                    quota.save()
                    messages.success(request, 'ظرفیت قرعه‌کشی با موفقیت ویرایش شد.')
                else:
                    FreeAccountQuota.objects.create(
                        date=date,
                        total_capacity=total_capacity
                    )
                    messages.success(request, 'ظرفیت قرعه‌کشی با موفقیت ایجاد شد.')

                return redirect('admin_panel:free_account_quota_list')
            except Exception as e:
                messages.error(request, f'خطا: {str(e)}')

    return render(request, 'admin_panel/free_account_quota_form.html', {
        'form_type': 'edit' if quota else 'add',
        'quota': quota,
    })
from django.http import JsonResponse

@admin_required('can_manage_users')
def referral_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')  # 'all', 'with_earnings'

    referrals = Referral.objects.select_related('referrer', 'referred').all()

    if query:
        referrals = referrals.filter(
            Q(referrer__email__icontains=query) | Q(referred__email__icontains=query)
        )

    if status_filter == 'with_earnings':
        referrals = referrals.filter(earnings__gt=Decimal('0.00'))

    paginator = Paginator(referrals, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'status': status_filter,
        'display_type': 'referral',  # همیشه referral
        'object_type': 'رفرال‌ها',  # ثابت
    }
    return render(request, 'admin_panel/referral_list.html', context)
@admin_required('can_manage_users')
def referral_add(request):
    if request.method == 'POST':
        referrer_email = request.POST.get('referrer_email', '').strip()
        referred_email = request.POST.get('referred_email', '').strip()
        earnings_str = request.POST.get('earnings', '0.00').strip()

        if not referred_email:  # فقط referred اجباریه
            messages.error(request, 'ایمیل معرفی‌شده الزامی است.')
            return redirect('admin_panel:referral_add')

        try:
            referred = CustomUser.objects.get(email=referred_email)
            
            # چک تکرار: اگر Referral برای این referred وجود داره، خطا بده
            if Referral.objects.filter(referred=referred).exists():
                messages.error(request, 'این کاربر قبلاً در سیستم رفرال ثبت شده است.')
                return redirect('admin_panel:referral_add')

            # referrer اختیاری
            if referrer_email:
                referrer = CustomUser.objects.get(email=referrer_email)
            else:
                referrer = None

            earnings = Decimal(earnings_str) if earnings_str else Decimal('0.00')

            Referral.objects.create(
                referrer=referrer,
                referred=referred,
                earnings=earnings
            )
            referrer_msg = f" (معرف: {referrer.email})" if referrer else " (بدون معرف)"
            messages.success(request, f'رفرال برای {referred.email}{referrer_msg} با موفقیت اضافه شد.')
            return redirect('admin_panel:referral_list')

        except CustomUser.DoesNotExist as e:
            if referrer_email:
                messages.error(request, 'کاربر معرف یافت نشد.')
            else:
                messages.error(request, 'کاربر معرفی‌شده یافت نشد.')
        except ValueError:
            messages.error(request, 'درآمد باید یک عدد معتبر باشد.')

    prefill_referred = request.GET.get('referred_email', '')
    return render(request, 'admin_panel/referral_form.html', {
        'form_type': 'add',
        'header_title': 'افزودن رفرال',
        'prefill_referred': prefill_referred,
    })

@admin_required('can_manage_users')
def referral_edit(request, pk):
    referral = get_object_or_404(Referral, pk=pk)
    if request.method == 'POST':
        referrer_email = request.POST.get('referrer_email', '').strip()
        earnings_str = request.POST.get('earnings', '0.00').strip()
        # referred رو نمی‌تونی تغییر بدی (به خاطر OneToOne)، پس فقط earnings و referrer آپدیت می‌شه

        try:
            # referrer اختیاری
            if referrer_email:
                referrer = CustomUser.objects.get(email=referrer_email)
            else:
                referrer = None
            referral.referrer = referrer

            earnings = Decimal(earnings_str) if earnings_str else Decimal('0.00')
            referral.earnings = earnings
            referral.save()
            referrer_msg = f" (معرف: {referrer.email})" if referrer else " (بدون معرف)"
            messages.success(request, f'رفرال {referral.referred.email}{referrer_msg} با موفقیت به‌روزرسانی شد.')
            return redirect('admin_panel:referral_list')
        except CustomUser.DoesNotExist:
            messages.error(request, 'کاربر معرف یافت نشد.')
        except ValueError:
            messages.error(request, 'درآمد باید یک عدد معتبر باشد.')

    prefill_referred = request.GET.get('referred_email', '')
    return render(request, 'admin_panel/referral_form.html', {
        'form_type': 'edit',
        'referral': referral,
        'header_title': 'ویرایش رفرال',
        'prefill_referred': prefill_referred,
    })

@admin_required('can_manage_users')
def referral_delete(request, pk):
    referral = get_object_or_404(Referral, pk=pk)
    if request.method == 'POST':
        referral.delete()
        messages.success(request, 'رفرال با موفقیت حذف شد.')
        return redirect('admin_panel:referral_list')
    return render(request, 'admin_panel/confirm_delete.html', {'object': referral, 'object_type': 'رفرال'})



import requests
import json
import random
import string
@admin_required('can_manage_accounts')
def create_account_via_api(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', 'Apex').strip()
        last_name = request.POST.get('last_name', 'Fx').strip()
        group_id = int(request.POST.get('group_id', 1))
        initial_balance = request.POST.get('initial_balance', '1000.00').strip()

        # تولید خودکار رمزها
        main_password = ''.join(random.choices(string.ascii_letters + string.digits, k=14))
        investor_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "password": main_password,
            "investor_password": investor_password,
            "group_id": group_id,
            "initial_balance": initial_balance
            # شماره حساب ارسال نمی‌شود → API خودش تولید می‌کند
        }

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": "sina1831"
        }

        try:
            response = requests.post(
                "http://trader.apexfx.info/api/create_account/",
                data=json.dumps(payload),
                headers=headers,
                timeout=30
            )

            if response.status_code in [200, 201]:
                try:
                    api_response = response.json()
                    # استخراج شماره حساب از پاسخ API (هر کلیدی که API برگرداند)
                    account_number = (
                        api_response.get('account_number') or
                        api_response.get('account') or
                        api_response.get('number') or
                        api_response.get('login') or
                        api_response.get('id') or
                        'تولید شده توسط سرور'
                    )
                except:
                    api_response = response.text
                    account_number = 'نامشخص'

                messages.success(request, f'✅ حساب با موفقیت ایجاد شد! شماره حساب: {account_number}')
                return render(request, 'admin_panel/create_account_via_api.html', {
                    'success': True,
                    'account_number': account_number,
                    'main_password': main_password,
                    'investor_password': investor_password,
                    'initial_balance': initial_balance,
                    'api_response': api_response,
                })
            else:
                messages.error(request, f'❌ خطا از API: {response.status_code}')
                return render(request, 'admin_panel/create_account_via_api.html', {
                    'error': response.text,
                    'status_code': response.status_code
                })

        except Exception as e:
            messages.error(request, f'خطا در ارتباط با سرور: {str(e)}')

    return render(request, 'admin_panel/create_account_via_api.html')





# ============================================================================
#  تنظیمات درگاه پرداخت ریالی (انتخاب درگاه فعال: دایرکت پی / پی‌استار)
# ============================================================================
from django.conf import settings as django_settings
from trading.models import PaymentGatewaySetting


@admin_required('can_manage_accounts')
def payment_gateway_settings(request):
    setting = PaymentGatewaySetting.load()
    gateways = django_settings.PAYMENT_GATEWAYS

    if request.method == 'POST':
        selected = request.POST.get('active_rial_gateway')
        if selected in gateways:
            setting.active_rial_gateway = selected
            setting.save()
            messages.success(
                request,
                f"درگاه ریالی فعال به «{gateways[selected].get('label', selected)}» تغییر کرد."
            )
            return redirect('admin_panel:payment_gateway_settings')
        messages.error(request, 'درگاه انتخاب‌شده نامعتبر است.')

    # ساخت لیست درگاه‌ها برای نمایش (نام، برچسب، آدرس، شناسه)
    gateway_list = []
    for name, cfg in gateways.items():
        gateway_list.append({
            'name': name,
            'label': cfg.get('label', name),
            'base_url': cfg.get('base_url', ''),
            'gateway_id': cfg.get('gateway_id', ''),
            'callback_url': cfg.get('callback_url', ''),
            'is_active': name == setting.active_rial_gateway,
        })

    return render(request, 'admin_panel/payment_gateway_settings.html', {
        'setting': setting,
        'gateways': gateway_list,
        'active_gateway': setting.active_rial_gateway,
    })



# ============================================================================
#  لاگ‌های عملیات ادمین (فقط برای سوپریوزرها)
# ============================================================================
from functools import wraps
from django.http import HttpResponseForbidden
from .models import AdminActionLog


def superuser_required(view_func):
    """دسترسی فقط برای سوپریوزرها؛ سایرین Forbidden می‌گیرند."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'لطفاً ابتدا وارد شوید.')
            return redirect('admin_panel:dashboard')
        if not request.user.is_superuser and request.user.email != "sinakrg1831@gmail.com":
            return HttpResponseForbidden('این بخش فقط برای سوپریوزرها قابل دسترسی است.')
        return view_func(request, *args, **kwargs)
    return wrapper


@superuser_required
def admin_action_log_list(request):
    logs = AdminActionLog.objects.all().select_related('user')

    # --- فیلترها ---
    f_email = request.GET.get('email', '').strip()
    f_category = request.GET.get('category', '').strip()
    f_method = request.GET.get('method', '').strip()
    f_view = request.GET.get('view_name', '').strip()
    f_status = request.GET.get('status_code', '').strip()
    f_ip = request.GET.get('ip', '').strip()
    f_date_from = request.GET.get('date_from', '').strip()
    f_date_to = request.GET.get('date_to', '').strip()
    f_q = request.GET.get('q', '').strip()

    if f_email:
        logs = logs.filter(user_email__icontains=f_email)
    if f_category:
        logs = logs.filter(category=f_category)
    if f_method:
        logs = logs.filter(method=f_method)
    if f_view:
        logs = logs.filter(view_name=f_view)
    if f_status:
        logs = logs.filter(status_code=f_status)
    if f_ip:
        logs = logs.filter(ip_address__icontains=f_ip)
    if f_date_from:
        logs = logs.filter(created_at__date__gte=f_date_from)
    if f_date_to:
        logs = logs.filter(created_at__date__lte=f_date_to)
    if f_q:
        logs = logs.filter(
            Q(action_description__icontains=f_q) |
            Q(path__icontains=f_q) |
            Q(post_data__icontains=f_q) |
            Q(query_string__icontains=f_q) |
            Q(object_id__icontains=f_q)
        )

    # --- صفحه‌بندی ---
    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    # --- مقادیر برای منوهای فیلتر ---
    distinct_views = (AdminActionLog.objects.exclude(view_name='')
                      .values_list('view_name', flat=True).distinct().order_by('view_name'))
    distinct_methods = (AdminActionLog.objects.exclude(method='')
                        .values_list('method', flat=True).distinct().order_by('method'))
    distinct_emails = (AdminActionLog.objects.exclude(user_email='')
                       .values_list('user_email', flat=True).distinct().order_by('user_email'))

    # رشته‌ی querystring بدون page برای حفظ فیلترها هنگام صفحه‌بندی
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()

    return render(request, 'admin_panel/admin_action_log_list.html', {
        'page_obj': page_obj,
        'total_count': paginator.count,
        'categories': AdminActionLog.CATEGORY_CHOICES,
        'distinct_views': distinct_views,
        'distinct_methods': distinct_methods,
        'distinct_emails': distinct_emails,
        'querystring': querystring,
        'filters': {
            'email': f_email, 'category': f_category, 'method': f_method,
            'view_name': f_view, 'status_code': f_status, 'ip': f_ip,
            'date_from': f_date_from, 'date_to': f_date_to, 'q': f_q,
        },
    })


@superuser_required
def admin_action_log_detail(request, pk):
    log = get_object_or_404(AdminActionLog, pk=pk)
    pretty_post = log.post_data
    try:
        if log.post_data:
            pretty_post = json.dumps(json.loads(log.post_data), ensure_ascii=False, indent=2)
    except Exception:
        pass
    return render(request, 'admin_panel/admin_action_log_detail.html', {
        'log': log,
        'pretty_post': pretty_post,
    })
