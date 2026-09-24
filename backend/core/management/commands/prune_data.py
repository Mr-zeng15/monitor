# -*- coding: utf-8 -*-
"""按保留策略清理旧数据（技术文件 + 过期业务数据）。

用途
----
担心 `db.sqlite3` 与周边目录越积越多时，手动跑一次收口。
（服务启动时也会**自动静默**跑这两部分，见 `manage.py` 的 `_maybe_retention()`
 —— ★ 不是 `core/apps.py`，更不是现在跑不起来的 `run_server.py`）

★ 两类的默认策略（可用参数覆盖）
    · 技术文件：backups/ ≤10 份且 ≤30 天、data_snapshots/ ≤20 份且 ≤90 天、logs/ ≤90 天
    · 业务数据：preplan_row 中 plan_ym 早于「当前月-5」的行（即保留最近 6 个自然月）
                 ★ 2026-09-23 用户拍板「全清，只留未归类」：
                   预排筛选 与 审核决议中心 是同一张表（exported 只是标记），
                   故超期行**连同已导出到决议 / 已归档 / 有 LongLife 的一起删**。
                   想恢复旧的「保护决策痕迹」语义 → 加 `--protect-decided`。

用法
----
    python manage.py prune_data                  # 只预览（不删任何东西）
    python manage.py prune_data --files          # 预览，且包含技术文件
    python manage.py prune_data --apply          # 真正执行
    python manage.py prune_data --apply --files --vacuum
    python manage.py prune_data --months 12 --apply
    python manage.py prune_data --protect-decided --apply   # 保留已导出/已归档/有 LongLife 的行
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.services import db_backup
from core.services.retention import BIZ_KEEP_MONTHS, PROTECT_DECIDED, describe, prune_business_rows


def _db_path():
    return settings.DATABASES['default'].get('NAME')


def _human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return '%.1f %s' % (n, unit) if unit != 'B' else '%d B' % n
        n /= 1024.0


class Command(BaseCommand):
    help = '按保留策略清理旧数据：技术文件（备份/快照/日志）+ 过期业务数据（preplan_row）'

    def add_arguments(self, parser):
        parser.add_argument('--months', type=int, default=BIZ_KEEP_MONTHS,
                            help='业务数据保留月数（默认 %d）' % BIZ_KEEP_MONTHS)
        parser.add_argument('--apply', action='store_true',
                            help='真正执行删除；不带此参数只预览')
        parser.add_argument('--protect-decided', action='store_true',
                            default=None,
                            help='保留「已导出到决议/有 LongLife/已归档」的行'
                                 '（默认不保护：全清，只留未归类）')
        parser.add_argument('--files', action='store_true',
                            help='同时清理技术文件（backups / data_snapshots / logs）')
        parser.add_argument('--vacuum', action='store_true',
                            help='执行后对 db.sqlite3 做 VACUUM 回收空闲页（需 --apply）')

    def handle(self, *args, **options):
        dry = not options['apply']
        protect = options.get('protect_decided')
        self.stdout.write(self.style.MIGRATE_HEADING(
            '=== 保留策略清理 %s ===' % ('（预览，不落盘）' if dry else '（执行）')))

        # ── 1. 技术文件
        if options['files']:
            res = db_backup.prune_all(_db_path(), dry_run=dry)
            verb = '将删除' if dry else '已删除'
            for key, label in (('backups', '数据库备份'), ('snapshots', '导入快照'), ('logs', '日志')):
                doomed, kept = res[key]
                if doomed:
                    self.stdout.write('  [%s] %s %d 个，保留 %d 个' % (label, verb, len(doomed), kept))
                    for p in doomed:
                        self.stdout.write('      ' + p)
                else:
                    self.stdout.write('  [%s] 无需清理（保留 %d 个）' % (label, kept))
        else:
            self.stdout.write('  [技术文件] 已跳过（加 --files 一并清理）')

        # ── 2. 业务数据
        if protect:
            self.stdout.write(self.style.WARNING(
                '  ⚠ --protect-decided：已导出到决议 / 有 LongLife / 已归档 的行会被保留'))
        elif protect is None and PROTECT_DECIDED:
            self.stdout.write(self.style.WARNING(
                '  ⚠ 模块默认 PROTECT_DECIDED=True：决策痕迹行会被保留'))
        else:
            self.stdout.write(self.style.WARNING(
                '  ⚠ 全清模式：超期的「已导出到决议 / 已归档 / 有 LongLife」行也会被删除'))
        rep = prune_business_rows(months=options['months'], dry_run=dry,
                                  protect_decided=protect)
        for line in describe(rep).split('\n'):
            self.stdout.write('  ' + line)

        # ── 3. VACUUM
        if options['vacuum']:
            if dry:
                self.stdout.write(self.style.WARNING('  [VACUUM] 预览模式不执行（需同时加 --apply）'))
            else:
                try:
                    r = db_backup.vacuum_db(_db_path())
                except RuntimeError as e:
                    self.stdout.write(self.style.ERROR('  [VACUUM] ' + str(e)))
                else:
                    if r:
                        self.stdout.write(self.style.SUCCESS(
                            '  [VACUUM] %s → %s（释放 %s）'
                            % (_human(r[0]), _human(r[1]), _human(r[0] - r[1]))))
                    else:
                        self.stdout.write('  [VACUUM] 未找到数据库文件')

        if dry:
            self.stdout.write(self.style.WARNING('以上为预览结果，未做任何修改。确认后加 --apply 执行。'))
        else:
            self.stdout.write(self.style.SUCCESS('清理完成。'))
