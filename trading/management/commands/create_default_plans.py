from django.core.management.base import BaseCommand
from trading.models import PropPlan, PlanStage


class Command(BaseCommand):
    help = 'Creates default Prop Plans with predefined account sizes and stages'

    def handle(self, *args, **kwargs):
        # حذف پلن‌های قبلی (اختیاری، اگر می‌خواهید داده‌های قبلی پاک شوند)
        PropPlan.objects.all().delete()

        # تعریف اندازه‌های حساب
        account_sizes = [
            {'size': 1000, 'price': 99},
            {'size': 3000, 'price': 149},
            {'size': 5000, 'price': 199},
            {'size': 10000, 'price': 299},
            {'size': 15000, 'price': 399},
        ]

        # تعریف پلن‌ها
        plan_types = [
            {
                'name': 'zero',
                'stages': [
                    {'type': 'real', 'profit_target': None, 'profit_target_percent': None, 'min_trading_days': None},
                ],
            },
            {
                'name': 'single_stage',
                'stages': [
                    {'type': 'stage_one', 'profit_target_percent': 8, 'min_trading_days': 3},
                    {'type': 'real', 'profit_target': None, 'profit_target_percent': None, 'min_trading_days': None},
                ],
            },
            {
                'name': 'two_stage',
                'stages': [
                    {'type': 'stage_one', 'profit_target_percent': 8, 'min_trading_days': 3},
                    {'type': 'stage_two', 'profit_target_percent': 5, 'min_trading_days': 3},
                    {'type': 'real', 'profit_target': None, 'profit_target_percent': None, 'min_trading_days': None},
                ],
            },
            {
                'name': 'weekly',
                'stages': [
                    {'type': 'stage_one', 'profit_target_percent': 8, 'min_trading_days': 3},
                    {'type': 'stage_two', 'profit_target_percent': 4, 'min_trading_days': 3},
                    {'type': 'real', 'profit_target': None, 'profit_target_percent': None, 'min_trading_days': None},
                ],
            },
        ]

        # ایجاد پلن‌ها و مراحل
        for account in account_sizes:
            for plan_type in plan_types:
                # بررسی اینکه پلن قبلاً وجود نداشته باشد
                if PropPlan.objects.filter(name=plan_type['name'], account_size=account['size']).exists():
                    self.stdout.write(
                        self.style.WARNING(
                            f"Plan {plan_type['name']} with size {account['size']} already exists."
                        )
                    )
                    continue

                # ایجاد پلن
                plan = PropPlan.objects.create(
                    name=plan_type['name'],
                    account_size=account['size'],
                    price=account['price'],
                    leverage='1:100',
                )

                # ایجاد مراحل
                for stage in plan_type['stages']:
                    profit_target = (
                        account['size'] * stage['profit_target_percent'] / 100
                        if stage['profit_target_percent']
                        else None
                    )
                    PlanStage.objects.create(
                        plan=plan,
                        stage_type=stage['type'],
                        profit_target=profit_target,
                        profit_target_percent=stage['profit_target_percent'],
                        max_loss_percent=10.0,
                        max_daily_loss_percent=5.0,
                        min_trading_days=stage['min_trading_days'],
                        floating_risk_percent=10.0,
                    )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created plan: {plan_type['name']} - {account['size']} USD"
                    )
                )

        self.stdout.write(self.style.SUCCESS('All default plans created successfully!'))