# -*- coding: utf-8 -*-
"""预排筛选（S13_DPS + Monthly input target）视图"""
import json
import os
import re
import traceback
import threading
import time
import urllib.parse
from datetime import datetime

from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from rest_framework import filters, viewsets

from ..models import EntryTable, OrtRule, PreplanRow
from ..serializers import EntryTableSerializer, OrtRuleSerializer
from ..services.preplan_service import (
    build_preplan_excel,
    preplan_row_to_dict,
    process_preplan,
    process_single_file,
    recompute_external_row,
    refresh_entry_backfill,
    _pick_ort_rule,
)
from ..services.import_task import (
    ImportCancelled,
    finish as import_task_finish,
    generation as import_generation,
    invalidate as import_invalidate,
    is_cancelled as import_is_cancelled,
    register_task as import_register_task,
    request_cancel as import_request_cancel,
)
from ..services.db_backup import backup_db as _backup_db_impl
from ..services.db_backup import save_import_snapshot as _save_snapshot_impl

BATCH_PREFIX = 'PREPLAN_'


# ==================== 预排年月（YYYYMM）维度 · 公共工具（★ 2026-09-20）====================
#   为什么需要「月」这一层：公司每月都要筛选计划，且同月还可能同时处理「本月」与
#   「未来几个月」的计划。原实现只有「年 + 来源」两个维度、覆盖范围又按文件名判定，
#   于是同名文件换月导入会顶掉上个月的数据，页面实际上只能保住一个月份。
#   现在 plan_ym = 该行【预排月份】所属的年月（YYYYMM；0 = 未归类的历史数据），
#   查询/清空/导出/重算/定版全部可传 ym 收窄到某一个月，互不干扰。

def _parse_ym(value):
    """请求里的 ym（YYYYMM）→ int；空或非法返回 None（= 不按月收窄，保持旧行为）。"""
    s = str(value or '').strip()
    if not s:
        return None
    try:
        n = int(s)
    except (TypeError, ValueError):
        return None
    if 190001 <= n <= 299912 and 1 <= n % 100 <= 12:
        return n
    return None


def _ym_summary(year=None):
    """当前库里出现过的「预排年月」清单（供前端月份下拉），按月倒序、未归类排末尾。

    - label 由 ym 现算（不再用各文件写死的 plan_month_label 文本，避免 '9月' 与
      '2026年9月' 这类写法把同一个月拆成两个选项）；
    - count = 该月行数，便于用户判断哪个才是要看的那批。
    """
    qs = PreplanRow.objects.all()
    if year:
        try:
            qs = qs.filter(plan_year=int(year))
        except (TypeError, ValueError):
            pass
    out = []
    for row in qs.values('plan_ym').annotate(n=Count('id')).order_by('-plan_ym'):
        ym = int(row['plan_ym'] or 0)
        label = '未归类' if not ym else f'{ym // 100}年{ym % 100}月'
        out.append({'ym': ym, 'label': label, 'count': row['n']})
    return out


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.strptime(str(value).strip()[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _post_data(request):
    """兼容 JSON body 与表单 POST（前端 axios 默认发 JSON）"""
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or b'{}')
        except Exception:
            return {}
    return request.POST


# ════════════════════════════════════════════════════════════
#  MTD 最近一次同步状态（查到总数持久化）
#  ★ 修复：预警页「MTD 查到总数」刷新/重进页面后变 0 的问题——
#    同步时把 total_sql 写入 <db目录>/data_snapshots/mtd_last_state.json，
#    查询行接口返回它，前端 loadData 时自动恢复，无需每次重跑 SQL。
# ════════════════════════════════════════════════════════════
_MTD_STATE_FILE = 'mtd_last_state.json'


def _mtd_state_dir():
    from django.conf import settings
    db = settings.DATABASES['default'].get('NAME')
    d = os.path.join(os.path.dirname(os.path.abspath(str(db))), 'data_snapshots')
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _save_mtd_total(total_sql):
    """同步成功后记录「SQL 查到总数」（写入 JSON，便于下次加载直接恢复显示）"""
    try:
        from datetime import datetime as _dt
        path = os.path.join(_mtd_state_dir(), _MTD_STATE_FILE)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'total_sql': int(total_sql or 0),
                       'saved_at': _dt.now().strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False)
    except Exception:
        pass


def _read_mtd_total():
    """读取最近一次 MTD 同步的查到总数；无记录返回 0"""
    try:
        path = os.path.join(_mtd_state_dir(), _MTD_STATE_FILE)
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        return int(d.get('total_sql') or 0)
    except Exception:
        return 0


# ════════════════════════════════════════════════════════════
#  ★ 数据持久化：破坏性操作前自动备份 + 导入批次 JSON 快照
#    （实现复用 core/services/db_backup.py，启动脚本同样调用该模块）
# ════════════════════════════════════════════════════════════
def _backup_db():
    """SQLite 备份：导入覆盖 / 清空 / 删除等破坏性操作前自动执行。
    备份到 <db 同目录>/backups/，仅保留最近 10 份，防止误操作丢数据。"""
    from django.conf import settings
    return _backup_db_impl(settings.DATABASES['default'].get('NAME'))


def _log_destructive(action, scope, matched=None, deleted=None, kept_exported=None, kept_external=None, error=''):
    """★ 2026-09-21 破坏性操作审计日志（append-only → <db 同目录>/logs/destructive_YYYYMMDD.log）。

    为什么需要：清空/删除这类操作一旦「静默空转」（请求成功、后端一条都没删），
    前端过去只弹一句「已清空」，用户看到表格没变化时无从判断究竟是
    「范围没匹配上」还是「请求失败了被吞掉」。这里把**实际生效范围 + 匹配数 +
    删除数 + 保留数 + 异常**全部留痕，下次再看「清空了但数据还在」直接读这个文件即可定位。
    （不抛异常：留痕失败绝不能影响主流程。）

    ★ 2026-09-23：文件名由固定 `destructive.log` 改为**按天分文件**。
    原因：单文件 append-only 的 mtime 永远是最新的，导致「按 mtime 保留 N 天」的
    清理策略对它**永远不触发** —— 日志会无限增长却清不掉。按天分文件后，
    写完的那一天文件就不再变动，`db_backup.prune_logs()` 才能按天自然淘汰。
    （历史遗留的 logs/destructive.log 同样会被 prune_logs 匹配到并逐步淘汰。）

    kept_exported : 因「已导出到审核决议」被保护而未删的行数（preplan/clear）
    kept_external : 因「计划外（按设计保留）」而未删的行数（preplan/clear-archive）
    """
    try:
        from django.conf import settings
        _db = settings.DATABASES['default'].get('NAME')
        _dir = os.path.join(os.path.dirname(os.path.abspath(str(_db))), 'logs')
        os.makedirs(_dir, exist_ok=True)
        _ts = timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')
        _line = (
            f'{_ts}\t{action}\tscope={json.dumps(scope, ensure_ascii=False)}'
            f'\tmatched={matched}\tdeleted={deleted}\tkept_exported={kept_exported}'
            f'\tkept_external={kept_external}'
        )
        if error:
            _line += f'\terror={error}'
        _fn = 'destructive_' + _ts[:10].replace('-', '') + '.log'
        with open(os.path.join(_dir, _fn), 'a', encoding='utf-8') as f:
            f.write(_line + '\n')
    except Exception:
        pass


def _save_import_snapshot(year, source, rows, batch_id):
    """导入成功后写入 JSON 快照（可回溯），目录：<db 同目录>/data_snapshots/"""
    from django.conf import settings
    return _save_snapshot_impl(year, source, rows, batch_id, settings.DATABASES['default'].get('NAME'))


_MTD_AUTO_CACHE_TTL = 120        # 自动重匹配：同一批导入 2 分钟内的外部 PG 查询只打一次
_mtd_rematch_lock = threading.Lock()


def _auto_rematch_mtd(year=None):
    """★ 2026-09-18 性能修复：导入后的 MTD 自动重匹配改为**后台异步线程**执行。
    原因：MTD 是外部 PostgreSQL 查询（单次可达数十秒~分钟级），原先在导入请求内
    同步等待、且每份文件各跑一次 → N 份文件就把导入拖成几分钟。
    此处与项目 P0 约定「外部调用禁止在请求内同步等待上游」一致：请求立刻返回，
    MTD 在后台补齐；配合短 TTL 缓存，一批导入只打一次外部 SQL。失败静默。
    （手动「同步MTD」按钮仍走同步路径、始终取实时值）"""
    try:
        from mtd_monitor_config import MTD_SQL, PG_CONFIG
        if not MTD_SQL or not MTD_SQL.strip():
            return
        if not PG_CONFIG.get('dbname', '') or PG_CONFIG.get('dbname') in ('', 'your_database'):
            return
    except Exception:
        return

    def _job():
        with _mtd_rematch_lock:      # 串行化：避免多份文件的后台任务并发写 SQLite
            try:
                from ..services.mtd_monitor import apply_mtd_to_preplan
                stat = apply_mtd_to_preplan(year, cache_ttl=_MTD_AUTO_CACHE_TTL)
                print(f'[导入] MTD 后台重匹配完成：{stat}')
            except Exception as e:
                print(f'[导入] MTD 后台重匹配失败（忽略，不影响导入结果）: {e}')

    try:
        threading.Thread(target=_job, name='mtd-auto-rematch', daemon=True).start()
        print(f'[导入] MTD 重匹配已转后台异步（year={year}），导入立即返回')
    except Exception:
        pass


def _save_rows(rows, year, source=None, task_id=None, captured_spec=None, captured_all=None, ym=None):
    """
    将解析后的行数据批量写入 PreplanRow。source 不为空时仅清理该来源。

    ★ 2026-09-04 覆盖语义（不再追加）：rows 中带有的 source_file_name（本次导入的文件名），
      写入前先删除库里「同来源+同年+同名文件、且未导出到审核决议(exported=False)」的旧行，
      实现「同名文件重新导入 = 覆盖旧数据」。已导出到审核决议的行(exported=True) 归决议页所有，
      绝不触碰 —— 决议数据与预排文件操作彻底解耦。
      返回 (batch_id, replaced)，replaced = 本次覆盖删除的旧行数。

    ★ 2026-09-20 增加「预排年月」维度（ym，YYYYMM）：
      覆盖条件追加 plan_ym —— 同名文件只在【同一个月桶】内覆盖。
      修的问题：公司每月的计划文件往往同名（同一套模板导出），旧逻辑只按
      年+来源+文件名定位，于是「导入本月计划」会把「上个月导入的、尚未导出的行」整批删掉，
      表现为"页面只能保住一个月份"。加了月份维度后，多个月份可并存、互不影响。
      ym 为空时回退为本次 rows 里唯一非 0 的 plan_ym；仍取不到才退回旧的（不带月份）语义。

    ★ 导入可中断：传入 task_id 与导入开始时的代际令牌后——
       - 写入前 / 写入事务内检查「任务被取消」或「期间发生清空/删除(代际变化)」；
       - 命中则抛 ImportCancelled，由 transaction.atomic 整体回滚（含旧数据删除），
         保证清空/删除后导入不会再把数据写回来，状态一致。
    """
    def _aborted():
        if task_id and import_is_cancelled(task_id):
            return True
        if captured_spec is not None and import_generation(year, source) != captured_spec:
            return True
        if captured_all is not None and import_generation(year, None) != captured_all:
            return True
        return False

    # ★ 2026-09-20：确定本次导入的「预排年月」
    #   优先级：调用方显式传入的 ym（用户在导入弹窗里人工确认/修改过）> rows 里唯一的 plan_ym
    #   （由文件名日期码或表格「预排月份」列推算）> 0（无法判定，退回旧的不分月语义）。
    try:
        ym = int(ym) if ym not in (None, '', 0, '0') else None
    except (TypeError, ValueError):
        ym = None
    if not ym:
        _yms = {int(r.get('plan_ym') or 0) for r in rows}
        _yms.discard(0)
        ym = _yms.pop() if len(_yms) == 1 else None

    # ★ 毫秒级时间戳：多文件导入时每份文件独立批次（同秒导入也能区分）
    batch_id = f'{BATCH_PREFIX}{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}'
    # ★ 性能优化：bulk_create 批量写入（原逐条 create，大数据量时显著拖慢导入）
    objs = [
        PreplanRow(
            batch_id=batch_id,
            plan_year=year,
            plan_ym=ym or int(r.get('plan_ym') or 0),
            serial_number=r.get('serial_number', 0),
            status=r.get('status', 'kept'),
            source=r.get('source', ''),
            plan_month_label=r.get('plan_month_label', ''),
            table_date=r.get('table_date', ''),
            type=r.get('type', ''),
            fab=r.get('fab', ''),
            material_code_52=r.get('material_code_52', ''),
            model=r.get('model', ''),
            pn=r.get('pn', ''),
            customer=r.get('customer', ''),
            n1_dps=r.get('n1_dps', 0),
            n2_dps=r.get('n2_dps', 0),
            box_quantity=r.get('box_quantity', 0),
            request_qty=r.get('request_qty', 0),
            issue_qty_box=r.get('issue_qty_box', 0),
            issue_qty_pcs=r.get('issue_qty_pcs', 0),
            ort_ok=r.get('ort_ok', ''),
            qe_requirement=r.get('qe_requirement', ''),
            qe_remark=r.get('qe_remark', ''),
            ra_remark=r.get('ra_remark', ''),
            gpc_reply=r.get('gpc_reply', ''),
            oqc_hold=r.get('oqc_hold', ''),
            q_order=r.get('q_order', ''),
            box_number=r.get('box_number', ''),
            sample_date=_parse_date(r.get('sample_date')),
            mtd_output=r.get('mtd_output', ''),
            judge=r.get('judge', ''),
            filter_reason=r.get('filter_reason', ''),
            missing_fields=r.get('missing_fields', ''),
            source_file_name=r.get('source_file_name', ''),
        )
        for r in rows
    ]
    _t_w = time.time()
    with transaction.atomic():
        if _aborted():
            raise ImportCancelled('导入已取消：任务被取消或数据已被清空，放弃写入')
        # ★ 数据持久化：写入前先备份整个 SQLite，防止误操作丢数据
        _t_bk = time.time()
        _backup_db()
        print(f'[导入计时] SQLite 备份 {(time.time() - _t_bk):.2f}s')
        # ★ 同名文件重新导入 = 覆盖旧预排数据（2026-09-04，不再追加）
        #   只删「同来源+同年+同名文件、未导出到决议(exported=False)」的旧行；
        #   已导出到审核决议的行(exported=True) 归决议页，绝不触碰。
        #   ★ 2026-09-20 追加：再加「同预排年月(plan_ym)」——同名文件跨月导入不再互相顶掉。
        replaced = 0
        fnames = {str(r.get('source_file_name') or '').strip() for r in rows}
        fnames.discard('')
        if fnames and source:
            old_qs = PreplanRow.objects.filter(
                plan_year=year, source=source,
                source_file_name__in=list(fnames), exported=False,
            )
            if ym:
                old_qs = old_qs.filter(plan_ym=ym)
            replaced = old_qs.count()
            if replaced:
                old_qs.delete()
        if _aborted():
            raise ImportCancelled('导入已取消：任务被取消或数据已被清空，放弃写入')
        # ★ 清理「纯自动生成、用户从未触碰」的计划外行（MTD 会按新计划重新匹配生成），
        #   已插入预排筛选(inserted_to_preplan)、已回填 Type、已写备注(filter_reason) 的计划外行一律保留。
        PreplanRow.objects.filter(is_plan_external=True).filter(
            ~Q(inserted_to_preplan=True) & ~Q(type__gt='') & ~Q(filter_reason__gt='')
        ).delete()
        if _aborted():
            raise ImportCancelled('导入已取消：任务被取消或数据已被清空，放弃写入')
        PreplanRow.objects.bulk_create(objs, batch_size=1000)
    print(f'[导入计时] 写库(备份+删旧+插入 {len(objs)} 行) {(time.time() - _t_w):.2f}s')
    return batch_id, replaced


# ==================== 独立导入端点 ====================

def _month_warning(rows, file_year=None, confirmed_ym=None):
    """月份校验（★ 2026-09-20 改口径）：比对「文件推算出的预排月份」与「本次人工确认的归属月份」。

    旧口径是拿预排月份与【当前月】比较 —— 支持多月并存后该判断已失去意义：
    导入未来月份的计划是正常操作，却每次都会弹「与当前月份不一致」的误报（长期挂账问题）。
    现改为与人工确认值比对：
      · 未传 confirmed_ym（老调用/接口直调）→ 返回 ''，不再比较当前月；
      · 传了且推算值一致 → 返回 ''；
      · 不一致 → 提示「推算为 X，已按你确认的 Y 归入」，供用户复核是否选错月份。

    推算值的年份优先级：标签自带年份（跨年标注，如「2027年2月」）→ file_year
    （文件修改日期年份，浏览器 file.lastModified 传入）→ 行 plan_year → 当前年份。
    """
    try:
        now = datetime.now()
        months = set()
        for r in rows:
            label = str(r.get('plan_month_label') or '').strip()
            if not label:
                continue
            mm = re.search(r'(\d{1,2})\s*月', label)
            if not mm:
                continue
            mon = int(mm.group(1))
            if not 1 <= mon <= 12:
                continue
            y = None
            ym = re.search(r'(20\d{2})\s*年', label)
            if ym:
                y = int(ym.group(1))
            if y is None and file_year:
                try:
                    y = int(file_year)
                except (TypeError, ValueError):
                    y = None
            if y is None:
                y = int(r.get('plan_year') or now.year)
            months.add((y, mon))
        if not months or not confirmed_ym:
            return ''
        try:
            _cy, _cm = int(confirmed_ym) // 100, int(confirmed_ym) % 100
        except (TypeError, ValueError):
            return ''
        bad = sorted((y, m) for y, m in months if (y, m) != (_cy, _cm))
        if not bad:
            return ''
        fmt = '、'.join(f'{y}年{m}月' for y, m in sorted(months))
        return (f'⚠ 文件推算的预排月份为 {fmt}，与本次确认的归属月份（{_cy}年{_cm}月）不一致，'
                f'已按你确认的月份归入，请复核')
    except Exception:
        return ''


@csrf_exempt
@require_POST
def import_preplan_a(request):
    """
    导入 A：S13_DPS 文件
    解析 → 规则七(Type判定) → 规则一/二过滤 → 规则三(录入表1) → 规则四(ORT)
    写入 PreplanRow (source='S13_DPS')
    """
    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'success': False, 'error': '请上传 file（S13_DPS 文件）'}, status=400)
    if not file.name.endswith(('.xlsx', '.xlsm', '.xls')):
        return JsonResponse({'success': False, 'error': f'文件 {file.name} 不是 .xlsx/.xlsm/.xls 格式'}, status=400)

    year = (request.POST.get('year') or '').strip()
    try:
        year = int(year) if year else None
    except ValueError:
        return JsonResponse({'success': False, 'error': 'year 必须是整数'}, status=400)
    # ★ 文件「修改日期」年份（浏览器 file.lastModified 解析传入），仅用于月份一致性校验补年份
    file_year = (request.POST.get('file_year') or '').strip()
    try:
        file_year = int(file_year) if file_year else None
    except ValueError:
        file_year = None

    # ★ 同名文件重新导入 = 覆盖旧数据（2026-09-04）：旧行删除在 _save_rows 原子事务内完成，
    #   不再拦截，也不追加副本；已导出到审核决议的旧行不触碰

    # ★ 2026-09-20：「本次导入的预排年月」(YYYYMM) —— 导入弹窗里人工确认，可改。
    #   传了就以它为准（行归到该月 + 覆盖只在本月桶内）；没传则由文件名/表格列推算。
    try:
        ym = int(str(request.POST.get('ym') or '').strip() or 0) or None
    except ValueError:
        return JsonResponse({'success': False, 'error': 'ym 必须是 YYYYMM 格式整数（如 202609）'}, status=400)

    # ★ 导入可中断：注册任务 + 记录代际令牌（清空/删除会让代际变化，导入自动放弃写入）
    #   前端可预生成 task_id 传入，保证「取消」按钮能定位到本次任务
    client_tid = str(request.POST.get('task_id') or '').strip() or None
    task_id = import_register_task(key=(year, 'S13_DPS'), task_id=client_tid)
    captured_spec = import_generation(year, 'S13_DPS')
    captured_all = import_generation(year, None)
    try:
        result = process_single_file(file, source_type='S13_DPS', year=year, task_id=task_id, file_year=file_year)
    except ImportCancelled as e:
        import_task_finish(task_id)
        return JsonResponse({'success': False, 'cancelled': True, 'error': str(e)}, status=409)
    except ValueError as e:
        import_task_finish(task_id)
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        import_task_finish(task_id)
        return JsonResponse(
            {'success': False, 'error': f'导入异常: {e}', 'traceback': traceback.format_exc()},
            status=500,
        )

    kept = result['kept']
    filtered = result['filtered']
    stats = result['stats']
    all_rows = kept + filtered

    # ★ 人工确认的归属月份优先：一份文件同属一个预排月份，统一写死（推算值可能因文件名
    #   不含日期码而落到当月，用户确认过的值最可信）
    if ym:
        for _r in all_rows:
            _r['plan_ym'] = ym

    if not all_rows:
        import_task_finish(task_id)
        return JsonResponse({
            'success': True,
            'message': 'S13_DPS 文件没有解析到有效数据行',
            'rows': [],
            'stats': stats,
        })

    # 只清理同一来源,保留另一个来源的数据
    try:
        batch_id, replaced = _save_rows(all_rows, year, source='S13_DPS', task_id=task_id,
                                        captured_spec=captured_spec, captured_all=captured_all, ym=ym)
    except ImportCancelled as e:
        import_task_finish(task_id)
        return JsonResponse({'success': False, 'cancelled': True, 'error': str(e)}, status=409)
    # ★ 数据持久化：本批次写入 JSON 快照，误清/误删后可回溯
    _save_import_snapshot(year, 'S13_DPS', all_rows, batch_id)
    _auto_rematch_mtd(year)
    import_task_finish(task_id)

    _rqs = PreplanRow.objects.filter(plan_year=year, source='S13_DPS')
    if ym:
        _rqs = _rqs.filter(plan_ym=ym)
    rows = [preplan_row_to_dict(o) for o in _rqs.order_by('serial_number', 'id')]
    msg = f'导入完成：S13_DPS 解析 {stats["parsed_total"]} 行，通过 {stats["kept"]} 行，被过滤 {stats["filtered"]} 行'
    if ym:
        msg += f'；本次归入 {ym // 100}年{ym % 100}月'
    if replaced:
        msg += f'；同月同名文件旧数据已自动覆盖 {replaced} 行（不追加，审核决议数据不受影响）'
    return JsonResponse({
        'success': True,
        'message': msg,
        'replaced': replaced,
        'batch': batch_id,
        'plan_ym': ym,
        'stats': stats,
        'rows': rows,
        'month_warning': _month_warning(all_rows, file_year, ym),      # ★ 月份一致性提示（与本次确认的归属月比较）
    })


@csrf_exempt
@require_POST
def import_preplan_b(request):
    """
    导入 B：Monthly input target 文件
    解析 → 规则一/二过滤 → 规则三(录入表1) → 规则四(ORT)
    Type 直接取自 BU 列
    每行拆成两行（MM+1 / MM+2）
    写入 PreplanRow (source='Monthly_Input')
    """
    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'success': False, 'error': '请上传 file（Monthly input target 文件）'}, status=400)
    if not file.name.endswith(('.xlsx', '.xlsm', '.xls')):
        return JsonResponse({'success': False, 'error': f'文件 {file.name} 不是 .xlsx/.xlsm/.xls 格式'}, status=400)

    year = (request.POST.get('year') or '').strip()
    try:
        year = int(year) if year else None
    except ValueError:
        return JsonResponse({'success': False, 'error': 'year 必须是整数'}, status=400)
    # ★ 文件「修改日期」年份（浏览器 file.lastModified 解析传入），仅用于月份一致性校验补年份
    file_year = (request.POST.get('file_year') or '').strip()
    try:
        file_year = int(file_year) if file_year else None
    except ValueError:
        file_year = None

    # ★ 同名文件重新导入 = 覆盖旧数据（2026-09-04）：旧行删除在 _save_rows 原子事务内完成，
    #   不再拦截，也不追加副本；已导出到审核决议的旧行不触碰

    # ★ 2026-09-20：「本次导入的预排年月」(YYYYMM) —— 导入弹窗里人工确认，可改（同 S13）
    try:
        ym = int(str(request.POST.get('ym') or '').strip() or 0) or None
    except ValueError:
        return JsonResponse({'success': False, 'error': 'ym 必须是 YYYYMM 格式整数（如 202609）'}, status=400)

    # ★ 导入可中断：注册任务 + 记录代际令牌
    client_tid = str(request.POST.get('task_id') or '').strip() or None
    task_id = import_register_task(key=(year, 'Monthly_Input'), task_id=client_tid)
    captured_spec = import_generation(year, 'Monthly_Input')
    captured_all = import_generation(year, None)
    try:
        result = process_single_file(file, source_type='Monthly_Input', year=year, task_id=task_id, file_year=file_year)
    except ImportCancelled as e:
        import_task_finish(task_id)
        return JsonResponse({'success': False, 'cancelled': True, 'error': str(e)}, status=409)
    except ValueError as e:
        import_task_finish(task_id)
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        import_task_finish(task_id)
        return JsonResponse(
            {'success': False, 'error': f'导入异常: {e}', 'traceback': traceback.format_exc()},
            status=500,
        )

    kept = result['kept']
    filtered = result['filtered']
    stats = result['stats']
    all_rows = kept + filtered

    # ★ 人工确认的归属月份优先（同 S13）：一份文件同属一个预排月份
    if ym:
        for _r in all_rows:
            _r['plan_ym'] = ym

    if not all_rows:
        import_task_finish(task_id)
        return JsonResponse({
            'success': True,
            'message': 'Monthly input target 文件没有解析到有效数据行',
            'rows': [],
            'stats': stats,
        })

    # ★ 旧数据清理统一交给 _save_rows 的原子块处理（含取消回滚），避免事务外先删导致取消后数据丢失
    try:
        batch_id, replaced = _save_rows(all_rows, year, source='Monthly_Input', task_id=task_id,
                                        captured_spec=captured_spec, captured_all=captured_all, ym=ym)
    except ImportCancelled as e:
        import_task_finish(task_id)
        return JsonResponse({'success': False, 'cancelled': True, 'error': str(e)}, status=409)
    # ★ 数据持久化：本批次写入 JSON 快照，误清/误删后可回溯
    _save_import_snapshot(year, 'Monthly_Input', all_rows, batch_id)
    _auto_rematch_mtd(year)
    import_task_finish(task_id)

    _rqs = PreplanRow.objects.filter(plan_year=year, source='Monthly_Input')
    if ym:
        _rqs = _rqs.filter(plan_ym=ym)
    rows = [preplan_row_to_dict(o) for o in _rqs.order_by('serial_number', 'id')]
    msg = f'导入完成：Monthly input target 解析 {stats["parsed_total"]} 行，通过 {stats["kept"]} 行，被过滤 {stats["filtered"]} 行'
    if ym:
        msg += f'；本次归入 {ym // 100}年{ym % 100}月'
    if replaced:
        msg += f'；同月同名文件旧数据已自动覆盖 {replaced} 行（不追加，审核决议数据不受影响）'
    return JsonResponse({
        'success': True,
        'message': msg,
        'replaced': replaced,
        'batch': batch_id,
        'plan_ym': ym,
        'stats': stats,
        'rows': rows,
        'month_warning': _month_warning(all_rows, file_year, ym),      # ★ 月份一致性提示（与本次确认的归属月比较）
    })


# ==================== 导入任务取消 ====================

@csrf_exempt
@require_POST
def preplan_import_cancel(request):
    """★ 取消进行中的导入任务（前端「取消导入」按钮调用）"""
    data = _post_data(request)
    task_id = str(data.get('task_id') or '').strip()
    if not task_id:
        return JsonResponse({'success': False, 'error': 'task_id 必填'}, status=400)
    import_request_cancel(task_id=task_id)
    return JsonResponse({'success': True, 'message': '已请求取消导入，任务将在当前阶段结束后停止写入'})


# ==================== 旧端点（向后兼容） ====================

@csrf_exempt
@require_POST
def import_preplan(request):
    """导入 S13_DPS + Monthly input target，合并筛选后持久化（向后兼容）"""
    file_a = request.FILES.get('file_a')
    file_b = request.FILES.get('file_b')
    if not file_a or not file_b:
        return JsonResponse(
            {'success': False, 'error': '请同时上传 file_a（S13_DPS）和 file_b（Monthly input target）'},
            status=400,
        )
    for f in (file_a, file_b):
        if not f.name.endswith(('.xlsx', '.xls')):
            return JsonResponse({'success': False, 'error': f'文件 {f.name} 不是 .xlsx/.xls 格式'}, status=400)

    year = (request.POST.get('year') or '').strip()
    try:
        year = int(year) if year else None
    except ValueError:
        return JsonResponse({'success': False, 'error': 'year 必须是整数'}, status=400)
    drop_ort_n = str(request.POST.get('drop_ort_n', '')).lower() in ('1', 'true', 'yes', 'on')

    try:
        result = process_preplan(file_a, file_b, year=year, drop_ort_n=drop_ort_n)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': f'导入异常: {e}', 'traceback': traceback.format_exc()},
            status=500,
        )

    kept = result['kept']
    filtered = result['filtered']
    stats = result['stats']
    if not kept and not filtered:
        return JsonResponse({
            'success': True,
            'message': '两份文件没有解析到有效数据行',
            'rows': [],
            'stats': stats,
        })

    PreplanRow.objects.filter(plan_year=year).delete()
    batch_id, _replaced = _save_rows(kept + filtered, year)
    _auto_rematch_mtd(year)

    rows = [preplan_row_to_dict(o) for o in PreplanRow.objects.filter(plan_year=year).order_by('serial_number', 'id')]
    return JsonResponse({
        'success': True,
        'message': f'导入完成：解析 {stats["parsed_total"]} 行，通过 {len(kept)} 行，被过滤 {len(filtered)} 行',
        'batch': batch_id,
        'stats': stats,
        'rows': rows,
    })


# ==================== 查询 / 更新 / 清空 / 导出 ====================

@require_GET
def preplan_rows(request):
    """查询预排筛选结果（可只查通过/被过滤，可指定来源/预排年月/导出/存档）"""
    year = (request.GET.get('year') or '').strip()
    ym = _parse_ym(request.GET.get('ym'))          # ★ 2026-09-20 预排年月（YYYYMM）
    status = (request.GET.get('status') or '').strip()
    source = (request.GET.get('source') or '').strip()
    exported = (request.GET.get('exported') or '').strip()
    archived = (request.GET.get('archived') or '').strip()
    warning = (request.GET.get('warning') or '').strip()
    # ★ include_exported='true'（2026-09-15）：预排页专用——已导出到决议中心的行也一并返回，
    #   只加「已导出」标记展示，不再从预排工作区消失（导出后页面全空的根因）。
    #   默认空 = 旧行为（排除），决议中心/预警/存档页不受影响。
    include_exported = (request.GET.get('include_exported') or '').strip()
    qs = PreplanRow.objects.all()
    if year:
        qs = qs.filter(plan_year=int(year))
    if ym:
        # ★ 2026-09-20：按「预排年月」收窄 —— 多月并存后，每个页面视图只作用于所选月份
        qs = qs.filter(plan_ym=ym)
    if status in ('kept', 'filtered'):
        qs = qs.filter(status=status)
    if source in ('S13_DPS', 'Monthly_Input'):
        qs = qs.filter(source=source)
    if warning == 'true':
        # ★ 预警页：活动计划(通过筛选的预排行) + 计划外（计划外排末尾）
        #   ★ 不再要求 archived 定版：导入并同步MTD 后即可实时查看
        #     达标 / 预警 / 未生产 / 计划外 四类，无需先走「导出到决议 → 存档定版」。
        from django.db.models import Q
        qs = qs.filter(Q(status='kept') | Q(is_plan_external=True))
        qs = qs.order_by('is_plan_external', 'created_at', 'id')
    elif archived == 'true':
        # ★ 存档中心：已存档定版的数据（计划外排末尾）
        qs = qs.filter(archived=True)
        qs = qs.order_by('is_plan_external', 'created_at', 'id')
    elif exported == 'true':
        # ★ 审核决议页：只显示「导出到决议」的行（计划外排末尾）
        qs = qs.filter(exported=True)
        qs = qs.order_by('is_plan_external', 'created_at', 'id')
    else:
        # ★ 预排页 = 筛选工作区（2026-09-04 语义修正：与审核决议彻底分家）
        #   只显示「尚未导出到审核决议」的行（待决议 kept + 被过滤 filtered）：
        #   - 已导入审核决议的行(exported=True)归决议/预警视图所有，预排页不再展示
        #     → 清空/移除文件后预排页真正清空，决议数据独立保留、互不干扰
        #   - S13_DPS 组在前、Monthly_Input 组在后，组内按序号；计划外排末尾
        #   - 计划外实时监控项默认不插入预排筛选（inserted_to_preplan=False），
        #     预排页仅展示已插入(inserted_to_preplan=True)的计划外行；插入与否在预警界面切换
        #   ★ 2026-09-15 修正：导出到决议后预排页整页变空（头部计数还在、表格没行）。
        #     预排页是「筛选工作区」，导出行仍应留在页面上供查看/溯源，
        #     仅打「已导出」标记；真正移出预排语义的场景（清空/移除文件）另行处理。
        if include_exported != 'true':
            qs = qs.exclude(exported=True)
        qs = qs.exclude(is_plan_external=True, inserted_to_preplan=False)
        source_order = Case(When(source='S13_DPS', then=Value(0)), default=Value(1), output_field=IntegerField())
        qs = qs.order_by('is_plan_external', 'plan_year', source_order, 'serial_number', 'id')

    # ★ ORT 预警值：加载当前启用规则，为每行附加命中规则的阈值（预排筛选里的规则值，如 300）
    _ort_rules = list(OrtRule.objects.filter(is_active=True))
    _rows = []
    for _o in qs:
        _d = preplan_row_to_dict(_o)
        try:
            _key, _rule = _pick_ort_rule(_d, _ort_rules)
            _d['ort_threshold'] = _rule.threshold if _rule else ''
        except Exception:
            _d['ort_threshold'] = ''
        _rows.append(_d)
    return JsonResponse({
        'success': True,
        'total': len(_rows),
        'ym': ym,                          # ★ 本次生效的预排年月（None = 未按月收窄）
        'yms': _ym_summary(year),          # ★ 该年份下出现过的月份清单（前端下拉 + 行数）
        'mtd_total': _read_mtd_total(),   # ★ 最近一次 MTD 同步查到总数（供预警页直接恢复显示）
        'data': _rows,
    })


@csrf_exempt
@require_POST
def preplan_export_decision(request):
    """★ 导出到审核决议：叠加式（不清旧标记），可先导一个表再导另一个叠加到后面

    - source='S13_DPS'       → 只导出 S13 的「通过」行
    - source='Monthly_Input' → 只导出 S11 的「通过」行
    - source 为空(合并)       → 导出全部来源的「通过」行
    - ym（★ 2026-09-20）      → 只导出该「预排年月」的行，避免把其它月份一起带进决议
    """
    data = _post_data(request)
    year = str(data.get('year') or '').strip()
    source = str(data.get('source') or '').strip()
    ym = _parse_ym(data.get('ym'))
    if not year:
        return JsonResponse({'success': False, 'error': 'year 必填'}, status=400)
    try:
        year = int(year)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'year 必须是整数'}, status=400)

    try:
        # ★ 叠加：只标记本次导出的行，不清除已有标记（决议页顺序=导入先后）
        # ★ 计划外行：默认不插入预排筛选；仅「已插入(inserted_to_preplan=True)」的计划外
        #   随本次导出叠加进决议中心，未插入的计划外不参与（插入与否在预警界面切换）。
        qs = PreplanRow.objects.filter(plan_year=year, status='kept').filter(
            Q(is_plan_external=False) | Q(is_plan_external=True, inserted_to_preplan=True)
        )
        if source in ('S13_DPS', 'Monthly_Input'):
            qs = qs.filter(source=source)
        if ym:
            qs = qs.filter(plan_ym=ym)
        cnt = qs.update(exported=True)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'导出失败: {e}'}, status=500)
    label = {'S13_DPS': 'S13', 'Monthly_Input': 'S11'}.get(source, '合并')
    mlab = f'（{ym // 100}年{ym % 100}月）' if ym else ''
    return JsonResponse({'success': True, 'exported': cnt,
                         'message': f'已叠加导出{mlab} {label}「通过」{cnt} 行到审核决议'})


@csrf_exempt
@require_POST
def preplan_archive(request):
    """★ 保存到存档中心：把当前「导出到决议」的行标记为已存档定版(archived=True)

    ★ 2026-09-20：body 可传 ym —— 只定版所选「预排年月」的行，多月并存时互不影响。
    """
    data = _post_data(request)
    year = str(data.get('year') or '').strip()
    ym = _parse_ym(data.get('ym'))
    if year:
        try:
            year = int(year)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'year 必须是整数'}, status=400)

    qs = PreplanRow.objects.filter(exported=True)
    if year:
        qs = qs.filter(plan_year=year)
    if ym:
        qs = qs.filter(plan_ym=ym)
    # ★ 2026-09-14：定版时同时写入定版时间，供存档中心「定版时间」列追溯批次
    cnt = qs.update(archived=True, archived_at=timezone.now())
    if cnt == 0:
        return JsonResponse({'success': False, 'error': '没有可存档的数据，请先在预排页导出到决议'}, status=400)
    mlab = f'{ym // 100}年{ym % 100}月 ' if ym else ''
    return JsonResponse({'success': True, 'archived': cnt, 'message': f'已保存 {mlab}{cnt} 行到存档中心（定版）'})


@csrf_exempt
@require_POST
def preplan_unarchive(request, pk):
    """★ 撤销存档（2026-09-14）：单行 archived 置回 False，数据回到审核决议中心。

    场景：误存档 / 需要修改决议后重新定版。行数据本体不删，仅撤定版标记；
    撤销前自动备份数据库，与删除单行同等的防误操作保障。
    """
    try:
        obj = PreplanRow.objects.get(pk=pk)
    except PreplanRow.DoesNotExist:
        return JsonResponse({'success': False, 'error': '数据不存在或已删除'}, status=404)
    if not obj.archived:
        return JsonResponse({'success': False, 'error': '该行不在存档中心（未定版）'}, status=400)
    _backup_db()
    obj.archived = False
    obj.archived_at = None
    obj.save(update_fields=['archived', 'archived_at', 'updated_at'])
    return JsonResponse({'success': True, 'message': f'已撤销存档（行已回到审核决议中心）'})


@csrf_exempt
@require_POST
def preplan_clear_decision(request):
    """★ 清空审核决议：清除导出标记，决议页回到空

    ★ 2026-09-20：body 可传 ym —— 只清所选「预排年月」的导出标记（其它月份不受影响）。
    """
    data = _post_data(request)
    year = str(data.get('year') or '').strip()
    ym = _parse_ym(data.get('ym'))
    qs = PreplanRow.objects.all()
    if year:
        try:
            year = int(year)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'year 必须是整数'}, status=400)
        qs = qs.filter(plan_year=year)
    if ym:
        qs = qs.filter(plan_ym=ym)
    cnt = qs.update(exported=False)
    mlab = f'{ym // 100}年{ym % 100}月 ' if ym else ''
    return JsonResponse({'success': True, 'cleared': cnt, 'message': f'已清空{mlab}审核决议数据'})


@csrf_exempt
@require_POST
def preplan_clear_archive(request):
    """★ 清空存档中心：只清「已定版存档(archived=True) 且 计划内」的行。

    计划外行(is_plan_external=True)一律保留 —— 用户在实时监控/决议中心处理的数据
    不随「清空存档」丢失（2026-09-02 优化）。

    ★ 2026-09-20：body 可传 ym —— 只清所选「预排年月」的存档行，其它月份不受影响。

    ★ 2026-09-21 「静默空转」修复（与 preplan_clear 同口径）：
      用户报「已清空存档中心 0 条（计划外数据已保留），但页面里还有一些数据」。
      根因不是删除失败 —— 而是本接口**按设计不删计划外行**，
      而存档中心的列表接口（/preplan/rows/?archived=true）会把计划外存档行一并列出（排末尾）。
      于是当存档中心只剩计划外行时，就是「deleted=0 + 页面仍有行」，
      且前端过去无条件弹**绿色成功**，用户完全看不出「为什么还剩」。
      现在：① 回传 matched / deleted / kept_external / noop / scope（前端据此分流提示）；
            ② 查询-删除段失败回 JSON 409 + 可读原因（不再吐 HTML 500）；
            ③ 每次调用落一行审计日志 logs/destructive.log，便于事后溯源。
      注意：**删除语义不变**（计划外照样保留）—— 本次只是把「沉默」变成「会说话」。
    """
    data = _post_data(request)
    ym = _parse_ym(data.get('ym'))
    scope = {'ym': ym}
    _backup_db()
    try:
        # ★ 2026-09-22 原子化：与 preplan_clear 同因 —— 「查 external_ids → 排除后删除」
        #   两段式，中间无事务时并发写（如另一线程刚把某存档行置为计划外）会让
        #   「计划外按设计保留」失效。整段包事务，读/写同一快照。
        with transaction.atomic():
            qs = PreplanRow.objects.filter(archived=True)
            if ym:
                qs = qs.filter(plan_ym=ym)
            matched = qs.count()
            # ★ 计划外存档行按设计保留（不随「清空存档」删除 → 存档中心仍会列出它们）
            external_ids = list(qs.filter(is_plan_external=True).values_list('id', flat=True))
            deleted, _ = qs.exclude(id__in=external_ids).delete()
    except Exception as exc:
        _log_destructive('preplan/clear-archive', scope, None, 0,
                         error=f'{type(exc).__name__}: {exc}')
        return JsonResponse({
            'success': False,
            'scope': scope,
            'error': f'清空存档失败（{type(exc).__name__}: {exc}）；数据库可能正被占用，请稍后重试',
        }, status=409)
    _log_destructive('preplan/clear-archive', scope, matched, deleted, kept_external=len(external_ids))
    mlab = f'{ym // 100}年{ym % 100}月 ' if ym else ''
    msg = f'已清空存档中心 {mlab}{deleted} 条'
    if external_ids:
        msg += f'；存档中心仍有 {len(external_ids)} 条「计划外」数据按设计保留（排末尾显示，不随清空删除）'
    if not deleted and not external_ids:
        msg += '（存档中心当前没有计划内存档数据）'
    return JsonResponse({
        'success': True,
        'deleted': deleted,
        'matched': matched,
        'kept_external': len(external_ids),   # ★ 保留在页面上、本次未删的计划外行数
        'noop': deleted == 0,                 # ★ 静默空转标记：前端据此给告警而不是弹绿条
        'scope': scope,
        'message': msg,
    })


@csrf_exempt
@require_POST
def preplan_recompute_judge(request):
    """★ 实时预警：按当前 ORT 规则(OrtRule) 重新判定已导入行的 ort_ok 与 judge。

    ★ 增量筛选优化：body 可选传 source / type_name 收窄重算范围，
      修改/删除某条规则后仅重算受影响的数据（前端在保存/删除规则后调用），避免全量重算。
      - source: 'S13_DPS' | 'Monthly_Input'（只重算该来源）
      - type_name: 只重算该 Type 的行（传 '' 表示空 Type 的行）
      - ym（★ 2026-09-20）: 'YYYYMM'，只重算该「预排年月」的行
      都不传 → 全量重算（兼容旧行为）。
    """
    data = _post_data(request)
    year = str(data.get('year') or '').strip()
    source = str(data.get('source') or '').strip()
    ym = _parse_ym(data.get('ym'))
    type_name = data.get('type_name', '__all__')
    if type_name == '__all__':
        type_name = None
    try:
        from ..services.preplan_service import recompute_judge
        # ★ 2026-09-22 原子化：recompute_judge 内部是「遍历读取全部候选行 → 汇总后
        #   bulk_update 一次写回」两段式。不包事务时，并发写（导入/清空/另一处重算）
        #   会在这两步之间提交 → 本次重算结果覆盖掉别人的修改（丢失更新），
        #   也可能把已被删除的行重新写回。纯本地读+写、无外部调用，可安全持有写锁。
        with transaction.atomic():
            updated = recompute_judge(
                int(year) if year else None,
                source=source or None,
                type_name=type_name,
                ym=ym,
            )
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'预警重算失败: {e}'}, status=500)
    scope = '全量' if not source and type_name is None and not ym else f'范围{source or "*"}/{type_name or "空"}/{ym or "全月"}'
    return JsonResponse({'success': True, 'updated': updated, 'message': f'已按当前 ORT 规则{scope}重算，更新 {updated} 行'})


@csrf_exempt
@require_POST
def preplan_sync_mtd(request):
    """★ MTD OUTPUT 实时抓取：执行用户配置的 PostgreSQL SQL，更新预排表格 MTD OUTPUT监控列

    baseline 参数：
      ''/'kept'（默认）→ 计划外对比基准 = 预排筛选「通过(kept)」计划行
      'decision'       → 计划外对比基准 = 审核决议中心（exported=True 的行），
                         供预警页「刷新」调用：以决议中心当前数据为准做匹配与计划外判定
    """
    data = _post_data(request)
    year = str(data.get('year') or '').strip()
    baseline = str(data.get('baseline') or '').strip().lower()
    if baseline not in ('decision',):
        baseline = ''
    # ★ 未配置 PG 时给出友好提示，而非 500 堆栈
    try:
        from mtd_monitor_config import PG_CONFIG, MTD_SQL
        if not MTD_SQL or not MTD_SQL.strip() or PG_CONFIG.get('dbname', '') in ('', 'your_database') \
                or PG_CONFIG.get('user', '') in ('', 'your_user'):
            return JsonResponse({
                'success': False,
                'error': 'MTD 尚未配置：请先在 backend/mtd_monitor_config.py 填写 PostgreSQL 连接与 SQL',
            }, status=400)
    except Exception:
        pass
    try:
        from ..services.mtd_monitor import apply_mtd_to_preplan, MtdBusyError
        stat = apply_mtd_to_preplan(int(year) if year else None, baseline=baseline or None)
    except MtdBusyError as e:
        # ★ 2026-09-22：并发触发被互斥锁拒绝 → 409 + 可读原因（不再是 500）
        _log_destructive('preplan/sync-mtd', {'year': year or None, 'baseline': baseline or None},
                         error=f'MtdBusyError: {e}')
        return JsonResponse({
            'success': False,
            'busy': True,
            'error': f'{e}：已有同步任务在执行（可能来自导入后的自动重匹配或另一次刷新），请稍后重试',
        }, status=409)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'MTD 同步失败: {e}'}, status=500)
    _save_mtd_total(stat['total_sql'])   # ★ 持久化「查到总数」，供刷新/重进页面直接恢复显示
    return JsonResponse({
        'success': True,
        'updated': stat['updated'],
        'not_produced': stat['not_produced'],
        'external': stat['external'],
        'total_keys': stat['total_sql'],
        'sql_cost': stat['sql_cost'],
        'apply_cost': stat.get('apply_cost', 0),
        'unmatched_samples': stat.get('unmatched_samples', []),
        'message': f'MTD 同步完成：SQL 抓取 {stat["total_sql"]} 条（耗时 {stat["sql_cost"]}s）→ 本地匹配回填 {stat.get("apply_cost", 0)}s，回填 {stat["updated"]} 行，未生产置0 {stat["not_produced"]} 行，计划外 {stat["external"]} 行',
    })


@require_GET
def preplan_batches(request):
    """★ 历史存档：返回每次导入批次（按 batch_id 分组），供历史存档页面展示"""
    from django.db.models import Count, Q
    qs = (PreplanRow.objects.values('batch_id', 'plan_year', 'source')
          .annotate(
              total=Count('id'),
              kept=Count('id', filter=Q(status='kept')),
          )
          .order_by('-plan_year', '-batch_id'))
    # 取每个批次的源文件名与创建时间（用首条记录代表）
    from collections import OrderedDict
    batches = []
    seen = set()
    rep = {r['batch_id']: r for r in PreplanRow.objects.order_by('id').values('batch_id', 'source_file_name', 'created_at')}
    for r in qs:
        if r['batch_id'] in seen:
            continue
        seen.add(r['batch_id'])
        info = rep.get(r['batch_id'], {})
        batches.append({
            'batch_id': r['batch_id'],
            'plan_year': r['plan_year'],
            'source': r['source'],
            'total': r['total'],
            'kept': r['kept'],
            'filtered': r['total'] - r['kept'],
            'source_file_name': info.get('source_file_name', ''),
            'created_at': info.get('created_at'),
        })
    return JsonResponse({'success': True, 'data': batches})


@csrf_exempt
def preplan_update(request, pk):
    """更新预排结果行的可编辑字段"""
    try:
        obj = PreplanRow.objects.get(pk=pk)
    except PreplanRow.DoesNotExist:
        return JsonResponse({'success': False, 'error': '记录不存在'}, status=404)

    try:
        data = json.loads(request.body or b'{}')
    except Exception:
        data = {}

    # ★ 审核决议中心：表格展示的全部列字段均可编辑，仅 mtd_output（MTD OUTPUT监控）只读
    #   字段集合与 frontend/src/config/preplanColumns.js 的 TABLE_COLUMNS 保持一致（剔除 mtd_output）
    editable = [
        'plan_month_label', 'table_date', 'type', 'fab', 'material_code_52', 'model',
        'pn', 'customer', 'n1_dps', 'n2_dps', 'box_quantity', 'request_qty',
        'issue_qty_box', 'issue_qty_pcs', 'ort_ok', 'qe_requirement', 'qe_remark',
        'ra_remark', 'gpc_reply', 'oqc_hold', 'q_order', 'box_number', 'sample_date', 'judge', 'source',
        # ★ 2026-09-16：LongLife（审核决议中心专用列，Y / N / 空）
        'longlife',
        # ★ 实时监控「原因」列支持手动编辑（作为备注使用，如记录未送货原因）；MTD 同步不覆盖该字段
        'filter_reason',
    ]
    # ★ 整数型列：转换为 int 存储（空串按 0 处理），避免把字符串写进 IntegerField
    int_fields = {'n1_dps', 'n2_dps', 'box_quantity', 'request_qty', 'issue_qty_box', 'issue_qty_pcs'}
    # ★ 严格归一化为 'Y' / 'N' / '' 的字段（防止 Excel/前端传来 YES/NO/是/否/Y/y/true/1）
    norm_fields = {'qe_requirement', 'gpc_reply', 'oqc_hold', 'longlife'}

    def _coerce(field, value):
        """把前端传来的原始值转成该字段的存储形态（两条写入路径共用，保证口径一致）"""
        if field in int_fields:
            try:
                s = str(value).strip() if value is not None else ''
                return int(s) if s not in ('', 'None') else 0
            except (ValueError, TypeError):
                return 0
        v = str(value or '').strip()
        if field in norm_fields:
            from ..services.preplan_service import _norm_decision
            v = _norm_decision(v)
        return v

    # ★★ 2026-09-16：LongLife 副本行（决议页在 LongLife=Y 的行下方复制出来的那一份）
    #   前端以 {_copy: true, <字段>: <值>} 提交 → 只写进 longlife_copy（JSON 覆盖值），
    #   完全不触碰原行字段；未覆盖的字段前端会继续跟随原行。
    #   longlife 本身不允许在副本上改（副本的存在与否由原行决定）。
    if data.get('_copy'):
        from ..services.preplan_service import parse_longlife_copy
        overrides = parse_longlife_copy(obj.longlife_copy)
        for field in editable:
            if field not in data or field == 'longlife':
                continue
            if field == 'sample_date':
                # 副本不落 DateField，按 'YYYY-MM-DD' 字符串存。
                # ★ 空串也照样存（显式覆盖为空），不能"移除覆盖"——否则清空后会回落到原行日期，
                #   用户点了「✕ 清空」却看起来没清掉。
                overrides['sample_date'] = str(data[field] or '').strip()
            else:
                overrides[field] = _coerce(field, data[field])
        obj.longlife_copy = json.dumps(overrides, ensure_ascii=False)
        obj.save(update_fields=['longlife_copy', 'updated_at'])
        return JsonResponse({'success': True, 'message': '副本行已更新', 'id': obj.id, 'copy': True,
                             'row': preplan_row_to_dict(obj)})

    for field in editable:
        if field not in data:
            continue
        value = data[field]
        if field == 'sample_date':
            obj.sample_date = _parse_date(value)
        else:
            setattr(obj, field, _coerce(field, value))
    obj.save()
    # ★ 计划外行回填后：按 Model 补基础资料 + 按当前 ORT 规则重算 ort_ok/judge
    if obj.is_plan_external:
        recompute_external_row(obj)
    return JsonResponse({'success': True, 'message': '更新成功', 'id': obj.id,
                          'row': preplan_row_to_dict(obj)})


@csrf_exempt
@require_POST
def preplan_set_inserted(request, pk):
    """★ 计划外实时监控项：切换是否插入预排筛选（inserted_to_preplan）

    - 预警界面每行「插入/不插入」开关调用；仅对计划外行(is_plan_external=True)有效
    - 设为 True → 预排筛选界面显示该计划外行；False → 预排界面隐藏（仍在预警界面可重新插入）
    """
    try:
        obj = PreplanRow.objects.get(pk=pk)
    except PreplanRow.DoesNotExist:
        return JsonResponse({'success': False, 'error': '记录不存在'}, status=404)
    if not obj.is_plan_external:
        return JsonResponse({'success': False, 'error': '仅计划外实时监控项可切换插入预排'}, status=400)
    try:
        data = json.loads(request.body or b'{}')
    except Exception:
        data = {}
    val = data.get('inserted')
    if isinstance(val, str):
        val = val.strip().lower() in ('1', 'true', 'yes', 'on', '是')
    obj.inserted_to_preplan = bool(val)
    obj.save(update_fields=['inserted_to_preplan', 'updated_at'])
    return JsonResponse({'success': True, 'inserted': obj.inserted_to_preplan, 'message': '已更新插入预排筛选状态'})


@csrf_exempt
@require_POST
def preplan_insert_all_external(request):
    """★ 预警页「一键全部插入到审核决议中心」：所有计划外行一次性插入预排筛选并纳入决议中心

    - inserted_to_preplan=True  → 计划外行进入预排筛选（预排页可见）
    - exported=True             → 计划外行纳入审核决议中心（可审核/决议）
    """
    data = _post_data(request)
    year = str(data.get('year') or '').strip()
    ym = _parse_ym(data.get('ym'))                 # ★ 2026-09-20 只插当前所选预排年月
    qs = PreplanRow.objects.filter(is_plan_external=True)
    if year:
        try:
            qs = qs.filter(plan_year=int(year))
        except ValueError:
            return JsonResponse({'success': False, 'error': 'year 必须是整数'}, status=400)
    if ym:
        qs = qs.filter(plan_ym=ym)
    cnt = qs.update(inserted_to_preplan=True, exported=True)
    if cnt == 0:
        return JsonResponse({'success': False, 'error': '没有可插入的计划外数据'}, status=400)
    return JsonResponse({'success': True, 'inserted': cnt, 'message': f'已一键插入 {cnt} 条计划外数据到审核决议中心'})


@csrf_exempt
@require_POST
def preplan_clear(request):
    """清空预排筛选结果（可指定年份和来源，不指定则全部清空）

    ★ 数据保护（2026-09-04 修订 —— 文件删除与审核决议彻底解耦）：
      1) 已导出到审核决议的行（exported=True）【完全不动】：既不删除、也不解除导出标记。
         预排页移除/清空文件只会清理「尚未决议」的筛选数据，审核决议中心数据永不随之丢失；
         （此前行为会把已导出行解除 exported 标记 → 决议页按 exported=True 过滤后看起来被"清空"）
      2) 计划外行中「已插入预排 / 已回填 Type / 已写备注」的保留 —— 用户处理成果不随清空丢失。

    ★ 2026-09-21 「静默空转」修复：本接口过去无论删了几条都返回 200 +「已清空N条」，
      而查询/删除一旦抛错则返回 HTML 500、前端只能弹一句「清空失败」并跳过刷新 ——
      两种情况下用户看到的都是「点了清空、表格一行没少」，无从判断原因
      （即用户报的「预排筛选页面某月数据清空了之后 页面数据仍旧保留」）。
      现在：① 回传实际生效范围 scope / 命中数 matched / 删除数 deleted / noop；
            ② 查询-删除段失败回 JSON 409 + 可读原因（不再吐 HTML 500）；
            ③ 每次调用落一行审计日志 logs/destructive.log，便于事后溯源。
    """
    data = _post_data(request)
    year = str(data.get('year') or '').strip()
    source = str(data.get('source') or '').strip()
    ym = _parse_ym(data.get('ym'))                 # ★ 2026-09-20 只清当前所选预排年月
    scope = {'year': year or None, 'source': source or None, 'ym': ym}
    # ★ 导入可中断：先失效该范围所有运行中的导入任务并提升代际，
    #   保证正在进行的导入在写入前自动中止（不再把清空前的数据写回来）
    if year:
        import_invalidate(int(year), source or None)
    # ★ 数据持久化：清空前自动备份
    _backup_db()
    # ★ 2026-09-21 「静默空转」修复：查询+删除整体包 try/except。
    #   旧实现若在此处抛错（典型：SQLite `database is locked`——后台 MTD 重匹配线程正在写，
    #   或外部工具占用 DB）→ 直接吐 HTML 500，前端只能弹一句「清空失败」且**跳过数据刷新**，
    #   用户看到的就是「点了清空、表格一行没少」，无从判断是「范围没匹配到」还是「请求失败」。
    try:
        # ★ 2026-09-22 原子化：本段是「先查 exported_ids / 命中数 → 再排除后删除」两段式，
        #   不做事务时并发写会在两步之间插入（典型：导入线程刚把某行置 exported=True），
        #   导致「已导出到审核决议的行完全保留」这条保证被打破（该行仍被删掉）。
        #   包进事务后，配合 settings 的 transaction_mode=IMMEDIATE，整段开始时即取写锁，
        #   读与写看到的是同一个一致的快照。纯本地操作、无外部调用，可以安全持有写锁。
        with transaction.atomic():
            qs = PreplanRow.objects.all()
            if year:
                qs = qs.filter(plan_year=int(year))
            if source in ('S13_DPS', 'Monthly_Input'):
                qs = qs.filter(source=source)
            if ym:
                qs = qs.filter(plan_ym=ym)
            matched = qs.count()            # 生效范围内命中多少行（区分"没匹配到"与"没删掉"）
            # ★ 保护1：已导出到审核决议的行完全保留（exported=True 原样不动，决议中心数据不受影响）
            exported_ids = list(qs.filter(exported=True).values_list('id', flat=True))
            qs = qs.exclude(id__in=exported_ids)
            # ★ 保护2：已插入预排/已回填Type/已写备注 的计划外行保留
            keep_external = Q(inserted_to_preplan=True) | Q(type__gt='') | Q(filter_reason__gt='')
            qs = qs.exclude(Q(is_plan_external=True) & keep_external)
            deleted, _ = qs.delete()
    except Exception as exc:
        _log_destructive('preplan/clear', scope, None, 0, error=f'{type(exc).__name__}: {exc}')
        return JsonResponse({
            'success': False,
            'scope': scope,
            'error': f'清空失败（{type(exc).__name__}: {exc}）；数据库可能正被占用，请稍后重试',
        }, status=409)
    _log_destructive('preplan/clear', scope, matched, deleted, kept_exported=len(exported_ids))
    label = f'{year}年' if year else '所有'
    if ym:
        label += f'{ym % 100}月'
    slabel = (' ' + source) if source else ''
    msg = f'已清空{label}{slabel}共 {deleted} 条预排数据'
    if not deleted and not exported_ids:
        msg += '（该范围内没有可清空的预排行，请核对年份/月份/来源是否与表格一致）'
    if exported_ids:
        msg += f'；{len(exported_ids)} 条已导出到审核决议的数据不受影响（如需清理请到审核决议页操作）'
    return JsonResponse({
        'success': True,
        'deleted': deleted,
        'matched': matched,
        'kept_exported': len(exported_ids),
        'noop': deleted == 0,           # ★ 静默空转标记：前端据此给告警而不是弹绿条
        'scope': scope,                 # ★ 后端实际生效的过滤范围（回显，便于比对前端状态）
        'message': msg,
    })


@csrf_exempt
@require_POST
def preplan_export(request):
    """导出预排筛选结果 Excel（严格跟随法：★ 前端传入当前视图过滤后的全部行 id，
    顺序与页面完全一致，杜绝「页面未显示的全零行却出现在导出」的偏差）

    - 传入 ids：导出这些行（已含来源Tab / 通过·过滤·全部 / 客户端筛选 / 优先级排序），顺序等同页面
    - 未传 ids（兼容旧调用）：仅导出「通过筛选」status='kept'（S13 组在前、Monthly 组在后）
    """
    from django.db.models import Case, Value, When
    data = _post_data(request)
    year = str(data.get('year') or '').strip()
    ym = _parse_ym(data.get('ym'))                 # ★ 2026-09-20 未传 ids 时按所选预排年月导出
    if not year:
        return JsonResponse({'success': False, 'error': 'year 必填'}, status=400)
    try:
        year = int(year)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'year 必须是整数'}, status=400)

    ids = data.get('ids')
    if isinstance(ids, list) and ids:
        ids = [int(i) for i in ids if str(i).isdigit()]
        qs = PreplanRow.objects.filter(plan_year=year, id__in=ids)
        # ★ 严格保持页面顺序（ids 的顺序）
        preserved = Case(*[When(id=pk, then=Value(i)) for i, pk in enumerate(ids)], default=Value(len(ids)))
        qs = qs.order_by(preserved)
        rows = [preplan_row_to_dict(o) for o in qs]
    else:
        # ★ 兼容旧调用：仅「通过筛选」（若传了 ym 则只导该月）
        qs = PreplanRow.objects.filter(plan_year=year)
        if ym:
            qs = qs.filter(plan_ym=ym)
        kept = [preplan_row_to_dict(o) for o in qs.filter(status='kept').order_by('serial_number', 'id')]
        kept = sorted(kept, key=lambda r: (0 if r.get('source') == 'S13_DPS' else 1, r.get('serial_number') or 0))
        rows = kept
    if not rows:
        return JsonResponse({'success': False, 'error': f'{year} 年暂无预排数据'}, status=400)

    # ★ 不导出被过滤清单（filtered 传空）
    out = build_preplan_excel(rows, [])
    filename = f'预排筛选结果_{year}年' + (f'{ym % 100}月' if ym else '') + '.xlsx'
    response = HttpResponse(
        out.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    encoded = urllib.parse.quote(filename)
    response['Content-Disposition'] = f"attachment; filename={encoded}; filename*=UTF-8''{encoded}"
    return response


@csrf_exempt
@require_POST
def preplan_export_decision_excel(request):
    """★ 决议中心导出：导出审核决议中心当前数据（已导出到决议的行，顺序与页面一致）"""
    data = _post_data(request)
    year = str(data.get('year') or '').strip()
    ym = _parse_ym(data.get('ym'))                 # ★ 2026-09-20 只导当前所选预排年月
    qs = PreplanRow.objects.filter(exported=True)
    if year:
        try:
            qs = qs.filter(plan_year=int(year))
        except ValueError:
            return JsonResponse({'success': False, 'error': 'year 必须是整数'}, status=400)
    if ym:
        qs = qs.filter(plan_ym=ym)
    rows = [preplan_row_to_dict(o) for o in qs.order_by('created_at', 'id')]
    if not rows:
        return JsonResponse({'success': False, 'error': '决议中心暂无数据，请先在预排页导出到决议'}, status=400)

    # ★ 2026-09-16（用户明确）：
    #   ① 导出带「LongLife」列；
    #   ② LongLife=Y 在页面上派生出来的「副本行」**不导出**（那只是给员工填写的便利，不是独立数据）；
    #   ③ 把副本里填的 Q工单用 '/' 并到原行的 Q工单上（原行空则不出现前导 '/'）。
    #   ②③ 由 build_preplan_excel(include_longlife=True) 内部统一完成，这里只需开关。
    # 与决议页显示顺序一致（导入先后）；决议中心数据均为已通过(kept)
    out = build_preplan_excel(rows, [], include_longlife=True)
    filename = f'审核决议_{year or "全部"}年' + (f'{ym % 100}月' if ym else '') + '.xlsx'
    response = HttpResponse(
        out.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    encoded = urllib.parse.quote(filename)
    response['Content-Disposition'] = f"attachment; filename={encoded}; filename*=UTF-8''{encoded}"
    return response


@require_GET
def preplan_months(request):
    """返回有预排数据的年份列表（★ 2026-09-20 每年附带 yms 月份清单）"""
    years = (
        PreplanRow.objects
        .values('plan_year')
        .distinct()
        .order_by('-plan_year')
    )
    data = []
    for y in years:
        year = y['plan_year']
        kept = PreplanRow.objects.filter(plan_year=year, status='kept').count()
        filtered = PreplanRow.objects.filter(plan_year=year, status='filtered').count()
        data.append({
            'year': year, 'kept': kept, 'filtered': filtered, 'total': kept + filtered,
            'yms': _ym_summary(year),          # ★ 该年下的预排年月清单（含 0=未归类）
        })
    return JsonResponse({'success': True, 'data': data})


@csrf_exempt
@require_POST
def preplan_export_archive_excel(request):
    """★ 存档中心导出：导出已存档定版(archived)的数据为 Excel

    ★ 2026-09-14：导出跟随页面筛选——body 可传 year / month，与存档中心页面下拉一致；
      文件名带筛选条件与时间戳，避免多次导出互相覆盖。
      ★ 2026-09-14 追加：body 可传 split_by_month=true，按「年份+月份」拆成多个 sheet，
        一次导出即可拿到分月明细表（跨年同名月份不会冲突，因为 key 含年份）。
    """
    data = _post_data(request)
    year = str(data.get('year') or '').strip()
    # ★ month 是裸月份标签（plan_month_label，真实格式 '9月' 不带年份），
    #   文件名由后端把 year + month 拼成 '2026年9月'，避免跨年同名月份无法区分。
    month = str(data.get('month') or '').strip()
    # ★ 2026-09-20：优先用 ym（YYYYMM 数值）收窄——比 '9月' 文本稳，且天然区分跨年同名月份。
    ym = _parse_ym(data.get('ym'))
    split_by_month = bool(data.get('split_by_month'))
    qs = PreplanRow.objects.filter(archived=True)
    if year:
        try:
            qs = qs.filter(plan_year=int(year))
        except ValueError:
            return JsonResponse({'success': False, 'error': 'year 必须是整数'}, status=400)
    if ym:
        qs = qs.filter(plan_ym=ym)
    elif month:
        qs = qs.filter(plan_month_label=month)
    rows = [preplan_row_to_dict(o) for o in qs.order_by('created_at', 'id')]
    if not rows:
        return JsonResponse({'success': False, 'error': '存档中心暂无数据'}, status=400)
    out = build_preplan_excel(rows, [], split_by_month=split_by_month, sheet_title='存档定版')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # ★ 文件名拼接规则：有 ym → 「2026年9月」；有 month → 「9月」；有 year → 「2026年」；都没有 → 「全部」
    if ym:
        label = f'{ym // 100}年{ym % 100}月'
    elif year and month:
        label = f'{year}年{month}'
    elif month:
        label = month
    elif year:
        label = f'{year}年'
    else:
        label = '全部'
    filename = f'存档中心_{label}{"_分月" if split_by_month else ""}_{stamp}.xlsx'
    response = HttpResponse(
        out.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    encoded = urllib.parse.quote(filename)
    response['Content-Disposition'] = f"attachment; filename={encoded}; filename*=UTF-8''{encoded}"
    return response


@csrf_exempt
@require_POST
def preplan_delete(request, pk):
    """★ 删除指定单行（处理误导入/测试数据）"""
    try:
        obj = PreplanRow.objects.get(pk=pk)
    except PreplanRow.DoesNotExist:
        return JsonResponse({'success': False, 'error': '数据不存在或已删除'}, status=404)
    # ★ 导入可中断：删除单行同样失效该年份/来源的导入任务与代际，
    #   防止正在进行的导入把该行所属批次数据重新写回
    import_invalidate(obj.plan_year, obj.source)
    # ★ 数据持久化：删除前自动备份
    _backup_db()
    obj.delete()
    return JsonResponse({'success': True, 'message': '已删除该行'})


@csrf_exempt
@require_POST
def preplan_refresh_entry(request):
    """★ 刷新：①录入表1 变更回填 ②按当前 ORT 规则重算 ort_ok/judge（修改/新增/删除规则后无需重新导入）"""
    data = _post_data(request)
    year = str(data.get('year') or '').strip()
    try:
        year = int(year) if year else None
    except ValueError:
        return JsonResponse({'success': False, 'error': 'year 必须是整数'}, status=400)
    try:
        from ..services.preplan_service import recompute_judge
        updated_backfill = refresh_entry_backfill(year)
        updated_judge = recompute_judge(year)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'刷新异常: {e}'}, status=500)
    return JsonResponse({
        'success': True,
        'updated': updated_backfill,
        'judge_updated': updated_judge,
        'message': f'已刷新：客户基础资料回填 {updated_backfill} 行，按当前 ORT 规则重算 {updated_judge} 行（无需重新导入）',
    })


class EntryTableViewSet(viewsets.ModelViewSet):
    """基础资料表 维护（P/N 主数据，永久有效）"""
    queryset = EntryTable.objects.all()
    serializer_class = EntryTableSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['pn', 'model', 'material_code_52', 'customer']
    ordering_fields = ['pn', 'model', 'updated_at']
    ordering = ['pn']


class OrtRuleViewSet(viewsets.ModelViewSet):
    """ORT 规则维护"""
    queryset = OrtRule.objects.all()
    serializer_class = OrtRuleSerializer
