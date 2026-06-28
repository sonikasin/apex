from django.db import migrations


def create_default_plans(apps, schema_editor):
    PropPlan = apps.get_model('trading', 'PropPlan')
    PlanStage = apps.get_model('trading', 'PlanStage')

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
            'name': 'weekly',
            'stages': [
                {'type': 'stage_one', 'profit_target_percent': 8, 'min_trading_days': 3},
                {'type': 'stage_two', 'profit_target_percent': 4, 'min_trading_days': 3},
                {'type': 'real', 'profit_target': None, 'profit_target_percent': None, 'min_trading_days': None},
            ],
        }
    ]

    # ایجاد پلن‌ها و مراحل
    for account in account_sizes:
        for plan_type in plan_types:
            # محاسبه هدف سود بر اساس اندازه حساب
            plan = PropPlan.objects.create(
                name=plan_type['name'],
                account_size=account['size'],
                price=account['price'],
                leverage='1:100',
            )

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


class Migration(migrations.Migration):
    dependencies = [
        ('your_app', '0001_initial'),  # جایگزین با آخرین مهاجرت شما
    ]

    operations = [
        migrations.RunPython(create_default_plans),
    ]