from django.db import models
from django.utils import timezone

class UserSubmission(models.Model):
    instagram_id = models.CharField(max_length=100, verbose_name="آیدی اینستاگرام")
    telegram_id = models.CharField(max_length=100, verbose_name="آیدی تلگرام")
    email = models.EmailField(unique=True, verbose_name="ایمیل")  # اضافه کردن unique=True برای جلوگیری از تکرار ایمیل
    is_approved = models.BooleanField(default=False, verbose_name="تأیید شده")
    submitted_at = models.DateTimeField(default=timezone.now, verbose_name="تاریخ ارسال")

    def __str__(self):
        return f"{self.email} - {'تأیید شده' if self.is_approved else 'در انتظار تأیید'}"

    class Meta:
        verbose_name = "ارسال اطلاعات کاربر"
        verbose_name_plural = "ارسال‌های اطلاعات کاربران"

class SubmissionAttempt(models.Model):
    ip_address = models.CharField(max_length=45, verbose_name="آدرس IP")  # پشتیبانی از IPv4 و IPv6
    attempt_count = models.PositiveIntegerField(default=0, verbose_name="تعداد تلاش‌ها")
    last_attempt = models.DateTimeField(default=timezone.now, verbose_name="آخرین تلاش")

    def __str__(self):
        return f"IP: {self.ip_address} - تلاش‌ها: {self.attempt_count}"

    class Meta:
        verbose_name = "تلاش ارسال"
        verbose_name_plural = "تلاش‌های ارسال"



class AdminActionLog(models.Model):
    """
    لاگ ممیزی پنل ادمین: هر درخواست/عملیاتی که هر ادمین در پنل انجام می‌دهد
    به همراه جزئیات (ایمیل ادمین، نوع عملیات، مسیر، داده‌های ارسالی، IP و نتیجه)
    در این جدول ثبت می‌شود. مشاهده‌ی این بخش فقط برای سوپریوزرها مجاز است.
    """
    CATEGORY_VIEW = 'view'
    CATEGORY_CREATE = 'create'
    CATEGORY_UPDATE = 'update'
    CATEGORY_DELETE = 'delete'
    CATEGORY_ACTION = 'action'
    CATEGORY_CHOICES = [
        (CATEGORY_VIEW, 'بازدید'),
        (CATEGORY_CREATE, 'ایجاد'),
        (CATEGORY_UPDATE, 'ویرایش'),
        (CATEGORY_DELETE, 'حذف'),
        (CATEGORY_ACTION, 'عملیات'),
    ]

    user = models.ForeignKey(
        'trading.CustomUser', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='admin_action_logs', verbose_name="ادمین",
    )
    # اسنپ‌شات ایمیل تا در صورت حذف کاربر هم باقی بماند
    user_email = models.CharField(max_length=254, blank=True, db_index=True, verbose_name="ایمیل ادمین")
    is_superuser = models.BooleanField(default=False, verbose_name="سوپریوزر بود")

    category = models.CharField(
        max_length=10, choices=CATEGORY_CHOICES, default=CATEGORY_VIEW,
        db_index=True, verbose_name="نوع عملیات",
    )
    action_description = models.CharField(max_length=300, blank=True, verbose_name="شرح عملیات")

    method = models.CharField(max_length=10, db_index=True, verbose_name="متد HTTP")
    path = models.CharField(max_length=500, db_index=True, verbose_name="مسیر")
    view_name = models.CharField(max_length=200, blank=True, db_index=True, verbose_name="نام ویو")
    query_string = models.TextField(blank=True, verbose_name="پارامترهای کوئری")
    post_data = models.TextField(blank=True, verbose_name="داده‌های ارسالی")
    object_id = models.CharField(max_length=100, blank=True, verbose_name="شناسه آبجکت")

    status_code = models.PositiveIntegerField(null=True, blank=True, db_index=True, verbose_name="کد وضعیت پاسخ")
    ip_address = models.CharField(max_length=45, blank=True, db_index=True, verbose_name="آدرس IP")
    user_agent = models.TextField(blank=True, verbose_name="User-Agent")

    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="زمان")

    class Meta:
        verbose_name = "لاگ عملیات ادمین"
        verbose_name_plural = "لاگ‌های عملیات ادمین"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user_email', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user_email} - {self.get_category_display()} - {self.action_description or self.path}"
