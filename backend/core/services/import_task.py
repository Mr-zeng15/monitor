# -*- coding: utf-8 -*-
"""
导入任务取消 / 代际令牌（内存版，适用于开发与单机部署）
======================================================
解决的问题：导入 Excel 期间用户「清空 / 删除 / 取消」时，旧实现里导入任务仍会把
数据写回，导致清空后数据又冒出来、或删除后任务继续写入。

机制（双保险）：
1. 任务级取消（cancel 标志）
   - 每个导入任务注册一个 task_id，并关联范围 key=(plan_year, source)。
   - 用户在页面点「取消导入」→ POST /api/preplan/import-cancel/ {task_id}
     → request_cancel(task_id)，导入流程在关键节点检查 is_cancelled() 即中止。
2. 代际令牌（generation）—— 清空/删除的一致性守卫
   - 清空/删除数据时调用 invalidate(year, source)：
       a) 取消该范围内所有正在运行的导入任务（提前中止）；
       b) 该范围代际 +1。
   - 导入在「写入前」与「写入事务内」校验代际是否与开始导入时一致，
     不一致说明期间发生过清空/删除 → 抛 ImportCancelled，
     由 transaction.atomic 回滚本次全部写入，保证最终状态一致。
"""
import threading
import time
import uuid

_lock = threading.Lock()
_tasks = {}        # task_id -> {'key': (year, source)|None, 'cancel_requested': bool, 'created_at': float}
_generations = {}  # (year, source) -> int


class ImportCancelled(Exception):
    """导入被取消 / 数据被清空导致代际过期时抛出"""


def register_task(key=None, task_id=None):
    """注册一个导入任务，返回 task_id。key=(plan_year, source) 用于范围取消。
    task_id：前端可预生成传入（便于取消按钮定位），否则自动生成。"""
    with _lock:
        tid = task_id or ('imp_%d_%s' % (int(time.time() * 1000), uuid.uuid4().hex[:6]))
        _tasks[tid] = {'key': key, 'cancel_requested': False, 'created_at': time.time()}
        _gc()
        return tid


def finish(task_id):
    """导入正常结束时清理任务记录"""
    with _lock:
        _tasks.pop(task_id, None)


def is_cancelled(task_id):
    with _lock:
        t = _tasks.get(task_id)
        return bool(t and t['cancel_requested'])


def request_cancel(task_id=None, key=None):
    """取消指定任务；不指定任务时取消所有 key 相同的运行中任务"""
    with _lock:
        if task_id is not None and task_id in _tasks:
            _tasks[task_id]['cancel_requested'] = True
            return
        if key is not None:
            for t in _tasks.values():
                if not t['cancel_requested'] and t['key'] == key:
                    t['cancel_requested'] = True


def invalidate(year, source=None):
    """
    清空 / 删除数据前调用：
    - 取消该范围所有运行中的导入任务
    - 该范围代际 +1（含 (year, source) 与 (year, None) 两个维度，
      保证「清空全部」也能打断指定来源的导入）
    """
    with _lock:
        for key in ((year, source), (year, None)):
            _generations[key] = _generations.get(key, 0) + 1
        for t in _tasks.values():
            if t['cancel_requested'] or t['key'] is None:
                continue
            t_year, t_source = t['key']
            if t_year == year and (source is None or t_source is None or t_source == source):
                t['cancel_requested'] = True


def generation(year, source=None):
    with _lock:
        return _generations.get((year, source), 0)


def _gc(max_age=3600):
    now = time.time()
    for tid in [t for t, v in _tasks.items() if now - v['created_at'] > max_age]:
        _tasks.pop(tid, None)
