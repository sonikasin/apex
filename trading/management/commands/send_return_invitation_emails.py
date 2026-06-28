import csv
import os
import time
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

class Command(BaseCommand):
    help = 'ارسال ایمیل دعوت به بازگشت به کاربران بدون حساب پراپ از فایل CSV با تأخیر 1 ثانیه'

    def handle(self, *args, **kwargs):
        csv_file_path = 'users_without_prop_account.csv'

        # بررسی وجود فایل CSV
        if not os.path.exists(csv_file_path):
            self.stdout.write(self.style.ERROR(f'فایل CSV یافت نشد: {csv_file_path}'))
            return

        # خواندن ایمیل‌ها از فایل CSV
        email_list = []
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                email_list.append(row['Email'])

        if not email_list:
            self.stdout.write(self.style.WARNING('هیچ ایمیلی در فایل CSV یافت نشد.'))
            return

        # ارسال ایمیل به هر کاربر
        for email in email_list:
            try:
                # رندر تمپلیت ایمیل
                html_content = render_to_string('emails/return_invitation.html')
                text_content = (
                    'دوست عزیز، دلمون برات تنگ شده!\n\n'
                    'پراپ اپکس اف ایکس رو فراموش کردی؟ ما یه هدیه ویژه برای بازگشتت آماده کردیم:\n'
                    'کد تخفیف ۴۰٪: 40OFF\n\n'
                    'با این کد می‌تونی دوباره به جمع معامله‌گران موفق ما بپیوندی و مسیر موفقیتت رو ادامه بدی!\n'
                    'همین حالا برگرد و از این فرصت استثنایی استفاده کن. ما منتظرت هستیم!\n\n'
                    'تماس با ما: 02171057717\n'
                    'سایت ما: https://apexfx.net/\n'
                    'کانال تلگرام: https://t.me/ApexFx_net\n'
                    'گروه تلگرام: https://t.me/+Xeon49199f9iNGFk\n'
                    'اینستاگرام: https://www.instagram.com/apexfx_net\n'
                )

                # ایجاد ایمیل
                email_message = EmailMultiAlternatives(
                    subject='دوست عزیز، به اپکس اف ایکس برگرد و ۴۰٪ تخفیف بگیر! 🎁',
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                email_message.attach_alternative(html_content, "text/html")
                email_message.send()

                self.stdout.write(self.style.SUCCESS(f'ایمیل با موفقیت به {email} ارسال شد.'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'خطا در ارسال ایمیل به {email}: {str(e)}'))

            # تأخیر 1 ثانیه‌ای بین ارسال ایمیل‌ها
            time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f'ارسال ایمیل به {len(email_list)} کاربر با موفقیت انجام شد.'))