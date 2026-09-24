# -*- coding: utf-8 -*-
"""服务器【自主定时】刷新外部数据缓存 —— 与"有没有人打开页面"无关。

背景（2026-09-16 用户明确）：
    「不是别人打开才去查，应该服务器自己定时，换成定时两小时更新数据吧」

此前刷新是【请求驱动】的：请求进来发现缓存过期才顺手起个后台线程 —— 没人访问就永不刷新。
本模块在 Django 进程内起一条守护线程，每 2 小时主动拉一次机器人数据写进 bot_data_cache。

设计要点
--------
① 只负责"定时触发"，真正的拉取仍复用 `byfab_views._refresh_abl`
   （在函数内【延迟 import】，避免 app 启动期循环依赖）。
② 多进程安全：借 `BotDataCache.last_attempt_at` 当锁，用**条件 UPDATE** 抢「租约」，
   抢不到就跳过 —— gunicorn 多 worker、runserver 自动重载的双进程都只会有一份在干活。
   顺带的好处：抢到租约即写了 last_attempt_at，请求驱动的后台刷新（60s 节流）不会重复起线程。
③ 每 TICK 秒醒一次，只读一行判断龄期（开销极小）；只有到点、或【从未取到过数据】才真拉。
④ 定时拉取用【长超时】（默认 660s）—— 这条线程是专用的，可以等；
   与请求驱动的后台刷新（120s）刻意区分：后者要让位于用户体验。
⑤ 单次失败只记 last_error 并等下一轮，线程不会死；成功即覆盖缓存（真值永久保存）。
"""
import os
import sys
import threading
import time
from datetime import date, timedelta

from django.utils import timezone as dj_timezone

# ── 可配参数（环境变量）──
INTERVAL_SECONDS = int(os.environ.get('BYFAB_AUTO_REFRESH_SECONDS', '7200'))   # 定时周期：2 小时
TICK_SECONDS = int(os.environ.get('BYFAB_AUTO_REFRESH_TICK', '60'))            # 唤醒检查间隔：1 分钟
LEASE_SECONDS = int(os.environ.get('BYFAB_AUTO_REFRESH_LEASE', '900'))         # 租约时长：15 分钟
FETCH_TIMEOUT = int(os.environ.get('BYFAB_AUTO_REFRESH_TIMEOUT', '660'))       # 单次拉取给上游的超时
# ★ 2026-09-24：payload 里还有按厂兜底种子（半故障）时的重试周期。
#   比 INTERVAL_SECONDS(2h) 短得多，让坏掉的那一厂尽快自愈（实际间隔受 _claim 租约限制）。
RETRY_SEED_SECONDS = int(os.environ.get('BYFAB_AUTO_REFRESH_RETRY_SECONDS', '300'))   # 5 分钟
ENABLED = os.environ.get('BYFAB_AUTO_REFRESH', '1').lower() not in ('0', 'false', 'no')

# 这些管理命令下不启动（会拖慢命令、污染输出，且没有必要）
# 注：实际用的是下面的【白名单】判断（只有 runserver / WSGI 服务才启动），
#     这个集合只是留着做显式文档，避免以后有人误以为"忘了排除"。
SKIP_COMMANDS = {
    'migrate', 'makemigrations', 'check', 'shell', 'dbshell', 'test', 'collectstatic',
    'createsuperuser', 'changepassword', 'dumpdata', 'loaddata', 'flush',
    'showmigrations', 'sqlmigrate', 'refresh_bot_cache', 'help',
}

_lock = threading.Lock()
_started = False
_thread = None
_last_pass = {'at': '', 'ok': 0, 'fail': 0, 'skip': 0}


def should_start():
    """是否该启动定时线程 → (bool, 原因, 是否值得打印)。

    ★ 用【白名单】：只有"真正在对外提供服务"的进程才启动 ——
      · `manage.py runserver`（且不是自动重载的父进程）
      · WSGI/ASGI 服务器（waitress / gunicorn / uvicorn 等，入口不是 manage.py）
      其余管理命令（migrate / check / shell / test / collectstatic …）一律不启动，
      而且**静默跳过**，免得在部署脚本的输出里刷出一行让人困惑的日志。
    """
    if not ENABLED:
        return False, '环境变量 BYFAB_AUTO_REFRESH=0（已禁用）', True
    argv = sys.argv
    entry = os.path.basename(argv[0] or '').replace('.exe', '').lower()
    cmd = argv[1] if len(argv) > 1 else ''
    if entry in ('manage.py', 'manage', 'django-admin', 'django-admin.py'):
        if cmd != 'runserver':
            return False, f'管理命令 `{cmd or "(空)"}` 不启动', False
        # runserver 开着自动重载时会有父子两个进程 —— 只在真正跑应用的那个（RUN_MAIN=true）里启动。
        # 用 --noreload 起时没有 RUN_MAIN，但那时本来就只有一份进程，正常启动。
        if '--noreload' not in argv and os.environ.get('RUN_MAIN') != 'true':
            return False, 'runserver 自动重载的父进程不启动（避免双份）', True
    return True, '', False


def targets():
    """要定时刷新的目标：[(中文名, 缓存键, 执行函数)]。

    ★ 仅保留 ABL 触发（折线图 JSON，机器人可正常返回 echarts）。
       「BY FAB 总览面板」契约（FD/fabList/PT/CAPA/OC）的定时拉取已移除：
       当前 Dify 工作流对所有查询只返回 ABL/OOS 类 echarts 折线图，不返回面板数据契约
       （详见 frontend/src/api/byfab.js 顶部 2026-09-04 记录、《BYFAB接入机器人数据指南.md》），
       定时拉取必然解析失败，只会每 2 小时在服务器日志刷 [AutoRefresh] 失败。
       前端主面板通道 USE_BOT_API 已为 false（改用内置静态示例），摘掉该目标对界面零影响。
       待 Dify 工作流能按指南输出面板契约、且前端 USE_BOT_API 改回 true 后，
       再于此处加回面板定时目标（届时需同步恢复 byfab_views 的 _refresh_panel / byfab_data）。
    """
    from ..views.byfab_views import CACHE_KEY_ABL, _refresh_abl, CACHE_KEY_DPPM, _refresh_dppm
    return [
        ('ABL 触发', CACHE_KEY_ABL, lambda: _refresh_abl(None, FETCH_TIMEOUT)),
        ('DPPM 云端(2A/2B)', CACHE_KEY_DPPM, lambda: _refresh_dppm(FETCH_TIMEOUT)),
    ]


def _due(row):
    """这家缓存是否到期该拉：从没取到过（fetched_at 为空）或龄期 ≥ 周期。

    ★ 2026-09-24：区分「完全成功」与「半故障」。
      DPPM 是 2A/2B 两次独立查询，一厂失败只回退该厂种子，但整份仍会被写成
      fetched_at=now / last_error=''（看似成功）→ 旧逻辑 `_due` 要等满 2 小时才重试，
      期间前端一直显示种子值（用户报的「2B 一直是 4100/3600/4800/5200」）。
      现在只要 payload 里还有 seed_fabs（还有厂没取到真值），就按 RETRY_SEED_SECONDS
      这个更短的周期重试，取到真值即自愈；完全成功的数据仍按 INTERVAL_SECONDS 走。
      （真正的执行间隔还会被 _claim 的租约 LEASE_SECONDS 兜住，不会形成重试风暴。）
    """
    if row is None:
        return False
    if not row.fetched_at:
        return True
    from ..views.byfab_views import _payload_has_seed
    due_seconds = RETRY_SEED_SECONDS if _payload_has_seed(row) else INTERVAL_SECONDS
    return (dj_timezone.now() - row.fetched_at).total_seconds() >= due_seconds


def _claim(key):
    """抢租约：把 last_attempt_at 置为当前时刻；抢到返回 True。

    用条件 UPDATE 实现（数据库层面原子），所以多进程也只有一个能抢到；
    没抢到说明别的进程刚接手，直接跳过本轮即可。
    """
    from ..models import BotDataCache
    now = dj_timezone.now()
    gate = now - timedelta(seconds=LEASE_SECONDS)
    try:
        return BotDataCache.objects.filter(key=key).exclude(
            last_attempt_at__gt=gate).update(last_attempt_at=now) > 0
    except Exception as e:
        print(f'[AutoRefresh] 抢租约失败 key={key}: {e}')
        return False


def run_once(force=False):
    """跑一轮检查；到期的就拉。返回 (成功数, 失败数, 跳过数)。"""
    from ..views.byfab_views import _cache_get, _cache_save_error
    ok = fail = skip = 0
    for label, key, fn in targets():
        row = _cache_get(key)
        if not force and not _due(row):
            skip += 1
            continue
        if not _claim(key):
            print(f'[AutoRefresh] {label}：另一进程正在处理（租约未过期），本轮跳过')
            skip += 1
            continue
        print(f'[AutoRefresh] 开始定时刷新：{label}（key={key}）')
        try:
            fn()
            ok += 1
            print(f'[AutoRefresh] 完成：{label}')
        except Exception as e:
            fail += 1
            print(f'[AutoRefresh] 失败：{label}：{e}')
            _cache_save_error(key, e)
    _last_pass.update(at=dj_timezone.localtime(dj_timezone.now()).strftime('%Y-%m-%d %H:%M:%S'),
                      ok=ok, fail=fail, skip=skip)
    return ok, fail, skip


def _loop():
    # 启动后先等一小会儿（让服务把首屏/DB 都就绪），随后立刻跑一轮 ——
    # 这样"服务器开机"就会有数据，正是用户要的「开机查一下真值」。
    time.sleep(min(10, max(1, TICK_SECONDS)))
    while True:
        try:
            run_once()
        except Exception as e:
            print(f'[AutoRefresh] 本轮异常（线程继续存活）：{e}')
        time.sleep(TICK_SECONDS)


def start_scheduler():
    """启动定时线程（幂等）。返回是否由本次调用启动。"""
    global _started, _thread
    with _lock:
        if _started:
            return False
        # ★ 2026-09-22 按用户要求：这里**不再打印**启动 / 未启动提示。
        #   原因：runserver 的 reloader 父子进程会各跑一次 ready()，原本每次启动
        #   都刷两行，看着像「服务启动出了问题」。是否在跑可查
        #   /api/byfab/dppm/?diag=1 的 autorefresh 字段。
        #   ★ 判定逻辑（should_start）与「父进程不启动、避免双份」的去重机制完全不变，
        #     只是把 print 摘掉。
        ok, _reason, _noisy = should_start()
        if not ok:
            _started = False
            return False
        _started = True
        _thread = threading.Thread(target=_loop, name='byfab-auto-refresh', daemon=True)
        _thread.start()
        return True


def status():
    """给 ?diag=1 用的状态快照。"""
    return {
        'enabled': ENABLED,
        'started': _started,
        'interval_seconds': INTERVAL_SECONDS,
        'tick_seconds': TICK_SECONDS,
        'fetch_timeout_sec': FETCH_TIMEOUT,
        'last_pass': dict(_last_pass),
    }
