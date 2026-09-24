# -*- coding: utf-8 -*-
"""
数据备份 / 恢复 命令行工具
==========================
用法：
  python backup_db.py                       # 备份当前数据库（保留最近 10 份 / 30 天）
  python backup_db.py list                  # 列出所有备份
  python backup_db.py restore <路径>        # 从备份恢复（★ 需先停止服务）
  python backup_db.py prune                 # ★ 一键清理三类技术文件（份数 + 天数双约束）
  python backup_db.py prune --dry-run       # 只预览，不删除
  python backup_db.py prune --vacuum        # 清理后 VACUUM 回收空闲页
  python backup_db.py prune-snapshots       # 只清单个类别：快照（保留 20 份 / 90 天）
  python backup_db.py vacuum                # 仅 VACUUM

  ★ 业务数据（preplan_row）不在此脚本 → python manage.py prune_data
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.services.db_backup import (
    backup_db, list_backups, restore_backup, prune_snapshots, prune_all,
    vacuum_db, SNAPSHOT_KEEP, KEEP, KEEP_DAYS,
    SNAPSHOT_KEEP_DAYS, LOG_KEEP_DAYS,
)


def _human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return '%.1f %s' % (n, unit) if unit != 'B' else '%d B' % n
        n /= 1024.0


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else 'backup'
    if cmd == 'backup':
        p = backup_db()
        print('[持久化] 备份完成: ' + str(p) if p else '[持久化] 未找到 db.sqlite3，跳过')
    elif cmd == 'list':
        items = list_backups()
        if not items:
            print('[持久化] 暂无备份')
        else:
            print('[持久化] 共 ' + str(len(items)) + ' 份备份（时间倒序）：')
            for i in items:
                print('  ' + i['mtime'] + '  ' + format(i['size'], ',') + ' B  ' + i['path'])
    elif cmd == 'restore':
        if len(args) < 2:
            print('用法: python backup_db.py restore <备份文件路径>')
            return 1
        try:
            db = restore_backup(args[1])
            print('[持久化] 已从备份恢复到: ' + str(db))
        except ValueError as e:
            print('[持久化] 恢复失败: ' + str(e))
            return 1
    elif cmd == 'prune':
        dry = '--dry-run' in args
        res = prune_all(dry_run=dry)
        verb = '将删除' if dry else '已删除'
        print('[保留策略] backups ≤%d 份/%d 天 | 快照 ≤%d 份/%d 天 | 日志 ≤%d 天'
              % (KEEP, KEEP_DAYS, SNAPSHOT_KEEP, SNAPSHOT_KEEP_DAYS, LOG_KEEP_DAYS))
        total = 0
        for key, label in (('backups', '备份'), ('snapshots', '快照'), ('logs', '日志')):
            doomed, kept = res[key]
            total += len(doomed)
            print('  [%s] %s %d 个，保留 %d 个' % (label, verb, len(doomed), kept))
            for p in doomed:
                print('      ' + p)
        if total == 0:
            print('  （没有需要清理的文件）')
        if '--vacuum' in args:
            if dry:
                print('  [VACUUM] 预览模式不执行（需去掉 --dry-run）')
            else:
                try:
                    r = vacuum_db()
                    if r:
                        print('  [VACUUM] %s → %s（释放 %s）'
                              % (_human(r[0]), _human(r[1]), _human(r[0] - r[1])))
                except RuntimeError as e:
                    print('  [VACUUM] ' + str(e))
    elif cmd == 'vacuum':
        try:
            r = vacuum_db()
        except RuntimeError as e:
            print('[持久化] ' + str(e))
            return 1
        if r:
            print('[持久化] VACUUM 完成: %s → %s（释放 %s）'
                  % (_human(r[0]), _human(r[1]), _human(r[0] - r[1])))
        else:
            print('[持久化] 未找到 db.sqlite3')
    elif cmd == 'prune-snapshots':
        dry = '--dry-run' in args
        doomed, kept = prune_snapshots(dry_run=dry)
        verb = '将删除' if dry else '已删除'
        if not doomed:
            print('[持久化] 快照数未超过上限（保留 %d 份 / %d 天），无需清理'
                  % (SNAPSHOT_KEEP, SNAPSHOT_KEEP_DAYS))
        else:
            print('[持久化] ' + verb + ' ' + str(len(doomed)) + ' 份旧快照，保留 ' + str(kept) + ' 份：')
            for p in doomed:
                print('  ' + p)
    else:
        print('未知命令。支持: backup / list / restore <路径> / prune [--dry-run] [--vacuum] '
              '/ prune-snapshots [--dry-run] / vacuum')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
