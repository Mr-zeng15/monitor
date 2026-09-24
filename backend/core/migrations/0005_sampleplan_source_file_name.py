from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_sampleplan_serial_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='sampleplan',
            name='source_file_name',
            field=models.CharField(blank=True, default='', help_text='导入时的原始 Excel 文件名', max_length=200, verbose_name='源文件名'),
        ),
    ]
