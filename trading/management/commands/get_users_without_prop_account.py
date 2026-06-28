import csv
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from trading.models import PropAccount  # جایگزین با مسیر درست مدل PropAccount

class Command(BaseCommand):
    help = 'ایجاد فایل CSV از ایمیل کاربرانی که حساب پراپ ندارند'

    def handle(self, *args, **kwargs):
        CustomUser = get_user_model()
        # پیدا کردن کاربرانی که حساب پراپ ندارند
        users_without_prop_account = CustomUser.objects.filter(prop_accounts__isnull=True)

        # نام فایل CSV
        output_file = 'users_without_prop_account.csv'

        if users_without_prop_account.exists():
            # ایجاد فایل CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                # نوشتن هدر
                writer.writerow(['Email', 'First Name', 'Last Name'])
                # نوشتن اطلاعات کاربران
                for user in users_without_prop_account:
                    writer.writerow([user.email, user.first_name, user.last_name])

            self.stdout.write(self.style.SUCCESS(f'فایل CSV با موفقیت ایجاد شد: {output_file}'))
        else:
            self.stdout.write(self.style.WARNING('هیچ کاربری بدون حساب پراپ یافت نشد.'))