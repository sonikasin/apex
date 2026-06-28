import re
from django.core.management.base import BaseCommand
from trading.models import CustomUser  # اسم اپ خودت رو جایگزین کن
class Command(BaseCommand):
    help = 'استخراج شماره موبایل کاربران (فقط 10 رقم آخر: 912xxxxxxx) و ذخیره در فایل txt'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='clean_10digit_phones.txt',
            help='نام فایل خروجی (پیش‌فرض: clean_10digit_phones.txt)'
        )

    def handle(self, *args, **options):
        output_file = options['output']

        # فقط کاربرانی که شماره موبایل دارن
        users = CustomUser.objects.exclude(
            phone_number__isnull=True
        ).exclude(
            phone_number=''
        )

        self.stdout.write(f"در حال پردازش {users.count()} کاربر...")

        cleaned_numbers = set()

        # تبدیل اعداد فارسی به انگلیسی
        persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')

        for user in users:
            raw = user.phone_number.strip()
            if not raw:
                continue

            # ۱. تبدیل فارسی → انگلیسی
            phone = raw.translate(persian_to_english)

            # ۲. حذف همه کاراکترهای غیرعددی جز +
            phone = re.sub(r'[^0-9+]', '', phone)

            # ۳. حذف +
            phone = phone.replace('+', '')

            # ۴. حذف تمام پیش‌شماره‌ها
            phone = phone.lstrip('0')  # حذف صفرهای اول
            if phone.startswith('98'):
                phone = phone[2:]      # حذف 98 اول

            # ۵. فقط ۱۰ رقم آخر رو نگه دار (اگر بیشتر بود)
            if len(phone) >= 10:
                phone = phone[-10:]  # فقط ۱۰ رقم آخر

            # ۶. بررسی نهایی: باید ۱۰ رقم باشه و با 9 شروع بشه (ایرانی)
            if len(phone) == 10 and phone.startswith('9') and phone.isdigit():
                cleaned_numbers.add(phone)

        # مرتب‌سازی و ذخیره
        sorted_numbers = sorted(cleaned_numbers)

        with open(output_file, 'w', encoding='utf-8') as f:
            for i, num in enumerate(sorted_numbers):
                if i < len(sorted_numbers) - 1:
                    f.write(num + ',\n')
                else:
                    f.write(num + '\n')    # آخرین خط بدون کاما

        self.stdout.write(
            self.style.SUCCESS(
                f'تعداد {len(sorted_numbers)} شماره معتبر (10 رقمی) در فایل "{output_file}" ذخیره شد.'
            )
        )