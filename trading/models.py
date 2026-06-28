from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import random
import string
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import random
import string
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('ایمیل باید وارد شود.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.verification_code = ''.join(random.choices(string.digits, k=6))
        user.is_active = False
        user.save(using=self._db)
        
        # تنظیم referral_code به str(id)
        user.referral_code = str(user.id)
        user.save(using=self._db)
        
        # ایجاد کیف پول برای کاربر
        Wallet.objects.create(user=user)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_email_verified', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=15, blank=True)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)
    referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True)  # کد رفرال منحصر به فرد
    affiliate_percentage = models.FloatField(default=0.0, verbose_name="درصد همکاری رفرال")

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_groups',
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_permissions',
        blank=True,
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return self.email
from decimal import Decimal

class Referral(models.Model):
    referrer = models.ForeignKey(CustomUser, related_name='referrals_given', on_delete=models.CASCADE, verbose_name="معرف", null=True, blank=True)  # اضافه کردن null=True, blank=True
    referred = models.OneToOneField(CustomUser, related_name='referral_received', on_delete=models.CASCADE, verbose_name="معرفی‌شده")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    earnings = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="درآمد رفرال")

    def __str__(self):
        return f"{self.referrer.email if self.referrer else 'سیستم'} معرفی کرد {self.referred.email}"

    class Meta:
        verbose_name = 'رفرال'
        verbose_name_plural = 'رفرال‌ها'
        unique_together = ['referrer', 'referred']  # جلوگیری از تکرار (اختیاری، چون OneToOne برای referred هست)

class Wallet(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='wallet')
    balance_usd = models.DecimalField(max_digits=1000, decimal_places=2000, default=0.00, verbose_name="موجودی (دلار)")

    def __str__(self):
        return f"کیف پول {self.user.email} - موجودی: {self.balance_usd} دلار"

    class Meta:
        verbose_name = 'کیف پول'
        verbose_name_plural = 'کیف پول‌ها'
class Employee(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='employee_profile')
    can_manage_users = models.BooleanField(default=False)
    can_manage_accounts = models.BooleanField(default=False)
    can_manage_orders = models.BooleanField(default=False)
    can_manage_tickets = models.BooleanField(default=False)
    can_manage_employees = models.BooleanField(default=False)
    can_manage_verifications = models.BooleanField(default=False)
    can_manage_plans = models.BooleanField(default=False)
    can_manage_discounts = models.BooleanField(default=False)  # New permission for discount codes


    def __str__(self):
        return f"کارمند: {self.user.email}"

    class Meta:
        verbose_name = 'کارمند'
        verbose_name_plural = 'کارمندان'

class PropPlan(models.Model):
    PLAN_TYPES = [
        ('zero', 'ریل'),
        ('single_stage', 'تک‌مرحله‌ای'),
        ('two_stage', 'دو مرحله‌ای'),
        ('weekly', 'هفتگی'),
        ('two_stage_lottery', 'دو مرحله‌ای (قرعه‌کشی)'),  # نوع پلن جدید اضافه شد
    ]
    LEVEL_CHOICES = [
        ('stage_one', 'مرحله اول'),
        ('stage_two', 'مرحله دوم'),
        ('real', 'ریل'),
    ]
    name = models.CharField(max_length=100, choices=PLAN_TYPES)
    account_size = models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    leverage = models.CharField(max_length=10, default='1:100')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='stage_one')

    def __str__(self):
        return f"{self.get_name_display()} - {self.account_size} دلار - {self.get_level_display()}"

    class Meta:
        verbose_name = 'پلن پراپ'
        verbose_name_plural = 'پلن‌های پراپ'

class PlanStage(models.Model):
    STAGE_TYPES = [
        ('stage_one', 'مرحله اول'),
        ('stage_two', 'مرحله دوم'),
        ('real', 'ریل'),
    ]
    plan = models.ForeignKey(PropPlan, on_delete=models.CASCADE, related_name='stages')
    stage_type = models.CharField(max_length=20, choices=STAGE_TYPES)
    profit_target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    profit_target_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    max_loss_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)
    max_daily_loss_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)
    min_trading_days = models.IntegerField(null=True, blank=True)
    floating_risk_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.plan} - {self.get_stage_type_display()}"

    class Meta:
        verbose_name = 'مرحله پلن'
        verbose_name_plural = 'مراحل پلن'

   
class DiscountCode(models.Model):
    DISCOUNT_TYPES = [
        ('percent', 'درصد'),
        ('amount', 'مقدار ثابت'),
    ]
    code = models.CharField(max_length=50, unique=True, verbose_name="کد تخفیف")
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, verbose_name="نوع تخفیف")
    discount_value = models.PositiveIntegerField(verbose_name="مقدار تخفیف")
    max_uses = models.PositiveIntegerField(default=1, verbose_name="حداکثر استفاده")
    max_uses_active = models.BooleanField(default=False, verbose_name="فعال بودن محدودیت استفاده")
    first_purchase_only = models.BooleanField(default=False, verbose_name="فقط برای خرید اول")
    affiliate_email = models.EmailField(blank=True, null=True, verbose_name="ایمیل معرف")
    affiliate_percentage = models.FloatField(default=0.0, verbose_name="درصد معرف")
    plans = models.ManyToManyField(PropPlan, blank=True, verbose_name="پلن‌های مجاز")
    users = models.ManyToManyField(CustomUser, blank=True, related_name='allowed_discount_users', verbose_name="کاربران مجاز")
    active = models.BooleanField(default=True, verbose_name="فعال")
    expiration_date = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ انقضا")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ به‌روزرسانی")

    def __str__(self):
        return self.code

    def use_code(self):
        if self.max_uses_active and self.max_uses > 0:
            self.max_uses -= 1
            if self.max_uses == 0:
                self.active = False
            self.save()

    class Meta:
        verbose_name = "کد تخفیف"
        verbose_name_plural = "کدهای تخفیف"

class PropOrder(models.Model):
    PAYMENT_METHODS = [
        ('tether', 'تتر'),
        ('rial', 'ریالی'),
    ]
    order_number = models.CharField(max_length=20, unique=True, verbose_name="شماره سفارش")
    dollar_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="قیمت دلاری"
        )

    plan = models.ForeignKey(PropPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name="پلن")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders', null=True, blank=True, verbose_name="کاربر")
    purchase_date = models.DateField(default=timezone.now, verbose_name="تاریخ خرید")
    status = models.CharField(max_length=20, choices=[('pending', 'در انتظار'), ('completed', 'تکمیل شده'), ('cancelled', 'لغو شده')], default='pending', verbose_name="وضعیت")
    server = models.CharField(max_length=50, blank=True, null=True, verbose_name="بروکر")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='tether', verbose_name="روش پرداخت")
    discount_code = models.ForeignKey(DiscountCode, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="کد تخفیف")
    original_price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="قیمت اصلی (دلار)")
    final_price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="قیمت نهایی (دلار)")
    final_price_toman = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name="قیمت نهایی (تومان)")
    transaction_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="شناسه")
    accnum = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name="اکانت تحویلی")

    used_wallet = models.BooleanField(default=False, verbose_name="استفاده از کیف پول")

    def __str__(self):
        return f"سفارش {self.order_number}"

    class Meta:
        verbose_name = 'سفارش پراپ'
        verbose_name_plural = 'سفارش‌های پراپ'

class PropAccount(models.Model):
    LEVEL_CHOICES = [
        ('level1', 'مرحله اول'),
        ('level2', 'مرحله دوم'),
        ('Real', 'ریل'),
    ]
    STATUS_CHOICES = [
        ('active', 'فعال'),
        ('profit_withdrawal', 'برداشت سود'),
        ('lost', 'از دست رفته'),
        ('frozen', 'فریز'),
    ]
    account_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    server = models.CharField(max_length=50, null=True, blank=True)
    investor_password = models.CharField(max_length=50, null=True, blank=True)
    main_password = models.CharField(max_length=50, null=True, blank=True)
    plan = models.ForeignKey(PropPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='accounts')
    balance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    daily_draw_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_draw_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    floating_risk_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    profit_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    level = models.CharField(max_length=50, choices=LEVEL_CHOICES, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='prop_accounts', null=True, blank=True)
    order = models.ForeignKey(PropOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='prop_accounts')
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ آخرین به‌روزرسانی")
    def __str__(self):
        return f"حساب {self.account_number or 'بدون شماره'} (کاربر: {self.user.email if self.user else 'بدون کاربر'})"

    class Meta:
        verbose_name = 'حساب پراپ'
        verbose_name_plural = 'حساب‌های پراپ'
        # 👈 مرتب‌سازی بر اساس آخرین آپدیت (جدیدترین تغییرات در ابتدای لیست نمایش داده می‌شوند)
        ordering = ['-updated_at']

class Ticket(models.Model):
    ticket_number = models.CharField(max_length=200, unique=True)
    subject = models.CharField(max_length=200)
    department = models.CharField(max_length=100)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=[('open', 'باز'), ('closed', 'بسته')])
    messages = models.JSONField(default=list)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tickets', null=True, blank=True)
    account = models.ForeignKey(PropAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets', verbose_name="حساب پراپ")

    def __str__(self):
        return f"تیکت {self.ticket_number}"

class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    slug = models.SlugField(max_length=200, unique=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']

class IdentityVerification(models.Model):
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('approved', 'تأیید شده'),
        ('rejected', 'رد شده'),
    ]
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='identity_verification')
    national_id_image = models.ImageField(upload_to='identity/national_id/%Y/%m/%d/')
    selfie_with_id_image = models.ImageField(upload_to='identity/selfie/%Y/%m/%d/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"احراز هویت {self.user.email}"

    class Meta:
        verbose_name = 'احراز هویت'
        verbose_name_plural = 'احراز هویت‌ها'
        
        
        
        

class Rule(models.Model):
    title = models.CharField(max_length=200, verbose_name="عنوان قانون")
    description = models.TextField(verbose_name="توضیحات قانون")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ به‌روزرسانی")

    class Meta:
        verbose_name = "قانون"
        verbose_name_plural = "قوانین"
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.order}. {self.title}"
    
    
    
 
 
 
class StageUpgradeRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('approved', 'تأیید شده'),
        ('rejected', 'رد شده'),
    ]
    
    account = models.ForeignKey(PropAccount, on_delete=models.CASCADE, related_name='upgrade_requests', verbose_name="حساب پراپ")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='upgrade_requests', verbose_name="کاربر")
    requested_at = models.DateTimeField(default=timezone.now, verbose_name="تاریخ درخواست")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    rejection_reason = models.TextField(blank=True, null=True, verbose_name="دلیل رد درخواست")
    
    class Meta:
        verbose_name = 'درخواست ارتقاء مرحله'
        verbose_name_plural = 'درخواست‌های ارتقاء مرحله'
        unique_together = [['account', 'user']]  # جلوگیری از درخواست‌های تکراری برای یک حساب

    def __str__(self):
        return f"درخواست ارتقاء برای حساب {self.account.account_number} - کاربر: {self.user.email}"



class Wallet(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='wallet')
    balance_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="موجودی (دلار)")

    def __str__(self):
        return f"کیف پول {self.user.email} - موجودی: {self.balance_usd} دلار"

    class Meta:
        verbose_name = 'کیف پول'
        verbose_name_plural = 'کیف پول‌ها'

class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'واریز'),
        ('withdrawal', 'برداشت'),
    ]
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='wallet_transactions', verbose_name="کاربر")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name="نوع تراکنش")
    amount_toman = models.DecimalField(max_digits=15, decimal_places=0, verbose_name="مبلغ (تومان)")
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="مبلغ (دلار)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="تاریخ ایجاد")
    transaction_id = models.CharField(max_length=50, unique=True, verbose_name="شناسه تراکنش")

    def __str__(self):
        return f"{self.transaction_type} - {self.user.email} - {self.amount_usd} دلار"

    class Meta:
        verbose_name = 'تراکنش کیف پول'
        verbose_name_plural = 'تراکنش‌های کیف پول'




class FreeAccountQuota(models.Model):
    date = models.DateField(default=timezone.now, unique=True, verbose_name="تاریخ")
    total_capacity = models.PositiveIntegerField(default=100, verbose_name="ظرفیت کل")
    allocated_count = models.PositiveIntegerField(default=0, verbose_name="تعداد تخصیص‌یافته")

    def __str__(self):
        return f"ظرفیت اکانت رایگان - {self.date}"

    class Meta:
        verbose_name = 'ظرفیت اکانت رایگان'
        verbose_name_plural = 'ظرفیت‌های اکانت رایگان'

    def is_capacity_available(self):
        return self.allocated_count < self.total_capacity

    def allocate_account(self):
        if self.is_capacity_available():
            self.allocated_count += 1
            self.save()
            return True
        return False
    
    
    
    

class Certificate(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='certificates', verbose_name="کاربر")
    account = models.OneToOneField(PropAccount, on_delete=models.CASCADE, related_name='certificate', verbose_name="حساب پراپ")
    name = models.CharField(max_length=100, verbose_name="نام روی سرتیفیکیت")
    file = models.FileField(upload_to='certificates/%Y/%m/%d/', verbose_name="فایل سرتیفیکیت")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="تاریخ ایجاد")

    def __str__(self):
        return f"سرتیفیکیت برای {self.user.email} - {self.account.account_number}"

    class Meta:
        verbose_name = 'سرتیفیکیت'
        verbose_name_plural = 'سرتیفیکیت‌ها'



class AccountSimulationLog(models.Model):
    account_number = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="شماره حساب")
    broker = models.CharField(max_length=50, blank=True, verbose_name="بروکر")
    email = models.EmailField(blank=True, null=True, verbose_name="ایمیل کاربر")
    order_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="شماره سفارش")
    plan = models.CharField(max_length=100, blank=True, null=True, verbose_name="پلن")
    level = models.CharField(max_length=50, blank=True, null=True, verbose_name="لول")
    initial_balance = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="بالانس اولیه")
    final_balance = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="بالانس نهایی")
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name="آدرس IP")
    checked_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان بررسی")

    class Meta:
        verbose_name = "لاگ شبیه‌سازی حساب"
        verbose_name_plural = "لاگ‌های شبیه‌سازی حساب"
        ordering = ['-checked_at']

    def __str__(self):
        return f"{self.account_number} - {self.checked_at.strftime('%Y-%m-%d %H:%M')}"