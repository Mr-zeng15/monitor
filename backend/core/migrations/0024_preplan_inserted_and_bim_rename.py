# -*- coding: utf-8 -*-
"""
2026-08-26 改造迁移：
1) PreplanRow 新增 inserted_to_preplan 字段（计划外实时监控项是否插入预排筛选，默认不插入）
2) 历史数据重命名：Type 'MIB' → 'BIM'（S13 P/N 左2位 97 的 Type 标签统一为 BIM）
   - PreplanRow.type
   - OrtRule.type_name（用户自建的 MIB 规则一并迁移，避免与新 BIM 类型不匹配）
"""
from django.db import migrations, models


def rename_mib_to_bim(apps, schema_editor):
    PreplanRow = apps.get_model('core', 'PreplanRow')
    OrtRule = apps.get_model('core', 'OrtRule')
    PreplanRow.objects.filter(type='MIB').update(type='BIM')
    OrtRule.objects.filter(type_name='MIB').update(type_name='BIM')


def reverse_bim_to_mib(apps, schema_editor):
    PreplanRow = apps.get_model('core', 'PreplanRow')
    OrtRule = apps.get_model('core', 'OrtRule')
    PreplanRow.objects.filter(type='BIM').update(type='MIB')
    OrtRule.objects.filter(type_name='BIM').update(type_name='MIB')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_entrytable_pn_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='preplanrow',
            name='inserted_to_preplan',
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text='计划外实时监控项是否插入预排筛选（默认不插入；预警界面可切换）',
            ),
        ),
        migrations.RunPython(rename_mib_to_bim, reverse_bim_to_mib),
    ]
