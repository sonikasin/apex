from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0003_adminactionlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='adminactionlog',
            name='changes',
            field=models.TextField(blank=True, verbose_name='جزئیات تغییرات (قبل/بعد)'),
        ),
    ]
