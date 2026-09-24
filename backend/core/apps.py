from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = '产量监控核心'

    def ready(self):
        # ★ 2026-09-16：启动「服务器自主定时刷新」守护线程 —— 每 2 小时主动拉一次外部数据。
        #   放在 ready() 里 → 服务一启动就开始定时，与"有没有人打开页面"无关
        #   （此前是请求驱动：没人访问就永不刷新）。
        #   守卫见 bot_refresh.should_start()：管理命令、runserver 自动重载的父进程都不启动；
        #   多进程/多 worker 由 DB 租约（BotDataCache.last_attempt_at）保证只有一份在干活。
        #   需要关掉时：设环境变量 BYFAB_AUTO_REFRESH=0。
        from .services import bot_refresh
        bot_refresh.start_scheduler()

        # ★ 保留策略（backups / data_snapshots / logs 清理 + 过期业务数据清理）
        #   **刻意不放在这里**：ready() 会被**任何** django.setup() 触发 ——
        #   包括 `python -c "..."`、一次性运维脚本、验证脚本 ——
        #   那些场景绝不该改动磁盘、更不该删业务行。
        #   （早期曾挂在此处，结果脚本一跑就真去清理了文件。）
        #   ✅ 正确的落点：「服务真正启动」的入口 → manage.py 里 runserver 专用的
        #      _maybe_retention()（start.bat 走的就是 manage.py runserver）。
        #   ☠ 反面教材：曾把落点改到 run_server.py —— 那是旧目录结构的残留，
        #      设的是不存在的 core.settings，根本跑不起来 → 自动清理**静默失效**。
