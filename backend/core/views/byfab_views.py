"""BY FAB 总览 · 公司机器人（Dify）数据代理

前端 ByFabView 通过 GET /api/byfab/data/?month=YYYY-MM 拉取面板数据，
ABL 触发图表通过 GET /api/byfab/abl/ 拉取 OOS 报警数等图表 JSON。

本视图在服务端调用公司 Dify 机器人的 chat-messages 接口：
  ★ 默认使用 **streaming（流式 / SSE）** 模式（对齐官方 Python 示例），
    流式异常时自动降级为 blocking，保证可用性。
  ★ API Key 只留在服务端，避免暴露在前端，也规避浏览器跨域（CORS）。

机器人工作流需把「面板数据契约」JSON 作为 answer 返回，详见项目根
《BYFAB接入机器人数据指南.md》。
"""
import json
import os
import re
import socket
import threading
import time
from datetime import date, timedelta
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.db import connection as db_connection
from django.utils import timezone as dj_timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..models import BotDataCache

# —— 机器人配置（优先读环境变量，再读 settings；真实值放 local_secrets.py，不进仓）——
BYFAB_BOT_API_KEY = (
    os.environ.get('BYFAB_BOT_API_KEY')
    or getattr(settings, 'BYFAB_BOT_API_KEY', '')
)
BYFAB_BOT_BASE_URL = (
    os.environ.get('BYFAB_BOT_BASE_URL')
    or getattr(settings, 'BYFAB_BOT_BASE_URL', '')
)
BYFAB_BOT_USER_ID = (
    os.environ.get('BYFAB_BOT_USER_ID')
    or getattr(settings, 'BYFAB_BOT_USER_ID', 'user-001')
)

BOT_ENDPOINT = f"{BYFAB_BOT_BASE_URL.rstrip('/')}/chat-messages"

# 流式读取超时（秒）；Dify 工作流可能较慢，与官方示例一致给足时间
BOT_STREAM_TIMEOUT = int(os.environ.get('BYFAB_BOT_TIMEOUT', '680'))

# —— ABL 触发 云端查询问题文本（支持 env / settings / 常量 三级覆盖）——
ABL_CLOUD_QUERY = (
    os.environ.get('ABL_CLOUD_QUERY')
    or getattr(settings, 'ABL_CLOUD_QUERY',
               '请提供各厂（2A/2B/2C/2D）的 ABL 触发 / OOS 报警数，按周别（含 WoW 环比）统计，'
               '用 echarts 代码块返回折线图数据。')
)


# ════════════════════════════════════════════════════════════
# —— DPPM 云端查询配置（2A / 2B 是两个【独立机器人应用】→ 各自独立 API Key）——
#
#  ★ 2026-09-23 修正：旧实现只有一个 `DPPM_BOT_API_KEY`、两个厂共用，而该默认值恰是 2A 的
#    Key → `_refresh_dppm` 里 2B 实际是拿 2A 的机器人提问，数据来源错位（用户的 2A/2B 串味）。
#    现在按厂拆成两个 Key，并保留同名环境变量覆盖能力。
#  ⚠️ 不再做「单 Key 兼容回退」：那种写法会让"漏配"退化成"静默用错机器人"，比直接报错更糟。
#    缺 Key 时 `_refresh_dppm` 会显式抛错 → 该厂回退缓存/种子 + last_error 写明原因。
DPPM_BOT_API_KEY_2A = (
    os.environ.get('DPPM_BOT_API_KEY_2A')
    or getattr(settings, 'DPPM_BOT_API_KEY_2A', '')
)
DPPM_BOT_API_KEY_2B = (
    os.environ.get('DPPM_BOT_API_KEY_2B')
    or getattr(settings, 'DPPM_BOT_API_KEY_2B', '')
)
DPPM_BOT_BASE_URL = (
    os.environ.get('DPPM_BOT_BASE_URL')
    or getattr(settings, 'DPPM_BOT_BASE_URL', BYFAB_BOT_BASE_URL)
)
DPPM_BOT_USER_ID = (
    os.environ.get('DPPM_BOT_USER_ID')
    or getattr(settings, 'DPPM_BOT_USER_ID', BYFAB_BOT_USER_ID)
)
# 按厂聚合：一处定义「哪个厂用哪个 Key / 问什么问题」，循环里直接取，避免再次漏传。
DPPM_BOT_API_KEYS = {'2A': DPPM_BOT_API_KEY_2A, '2B': DPPM_BOT_API_KEY_2B}
DPPM_CLOUD_QUERY_2A = (
    os.environ.get('DPPM_CLOUD_QUERY_2A')
    or getattr(settings, 'DPPM_CLOUD_QUERY_2A',
               '请提供 2A 车间的 DPPM（百万不良率），按周别（W 周次，如 W2639 表示最新周）统计最近各周，'
               '用 echarts 代码块返回折线图数据，xAxis 为周别、series 为该周 DPPM 数值。')
)
DPPM_CLOUD_QUERY_2B = (
    os.environ.get('DPPM_CLOUD_QUERY_2B')
    or getattr(settings, 'DPPM_CLOUD_QUERY_2B',
               '请提供 2B 车间的抽检量，按周别（W 周次，如 W2639 表示最新周）统计最近各周，'
               '用 echarts 代码块返回折线图数据，xAxis 为周别、series 为该周抽检量数值。')
)
DPPM_CLOUD_QUERIES = {'2A': DPPM_CLOUD_QUERY_2A, '2B': DPPM_CLOUD_QUERY_2B}


def _mask_key(key):
    """Key 指纹：仅回「是否已配置 + 末 4 位」，供 `?diag=1` 排查"两个厂是否用错 Key"。
    完整 Key 绝不下发（前端与任何接口都拿不到原文）。"""
    key = (key or '').strip()
    if not key:
        return {'configured': False, 'tail': ''}
    # 过短的 Key 一律不露尾（避免把本身就短的值整串带出去）
    return {'configured': True, 'tail': key[-4:] if len(key) >= 8 else '****'}

#  ★ 2026-09-16：服务端持久缓存 + 兜底种子 + 后台静默刷新
#
#  背景（部署到服务器后暴露）：
#    原实现每收到一次 /api/byfab/abl/ 就现场打一次机器人 workflow（可阻塞到 680 秒），
#    而前端失败后每 1.5 秒重试一次 → 服务器线程被占满 → 浏览器侧 ERR_CONNECTION_RESET、
#    随后大量 500；又因两条通道都拿不到数据，DATA_ONLINE=false → 整页压暗（"ABL 面板灰色"）。
#    且缓存只存浏览器 localStorage，换浏览器/服务器重启即失效。
#
#  现在：
#    ① 每次成功取到真值 → 落库持久化（服务器重启也在）；
#    ② 从未取到过真值 → 用一份内置「兜底种子」保证页面有数据可显示，绝不空/灰；
#    ③ 接口【立即】返回缓存，绝不阻塞在机器人上；后台线程静默刷新，取到真值自动覆盖；
#    ④ ?force=1 才同步刷新（短超时），供前端「↻ 重新查询」按钮；
#    ⑤ ?diag=1 返回上游可达性探测，供 IT 定位"服务器连不上机器人"的网络问题。
# ════════════════════════════════════════════════════════════
CACHE_KEY_ABL = 'abl'

# 数据新鲜期：超过则视为过期（同时是前端判断"要不要再问"的依据，经 _meta.stale 下发）
# ★ 2026-09-16：改为 2 小时，与「服务器自主定时刷新」的周期对齐 ——
#   刷新已由 bot_refresh 的守护线程每 2 小时主动负责，请求只是兜底的自愈路径。
ABL_TTL_SECONDS = int(os.environ.get('BYFAB_ABL_TTL', '7200'))       # 2 小时

# 两次后台刷新之间的最小间隔（秒）——防止每个请求都触发一次刷新
BG_REFRESH_MIN_INTERVAL = int(os.environ.get('BYFAB_BG_MIN_INTERVAL', '60'))

# 同步刷新（?force=1）给上游的超时（秒）。远小于 BOT_STREAM_TIMEOUT，
# 避免"点一下重新查询要等 11 分钟"。
SYNC_REFRESH_TIMEOUT = int(os.environ.get('BYFAB_SYNC_TIMEOUT', '30'))

# 后台刷新给上游的超时（秒）
BG_REFRESH_TIMEOUT = int(os.environ.get('BYFAB_BG_TIMEOUT', '120'))

# 探测上游可达性的 TCP 超时（秒）
PROBE_TIMEOUT = float(os.environ.get('BYFAB_PROBE_TIMEOUT', '3'))


def _recent_week_labels(n=4):
    """最近 n 个 ISO 周别标签，形如 WK202633（与云端返回格式保持一致）。"""
    labels = []
    today = date.today()
    for i in range(n - 1, -1, -1):
        y, w, _ = (today - timedelta(weeks=i)).isocalendar()
        labels.append(f'WK{y}{w:02d}')
    return labels


# ★ 2026-09-16（用户要求）：兜底数据不要全 0，改用一组"看起来像真实 OOS 报警数"的样例值，
#   保证没连上机器人时面板的出图效果（折线起伏 / y 轴刻度 / WoW 列）与真实数据一致，
#   便于上线前确认版式。这只是**占位样例**、不是真实数据；未取到真值时控制台会打印 warn 提醒
#   （界面按要求不加任何标注）。每厂 4 个值 = 最近 4 个 ISO 周。
ABL_SEED_SERIES = {
    '2A': [8, 5, 13, 6],
    '2B': [3, 7, 4, 9],
    '2C': [11, 6, 8, 12],
    '2D': [2, 4, 6, 3],
}


def _abl_seed_payload():
    """ABL 兜底种子：合法可渲染的 echarts 结构（周别取最近 4 个 ISO 周）。

    ★ 2026-09-16 起不再全 0，改用样例数值；WoW 列按「最新周 − 上周」本地算好，
      与云端返回格式保持一致（前端 extractAblFields 会把末列 WoW 拆出来、不画进折线图）。
    """
    labels = _recent_week_labels(4)
    series = []
    for fab in ('2A', '2B', '2C', '2D'):
        vals = list(ABL_SEED_SERIES.get(fab, []))[:len(labels)]
        vals += [0] * (len(labels) - len(vals))   # 长度对齐：样例周数与 labels 变化时不越界/不缺列
        wow = vals[-1] - vals[-2] if len(vals) >= 2 else 0
        series.append({'name': fab, 'data': vals + [wow]})
    return {
        'title': {'text': 'OOS报警数'},
        'unit': '次数',
        'xAxis': {'data': labels + ['WoW']},
        'series': series,
    }


def _cache_get(key, seed_factory=None):
    """取缓存行；不存在时按需创建（带兜底种子）。DB 异常一律降级为 None，不影响接口可用性。"""
    try:
        obj = BotDataCache.objects.filter(key=key).first()
        if obj is None:
            seed = (seed_factory() if seed_factory else None)
            obj = BotDataCache.objects.create(
                key=key,
                payload=json.dumps(seed, ensure_ascii=False) if seed else '',
                is_seed=bool(seed),
            )
        return obj
    except Exception as e:
        print(f'[BotCache] 读取缓存失败 key={key}: {e}')
        return None


def _cache_payload(obj):
    if obj is None or not obj.payload:
        return None
    try:
        return json.loads(obj.payload)
    except Exception:
        return None


def _log_byfab_error(tag, exc):
    """★ 2026-09-22：BY FAB 云端通道的服务端异常留痕（<db 同目录>/logs/byfab_errors_YYYYMMDD.log）。

    为什么需要：`dppm_cloud_data` / `abl_cloud_data` 的契约是「绝不阻塞、永不失败、永远有兜底」，
    但线上仍然出现过**请求直接 500** —— 浏览器侧只能看到 `Request failed with status code 500`
    这一句，没有任何成因信息；前端 catch 后沿用静态示例，表现就是「面板不点亮」，
    而服务端把 traceback 打在了 runserver 控制台上，翻页就找不到了。
    这里把异常类型 + 完整 traceback 落盘，下次再出现可以直接读文件定位，不必再从浏览器猜。
    （best-effort：留痕失败绝不影响主流程。）

    ★ 2026-09-23：文件名由固定 `byfab_errors.log` 改为**按天分文件**（同 destructive.log）。
    原因：单文件 append-only 的 mtime 永远最新 → 「按 mtime 保留 N 天」的清理永不触发。
    """
    try:
        import traceback as _tb
        from django.conf import settings
        _db = settings.DATABASES['default'].get('NAME')
        _dir = os.path.join(os.path.dirname(os.path.abspath(str(_db))), 'logs')
        os.makedirs(_dir, exist_ok=True)
        _ts = dj_timezone.localtime(dj_timezone.now()).strftime('%Y-%m-%d %H:%M:%S')
        _fn = 'byfab_errors_' + _ts[:10].replace('-', '') + '.log'
        with open(os.path.join(_dir, _fn), 'a', encoding='utf-8') as f:
            f.write('[%s] [%s] %s: %s\n' % (_ts, tag, type(exc).__name__, exc))
            f.write(''.join(_tb.format_exception(type(exc), exc, exc.__traceback__)))
            f.write('-' * 60 + '\n')
    except Exception as e:
        print('[ByFab] 错误留痕失败: %s' % e)


def _dt_local_str(dt):
    """把 datetime 安全转成本地时间字符串（USE_TZ=True 下必须 localtime，否则早 8 小时）。

    ★ 2026-09-22：原实现直接 `dj_timezone.localtime(dt)` —— 一旦库里存在 **naive** 时间戳
    （旧版本代码写入 / 外部工具改库 / 手工改行都可能留下无时区值），它会抛
    `ValueError: localtime() cannot be applied to a naive datetime`。
    而这个调用位于**请求路径**上（`_cache_meta` / `_diag`）→ 整个接口 500。
    实测复现：ABL 的 500 正是死在这里。现在退化为「原值格式化」（至少不崩），并打一行告警。
    """
    if not dt:
        return ''
    try:
        return dj_timezone.localtime(dt).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        try:
            print('[BotCache] 时间戳无时区信息（已按原值展示，建议核查该缓存行）: %r' % (dt,))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return ''


def _payload_has_seed(obj):
    """缓存 payload 里是否还残留**按厂兜底种子**（`seed_fabs` 非空）。

    ★ 2026-09-24（用户报「2B 一直是假数据 4100/3600/4800/5200」的服务端根因）：

      DPPM 是 2A / 2B 两次【互相独立】的查询，单厂失败只回退**该厂**的种子。
      于是「2A 真值 + 2B 种子」会走完 `_cache_save_success(force_seed=all_seed)`
      —— 因为不是全员种子，`is_seed` 被清成 False、`fetched_at` 也被刷成"刚刚"：
        · `_cache_is_stale()` → False  ⇒ 请求路径不再触发后台刷新；
        · `bot_refresh._due()`  → False ⇒ 定时线程也要等满 2 小时才重试。
      结果：坏掉的那一厂要卡满一个 TTL 才会被重问，期间前端一直显示种子值，
      而且整份缓存对外声称"新鲜、成功"，`last_error` 还被清空了（运维无从发现）。

      所以「新鲜度」必须把"还有厂没取到真值"算进来：只要 `seed_fabs` 非空就不算新鲜。
      这样请求会继续驱动后台刷新（受 BG_REFRESH_MIN_INTERVAL 节流），
      该厂一旦取到真值立刻自愈，无需人工干预、也不用等 2 小时。

    ABL 的 payload 是图表结构（无 seed_fabs 字段）→ 恒 False，行为完全不变。
    """
    if obj is None or not obj.payload:
        return False
    try:
        p = json.loads(obj.payload)
    except Exception:
        return False
    return bool(isinstance(p, dict) and p.get('seed_fabs'))


def _cache_seed_fabs(obj):
    """该缓存 payload 里仍在使用兜底种子的厂别列表（诊断用；无则返回 []）。"""
    if obj is None or not obj.payload:
        return []
    try:
        p = json.loads(obj.payload)
    except Exception:
        return []
    if not isinstance(p, dict):
        return []
    return list(p.get('seed_fabs') or [])


def _cache_is_stale(obj, ttl):
    if obj is None or obj.is_seed or not obj.fetched_at:
        return True
    if _payload_has_seed(obj):
        return True          # ★ 还有厂是兜底种子 → 视为不新鲜，尽快重试（见 _payload_has_seed）
    try:
        return (dj_timezone.now() - obj.fetched_at).total_seconds() > ttl
    except Exception as e:
        # 时间戳无时区/类型异常 → 当作「已过期」（顺带触发一次刷新），绝不把异常抛到请求路径
        print('[BotCache] 判断缓存新鲜度失败（按过期处理）: %s' % e)
        return True


def _cache_meta(obj):
    """下发缓存元信息，供前端显示数据时间/兜底提示。"""
    if obj is None:
        return {'cached': False, 'is_seed': True, 'fetched_at': '', 'stale': True,
                'refreshing': False, 'last_error': '', 'last_attempt_at': ''}
    return {
        'cached': True,
        'is_seed': bool(obj.is_seed),
        # USE_TZ=True → 必须 localtime（经 _dt_local_str 做 naive 时间戳防御）
        'fetched_at': _dt_local_str(obj.fetched_at),
        'last_attempt_at': _dt_local_str(obj.last_attempt_at),
        'stale': _cache_is_stale(obj, ABL_TTL_SECONDS),
        'refreshing': obj.key in _bg_running(),
        'last_error': obj.last_error or '',
    }


def _cloud_fallback(key, seed_factory, exc):
    """★ 2026-09-22：云端接口的「最终兜底响应」——任何异常都回这个，保证接口永不失败。

    取值顺序：**上一次缓存的真值 → 内置兜底种子**。
    返回 `{success, data, ...meta}`；用种子时把 `is_seed` 强制置 True，
    避免把兜底数据对外声称成真值（前端据此决定「拒绝降级」是否生效）。
    """
    cache, data, used_seed = None, None, False
    try:
        cache = _cache_get(key)
        data = _cache_payload(cache)
    except Exception:
        data = None
    if data is None:
        used_seed = True
        try:
            data = seed_factory()
        except Exception:
            data = None
    try:
        meta = _cache_meta(cache)
    except Exception:
        meta = {'cached': False, 'is_seed': True, 'fetched_at': '', 'stale': True,
                'refreshing': False, 'last_error': '', 'last_attempt_at': ''}
    meta['last_error'] = str(exc)[:300]
    if used_seed:
        meta['is_seed'] = True
    if data is None:
        return {'success': False, 'error': '暂无数据且兜底种子不可用', 'data': None}
    return {'success': True, 'data': data, **meta}


def _cache_save_success(key, payload_obj, force_seed=False):
    try:
        obj = BotDataCache.objects.filter(key=key).first()
        if obj is None:
            BotDataCache.objects.create(key=key, payload=json.dumps(payload_obj, ensure_ascii=False), is_seed=force_seed)
            return
        now = dj_timezone.now()
        obj.payload = json.dumps(payload_obj, ensure_ascii=False)
        obj.is_seed = force_seed
        obj.fetched_at = now
        obj.last_attempt_at = now
        obj.last_error = ''
        obj.fail_count = 0
        obj.save(update_fields=['payload', 'is_seed', 'fetched_at', 'last_attempt_at',
                                'last_error', 'fail_count', 'updated_at'])
    except Exception as e:
        print(f'[BotCache] 写入缓存失败 key={key}: {e}')


def _cache_save_error(key, err):
    try:
        obj = BotDataCache.objects.filter(key=key).first()
        if obj is None:
            return
        obj.last_attempt_at = dj_timezone.now()
        obj.last_error = str(err)[:300]
        obj.fail_count = (obj.fail_count or 0) + 1
        obj.save(update_fields=['last_attempt_at', 'last_error', 'fail_count', 'updated_at'])
    except Exception as e:
        print(f'[BotCache] 记录失败信息失败 key={key}: {e}')


# —— 后台刷新：同一 key 同时只跑一个线程；并限制最小间隔 ——
_bg_lock = threading.Lock()
_bg_keys = set()


def _bg_running():
    with _bg_lock:
        return set(_bg_keys)


def _bg_allowed(obj):
    """距上次尝试是否已超过最小间隔（防止连不上机器人时疯狂起线程）。"""
    if obj is None or not obj.last_attempt_at:
        return True
    try:
        return (dj_timezone.now() - obj.last_attempt_at).total_seconds() >= BG_REFRESH_MIN_INTERVAL
    except Exception as e:
        # ★ 2026-09-22：naive 时间戳会让时间减法抛 TypeError。这里刻意 **fail-open**（放行刷新）——
        #   宁可多起一次后台刷新，也不能让异常跑到请求路径上把接口打成 500。
        print('[BotCache] 判断后台刷新间隔失败（放行本次刷新）: %s' % e)
        return True


def _start_bg_refresh(key, task):
    """在守护线程里跑一次刷新任务；已有同 key 任务在跑则跳过。

    ★ 2026-09-22 加固（本次「DPPM 500 / ABL 正常」的根因所在）：
      原实现只有一行：
        if key in _bg_keys or not _bg_allowed(BotDataCache.objects.filter(key=key).first()):
      这行把两个风险点**串在了 `or` 里并且完全没有保护**：① 一次 DB 查询；② `_bg_allowed` 的时间减法。
      而它就在**请求路径**上（dppm_cloud_data / abl_cloud_data 过期分支）→ 任一出错 = 接口 500。
      更隐蔽的是 `or` 的**短路**：若该 key 恰好已在 `_bg_keys`（例如 bot_refresh 守护线程正占着
      'abl'），右边的 DB 查询与时间减法**根本不会求值** → 该通道侥幸 200。
      ⇒ 于是同一份代码、同一个故障，表现成「ABL 点亮、DPPM 报错」这种与数据无关的不对称。
      现在本函数**任何异常都不上抛**：查不到租约状态就当作"可以刷新"（fail-open），
      宁可多刷一次后台线程，也绝不让面板黑掉。
    """
    try:
        with _bg_lock:
            if key in _bg_keys:
                return False
            try:
                allowed = _bg_allowed(BotDataCache.objects.filter(key=key).first())
            except Exception as e:
                print('[BotCache] 读取刷新租约失败（放行本次刷新） key=%s: %s' % (key, e))
                allowed = True
            if not allowed:
                return False
            _bg_keys.add(key)
    except Exception as e:
        print('[BotCache] 启动后台刷新失败 key=%s: %s' % (key, e))
        return False

    def _run():
        try:
            task()
        except Exception as e:
            print(f'[BotCache] 后台刷新失败 key={key}: {e}')
            _cache_save_error(key, e)
        finally:
            with _bg_lock:
                _bg_keys.discard(key)
            # ★ 线程里用的是独立 DB 连接，必须显式关闭，否则长跑会泄漏连接
            try:
                db_connection.close()
            except Exception:
                pass

    threading.Thread(target=_run, name=f'botcache-{key}', daemon=True).start()
    return True


def _probe_bot(timeout=None):
    """对机器人地址做一次 TCP 连通性探测（不触发 workflow）——给 IT 定位网络问题用。"""
    u = urlparse(BYFAB_BOT_BASE_URL)
    host = u.hostname or ''
    port = u.port or (443 if u.scheme == 'https' else 80)
    target = f'{host}:{port}'
    t0 = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout or PROBE_TIMEOUT):
            return {'ok': True, 'target': target, 'elapsed_ms': int((time.time() - t0) * 1000), 'error': ''}
    except Exception as e:
        return {'ok': False, 'target': target, 'elapsed_ms': int((time.time() - t0) * 1000),
                'error': f'{type(e).__name__}: {e}'}


# ════════════════════════════════════════════════════════════
#  Dify chat-messages · streaming（SSE）
# ════════════════════════════════════════════════════════════
def _bot_inputs(month=None, week=None):
    """组装工作流必填变量 inputs（month / week）。

    优先级：调用参数 > settings.BYFAB_BOT_INPUTS > 默认值（当前月 / W1）。
    """
    base = dict(getattr(settings, 'BYFAB_BOT_INPUTS', None) or {})
    if month is not None:
        base['month'] = month
    if week is not None:
        base['week'] = week
    if base.get('month') in (None, ''):
        base['month'] = date.today().month
    if base.get('week') in (None, ''):
        base['week'] = 'W1'
    return base


def _headers(api_key=None):
    return {
        'Authorization': f'Bearer {api_key or BYFAB_BOT_API_KEY}',
        'Content-Type': 'application/json',
    }


def _chat_streaming(query, inputs=None, timeout=None, api_key=None):
    """Dify chat-messages **streaming** 模式，逐行解析 SSE，返回完整 answer。

    ★ timeout：由调用方按场景给（后台刷新 120s / 同步查询 30s / 默认 680s）

    SSE 每行形如：  data: {"event": "message", "answer": "..."}
      - event == 'message'     → 累加 answer 片段
      - event == 'message_end' → 结束
      - event == 'error'       → 抛错
      - data == '[DONE]'       → 结束
    """
    payload = {
        'inputs': inputs or {},
        'query': query,
        'response_mode': 'streaming',
        'user': BYFAB_BOT_USER_ID,
        'conversation_id': '',
    }
    full_answer = ''
    with requests.post(
        BOT_ENDPOINT,
        headers=_headers(api_key),
        json=payload,
        stream=True,
        timeout=timeout or BOT_STREAM_TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode('utf-8') if isinstance(line, bytes) else str(line)
            if not line_str.startswith('data: '):
                continue
            data_str = line_str[6:]
            if data_str.strip() == '[DONE]':
                break
            try:
                data = json.loads(data_str)
            except (json.JSONDecodeError, ValueError):
                continue
            event = data.get('event', '') or ''
            # ★ 兼容 Dify 不同版本的流事件：
            #   chat 应用 → 'message' 事件携带 answer 增量；
            #   workflow(chatflow) 应用 → LLM 节点流式输出经 'text_chunk'（data.text）下发，
            #   部分版本结束事件为 'workflow_finished' / 'message_replace' / 'message_end'。
            if event == 'message':
                full_answer += data.get('answer', '') or ''
            elif event in ('text_chunk', 'agent_message'):
                chunk = data.get('data', {})
                text = chunk.get('text') if isinstance(chunk, dict) else None
                if text is None:
                    text = data.get('text')
                if text is None:
                    text = data.get('answer')
                full_answer += text or ''
            elif event == 'error':
                raise RuntimeError(data.get('message', '机器人返回 error 事件'))
            elif event in ('message_end', 'workflow_finished'):
                break
    if not full_answer:
        print('[Dify] streaming 未累积到任何 answer 文本，请检查机器人是否配置为可返回 answer/文本输出')
    return full_answer


def _chat_blocking(query, inputs=None, timeout=None, api_key=None):
    """降级通道：blocking 模式（流式不可用时兜底）。"""
    payload = {
        'inputs': inputs or {},
        'query': query,
        'response_mode': 'blocking',
        'user': BYFAB_BOT_USER_ID,
        'conversation_id': '',
    }
    resp = requests.post(
        BOT_ENDPOINT, headers=_headers(api_key), json=payload, timeout=timeout or 120
    )
    resp.raise_for_status()
    return (resp.json() or {}).get('answer', '') or ''


def _chat(query, inputs=None, timeout=None, api_key=None):
    """统一入口：优先 streaming，失败自动降级 blocking。"""
    try:
        return _chat_streaming(query, inputs, timeout=timeout, api_key=api_key)
    except requests.exceptions.Timeout:
        raise
    except requests.exceptions.ConnectionError:
        raise
    except Exception as e:  # 流式异常（含 error 事件）→ 降级
        print(f'[Dify] streaming 失败，降级 blocking：{e}')
        return _chat_blocking(query, inputs, timeout=timeout, api_key=api_key)


# ════════════════════════════════════════════════════════════
#  JSON 提取
# ════════════════════════════════════════════════════════════
def _extract_json(text):
    """从机器人 answer 文本中尽力解析出 JSON 对象。"""
    if not text:
        return None
    text = text.strip()
    if text.startswith('\ufeff'):
        text = text[1:]
    # 去掉 ```json ... ``` / ```echarts ... ``` 代码围栏
    fence = re.search(r'```(?:json|echarts)?\s*([\s\S]*?)```', text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    # 直接就是 JSON
    try:
        return json.loads(text)
    except Exception:
        pass
    # 截取第一个 { 到最后一个 }
    s = text.find('{')
    e = text.rfind('}')
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s:e + 1])
        except Exception:
            pass
    # ★ 2026-09-21：answer 可能是裸 JSON 数组（LLM 直接把数据表回吐）
    s = text.find('[')
    e = text.rfind(']')
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s:e + 1])
        except Exception:
            pass
    return None


# ════════════════════════════════════════════════════════════
#  图表 JSON「形状容错」归一化（2026-09-21）
#
#  规则与前端 frontend/src/utils/chartShape.js 逐条对齐（同契约、同取舍）。
#
#  为什么需要：机器人（Dify 工作流）后面挂了一层 LLM，同一个问题多次提问，回覆 JSON 的形状会漂移。
#  已观察到的形态：
#    ① 标准 echarts option：{title:{text}, xAxis:{data:[...]}, series:[{name,data:[...]}]}
#    ② 原始行表（LLM 把数据表原样回吐，附 message）：{data:[{fab,week,count_value},…], message:'…'}
#    ③ 包装层：{option:{…}} / {data:{…}} / {result:{chart:{…}}} / 裸数组 [ {…} ]
#    ④ 宽表：{rows:[{week:'WK..','2A':8,'2B':3}]} —— 厂别挂在列名上
#    ⑤ series 写成 map：{series:{'2A':[8,5],'2B':[3,7]}}
#    ⑥ xAxis 写成逗号串、series 里混着字符串数字
#  图表真正必需的只有「x 轴标签 + 每厂一条数值」，其余（title/unit/message/多余列）都是附加值。
#  归一化后契约：{title, unit, xAxis:[str], series:[{name, data:[num|None]}], wow:{label,byFab}|None, shape}
# ════════════════════════════════════════════════════════════
_FAB_KEYS = ('fab', 'fabno', 'fabname', 'factory', 'factoryname', 'workshop', 'shop', 'area', 'areaname',
             'dept', 'line', '车间', '厂别', '厂', '车间别', '厂区', '产线')
_WEEK_KEYS = ('week', 'weeklabel', 'weekname', 'weekno', 'wk', 'wkno', 'wkid', 'yearweek', 'weekid',
              'xaxis', 'x', 'label', 'labels', 'category', 'categories', 'period', 'date', 'month',
              '周别', '周次', '周', '日期', '月份', '时间', '周期')
_VALUE_KEYS = ('countvalue', 'cntvalue', 'count', 'cnt', 'value', 'numbers', 'number', 'num',
               'qty', 'quantity', 'total', 'amount', 'sum', 'result',
               '报警数', '不良数', '数量', '数值', '值', '次数', '件数')
_CONTAINER_KEYS = ('option', 'options', 'echarts', 'chart', 'chartoption', 'config',
                   'data', 'dataset', 'result', 'results', 'output', 'outputs', 'payload', 'body',
                   'answer', 'json', 'content', 'rows', 'records', 'list', 'items', 'table', 'values')
_WOW_RE = re.compile(r'^(wow|w/w|环比|较上周|变化|变化幅度|差值|增减)$', re.IGNORECASE)


def _norm_key(k):
    return re.sub(r'[\s_\-./\\()\[\]{}（）【】:：,，]', '', str(k if k is not None else '').lower())


def _to_num(v):
    """宽松取数：数字 / '1,234' / '12%' / '8.0' → float；'—' / '-' / 'N/A' / '' → None。"""
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if v is None:
        return None
    s = re.sub(r'[次件个]$', '', re.sub(r'%$', '', str(v).strip().replace(',', ''))).strip()
    if not s or s in ('-', '--', '—') or re.match(r'^(n/?a|null|nan|none)$', s, re.IGNORECASE):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _num_like(v):
    return isinstance(v, (int, float)) or _to_num(v) is not None


def _week_sort_key(label):
    """周别标签的排序键：`'W2639'` / `'WK202639'` / `'2026-W39'` → 按其中的数字段排。

    用途见 `_week_map_items` —— JSON 对象的键序**不可依赖**，必须自己按周排回来，
    否则「取最近 4 周」会取成最旧 4 周。
    """
    digits = re.sub(r'[^0-9]', '', str(label if label is not None else ''))
    try:
        return (0, int(digits)) if digits else (1, 0)
    except Exception:
        return (1, 0)


def _week_map_items(node):
    """把一个 dict 认成「周别 → 数值」的对象映射，返回按周排好序的 (labels, values)。

    ★ 2026-09-24（用户：「拿到的回复解析不一定格式一样，但一定会有需要的那些数据，
      所以不要写死」）：上游偶尔不吐 echarts，而是直接给 `{"W2636":1180.5,"W2637":1320,…}`。
      这也是一份完整数据 —— 键是周别、值是数值 —— 没有理由因为"不是 echarts"就判失败回退种子。

    只在**同时**满足下列条件时才认（避免误吞普通配置对象）：
      · 至少 2 个键；键值都是标量（不含 dict/list）；
      · 值全部可转数字；键全部含数字（长得像周别）。
    不像则返回 None。
    """
    if not isinstance(node, dict) or len(node) < 2:
        return None
    items = list(node.items())
    if any(isinstance(v, (dict, list)) for _, v in items):
        return None
    if not all(_num_like(v) for _, v in items):
        return None
    if not all(re.search(r'\d', str(k)) for k, _ in items):
        return None
    # 反例守卫：{"2A":8,"2B":3,"2C":5} 是「厂别 → 数值」而不是「周别 → 数值」。
    # 纯厂别键（形如 2A/2B）一律不认，避免把厂别当成周别排出假折线。
    if all(re.fullmatch(r'\s*2\s*[A-Da-d]\s*', str(k)) for k, _ in items):
        return None
    items.sort(key=lambda kv: _week_sort_key(kv[0]))
    return ([str(k).strip() for k, _ in items], [_to_num(v) for _, v in items])


def _coerce_fab(name, fab_list=None):
    """'2A' / 'FAB2A' / '2a车间' / '2A FAB' → '2A'（LLM 厂名写法漂移，统一回来）。"""
    s = str(name if name is not None else '').strip().upper()
    if not s:
        return ''
    if fab_list:
        for f in fab_list:
            u = f.upper()
            if s == u or re.sub(r'[^0-9A-Z]', '', s) == u:
                return f
    m = re.search(r'(?:^|[^0-9])2\s*([A-D])(?:[^0-9A-Z]|$)', s) or re.match(r'^2([A-D])$', s)
    return ('2' + m.group(1)) if m else ''


def _collect_candidates(root, max_depth=6):
    """把包装层逐层剥开，按「先父后子」顺序收集候选节点。"""
    out, seen = [], set()

    def walk(node, depth):
        if node is None or depth > max_depth:
            return
        if isinstance(node, list):
            if id(node) in seen:
                return
            seen.add(id(node))
            out.append(node)
            for it in node[:30]:
                if isinstance(it, dict):
                    walk(it, depth + 1)
            return
        if not isinstance(node, dict) or id(node) in seen:
            return
        seen.add(id(node))
        out.append(node)
        for k in _CONTAINER_KEYS:
            if k in node:
                walk(node[k], depth + 1)

    walk(root, 0)
    return out


def _axis_from(node):
    for c in (node.get('xAxis'), node.get('xaxis'), node.get('x'), node.get('categories'),
              node.get('category'), node.get('labels'), node.get('xLabels'), node.get('xlabels'),
              node.get('weeks'), node.get('periods')):
        if isinstance(c, list) and c:
            return [str(v).strip() for v in c]
        if isinstance(c, dict):
            if isinstance(c.get('data'), list) and c['data']:
                return [str(v).strip() for v in c['data']]
            if isinstance(c.get('categories'), list) and c['categories']:
                return [str(v).strip() for v in c['categories']]
        if isinstance(c, str) and c.strip():
            parts = [p for p in re.split(r'[,，|;；\s]+', c.strip()) if p]
            if len(parts) >= 2:
                return parts
    return []


def _series_from(node, fab_list=None):
    out = []
    raw = node.get('series') or node.get('lines') or node.get('datasets') or node.get('items')
    legend = [str(v).strip() for v in node['legend']['data']] \
        if isinstance(node.get('legend'), dict) and isinstance(node['legend'].get('data'), list) else []
    if isinstance(raw, list):
        for i, s in enumerate(raw):
            if isinstance(s, list):                       # series: [[8,5,13], [3,7,4]]
                nm = _coerce_fab(legend[i] if i < len(legend) else '', fab_list) or (legend[i] if i < len(legend) else '')
                out.append({'name': str(nm), 'data': [_to_num(v) for v in s]})
                continue
            if not isinstance(s, dict):
                continue
            nm = s.get('name', s.get('fab', s.get('label', s.get('title', legend[i] if i < len(legend) else ''))))
            data = s.get('data', s.get('values', s.get('value', s.get('count', s.get('count_value', s.get('y', []))))))
            if not isinstance(data, list):
                data = [data]
            out.append({'name': str(_coerce_fab(nm, fab_list) or (nm if nm is not None else '')),
                        'data': [_to_num(v) for v in data]})
        return out
    if isinstance(raw, dict):                             # series: {'2A':[..], '2B':[..]}
        for k, v in raw.items():
            if isinstance(v, list):
                out.append({'name': str(_coerce_fab(k, fab_list) or k), 'data': [_to_num(x) for x in v]})
        return out
    for c in (node.get('yAxis'), node.get('yaxis'), node.get('y')):
        if isinstance(c, dict) and isinstance(c.get('data'), list) and any(_num_like(v) for v in c['data']):
            nm = node.get('name', node.get('fab', node.get('label', '')))
            out.append({'name': str(_coerce_fab(nm, fab_list)), 'data': [_to_num(v) for v in c['data']]})
            break
    if out:
        return out
    # ★ 2026-09-24：**裸数值数组** —— {"data":[1180,1320,980,760]} / {"values":[…]} / {"numbers":[…]}。
    #   上游只把「需要的数值」吐出来、不带 series 包装，也是完整数据。
    #   守卫：必须是「全标量」的列表且有数值，避免把 {"data":[{week,v},…]} 这类行表误当数值序列。
    for k in ('data', 'values', 'numbers', 'y'):
        arr = node.get(k)
        if (isinstance(arr, list) and arr
                and not any(isinstance(v, (dict, list)) for v in arr)
                and any(_num_like(v) for v in arr)):
            nm = node.get('name', node.get('fab', node.get('label', '')))
            return [{'name': str(_coerce_fab(nm, fab_list)), 'data': [_to_num(v) for v in arr]}]
    return out


def _match_key(keys, cands):
    nk = [(k, _norm_key(k)) for k in keys]
    for c in cands:
        for k, n in nk:
            if n == c:
                return k
    for c in cands:
        for k, n in nk:
            if n.startswith(c):
                return k
    for c in cands:
        for k, n in nk:
            if c in n:
                return k
    return ''


def _guess_numeric_key(sample, keys, exclude):
    for k in keys:
        if k in exclude:
            continue
        vals = [r.get(k) for r in sample if r.get(k) not in (None, '')]
        if vals and sum(1 for v in vals if _num_like(v)) / float(len(vals)) >= 0.6:
            return k
    return ''


def _pivot_rows(rows, columns, fab_list=None, default_name=''):
    if columns and rows and isinstance(rows[0], list):     # 矩阵形态 → 行对象
        rows = [{str(columns[i] if i < len(columns) else 'c%d' % i): (arr[i] if i < len(arr) else None)
                 for i in range(max(len(columns), len(arr)))} for arr in rows]
    objs = [r for r in rows if isinstance(r, dict)]
    if not objs:
        return None
    sample = objs[:30]
    keys = []
    for r in sample:
        for k in r.keys():
            if k not in keys:
                keys.append(k)
    if not keys:
        return None

    fab_key = _match_key(keys, _FAB_KEYS)
    week_key = _match_key(keys, _WEEK_KEYS)
    fab_cols = [k for k in keys if k != week_key and k != fab_key and _coerce_fab(k, fab_list)]
    value_key = _match_key(keys, _VALUE_KEYS) or _guess_numeric_key(sample, keys,
                                                                   [x for x in (fab_key, week_key) if x])

    def id_of(r, i):
        return str(r.get(week_key, '')).strip() if week_key else ('#' + str(i))

    ids = []
    for i, r in enumerate(objs):
        l = id_of(r, i)
        if l != '' and l not in ids:
            ids.append(l)

    series, shape = [], ''
    if value_key and fab_key:
        shape = 'rows-long'
        by_fab = {}
        for i, r in enumerate(objs):
            fab = _coerce_fab(r.get(fab_key), fab_list) or str(r.get(fab_key, '')).strip() or default_name
            by_fab.setdefault(fab, {})[id_of(r, i)] = _to_num(r.get(value_key))
        series = [{'name': k, 'data': [m.get(l) for l in ids]} for k, m in by_fab.items()]
    elif fab_cols:
        shape = 'rows-wide'
        for col in fab_cols:
            m = {id_of(r, i): _to_num(r.get(col)) for i, r in enumerate(objs)}
            series.append({'name': _coerce_fab(col, fab_list) or str(col).strip(),
                           'data': [m.get(l) for l in ids]})
    else:
        k = value_key or _guess_numeric_key(sample, keys, [x for x in (fab_key, week_key) if x])
        if not k:
            return None
        shape = 'rows-single'
        m = {id_of(r, i): _to_num(r.get(k)) for i, r in enumerate(objs)}
        series = [{'name': default_name, 'data': [m.get(l) for l in ids]}]

    x_axis = ids if week_key else ['W%d' % (i + 1) for i in range(len(ids))]
    if not x_axis:
        return None
    return {'xAxis': x_axis, 'series': series, 'shape': shape}


def _split_wow(x_axis, series):
    if len(x_axis) < 2 or not _WOW_RE.match(str(x_axis[-1]).strip()):
        return x_axis, series, None
    by_fab = {}
    for s in series:
        if len(s['data']) >= len(x_axis):
            by_fab[s['name']] = s['data'][-1]
    return (x_axis[:-1],
            [{'name': s['name'], 'data': s['data'][:len(x_axis) - 1]} for s in series],
            {'label': str(x_axis[-1]).strip(), 'byFab': by_fab})


def _normalize_chart(raw, fab_list=None, default_name=''):
    """把任意形状的云端 JSON 归一化成图表契约；真的没有可用轴/数值时返回 None。

    fab_list 给定时（ABL 场景）会把折线名强制归一化到该集合，且「一条都对不上」视为失败
    —— 宁可不亮也不半亮。
    """
    if raw is None:
        return None
    axis, series, node, shape = [], [], None, ''
    cands = _collect_candidates(raw, 6)

    for c in cands:                                   # ① 标准 echarts 形态
        if not isinstance(c, dict):
            continue
        a, s = _axis_from(c), _series_from(c, fab_list)
        if a and s:
            node, axis, series, shape = c, a, s, 'echarts'
            break

    if not shape:                                     # ② 行表形态（长表 / 宽表 / 矩阵 / 单列）
        for c in cands:
            if isinstance(c, list):
                if not c or not isinstance(c[0], dict):
                    continue
                p = _pivot_rows(c, None, fab_list, default_name)
            elif isinstance(c, dict) and isinstance(c.get('rows'), list):
                p = _pivot_rows(c['rows'], c.get('columns') or c.get('header') or c.get('headers'),
                                fab_list, default_name)
            else:
                continue
            if p and p['series']:
                axis, series, shape, node = p['xAxis'], p['series'], p['shape'], None
                break

    if not shape:                                     # ③ 只有 series，x 轴自己编号
        for c in cands:
            if not isinstance(c, dict):
                continue
            s = _series_from(c, fab_list)
            if s and any(any(v is not None for v in x['data']) for x in s):
                node, series, shape = c, s, 'series-only'
                break

    if not shape:                                     # ④ 「周别 → 数值」对象映射
        # ★ 2026-09-24：{"W2636":1180.5,"W2637":1320,…}（或包在 data/values/result 里）。
        #   键是周别、值是数值，同样是完整数据；`_week_map_items` 会按周排好序再交出来。
        for c in cands:
            m = _week_map_items(c)
            if m:
                axis, series, node, shape = m[0], [{'name': '', 'data': m[1]}], None, 'week-map'
                break

    if not shape:
        return None

    series = [{'name': (_coerce_fab(s['name'], fab_list) or str(s['name'] or '')),
               'data': [_to_num(v) for v in (s['data'] or [])]} for s in series]
    series = [s for s in series if s['data']]
    max_len = max([len(s['data']) for s in series] or [0])
    if not max_len:
        return None

    # ★ 2026-09-24：轴 / 数值长度不一致时，一律【按尾部对齐】（最新的标签 ↔ 最新的数值）。
    #
    #   旧实现是**按头部对齐**：数值不够就在末尾补 None、轴不够就在末尾编 'W1'…'Wn'。
    #   而 DPPM 面板只展示 values 末尾 4 个（前端 dppmStatsFor 的 slice(-4)），于是：
    #     · 轴 6 格 / 数值 4 个 → 4 个数值占住【最旧】的 4 格、末尾两周变 None
    #       ⇒ 面板 slice(-4) 拿到 [4100, 3600, None, None]：只剩 2 个真实点 + 2 个空
    #         （实测 T4；用户报的「2B 拿到 6 个周，只取最近四周，却和 2A 不一样」）；
    #     · 轴 4 格 / 数值 6 个 → 轴尾被编造 'W5'/'W6'
    #       ⇒ 面板显示 W2638 / W2639 / W5 / W6，界面上出现【不存在的周别】（实测 T5）。
    #   按尾部对齐后：缺的补在最旧端（None），多余的从最旧端裁掉；轴原本为空时**不编造**
    #   任何标签（宁可无标签，也不给假周别——与「界面不出现虚假信息」的口径一致）。
    axis_len = len(axis)
    n = axis_len if axis_len >= max_len else max_len
    if axis_len and axis_len != n:
        axis = axis[-n:] if axis_len > n else ([''] * (n - axis_len) + axis)
    series = [{'name': s['name'],
               'data': s['data'] if len(s['data']) == n else
                       (s['data'][-n:] if len(s['data']) > n
                        else [None] * (n - len(s['data'])) + s['data'])} for s in series]

    if fab_list and not any(s['name'] in fab_list for s in series):
        return None

    title = ''
    if node:
        t = node.get('title')
        title = str((t.get('text') if isinstance(t, dict) else t) or '').strip()
        if not title:
            title = str(node.get('name') or node.get('chartTitle') or node.get('chart_title') or '').strip()
    unit = ''
    if node:
        unit = str(node.get('unit') or node.get('unitName') or node.get('unit_name') or '').strip()
        if not unit:
            y = node.get('yAxis') or node.get('yaxis')
            yname = str(y.get('name') or '').strip() if isinstance(y, dict) else ''
            # ★ 2026-09-22：echarts 里 yAxis.name 是「轴的名字」，**不等于单位**。
            #   DPPM 2B 的真实回覆就是 {"yAxis":{"name":"DPPM"}} —— 指标名被当成单位后，
            #   界面会把数值显示成「3851.09DPPM」。故仅当该轴名既不是图表标题、
            #   也不等于任何折线名时，才把它当单位（ABL 的 "次数" 仍然成立）。
            if yname and yname != title and not any(yname == s['name'] for s in series):
                unit = yname

    x_axis, series, wow = _split_wow(axis, series)
    return {'title': title, 'unit': unit, 'xAxis': x_axis, 'series': series, 'wow': wow, 'shape': shape}




def _err_response(e, tag):
    """统一错误响应。"""
    if isinstance(e, requests.exceptions.Timeout):
        return Response({'success': False, 'error': f'{tag} 机器人请求超时', 'data': None}, status=504)
    if isinstance(e, requests.exceptions.ConnectionError):
        return Response({'success': False, 'error': f'无法连接机器人：{BYFAB_BOT_BASE_URL}', 'data': None}, status=502)
    return Response({'success': False, 'error': f'{tag} 机器人请求失败: {e}', 'data': None}, status=502)


# ════════════════════════════════════════════════════════════
#  API 视图
# ════════════════════════════════════════════════════════════
def _qs_flag(request, name):
    """把 ?force=1 / ?diag=1 / ?force=true 之类的开关统一解析成 bool。"""
    return (request.GET.get(name) or '').strip().lower() in ('1', 'true', 'yes', 'on')


def _dt_str(dt):
    """本地时间字符串（USE_TZ=True 下必须 localtime，否则比北京时间早 8 小时）。

    ★ 2026-09-22：改为直接复用 `_dt_local_str`，把「naive 时间戳会抛 ValueError」的防御
    一并覆盖到 `_diag()` 的 diagnostics 路径上（否则 `?diag=1` 同样会 500）。
    """
    return _dt_local_str(dt)


def _diag(key):
    """诊断信息：上游可达性 + 缓存状态 + 定时刷新状态。给 IT 定位"服务器连不上机器人"用。"""
    from ..services import bot_refresh
    cache = BotDataCache.objects.filter(key=key).first()
    return {
        'bot_base_url': BYFAB_BOT_BASE_URL,
        'bot_endpoint': BOT_ENDPOINT,
        'bot_timeout_default_sec': BOT_STREAM_TIMEOUT,
        'sync_refresh_timeout_sec': SYNC_REFRESH_TIMEOUT,
        'bg_refresh_timeout_sec': BG_REFRESH_TIMEOUT,
        'bg_refresh_min_interval_sec': BG_REFRESH_MIN_INTERVAL,
        'abl_ttl_sec': ABL_TTL_SECONDS,
        # ★ 2026-09-23：Key 指纹（仅末 4 位；完整 Key 永不下发）。
        #   只为一眼看出两类配置事故：① 2A/2B 配成了同一个 Key；② DPPM 误用了 ABL 的 Key。
        'bot_api_keys': {
            **{('dppm_%s' % fab.lower()): _mask_key(k) for fab, k in DPPM_BOT_API_KEYS.items()},
            'abl': _mask_key(BYFAB_BOT_API_KEY),
            'dppm_keys_distinct': bool(
                DPPM_BOT_API_KEYS.get('2A') and DPPM_BOT_API_KEYS.get('2B')
                and DPPM_BOT_API_KEYS['2A'] != DPPM_BOT_API_KEYS['2B']
            ),
            'dppm_reuses_abl_key': any(
                k and k == BYFAB_BOT_API_KEY for k in DPPM_BOT_API_KEYS.values()
            ),
        },
        # ★ 服务器自主定时刷新（不依赖有人访问）：周期、是否已启动、上一轮结果
        'auto_refresh': bot_refresh.status(),
        # ★ 真实探一次 TCP：ok=false 就是网络不通（VLAN/防火墙/IP 白名单），与代码无关
        'reachability': _probe_bot(),
        'cache': {
            'key': key,
            'has_payload': bool(cache and cache.payload),
            'is_seed': bool(cache.is_seed) if cache else None,
            # ★ 2026-09-24：把「哪一厂还在用兜底种子」直接摊开 ——
            #   排查「2A 正常、2B 假数据」时不必再猜，一眼就能看出是 2B 没取到真值。
            'seed_fabs': _cache_seed_fabs(cache),
            'fetched_at': _dt_str(cache.fetched_at) if cache else '',
            'last_attempt_at': _dt_str(cache.last_attempt_at) if cache else '',
            'last_error': (cache.last_error if cache else '') or '',
            'fail_count': (cache.fail_count if cache else 0) or 0,
            'payload_bytes': len(cache.payload or '') if cache else 0,
        },
    }


# —— 具体刷新任务：成功→落库；失败→由调用方记 last_error ——
def _refresh_abl(week, timeout):
    """向机器人取一次 ABL 图表 JSON，成功则写入持久缓存。

    ★ 2026-09-21：改为「先归一化再落库」
      原实现只要 answer 能解析成一个 dict 就整体覆盖缓存 —— 而机器人后面挂着 LLM，偶尔会把
      **原始数据表**（{data:[{fab,week,count_value},…], message:'您没有提出具体问题…'}）当成
      "答案"回吐，这种形状前端渲染不出来，却会把上一份**好数据覆盖掉**。
      现在交给 `_normalize_chart` 归一化（容错识别 echarts / 行表 / 包装层 / 宽表 / series-map …），
      归一化不出来就当本次刷新失败（保留上一份真值，由调用方记 last_error），不再让垃圾覆盖好数据。
    """
    answer = _chat(ABL_CLOUD_QUERY, _bot_inputs(week=week), timeout=timeout)
    data = _extract_json(answer)
    chart = _normalize_chart(data, fab_list=('2A', '2B', '2C', '2D'))
    if chart is None:
        raise ValueError(f'ABL 云端返回无法归一化为图表 JSON；answer前200字={str(answer)[:200]!r}')
    _cache_save_success(CACHE_KEY_ABL, chart)
    return chart


@api_view(['GET'])
@permission_classes([AllowAny])
def abl_cloud_data(request):
    """ABL 触发 · 云端图表数据（服务端持久缓存 + 永久兜底种子 + 后台刷新）

    前端 GET /api/byfab/abl/ → 本视图立即返回服务端缓存（真值 or 兜底种子），
    绝不阻塞在机器人上；过期时后台静默刷新，取到真值自动覆盖缓存。

    ★ 2026-09-16 改造原因：原实现每请求现场打一次机器人 workflow（可阻塞 680 秒），
      叠加前端 1.5 秒重试 → 服务器线程被占满 → 浏览器 ERR_CONNECTION_RESET + 大量 500，
      且两条通道都失败导致整页压暗（"ABL 面板灰色"）。

    查询参数：
      force=1  同步刷新一次（短超时），供前端「↻ 重新查询」按钮
      diag=1   返回上游可达性探测 + 缓存状态，供 IT 排查网络
      week=..  透传给机器人工作流的 week 变量
    """
    try:
        if _qs_flag(request, 'diag'):
            return Response({'success': True, 'diagnostics': _diag(CACHE_KEY_ABL)})

        week = (request.GET.get('week') or '').strip() or None
        cache = _cache_get(CACHE_KEY_ABL, seed_factory=_abl_seed_payload)

        if _qs_flag(request, 'force'):
            try:
                _refresh_abl(week, SYNC_REFRESH_TIMEOUT)
            except Exception as e:
                print(f'[Dify] ABL 同步刷新失败：{e}')
                _cache_save_error(CACHE_KEY_ABL, e)
            cache = _cache_get(CACHE_KEY_ABL, seed_factory=_abl_seed_payload)
        elif _cache_is_stale(cache, ABL_TTL_SECONDS):
            _start_bg_refresh(CACHE_KEY_ABL, lambda: _refresh_abl(week, BG_REFRESH_TIMEOUT))

        data = _cache_payload(cache)
        if data is None:
            # ★ 2026-09-22：这里不再回 503 —— 本接口契约是「永远有结构可渲染」。
            #   没有缓存就直接上兜底种子；回 503 会让前端 fetchXxx 拿到 null → 面板不点亮。
            data = _abl_seed_payload()

        return Response({'success': True, 'data': data, **_cache_meta(cache)})
    except Exception as e:
        # ★ 本接口契约是「绝不失败」：任何未预期异常（DB / naive 时间戳 / 线程租约 …）
        #   都回落成「缓存或兜底种子 + 200」，并落盘 traceback，保证面板照常点亮。
        _log_byfab_error('abl_cloud_data', e)
        return Response(_cloud_fallback(CACHE_KEY_ABL, _abl_seed_payload, e))


# ════════════════════════════════════════════════════════════
#  DPPM 云端（2A / 2B）· 与 ABL 同款：服务端持久缓存 + 兜底种子 + 后台刷新
#
#  机器人返回【单厂 echarts】（series 不带 name，仅一条 data 折线）：
#    2A → {"title":{"text":"DPPM"},"xAxis":{"data":["W2636",...,"W2639"]},"series":[{"data":[...]}]}
#    2B → {"title":{"text":"抽检量"},"xAxis":{...},"series":[{"data":[...]}]}
#  后端按提问厂别打标签，合并为 {fabs:{ "2A":{title,unit,xAxis,values}, "2B":{...} }}。
#
#  ★ 2026-09-24（用户明确）：「解析拿到的回复只取 4 周」——
#    上游回覆的**周数不固定**（实测 2A / 2B 都可能给 4 周或 6 周），而面板口径恒为「最近四周」。
#    裁周统一收敛到**解析层**（`_extract_dppm_fab` + 兜底种子），而不是留给前端各自 slice：
#    这样缓存里两个厂**天然同构**（等长 xAxis + 等长 values、都 ≤4 周），
#    面板 / 浮层 / 弹窗 / 2A-2B 对比图拿到的就是同一形状，不会再出现「一边 4 点一边 6 点」。
#    前端保留了 `slice(-4)` 作为幂等兜底（重复裁无副作用）。
# ════════════════════════════════════════════════════════════
CACHE_KEY_DPPM = 'dppm'

# 面板只展示【最近 N 周】（用户口径：4 周）。解析回覆时按此裁到末尾 N 周。
DPPM_RECENT_WEEKS = int(os.environ.get('DPPM_RECENT_WEEKS', '4'))

# ★ 兜底种子：用"看起来像真实 DPPM / 抽检量"的样例值（非全 0），保证未连上机器人时面板有结构、不空白。
#   2A = DPPM（百万不良率，量级 ~千），2B = 抽检量（量级 ~千~万）。
#   ★ 2026-09-24：两厂种子都裁成 4 周（与 DPPM_RECENT_WEEKS 一致）——
#     此前 2B 种子是 6 周，与 2A 的 4 周不同构，正是"真假数据形状不一致"的源头之一。
_DPPM_SEED = {
    '2A': {'title': 'DPPM', 'unit': '', 'xAxis': ['W2636', 'W2637', 'W2638', 'W2639'],
           'values': [1180.5, 1320.0, 980.2, 760.4]},
    '2B': {'title': '抽检量', 'unit': '', 'xAxis': ['W2636', 'W2637', 'W2638', 'W2639'],
           'values': [4100, 3600, 4800, 5200]},
}


def _dppm_seed_fab(fab):
    """单厂兜底种子（深拷贝，避免被调用方改动原始样例）。

    ★ `seeded=True` 是**关键内部标记**：DPPM 是按厂分别查询、单厂失败只回退该厂，
      所以"这份 payload 是不是种子"必须**按厂**判断，不能只看整份的 is_seed。
      前端据此做「按厂抗降级」（已有真值的那一厂绝不退回种子）。
    """
    s = _DPPM_SEED.get(fab)
    if not s:
        return {'title': '', 'unit': '', 'xAxis': [], 'values': [], 'seeded': True}
    out = {k: (list(v) if isinstance(v, list) else v) for k, v in s.items()}
    out['seeded'] = True
    return out


def _dppm_seed_payload():
    """DPPM 兜底种子：合法可渲染的 fabs 结构。"""
    return {'fabs': {fab: _dppm_seed_fab(fab) for fab in ('2A', '2B')}}


def _extract_dppm_fab(raw, fab):
    """从机器人返回里提取【单厂】的 {title, unit, xAxis, values, seeded}。

    ★ 2026-09-21：改为走 `_normalize_chart` 容错解析。
      LLM 的输出形状会漂移 —— 可能是单厂 echarts option、{option:{…}} 包装层、原始行表
      （{data:[{week,count_value},…]}）、宽表、series 写成 map、xAxis 写成逗号串……
      原先只认「xAxis + series[0].data」这一种，形状一变就判失败 → 该厂回退种子（真数据白丢）。
      现在统一归一化后按厂认领折线：名字精确匹配 → 名字包含 → **数值最多的那条**。
     ★ 2026-09-24：最后一级由「只有一条折线才采用」放宽为「数值最多的一条」——
       上游折线名会漂移（'抽检量' / 'series1' / 空），不该因此判失败回退种子。
    返回 None 表示该厂确实取不到可用数值（由调用方回退缓存/种子）。
    """
    chart = _normalize_chart(raw)
    if not chart or not chart.get('series'):
        return None
    series = None
    for s in chart['series']:                       # ① 名字精确匹配
        if s['name'] == fab:
            series = s
            break
    if series is None:                              # ② 名字包含（'2A车间' / 'FAB2A'）
        for s in chart['series']:
            if s['name'] and fab in s['name']:
                series = s
                break
    if series is None:
        # ★ 2026-09-24（用户：「格式不一定一样，但一定会有需要的数据，不要写死」）：
        #   不再要求「只有一条折线」才认领。折线名对不上时（LLM 写成 '抽检量' / 'series1' / 空）
        #   退化为「数值最多、且有非空值的那一条」—— DPPM 是按厂单独提问的，
        #   回覆里本就该只有该厂的数据，认领正确率远高于直接判失败回退种子。
        cands = [s for s in chart['series'] if any(v is not None for v in s['data'])]
        if cands:
            # 只有【多条】折线时才值得留痕：单条无名折线是上游常态（裸数值数组 / week-map），
            # 不是"匹配失败"，打了反而像异常。
            if len(chart['series']) > 1:
                print('[Dify] DPPM %s 折线名无法匹配 %s，按「数值最多的一条」认领'
                      % (fab, [s['name'] for s in chart['series']]))
            series = max(cands, key=lambda s: sum(1 for v in s['data'] if v is not None))
    if series is None:
        return None
    values = series['data']
    if not any(v is not None for v in values):
        return None
    # ★ 2026-09-24（用户要求）：「解析拿到的回复只取 4 周」——
    #   在**解析层**就裁到末尾 DPPM_RECENT_WEEKS 周（裁最旧端、保留最新），
    #   让缓存里两厂天然同构（等长 xAxis + 等长 values、都 ≤4 周），
    #   面板/浮层/弹窗/对比图不必再各自假设周数，彻底消掉「一边 4 点一边 6 点」。
    #   统一走 `_trim_recent_fab`，与「沿用上次缓存值」的回退分支共用同一口径。
    return _trim_recent_fab({'title': chart['title'], 'unit': chart['unit'],
                             'xAxis': chart['xAxis'], 'values': values, 'seeded': False})


def _trim_recent_fab(fabdata, n=None):
    """把单厂数据结构裁到【最近 n 周】（原地返回新 dict）。

    ★ 2026-09-24：抽出成公共函数，让「payload 里每个厂都 ≤ N 周且轴值等长」成为**不变量** ——
      `_extract_dppm_fab`（解析回覆）、以及 `_refresh_dppm` 里「沿用上次缓存值」的回退分支
      都走它。否则老库里的 6 周旧值会在回退时被原样沿用，两厂又不同构了。
      （种子本身已按 N 周定义，无需再裁；重复裁是幂等的。）
    """
    if not isinstance(fabdata, dict):
        return fabdata
    n = DPPM_RECENT_WEEKS if n is None else n
    axis = list(fabdata.get('xAxis') or [])
    values = list(fabdata.get('values') or [])
    if n > 0 and len(values) > n:
        values = values[-n:]
        axis = axis[-n:] if len(axis) >= n else axis
    out = dict(fabdata)
    out['xAxis'], out['values'] = axis, values
    return out


def _refresh_dppm(timeout):
    """向机器人取 2A(DPPM) / 2B(抽检量) 两份 echarts，合并写入持久缓存。

    ★ 单厂失败不影响另一厂：失败的厂回退到「上一次缓存值」，没有则兜底种子，
      保证面板永远有结构可渲染（与 ABL 的"整体失败才报错"不同，DPPM 是双独立查询）。

    ★ 2026-09-20 修正（上一版有 bug）：回退时**必须区分"上次缓存"本身是不是种子**。
      旧实现直接 `cached.get('fabs')[fab]` 当作"上次真值"，而 cache 在首次读取时
      就是由 `seed_factory` 用种子填充的 → 种子被当成真值沿用、`is_seed` 被清成 False，
      结果"永远是假数据却对外声称是真数据"（前端抗降级也因此完全失效）。
      现在改为：① 缓存整份是种子时，其 payload 一律不算真值；② 按厂记录 seed_fabs，
      整份只有全厂都是种子才把 is_seed 标 True（至少一厂真值 → 面板仍可用）。
    """
    cached_obj = _cache_get(CACHE_KEY_DPPM)
    cached_fabs = ((_cache_payload(cached_obj) or {}) or {}).get('fabs') or {}
    cached_is_seed = bool(cached_obj and cached_obj.is_seed)

    fabs = {}
    seed_fabs = set()
    errors = []
    for fab in ('2A', '2B'):
        try:
            # ★ 2026-09-23：2A / 2B 是两个独立机器人应用 → 必须各传各的 Key。
            #   旧代码这里写死 `api_key=DPPM_BOT_API_KEY`（单 Key），2B 一直借用了 2A 的机器人。
            key = (DPPM_BOT_API_KEYS.get(fab) or '').strip()
            # ⚠️ 不能放行空 Key：`_headers(None)` 会回退成 BYFAB_BOT_API_KEY（ABL 的 Key）→
            #    静默问错机器人且毫无痕迹。这里显式失败，交由下面的 except 回退并写进 last_error。
            if not key:
                raise ValueError(
                    'DPPM %s 未配置 API Key（请设置 settings.DPPM_BOT_API_KEY_%s 或同名环境变量）' % (fab, fab)
                )
            answer = _chat(DPPM_CLOUD_QUERIES.get(fab, ''), None, timeout=timeout, api_key=key)
            raw = _extract_json(answer)
            fab_data = _extract_dppm_fab(raw, fab)
            if not fab_data or not any(v is not None for v in fab_data.get('values', [])):
                raise ValueError('DPPM 机器人返回无法解析为单厂图表（%s）' % fab)
            fabs[fab] = fab_data
        except Exception as e:
            print('[Dify] DPPM %s 刷新失败，回退缓存/种子：%s' % (fab, e))
            errors.append('%s: %s' % (fab, e))
            fb = cached_fabs.get(fab)
            if fb and not cached_is_seed:
                # 沿用上次【真值】，不降级；★ 同时再裁一次最近 N 周 ——
                # 老库里可能存着改造前的 6 周旧值，不裁就会让两厂重新不同构。
                fabs[fab] = _trim_recent_fab(fb)
                if fb.get('seeded'):
                    seed_fabs.add(fab)          # 防御：缓存里万一混着种子也如实标记
            else:
                fabs[fab] = _dppm_seed_fab(fab)   # 真没办法 → 种子兜底
                seed_fabs.add(fab)
    payload = {'fabs': fabs, 'seed_fabs': sorted(seed_fabs)}
    # 仅当【两个厂都是种子】才把整份标记为 is_seed=True（与 ABL 一致：种子是最后兜底且明确标记，
    # 已有真值绝不降级）；只坏一个厂时整份仍算真值，避免面板因一厂故障被前端抗降级整体冻住。
    all_seed = bool(seed_fabs) and len(seed_fabs) == len(fabs)
    _cache_save_success(CACHE_KEY_DPPM, payload, force_seed=all_seed)
    # ★ 2026-09-21 对齐 ABL 的失败口径：只要有厂落到种子，这一轮就不算完全成功。
    #   `_cache_save_success` 会把 last_error 清空、fail_count 归零（它按"成功"处理）→
    #   若不补记，会出现「假数据却声称成功」、运维看不到 last_error。
    #   ★ 2026-09-24 扩到【部分失败】：旧实现只在 all_seed 时补记，于是「2A 好、2B 坏」
    #   这种最该被看见的半故障在运维视角完全静默（last_error=''、fail_count=0），
    #   而它恰恰就是用户报的「2A 正常、2B 一直假数据」。
    if seed_fabs:
        _cache_save_error(CACHE_KEY_DPPM, '；'.join(errors) or '部分厂未取到真值，已回退兜底种子')
    return payload


@api_view(['GET'])
@permission_classes([AllowAny])
def dppm_cloud_data(request):
    """DPPM 云端（2A / 2B）· 服务端持久缓存 + 永久兜底种子 + 后台刷新。

    前端 GET /api/byfab/dppm/ → 立即返回服务端缓存（真值 or 兜底种子），绝不阻塞在机器人上；
    过期时后台静默刷新，取到真值自动覆盖缓存。

    查询参数同 ABL：
      force=1  同步刷新一次（短超时），供前端「↻ 重新查询」
      diag=1   返回上游可达性探测 + 缓存状态，供 IT 排查网络
    """
    try:
        if _qs_flag(request, 'diag'):
            return Response({'success': True, 'diagnostics': _diag(CACHE_KEY_DPPM)})

        cache = _cache_get(CACHE_KEY_DPPM, seed_factory=_dppm_seed_payload)

        if _qs_flag(request, 'force'):
            try:
                _refresh_dppm(SYNC_REFRESH_TIMEOUT)
            except Exception as e:
                print('[Dify] DPPM 同步刷新失败：%s' % e)
                _cache_save_error(CACHE_KEY_DPPM, e)
            cache = _cache_get(CACHE_KEY_DPPM, seed_factory=_dppm_seed_payload)
        elif _cache_is_stale(cache, ABL_TTL_SECONDS):
            _start_bg_refresh(CACHE_KEY_DPPM, lambda: _refresh_dppm(BG_REFRESH_TIMEOUT))

        data = _cache_payload(cache)
        if data is None:
            # ★ 2026-09-22：不再回 503。本接口契约是「永久兜底种子 + 永远有结构可渲染」，
            #   回 503 会让前端 fetchDppmCloud 拿到 null → dppmCloudData 恒 null
            #   → dppmHasFab 恒 false → DPPM 面板既不亮也点不进去（用户报的"面板不点亮"）。
            data = _dppm_seed_payload()

        return Response({'success': True, 'data': data, **_cache_meta(cache)})
    except Exception as e:
        # ★ 本接口契约是「绝不失败」。2026-09-22 线上出现「DPPM 500 / ABL 正常」——
        #   根因是 `_start_bg_refresh` 里那次未保护的 DB 查询 + 时间减法（`or` 短路让 ABL 侥幸避开）。
        #   现在除了修掉那个根因，这里再加一层：任何未预期异常都回落成「缓存或兜底种子 + 200」，
        #   并把 traceback 落盘到 <db 同目录>/logs/byfab_errors.log，保证面板照常点亮。
        _log_byfab_error('dppm_cloud_data', e)
        return Response(_cloud_fallback(CACHE_KEY_DPPM, _dppm_seed_payload, e))
