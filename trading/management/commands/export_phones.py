import re
from django.core.management.base import BaseCommand
from trading.models import CustomUser  # مدل اختصاصی شما در اپلیکیشن trading

class Command(BaseCommand):
    help = 'خروجی گرفتن و استانداردسازی شماره تلفن کاربران در قالب فایل متنی'

    def handle(self, *args, **options):
        # ۱. دریافت تمام شماره‌های غیرخالی از دیتابیس
        raw_phones = CustomUser.objects.exclude(phone_number='').exclude(phone_number__isnull=True).values_list('phone_number', flat=True)
        
        if not raw_phones:
            self.stdout.write(self.style.WARNING('هیچ شماره تلفنی در دیتابیس یافت نشد.'))
            return

        cleaned_numbers = []
        
        # جدول تبدیل اعداد فارسی و عربی به انگلیسی
        persian_arabic_digits = "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩"
        english_digits = "01234567890123456789"
        translation_table = str.maketrans(persian_arabic_digits, english_digits)

        for phone in raw_phones:
            if not phone:
                continue
                
            # الف) تبدیل اعداد فارسی/عربی به انگلیسی و حذف فاصله‌های خالی
            phone_en = phone.translate(translation_table).replace(" ", "").strip()
            
            # ب) استخراج فقط ارقام (حذف علامت پلاس + و حروف مثل ایمیل‌ها)
            digits_only = re.sub(r'\D', '', phone_en)
            
            # ج) استانداردسازی شماره‌های ایران (باید با 9 شروع شوند و 10 رقم باشند)
            if digits_only.startswith('98') and len(digits_only) > 10:
                # حذف کد کشور 98 ابتدایی
                digits_only = digits_only[2:]
            
            if digits_only.startswith('0'):
                # حذف صفر اول شماره (مثال: 0912 -> 912)
                digits_only = digits_only.lstrip('0')
                
            # د) اعتبارسنجی نهایی: شماره موبایل معتبر ایران بدون صفر باید دقیقا ۱۰ رقم بوده و با 9 شروع شود
            if len(digits_only) == 10 and digits_only.startswith('9'):
                cleaned_numbers.append(digits_only)

        # ۲. حذف شماره‌های تکراری احتمالی در دیتابیس (بر اساس فرمت جدید)
        final_numbers = list(set(cleaned_numbers))
        total_count = len(final_numbers)

        if total_count == 0:
            self.stdout.write(self.style.WARNING('پس از پاک‌سازی، هیچ شماره موبایل معتبری پیدا نشد.'))
            return

        # ۳. نوشتن در فایل متنی دقیقاً با فرمت درخواستی شما
        filename = 'user_phone_numbers.txt'
        with open(filename, 'w', encoding='utf-8') as f:
            for index, phone in enumerate(final_numbers):
                if index < total_count - 1:
                    f.write(f"{phone},\n")
                else:
                    f.write(phone)  # خط آخر بدون ویرگول و بدون اینتر اضافه

        self.stdout.write(self.style.SUCCESS(f'موفقیت‌آمیز: تعداد {total_count} شماره استانداردسازی شده در فایل {filename} ذخیره شد.'))