# -*- coding: utf-8 -*-
# 手动创建（2026-09-14）：PreplanRow 新增「定版时间」列（archived_at）

from django.db import migrations, models


def backfill_archived_at(apps, schema_editor):
    """历史存量：已定版但无时间的行，用 updated_at 近似回填，保证时间列不为空。"""
    PreplanRow = apps.get_model('core', 'PreplanRow')
    PreplanRow.objects.filter(archived=True, archived_at__isnull=True).update(
        archived_at=models.F('updated_at')
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_preplanrow_oqc_hold'),
    ]

    operations = [
        migrations.AddField(
            model_name='preplanrow',
            name='archived_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='定版时间',
                help_text='保存到存档中心的时间；撤销存档时清空（2026-09-14）',
            ),
        ),
        migrations.RunPython(backfill_archived_at, migrations.RunPython.noop),
    ]
