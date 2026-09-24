# -*- coding: utf-8 -*-
"""手动跑一轮外部数据刷新（不等定时器）。

用途
----
① IT / 运维验证"服务器能不能连到机器人并取到数据"，不必等 2 小时；
② 万一进程内定时线程被禁用（`BYFAB_AUTO_REFRESH=0`）或服务不常驻，
   可以用 Windows 计划任务调这个命令来实现同样的定时效果：
       python manage.py refresh_bot_cache

用法
----
    python manage.py refresh_bot_cache            # 只刷到期的（龄期 ≥ 2 小时 或 从没取到过）
    python manage.py refresh_bot_cache --force    # 忽略龄期，强制全部刷一遍
"""
from django.core.management.base import BaseCommand

from core.services import bot_refresh


class Command(BaseCommand):
    help = '立即刷新一轮外部数据缓存（机器人 ABL / BY FAB 面板）；未到刷新周期则跳过'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='忽略刷新周期，强制刷新全部目标')

    def handle(self, *args, **options):
        self.stdout.write(f'定时周期 {bot_refresh.INTERVAL_SECONDS}s'
                          f'（{bot_refresh.INTERVAL_SECONDS / 3600:g} 小时），'
                          f'单次上游超时 {bot_refresh.FETCH_TIMEOUT}s')
        ok, fail, skip = bot_refresh.run_once(force=options['force'])
        self.stdout.write(self.style.SUCCESS(f'本轮结束：成功 {ok} / 失败 {fail} / 跳过 {skip}'))
        if fail and not ok:
            # 给计划任务一个非零退出码，便于告警
            raise SystemExit(1)
