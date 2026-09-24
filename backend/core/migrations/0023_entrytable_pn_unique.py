# -*- coding: utf-8 -*-
"""
基础资料表唯一键 model → P/N 迁移
- 新增 pn 字段；已有行的 pn 用 model 值回填（历史数据平滑过渡）
- pn 设为唯一键；model 保留但不再唯一（可空）
"""
from django.db import migrations, models


def backfill_pn_from_model(apps, schema_editor):
    EntryTable = apps.get_model('core', 'EntryTable')
    for e in EntryTable.objects.all():
        if not (e.pn or '').strip():
            e.pn = (e.model or '').strip()
            e.save(update_fields=['pn'])


def reverse_backfill(apps, schema_editor):
    """反向：无需恢复（数据本身不丢）"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_preplanrow_mtd_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='entrytable',
            name='pn',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='P/N'),
        ),
        migrations.RunPython(backfill_pn_from_model, reverse_backfill),
        migrations.AlterField(
            model_name='entrytable',
            name='model',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Model'),
        ),
        migrations.AlterField(
            model_name='entrytable',
            name='pn',
            field=models.CharField(max_length=100, unique=True, verbose_name='P/N'),
        ),
        migrations.AlterModelOptions(
            name='entrytable',
            options={'ordering': ['pn'], 'verbose_name': '基础资料表', 'verbose_name_plural': '基础资料表'},
        ),
    ]
