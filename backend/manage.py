#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def _maybe_retention():
    """服务真正启动时跑一次「保留策略」收口（技术文件 + 过期业务数据）。

    ★ 为什么不放在 AppConfig.ready()：ready() 会被**任何** django.setup() 触发 ——
      `python -c "..."`、一次性运维/验证脚本、测试脚本都算；那些场景绝不该偷偷
      删磁盘、更不该删业务行。（2026-09-23 早期就挂在 ready()，结果跑个脚本真去清了文件。）
    ★ 为什么落在 manage.py：当前部署入口是 `start.bat` → `manage.py runserver`。
      `run_server.py` 是旧目录结构（core/settings）的残留、现在**根本跑不起来**，
      之前误把落点放在那里 → 等于「自动清理从未生效」。
    ★ 只认 runserver：manage.py 的其它子命令（migrate / shell / prune_data /
      collectstatic / 自定义命令…）都会在第 1 行就 return，绝不动数据。
    ★ 自动重载（不带 --noreload）下，只有**真正提供服务的进程**（RUN_MAIN=true）
      才执行，避免父/子进程各跑一遍。
    """
    if 'runserver' not in sys.argv:
        return
    if '--noreload' not in sys.argv and os.environ.get('RUN_MAIN') != 'true':
        return

    try:
        import django
        django.setup()          # 幂等；也为后面用 ORM 做准备
    except Exception:
        return

    # ── 1) 技术文件：backups ≤10 份且 ≤30 天、data_snapshots ≤20 份且 ≤90 天、logs ≤90 天
    try:
        from django.conf import settings
        from core.services.db_backup import prune_all
        _db = settings.DATABASES['default'].get('NAME')
        _res = prune_all(db_path=str(_db) if _db else None, dry_run=False)
        _n = sum(len(v[0]) for v in _res.values() if isinstance(v, tuple))
        if _n:
            print('[保留策略] 已清理 ' + str(_n) + ' 个过期文件（备份 / 快照 / 日志）')
    except Exception as e:
        print('[保留策略] 文件清理失败（不影响启动）: ' + str(e))

    # ── 2) 业务数据：preplan_row（= 预排筛选 + 审核决议中心**共用的同一张表**）
    #      默认保留最近 6 个自然月，超期全清、只留 plan_ym=0（未归类）。
    #      ★ 想恢复「决议/存档/longlife 永不被清」→ core/services/retention.PROTECT_DECIDED = True
    try:
        from core.services.retention import prune_business_rows
        _biz = prune_business_rows(dry_run=False)
        if _biz.get('deleted'):
            print('[保留策略] 已清理 ' + str(_biz['deleted']) + ' 行过期业务数据'
                  '（预排 / 决议，保留最近 ' + str(_biz['months']) + ' 个月）')
    except Exception as e:
        print('[保留策略] 业务数据清理失败（不影响启动）: ' + str(e))


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

    # ★ 保留策略收口：只在 `manage.py runserver` 时执行一次（见函数 docstring）
    _maybe_retention()

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
