from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from trading.models import PropPlan, PlanStage

class Command(BaseCommand):
    help = 'Adds a new Two-Stage Lottery plan with three stages'

    def handle(self, *args, **kwargs):
        try:
            with transaction.atomic():
                # بررسی وجود پلن برای جلوگیری از ایجاد تکراری
                if PropPlan.objects.filter(name='two_stage_lottery').exists():
                    self.stdout.write(self.style.WARNING('پلن "دو مرحله‌ای (قرعه‌کشی)" قبلاً وجود دارد.'))
                    return

                # ایجاد پلن جدید
                prop_plan = PropPlan.objects.create(
                    name='two_stage_lottery',
                    account_size=Decimal('10000.00'),
                    price=Decimal('100.00'),
                    leverage='1:100',
                    level='stage_one'
                )

                # اضافه کردن مراحل
                PlanStage.objects.create(
                    plan=prop_plan,
                    stage_type='stage_one',
                    profit_target=Decimal('1000.00'),
                    profit_target_percent=Decimal('10.00'),
                    max_loss_percent=Decimal('10.00'),
                    max_daily_loss_percent=Decimal('5.00'),
                    min_trading_days=10,
                    floating_risk_percent=Decimal('2.00')
                )

                PlanStage.objects.create(
                    plan=prop_plan,
                    stage_type='stage_two',
                    profit_target=Decimal('500.00'),
                    profit_target_percent=Decimal('5.00'),
                    max_loss_percent=Decimal('8.00'),
                    max_daily_loss_percent=Decimal('4.00'),
                    min_trading_days=10,
                    floating_risk_percent=Decimal('1.50')
                )

                PlanStage.objects.create(
                    plan=prop_plan,
                    stage_type='real',
                    profit_target=None,
                    profit_target_percent=None,
                    max_loss_percent=Decimal('6.00'),
                    max_daily_loss_percent=Decimal('3.00'),
                    min_trading_days=None,
                    floating_risk_percent=None
                )

                self.stdout.write(self.style.SUCCESS(
                    f'پلن "دو مرحله‌ای (قرعه‌کشی)" با موفقیت ایجاد شد: {prop_plan}'
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'خطا در ایجاد پلن: {str(e)}'))