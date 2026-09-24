# -*- coding: utf-8 -*-
from django.db import migrations

DEFAULT_ORT_RULES = [
    ('S13', 'S13', '>=', 300),
    ('PD', 'ALL', '>=', 300),
    ('TV', 'ALL', '>=', 2000),
    ('DT', 'ALL', '>=', 2000),
]


def create_default_rules(apps, schema_editor):
    OrtRule = apps.get_model('core', 'OrtRule')
    # ★ 仅在规则表为空时初始化默认规则（首次 migrate）。之后删光不会自动补回。
    if OrtRule.objects.count() == 0:
        for type_name, source, op, threshold in DEFAULT_ORT_RULES:
            OrtRule.objects.create(
                type_name=type_name,
                source=source,
                operator=op,
                threshold=threshold,
                is_active=True,
                remark='默认规则（可在页面修改/删除）',
            )


def reverse(apps, schema_editor):
    OrtRule = apps.get_model('core', 'OrtRule')
    OrtRule.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0020_preplanrow_archived'),
    ]

    operations = [
        migrations.RunPython(create_default_rules, reverse),
    ]
