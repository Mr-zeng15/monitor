# -*- coding: utf-8 -*-
"""
业务数据保留策略（★ 会真正删除 preplan_row 业务记录）
======================================================
为什么单独一个模块：`db_backup.py` 只覆盖 backups / 快照 / logs 这些**技术性文件**，
而真正随日常使用不断累积的是 **preplan_row**（每月约 2 千行）。
用户诉求：「sqlite 数据会不会存太多爆满？希望过段时间就把以前的旧数据删除掉」，
2026-09-23 进一步明确：「预排筛选和审核决议中心都是按月存的，过了 6 个月删一些，不然卡顿」。

★ 关键前提：预排筛选 与 审核决议中心 **是同一张表**
  `preplan_row` —— `exported=True` 只表示「这一行已导出到决议中心、决议页正在展示」，
  并不是另存一份。所以「清理预排」和「清理决议」本质是同一个动作，
  无法只清一边。想保留决议页历史，只能靠「不删」。

★ 安全设计（删业务数据不可逆，所以条件从严、默认只预览）
  1. **默认 dry_run=True** —— 不带 --apply 绝不落盘，先把「将删什么」打出来核对；
  2. **只删超期月份**：plan_ym < 当前月 - (months-1)，默认 months=6
     （即保留含当月在内的最近 6 个自然月）；
     plan_ym=0（未归类）**永不删** —— 导入时没确认月份，可能还要用；
  3. **超期即清（用户拍板「全清，只留未归类」）**：
     超期行**连同已导出到决议 / 已归档 / 有 LongLife 的一起删**，不做额外保护。
     ★ 旧的「保护 exported / archived / longlife」语义被保留为**可选开关**：
       模块常量 `PROTECT_DECIDED=True`，或命令 `--protect-decided`，
       即可恢复「决议页 / 存档中心的内容永不被清」。回滚只改这一处。
  4. 每次真正执行都往 logs/destructive_YYYYMMDD.log 留一行审计（与 preplan/clear 同一份日志）。

用法：
  from core.services.retention import prune_business_rows
  prune_business_rows(months=6, dry_run=True)     # 预览
  prune_business_rows(months=6, dry_run=False)    # 执行（全清）
  prune_business_rows(months=6, dry_run=False, protect_decided=True)  # 保留决策痕迹
或命令行：python manage.py prune_data --months 6 [--apply] [--protect-decided]
"""
import os
from datetime import datetime

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from core.models import PreplanRow

# 业务数据保留月数（早于「当前月 - (N-1) 个月」的行视为旧数据）
# ★ 2026-09-23 用户拍板：预排筛选 + 审核决议中心统一保留 **6 个月**。
BIZ_KEEP_MONTHS = 6

# ★ 是否额外保护「人工决策痕迹」的行（exported / longlife / archived）。
#   2026-09-23 用户选择「全清，只留未归类」→ 默认 False；
#   若要回到旧语义（决议页 / 存档中心的内容永不被自动清理），改成 True
#   或临时加 CLI 旗标 `--protect-decided` 即可，无需改代码结构。
PROTECT_DECIDED = False


def _cutoff_ym(months, now=None):
    """算出保留期下界，返回 (cutoff_int, 'YYYY-MM')。

    months=6 且当前 2026-09 → 保留 202604..202609，超期 = plan_ym < 202604。
    （月份用 12 进制算，避免 12 月跨年时裸月份比较出错 —— 与 plan_ym 的设计一致）
    """
    now = now or timezone.localtime(timezone.now())
    total = now.year * 12 + (now.month - 1) - (max(0, int(months)) - 1)
    y, m = divmod(total, 12)
    return y * 100 + (m + 1), '%04d-%02d' % (y, m + 1)


def _protected_q():
    """人工决策痕迹 → 一律保留（仅在 protect_decided=True 时生效）。"""
    return Q(exported=True) | Q(longlife__gt='') | Q(archived=True)


def _audit(line):
    """审计留痕（best-effort，失败不影响主流程）。写入与 preplan 同一份日志。"""
    try:
        from django.conf import settings
        db = settings.DATABASES['default'].get('NAME')
        d = os.path.join(os.path.dirname(os.path.abspath(str(db))), 'logs')
        os.makedirs(d, exist_ok=True)
        ts = timezone.localtime(timezone.now())
        fn = 'destructive_' + ts.strftime('%Y%m%d') + '.log'
        with open(os.path.join(d, fn), 'a', encoding='utf-8') as f:
            f.write('%s\tretention/prune_business\t%s\n' % (ts.strftime('%Y-%m-%d %H:%M:%S'), line))
    except Exception:
        pass


def preview_business_rows(months=None, protect_decided=None):
    """只统计不删除，返回 (queryset, 报告 dict)。

    protect_decided=None → 取模块默认 PROTECT_DECIDED（False = 全清）。
    """
    months = BIZ_KEEP_MONTHS if months is None else months
    if protect_decided is None:
        protect_decided = PROTECT_DECIDED
    cutoff, label = _cutoff_ym(months)
    qs = PreplanRow.objects.filter(plan_ym__gt=0, plan_ym__lt=cutoff)
    matched = qs.count()
    if protect_decided:
        doomed = qs.exclude(_protected_q())
        protected = matched - doomed.count()
    else:
        doomed, protected = qs, 0
    by_ym = {r['plan_ym']: r['c'] for r in
             doomed.values('plan_ym').annotate(c=Count('id')).order_by('plan_ym')}
    report = {
        'months': months,
        'cutoff_ym': cutoff,        # int，如 202604（便于比较）
        'cutoff_label': label,      # str，如 '2026-04'（便于阅读）
        'matched': matched,          # 超期月份命中总行数
        'protected': protected,      # 因决策痕迹被保护（仅 protect_decided=True 时可能 >0）
        'deleted': sum(by_ym.values()),  # 将删除行数
        'protect_decided': bool(protect_decided),
        'by_ym': by_ym,
    }
    return doomed, report


def prune_business_rows(months=None, dry_run=True, protect_decided=None):
    """按 plan_ym 清理过期业务数据。返回报告 dict（含 dry_run 标记）。

    dry_run=True（默认）：只统计，不落盘。
    protect_decided=None → 取模块默认 PROTECT_DECIDED（False = 全清）。
    """
    if protect_decided is None:
        protect_decided = PROTECT_DECIDED
    doomed, report = preview_business_rows(months=months, protect_decided=protect_decided)
    report['dry_run'] = bool(dry_run)
    if dry_run or report['deleted'] == 0:
        return report

    # ★ 多语句「查→写」包原子事务；失败回滚，避免删一半留下不一致状态。
    with transaction.atomic():
        deleted, _detail = doomed.delete()
    report['deleted'] = deleted
    _audit('cutoff<%(cutoff_label)s matched=%(matched)s protected=%(protected)s '
           'deleted=%(deleted)s by_ym=%(by_ym)s protect_decided=%(protect_decided)s' % report)
    return report


def describe(report):
    """把报告渲染成多行文本（CLI / 启动日志打印用）。"""
    verb = '将删除' if report.get('dry_run') else '已删除'
    head = '[保留策略] 业务数据：保留最近 %s 个月（%s 及之后），超期命中 %s 行' % (
        report['months'], report.get('cutoff_label') or report['cutoff_ym'], report['matched'])
    lines = [head]
    if report.get('protect_decided'):
        if report['protected']:
            lines.append('  · 其中因「已导出/有 LongLife/已归档」受保护 %s 行（不删）' % report['protected'])
    else:
        lines.append('  · 全清模式：已导出到决议 / 已归档 / 有 LongLife 的旧行一并清理'
                     '（仅 plan_ym=0 未归类保留）')
    by_ym = report.get('by_ym') or {}
    if not by_ym:
        lines.append('  · 没有需要清理的过期行')
    else:
        lines.append('  · %s %s 行，按月份分布：' % (verb, report['deleted']))
        for ym in sorted(by_ym):
            s = str(ym)
            lines.append('      %s-%s  %s 行' % (s[:4], s[4:], by_ym[ym]))
    return '\n'.join(lines)


__all__ = [
    'BIZ_KEEP_MONTHS', 'PROTECT_DECIDED',
    'prune_business_rows', 'preview_business_rows', 'describe',
]
