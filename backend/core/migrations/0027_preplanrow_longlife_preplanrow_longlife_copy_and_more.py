# ★ 2026-09-16：LongLife 列（审核决议中心专用）
#
# 只做两件与本次需求直接相关的事：
#   1. longlife        —— LongLife 标记（Y / N / 空）
#   2. longlife_copy   —— 副本行（LongLife=Y 时下方复制出来的那一行）的独立字段值，JSON
#
# 说明：
# - 用「原行 + JSON 覆盖」而不是另建一行，是为了满足需求里的
#   「序号不变、总项数不变」——一份记录仍然只算一个条目，
#   KPI / 分页合计 / 导出条目数都不受影响。
# - 该字段仅审核决议中心读写；预排筛选 / 实时预警 / 存档中心 / 导出均忽略。
# - 本次 makemigrations 还顺带检测到长期遗留的模型漂移
#   （inserted_to_preplan.db_index、source.choices），**已从本迁移中剔除**：
#   那是历史遗留、此前有意未生成（运行期无影响），不属于本次需求，
#   避免一个迁移混入两件事、后续难以回滚归因。

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_preplanrow_archived_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="preplanrow",
            name="longlife",
            field=models.CharField(
                blank=True,
                default="",
                help_text="LongLife 标记，仅允许 Y / N / 空；为 Y 时决议页在下方复制一行",
                max_length=4,
                verbose_name="LongLife",
            ),
        ),
        migrations.AddField(
            model_name="preplanrow",
            name="longlife_copy",
            field=models.TextField(
                blank=True,
                default="",
                help_text="JSON：副本行相对原行被覆盖的字段值",
                verbose_name="LongLife复制行数据",
            ),
        ),
    ]
