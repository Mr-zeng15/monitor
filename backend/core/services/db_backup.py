# -*- coding: utf-8 -*-
"""
数据持久化工具：SQLite 备份 / 列表 / 恢复 / 导入快照
=====================================================
正式测试期数据保护方案：
  1. 数据本体：backend/db.sqlite3（SQLite 文件，关机/重启天然保留）
  2. 自动备份：启动时（start.bat → backup_db.py / manage.py runserver）与
                导入/清空/删除前（preplan_views）各备份一次
  3. 导入快照：每次导入写 JSON 到 data_snapshots/，可回溯
  4. 手动恢复：python backup_db.py restore <备份文件>
  5. 保留策略（★ 2026-09-23 升级：从「只看份数」→「份数 + 天数」双约束）：
       backups/           ≤ KEEP 份 且 ≤ KEEP_DAYS 天      （单份 = 整库大小，最占空间）
       data_snapshots/    ≤ SNAPSHOT_KEEP 份 且 ≤ SNAPSHOT_KEEP_DAYS 天
       logs/*.log         ≤ LOG_KEEP_DAYS 天（写入侧按天分文件，详见 prune_logs）
     一键清理：python backup_db.py prune [--dry-run] [--vacuum]
     ★ 业务数据（preplan_row 等）**不在本模块** → 见 core/services/retention.py

本模块不依赖 Django（纯文件操作），便于 CLI 与启动脚本直接调用。
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

KEEP = 10  # 备份保留份数
# ★ 2026-09-21 新增：导入快照保留份数。
#   背景：save_import_snapshot 每次导入都写一份 import_*.json，而线上没有清理机制，
#   实测 21 天累积 53 份 / 11.7 MB —— 属于「会持续增长且无上限」的一类磁盘占用。
#   这里对齐 backups 的做法，只保留最近 SNAPSHOT_KEEP 份。
SNAPSHOT_KEEP = 20

# ── ★ 2026-09-23：保留策略从「只看份数」升级为「份数 + 天数双约束」────────────
#   为什么必须加天数：份数上限**不保证时间跨度** ——
#     · 导入密集时（一天 10 次）10 份可能只覆盖几个小时，前几天的备份全被挤掉；
#     · 长期不导入时（放假一个月）30 天前的旧备份又一直躺着不删。
#   这正是用户说的「过段时间就把旧数据删掉」要解决的缺口。
#   判定规则：**份数超限 或 存放超期，满足任一即删**（两个约束取严的那个）。
KEEP_DAYS = 30            # 数据库备份保留天数（单份 = 整库大小，是最占空间的）
SNAPSHOT_KEEP_DAYS = 90   # 导入快照保留天数（JSON，~70KB/份）
LOG_KEEP_DAYS = 90        # logs/*.log 审计与异常日志保留天数


def _age_days(p, now=None):
    """文件已经存放了多少天（按 mtime）。取不到时返回 0（宁可不删）。"""
    now = now or datetime.now()
    try:
        m = datetime.fromtimestamp(Path(p).stat().st_mtime)
    except OSError:
        return 0.0
    return (now - m).total_seconds() / 86400.0


def _select_doomed(files, keep, days):
    """份数 + 天数双约束选待删文件。

    files : 文件路径列表
    keep  : 保留份数
              · None → **不按份数限制**（只按天数）
              · <=0  → 全删（保留旧的 `keep<=0 表示全删` 语义）
              · >0   → 保留最新 keep 份
    days  : 保留天数（<=0 表示不按天数限制）
    返回 (待删列表, 保留份数)

    ★ 必须区分 None 与 0：日志（prune_logs）只按天数清理、**不设份数上限**
      （审计日志的份数没有意义，按天留才合理）；而 0 在旧语义里是「全删」。
      早期版本把两者混为一谈 → prune_logs 传 0 会把当天日志也删光。
    """
    files = sorted(files)
    n = len(files)
    if keep is None:
        over_keep = set()
    elif keep <= 0:
        over_keep = set(files)
    else:
        over_keep = set(files[:max(0, n - keep)])
    over_age = set(f for f in files if days > 0 and _age_days(f) > days)
    doomed = [f for f in files if f in over_keep or f in over_age]
    return doomed, n - len(doomed)


def _default_db_path():
    """默认数据库路径：当前工作目录下的 db.sqlite3（start.bat / CLI 场景 cwd=backend）"""
    return Path(os.getcwd()) / 'db.sqlite3'


def _safe_copy_sqlite(src, dst):
    """★ 2026-09-22 WAL 安全复制：用 SQLite 在线备份 API 取一致性快照。

    为什么不能直接 shutil.copy2 主库文件：开启 WAL 后（settings.OPTIONS.init_command），
    最近提交的事务可能还留在 <db>-wal 里尚未 checkpoint 回主库——只拷主库会**丢数据**，
    而备份恰恰是「防丢数据」的最后一道防线，绝不能自己成为丢失源。
    `sqlite3.Connection.backup()` 是 SQLite 官方在线备份 API：它按页拷贝并自动处理
    锁与 WAL，得到的是一个**一致**的完整快照，且不阻塞读取。
    先写 .tmp 再 os.replace，避免拷贝中途失败留下半截文件冒充有效备份。
    """
    src = Path(src)
    dst = Path(dst)
    tmp = Path(str(dst) + '.tmp')
    if tmp.exists():
        try:
            tmp.unlink()
        except OSError:
            pass
    src_conn = sqlite3.connect(str(src))
    try:
        dst_conn = sqlite3.connect(str(tmp))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    os.replace(str(tmp), str(dst))


def backup_db(db_path=None, keep=KEEP, days=KEEP_DAYS):
    """备份 SQLite 到 <db 同目录>/backups/db_YYYYMMDD_HHMMSS.sqlite3，保留最近 keep 份 / days 天。
    返回备份文件路径；失败返回 None（不抛异常，避免阻断启动）。"""
    try:
        db = Path(db_path) if db_path else _default_db_path()
        if not db.exists():
            return None
        bdir = db.parent / 'backups'
        bdir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        dst = bdir / ('db_' + ts + '.sqlite3')
        _safe_copy_sqlite(db, dst)
        prune_backups(db, keep=keep, days=days)
        return str(dst)
    except Exception as e:
        print('[持久化] SQLite 备份失败: ' + str(e))
        return None


def prune_backups(db_path=None, keep=KEEP, days=KEEP_DAYS, dry_run=False):
    """★ 2026-09-23 新增：备份保留策略（份数 + 天数双约束）。

    备份单份 = 整库大小，是**唯一会随库增长而线性放大**的占用
    （库 10 MB × 10 份 = 100 MB），所以要同时按份数和天数收口。
    返回 (待删/已删路径列表, 保留份数)。
    """
    db = Path(db_path) if db_path else _default_db_path()
    bdir = db.parent / 'backups'
    if not bdir.exists():
        return [], 0
    doomed, kept = _select_doomed(list(bdir.glob('db_*.sqlite3')), keep, days)
    if not dry_run:
        for old in doomed:
            try:
                old.unlink()
            except OSError:
                pass
    return [str(p) for p in doomed], kept


def list_backups(db_path=None):
    """列出所有备份文件（按时间倒序）"""
    db = Path(db_path) if db_path else _default_db_path()
    bdir = db.parent / 'backups'
    if not bdir.exists():
        return []
    out = []
    for p in sorted(bdir.glob('db_*.sqlite3'), reverse=True):
        st = p.stat()
        out.append({
            'path': str(p),
            'size': st.st_size,
            'mtime': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        })
    return out


def restore_backup(src, db_path=None):
    """从备份恢复：把 src 复制覆盖到 db.sqlite3（★ 调用方需先停止服务）。
    返回 db 路径；校验失败抛 ValueError。"""
    src = Path(src)
    if not src.exists():
        raise ValueError('备份文件不存在: ' + str(src))
    if src.suffix.lower() != '.sqlite3' or not src.name.startswith('db_'):
        raise ValueError('不是有效的备份文件（需为 backups/db_*.sqlite3）')
    db = Path(db_path) if db_path else _default_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    # ★ 2026-09-22：恢复前先清掉旧库的 WAL 边车文件。
    #   开 WAL 后 <db>-wal 里是「旧库」尚未 checkpoint 的页；若不清掉就覆盖主库，
    #   恢复出来的库会与残留的 -wal/-shm 不匹配 → 轻则数据回退到旧状态，重则库损坏。
    for suffix in ('-wal', '-shm'):
        side = Path(str(db) + suffix)
        if side.exists():
            try:
                side.unlink()
            except OSError:
                pass
    _safe_copy_sqlite(src, db)
    return str(db)


def prune_snapshots(db_path=None, keep=SNAPSHOT_KEEP, days=SNAPSHOT_KEEP_DAYS, dry_run=False):
    """★ 2026-09-21 新增：导入快照保留策略（防止线上无限增长）。
    ★ 2026-09-23：加 days 参数（份数 + 天数双约束）。

    只处理 data_snapshots/ 下的 import_*.json —— 同目录的 mtd_last_state.json
    是 MTD 同步状态文件，**不匹配该 glob，因此不会被误删**。

    文件名格式 import_YYYYmmdd_HHMMSS_<source>_<year>.json，字典序即时序，
    所以直接按文件名排序取「最近 keep 份」即可，无需解析时间。

    dry_run=True 时只返回将删除的列表，不真正落盘（供清理前预览）。
    返回 (将被删除/已删除的路径列表, 保留份数)。
    """
    db = Path(db_path) if db_path else _default_db_path()
    sdir = db.parent / 'data_snapshots'
    if not sdir.exists():
        return [], 0
    snaps = sorted(sdir.glob('import_*.json'))
    doomed, kept = _select_doomed(snaps, keep, days)
    if not dry_run:
        for old in doomed:
            try:
                old.unlink()
            except OSError:
                pass
    return [str(p) for p in doomed], kept


def prune_logs(db_path=None, days=LOG_KEEP_DAYS, dry_run=False):
    """★ 2026-09-23 新增：logs/*.log 保留策略（按天数）。

    为什么日志也要纳入：destructive.log / byfab_errors.log 都是 **append-only**，
    此前**没有任何清理机制** —— 属于「会持续增长且无上限」的一类。
    ★ 并且单文件 append-only 有个隐形问题：**mtime 永远是最新的**，
    所以「按 mtime 清理」对单一长文件永远不触发。因此写入侧已改为**按天分文件**
    （logs/destructive_YYYYMMDD.log），一天一个文件、写完就不再动，mtime 才会沉淀下来。
    历史遗留的旧单文件（如 logs/destructive.log）同样匹配 *.log，
    由本条按 mtime 自然淘汰，无需特殊处理。

    返回 (待删/已删路径列表, 保留份数)。
    """
    db = Path(db_path) if db_path else _default_db_path()
    ldir = db.parent / 'logs'
    if not ldir.exists():
        return [], 0
    logs = sorted(p for p in ldir.glob('*.log') if p.is_file())
    doomed, kept = _select_doomed(logs, None, days)  # keep=None → 只按天数，不设份数上限
    if not dry_run:
        for old in doomed:
            try:
                old.unlink()
            except OSError:
                pass
    return [str(p) for p in doomed], kept


def prune_all(db_path=None, dry_run=False):
    """★ 2026-09-23 新增：一次性执行全部**技术性文件**的保留策略。

    覆盖 backups / data_snapshots / logs 三类，全部按「份数 + 天数」双约束。
    **不含业务数据**（preplan_row 等），那部分在 Django 侧
    `core/services/retention.py`，必须显式调用才生效。

    返回汇总 dict，便于 CLI / 启动日志打印。
    """
    return {
        'backups': prune_backups(db_path, dry_run=dry_run),
        'snapshots': prune_snapshots(db_path, dry_run=dry_run),
        'logs': prune_logs(db_path, dry_run=dry_run),
        'dry_run': dry_run,
    }


def vacuum_db(db_path=None):
    """★ 2026-09-23 新增：VACUUM 回收空闲页。

    为什么需要：SQLite 删除数据后**文件不会自动缩小**，删掉的页只是进了空闲列表
    （实测本库 1.51 MB 里有 0.49 MB / 32% 是空闲页）。VACUUM 会重建库文件把空隙填掉。

    ★ 注意事项：
      · VACUUM 需要**独占锁**且**不能在事务中**执行 → 用 isolation_level=None（autocommit）；
      · **强烈建议先停止服务再执行** —— 服务在跑时：
          - 写事务会让 VACUUM 拿不到锁（抛 OperationalError）；
          - 未 checkpoint 的改动还留在 <db>-wal 里（实测见过 1 MB），
            此时对主库 VACUUM 的效果会被 WAL 掩盖，看不出回收量。
        所以本函数**不做显式的 wal_checkpoint(TRUNCATE)** —— 那个模式要等所有读者退出，
        在服务运行时可能长时间阻塞；交给 VACUUM 自身处理更安全。
      · 只在 CLI 手动调用，不要放进启动流程（耗时 + 锁库）。
    返回 (收缩前字节, 收缩后字节)；库不存在返回 None；被占用抛 RuntimeError。
    """
    db = Path(db_path) if db_path else _default_db_path()
    if not db.exists():
        return None
    before = db.stat().st_size
    con = sqlite3.connect(str(db), isolation_level=None)
    try:
        con.execute('VACUUM')
    except sqlite3.OperationalError as e:
        raise RuntimeError(
            'VACUUM 失败：数据库被占用（服务正在运行？）。请先停止服务再重试。原始错误：%s' % e
        ) from None
    finally:
        con.close()
    return before, db.stat().st_size


def save_import_snapshot(year, source, rows, batch_id, db_path=None, keep=SNAPSHOT_KEEP):
    """导入成功后写 JSON 快照到 <db 同目录>/data_snapshots/，可回溯恢复。

    ★ 2026-09-21：写完立即执行保留策略（只留最近 keep 份），
    否则线上每次导入留一个 JSON，磁盘会一直涨。
    """
    try:
        db = Path(db_path) if db_path else _default_db_path()
        sdir = db.parent / 'data_snapshots'
        sdir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fn = sdir / ('import_' + ts + '_' + (source or 'ALL') + '_' + str(year or 'NA') + '.json')
        with open(fn, 'w', encoding='utf-8') as f:
            json.dump({
                'year': year, 'source': source, 'batch_id': batch_id,
                'time': ts, 'rows': rows,
            }, f, ensure_ascii=False, default=str)
        prune_snapshots(db_path=db, keep=keep)
    except Exception as e:
        print('[持久化] 导入快照写入失败: ' + str(e))
