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