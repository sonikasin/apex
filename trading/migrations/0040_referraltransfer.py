from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('trading', '0039_paymentgatewaysetting_proporder_payment_gateway_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReferralTransfer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount_usd', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='مبلغ منتقل‌شده (دلار)')),
                ('breakdown', models.TextField(blank=True, verbose_name='ریز درآمد (JSON)')),
                ('wallet_before', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='موجودی کیف‌پول قبل')),
                ('wallet_after', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='موجودی کیف‌پول بعد')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاریخ انتقال')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='referral_transfers', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'انتقال درآمد رفرال',
                'verbose_name_plural': 'انتقال‌های درآمد رفرال',
                'ordering': ['-created_at'],
            },
        ),
    ]
