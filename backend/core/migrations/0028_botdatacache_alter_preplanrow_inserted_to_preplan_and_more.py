# ★ 2026-09-16：机器人（Dify）数据的服务端持久缓存
#
# 本次只做一件事：建 BotDataCache 表 —— 持久化「最后一次成功取到的真值」+「永久兜底种子」，
# 让 ABL / 面板数据在机器人临时不可达或服务器重启后依然可显示（不再整页灰）。
#
# 说明：makemigrations 顺带检测到长期遗留的模型漂移
# （inserted_to_preplan.db_index、source.choices），**已从本迁移中剔除**：
# 那是历史遗留、此前有意未生成（运行期无影响），不属本次需求。

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0027_preplanrow_longlife_preplanrow_longlife_copy_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BotDataCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=32, unique=True, verbose_name="缓存键")),
                ("payload", models.TextField(blank=True, default="", verbose_name="数据(JSON)")),
                ("is_seed", models.BooleanField(default=False, help_text="True=尚未取到真值，当前是内置兜底数据", verbose_name="是否兜底种子")),
                ("fetched_at", models.DateTimeField(blank=True, help_text="最近一次成功从机器人取到真值的时间", null=True, verbose_name="取到真值时间")),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True, verbose_name="最近尝试时间")),
                ("last_error", models.CharField(blank=True, default="", max_length=300, verbose_name="最近错误")),
                ("fail_count", models.IntegerField(default=0, verbose_name="连续失败次数")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "机器人数据缓存",
                "verbose_name_plural": "机器人数据缓存",
                "db_table": "bot_data_cache",
                "ordering": ["key"],
            },
        ),
    ]
