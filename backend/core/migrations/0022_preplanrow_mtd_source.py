# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_ortrule_defaults'),
    ]

    operations = [
        migrations.AddField(
            model_name='preplanrow',
            name='mtd_source',
            field=models.CharField('MTD来源', max_length=10, blank=True, default='', help_text='MTD SQL 的 source 列（s13/s11），计划外行用于区分预警规则来源'),
        ),
    ]
