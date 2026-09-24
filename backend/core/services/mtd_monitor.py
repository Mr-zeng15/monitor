# -*- coding: utf-8 -*-
"""
MTD OUTPUT 实时抓取服务 v5
===========================
v5 修正（★ 预警严格只对「筛选后通过」的数据匹配）：
  [v5-1] 计划基准 = 筛选后通过的行：PreplanRow.filter(status='kept', is_plan_external=False)
         不再用 archived（存档定版）作为基准，也不再拿全部行（含 filtered）匹配。
         被过滤(filtered)的行不参与 MTD 匹配 / 计划外判断 / 预警。
  [v5-2] 不做「本月过滤」：plan_month_label 是 N+1（下个月），
         用当前月过滤会把所有计划行清空 → 全部误判计划外（沿用 v4 结论）。
  [v5-3] 严格按 P/N（SQL 的 part_no 列）与计划匹配，不再用 Model 兜底；
         model 名称显示也统一取自 SQL 查询结果的 model 列（而非计划文件里的 model）。
  [v5-4] 计划外行：SQL 有、筛选后通过的 kept 计划里没有 → 计划外（新增/更新/清理差异更新）。
  [v5-5] 关键诊断 print() 输出，确保一定可见。

匹配规则：
  1. kept 计划中有、SQL 也有（P/N 匹配）→ 回填具体产量
  2. kept 计划中有、SQL 无完全匹配 → 视为「未生产」，产量回填 0（前端换色标注）
  3. SQL 中有、kept 计划中不存在 → 视为「计划外」，新增并回填到预警

用法：
    1. 编辑 backend/mtd_monitor_config.py（填 PG 连接 + SQL）
    2. 手动触发：POST /api/preplan/sync-mtd/（前端「同步MTD」按钮）
"""
import logging
import re
import threading
import time

logger = logging.getLogger(__name__)

_KNOWN_SOURCES = ('s13', 's11', '')

# ★ 2026-09-22 并发互斥：apply_mtd_to_preplan 会被多处并发触发 ——
#   ① 预警页「刷新」按钮（请求线程）② 导入后的后台自动重匹配线程（_auto_rematch_mtd）
#   ③ 其它调用点。三者的「读取基准行 → bulk_update 回填 / 计划外差异更新」若交叉执行，
#   会产生重复建行、互相覆盖、统计口径错乱。MTD 回填本身是幂等的（下次同步会自我纠正），
#   但并发交叉既产生瞬时错数据、又放大 SQLite 锁竞争，故用进程内锁串行化。
#   （服务为单进程多线程部署 → threading.Lock 即全局互斥；与项目既有的
#    bot_refresh._lock / import_task._lock / preplan_views._mtd_rematch_lock 同一套做法。）
_apply_lock = threading.Lock()


class MtdBusyError(RuntimeError):
    """MTD 回填正在进行中（并发触发被拒）。调用方应提示「稍后重试」而非报 500。"""

# ★ 2026-09-18 性能：MTD 抓取结果短 TTL 缓存。
#   仅当调用方显式传 cache_ttl>0 时启用 —— 导入后的「自动重匹配」走后台线程 + 缓存，
#   同一批导入在 TTL 内只打一次外部 PG；手动「同步MTD」按钮不传 → 始终取实时值。
_FETCH_CACHE = {'ts': 0.0, 'rows': None, 'cost': 0.0}


def _normalize(s):
    """匹配键归一化：去所有空白 + 转大写，避免空格/大小写导致匹配不上"""
    return re.sub(r'\s+', '', str(s or '')).upper()


# ─────────────────────────────────────────────────────────────────────────────
# fetch_mtd_rows：执行 SQL，返回 [{model, pn, value, source}, ...]
# ─────────────────────────────────────────────────────────────────────────────
def fetch_mtd_rows(sql=None, cache_ttl=0):
    """
    执行 MTD SQL，返回 (rows, 耗时秒数)。
    - 值取最后一列；model/pn 按列名自动识别；
    - source 列（如新 SQL 的 source='s13'/'s11'）自动识别并透传，
      供 apply_mtd_to_preplan 按来源分离匹配与预警规则。
    ★ cache_ttl>0（且用默认 SQL）时：TTL 内命中缓存直接返回，避免导入批次内反复打外部 PG。
    """
    from mtd_monitor_config import MTD_SQL, PG_CONFIG
    import psycopg2

    is_default_sql = not sql
    if cache_ttl and is_default_sql and _FETCH_CACHE['rows'] is not None \
            and (time.time() - _FETCH_CACHE['ts']) < cache_ttl:
        logger.info('MTD 抓取命中缓存（%.0fs 内），跳过外部 SQL', cache_ttl)
        return _FETCH_CACHE['rows'], 0.0

    sql = sql or MTD_SQL
    if not sql or not sql.strip():
        raise ValueError('MTD_SQL 为空，请先在 mtd_monitor_config.py 中填写 SQL')

    conn = None
    t0 = time.time()
    try:
        conn = psycopg2.connect(
            host=PG_CONFIG.get('host') or '127.0.0.1',
            port=PG_CONFIG.get('port') or 5432,
            dbname=PG_CONFIG.get('dbname') or '',
            user=PG_CONFIG.get('user') or '',
            password=PG_CONFIG.get('password') or '',
            connect_timeout=15,
        )
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [d[0].lower() for d in cur.description] if cur.description else []
            if not columns:
                raise ValueError('MTD_SQL 没有返回任何列')

            # 识别列：model / pn / source / 值(最后一列)
            model_idx = next((i for i, c in enumerate(columns) if 'model' in c), None)
            pn_idx = next((i for i, c in enumerate(columns) if 'part' in c or c == 'pn' or 'p/n' in c), None)
            src_idx = next((i for i, c in enumerate(columns) if 'source' in c or c == 'src' or '来源' in c), None)
            val_idx = len(columns) - 1

            rows = []
            for row in cur.fetchall():
                model = str(row[model_idx]).strip() if (model_idx is not None and row[model_idx] is not None) else ''
                pn = str(row[pn_idx]).strip() if (pn_idx is not None and row[pn_idx] is not None) else ''
                val = row[val_idx] if val_idx < len(row) else None
                src = ''
                if src_idx is not None and src_idx < len(row) and row[src_idx] is not None:
                    src = str(row[src_idx]).strip().lower()
                rows.append({'model': model, 'pn': pn, 'value': val, 'source': src})
            cost = round(time.time() - t0, 2)
            logger.info('MTD 抓取完成：%d 条，SQL 耗时 %.2fs（列: %s）', len(rows), cost, columns)
            if is_default_sql:
                _FETCH_CACHE.update({'ts': time.time(), 'rows': rows, 'cost': cost})
            return rows, cost
    finally:
        if conn:
            conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# apply_mtd_to_preplan：抓取 MTD 并回填「筛选后通过」的计划行 + 计划外
# ─────────────────────────────────────────────────────────────────────────────
def apply_mtd_to_preplan(year=None, match_key=None, baseline=None, cache_ttl=0):
    """★ 2026-09-22 并发互斥入口：同一时刻只允许一个 MTD 回填在跑。

    并发触发（手动刷新 / 导入后自动重匹配 / 定时任务）若同时进入，会交叉执行
    「读基准行 → 回填」，产生重复行与互相覆盖。此处**非阻塞**取锁：
    已有任务在跑 → 立即抛 MtdBusyError，由调用方转成友好提示（409）。
    刻意不排队等待 —— 排队会让手动刷新挂到超时，也违背项目「外部调用不阻塞请求」的约定。
    """
    if not _apply_lock.acquire(blocking=False):
        raise MtdBusyError('MTD 同步正在进行中')
    try:
        return _apply_mtd_to_preplan_impl(
            year=year, match_key=match_key, baseline=baseline, cache_ttl=cache_ttl)
    finally:
        _apply_lock.release()


def _apply_mtd_to_preplan_impl(year=None, match_key=None, baseline=None, cache_ttl=0):
    """
    抓取 MTD 数据并回填。返回统计 dict：
      updated      = 回填了具体产量的行数
      not_produced = 计划有但 SQL 无 → 产量置 0 的「未生产」行数
      external     = SQL 有但计划无 → 计划外新增行数
      total_sql    = SQL 抓取到的总条数
      sql_cost     = SQL 执行耗时(秒)

    baseline：
      None/''（默认）→ 计划外对比基准 = 预排筛选「通过(kept)」计划行（v5 语义）
      'decision'    → 计划外对比基准 = 审核决议中心（exported=True 的行），
                      由预警页「刷新」触发：以决议中心当前数据（含已补充的计划外行）为准
    """
    from core.models import PreplanRow
    from django.utils import timezone

    raw_rows, sql_cost = fetch_mtd_rows(cache_ttl=cache_ttl)
    _t0 = time.time()  # ★ 本地处理计时（匹配/回填/计划外差异更新）

    # ★ 按 SQL source 分离建立索引（s13 / s11 / 空=旧SQL无source列）
    #   ★ 严格按 P/N(part_no) 匹配：仅建 P/N 索引，不再用 Model 精确 / 前缀兜底。
    #   ★ 索引值同时存 value 与 model —— model 取 SQL 查询出来的，回填时覆盖显示。
    maps = {src: {} for src in _KNOWN_SOURCES}
    for r in raw_rows:
        v = str(r['value']).strip()
        src = (r.get('source') or '').strip().lower()
        if src not in maps:
            src = ''
        pn = _normalize(r['pn'])
        if pn:
            maps[src].setdefault(pn, {'value': v, 'model': str(r.get('model', '') or '').strip()})

    if baseline == 'decision':
        # ★ 基准 = 审核决议中心（exported=True）：包含已通过的 kept 计划 + 已插入决议中心的计划外行
        qs = PreplanRow.objects.filter(exported=True)
        if year:
            qs = qs.filter(plan_year=year)
        all_plan_rows = list(qs)
    else:
        # ★ 计划基准 = 筛选后通过的行（status='kept'），排除计划外，排除被过滤(filtered)行
        qs = PreplanRow.objects.filter(status='kept', is_plan_external=False)
        if year:
            qs = qs.filter(plan_year=year)
        all_plan_rows = list(qs)

    # ★ 所有基准计划（任何排产月份）的 P/N 集合，用于「计划外」判断——
    #   只要 P/N 在基准计划里存在（哪怕排产月份未到），就不算计划外，只是本月没数据
    all_plan_pns = set()
    for obj in all_plan_rows:
        pn = _normalize(obj.pn)
        if pn:
            all_plan_pns.add(pn)

    # ★ 预警 SQL 固定取「本月」产量（见 mtd_monitor_config.MTD_SQL 的 DATE_TRUNC('month', CURRENT_DATE)），
    #   因此仅预排月份 == 本月的计划行才参与匹配/回填/未生产判定；
    #   非本月计划（如 S13 的 N+2、S11 的 N+1 未来月份）不匹配、不回填，避免把本月产量错误关联到其他月份计划。
    now = timezone.now()
    def _plan_month(obj):
        label = obj.plan_month_label or ''
        m = re.search(r'(\d+)月', label)
        y = re.search(r'(\d+)年', label)
        month = int(m.group(1)) if m else 0
        py = int(y.group(1)) if y else (obj.plan_year or now.year)
        return (py, month)

    # 只处理计划行（回填 / 未生产置 0）——★ 仅本月计划参与（外部行由下方计划外差异更新处理）
    rows = [obj for obj in all_plan_rows
            if not obj.is_plan_external and _plan_month(obj) == (now.year, now.month)]

    # ★ 计划行期望的 SQL 来源：S13_DPS → s13；Monthly_Input → s11；
    #   查找时先查对应来源索引，查不到再兜底「空来源」（兼容旧 SQL 无 source 列）
    def _plan_expected_src(obj):
        if obj.source == 'S13_DPS':
            return 's13'
        if obj.source == 'Monthly_Input':
            return 's11'
        return ''

    def _lookup_value(pn, model, expect):
        # ★ 严格 P/N 匹配：仅按 part_no 查索引，不再用 model 精确 / 前缀兜底
        for src in (expect, '') if expect else ('',):
            m = maps[src]
            if pn and pn in m:
                return m[pn], src
        return None, None

    matched_pns = set()
    to_update = []
    not_produced = []
    unmatched_samples = []  # ★ 诊断：计划有但 SQL 没匹配到的样本(pn/model)

    for obj in rows:
        pn = _normalize(obj.pn)
        model = _normalize(obj.model)
        expect = _plan_expected_src(obj)
        val, hit_src = _lookup_value(pn, model, expect)
        if hit_src and pn:
            matched_pns.add(pn)

        if val is None:
            # ★ 计划有但 SQL 无 → 未生产，产量置 0（前端换色标注）
            if str(obj.mtd_output or '').strip() != '0':
                obj.mtd_output = '0'
                not_produced.append(obj)
            if len(unmatched_samples) < 5:
                unmatched_samples.append(f'{obj.pn}/{obj.model}(期望来源{expect or "任意"})')
        else:
            changed = False
            m_val = str(val['value']).strip()
            # ★ 回填产量
            if str(obj.mtd_output or '').strip() != m_val:
                obj.mtd_output = m_val
                changed = True
            # ★ model 名称显示用 SQL 查询出来的（而非计划文件里的 model）
            m_model = str(val.get('model', '') or '').strip()
            if m_model and str(obj.model or '').strip() != m_model:
                obj.model = m_model
                changed = True
            if changed:
                to_update.append(obj)

    if to_update:
        PreplanRow.objects.bulk_update(to_update, ['mtd_output', 'model', 'updated_at'])
    if not_produced:
        PreplanRow.objects.bulk_update(not_produced, ['mtd_output', 'updated_at'])

    # 计划外：SQL 有但 kept 计划无 → ★ 差异更新（增量优化）：
    #   已存在的计划外行按 pn 复用，仅更新 MTD 值（保留操作人员回填的 type/judge 等）；
    #   新出现的行创建；SQL 已消失的旧计划外行删除，避免每次同步全删全建造成抖动。
    # ★ 计划外行默认不参与决议中心：仅重置「未手动插入」的自动行 exported=False。
    #   ★ 关键修复：不再 blanket 重置全部计划外行，避免把用户「一键插入决议中心」
    #     (inserted_to_preplan=True) 的修改冲掉——该修改必须在执行 SQL 后保留不丢失。
    PreplanRow.objects.filter(is_plan_external=True).exclude(inserted_to_preplan=True).update(exported=False)
    # ★ 计划外行的「预排月份」= 本次执行 SQL 的时刻所属月份（北京时间，裸月份如 '9月'）。
    #   计划外没有来源计划文件，原先该列恒为空 → 进决议中心后永远补不上月份。
    #   取一次即可：整批计划外行同属一个同步批次，月份必然一致。
    _now_local = timezone.localtime(timezone.now())
    ext_year = year or _now_local.year
    ext_month_label = f'{_now_local.month}月'
    # ★ 2026-09-20 预排年月（YYYYMM）：与 plan_month_label 同源，供「按月分类」维度使用。
    ext_ym = ext_year * 100 + _now_local.month
    existing_ext = {}
    for o in PreplanRow.objects.filter(is_plan_external=True, plan_year=ext_year):
        k = _normalize(o.pn) or _normalize(o.model)
        if k:
            existing_ext[k] = o

    def _infer_type_for_s13(pn):
        """★ s13 来源的计划外行：按 P/N 左 2 位自动推 Type（与规则七一致），
        无需人工回填即可按 S13 规则判定 ORT；s11 仍需人工回填 Type"""
        left2 = (pn or '').strip().upper()[:2]
        if left2 == '97':
            return 'BIM'
        if left2 in ('93', '99'):
            return 'SET'
        return ''

    external_new = []          # 需要新建
    external_update = []       # 需要更新 mtd_output
    external_stale = []        # SQL 已不存在 → 删除
    seen_keys = set()
    created_keys = set()       # ★ 本次同步内已新建的键，防止 SQL 未去重时重复建行（重复累积根因）
    for r in raw_rows:
        pn = _normalize(r['pn'])
        src = (r.get('source') or '').strip().lower()
        if src not in ('s13', 's11'):
            src = ''
        # ★ 计划外判断：对比「基准计划 P/N 集合」（默认=筛选后通过 kept 计划；
        #   baseline='decision' 时=审核决议中心 exported 行）。只要 P/N 在基准里存在就不算计划外。
        #   ★ 严格 P/N 匹配：仅按 P/N 判断，不再用 model 兜底
        #   ★ hit 仅阻止「新建」，已存在的计划外行（existing_ext）仍照常更新 mtd_output，
        #     避免基准扩大（如决议中心已纳入该 P/N）后已有计划外行不再更新。
        hit = (pn and pn in all_plan_pns)
        key = pn
        if not key:
            continue
        seen_keys.add(key)
        val = str(r['value']).strip()
        ext = existing_ext.get(key)
        if ext is None and key in created_keys:
            # ★ 同一同步内重复出现的键（SQL 未 GROUP BY 去重时）不再建第二行
            continue
        if ext is None:
            if hit:
                # ★ 基准内已有该 P/N（如已在预排计划/决议中心）→ 不算计划外，不新建
                continue
            created_keys.add(key)
            external_new.append(PreplanRow(
                batch_id='MTD_EXTERNAL',
                plan_year=ext_year,
                plan_ym=ext_ym,                      # ★ 同步时刻所属预排年月（YYYYMM）
                plan_month_label=ext_month_label,   # ★ 同步时刻所属月份
                serial_number=0,
                status='kept',
                source='MTD_EXTERNAL',  # ★ 独立来源，避免 clear 指定 S13/Monthly 时误删计划外
                model=r['model'],
                pn=r['pn'],
                mtd_output=val,
                is_plan_external=True,
                mtd_source=src,           # ★ 记录 SQL 来源(s13/s11)，供预警规则区分
                type=_infer_type_for_s13(pn) if src == 's13' else '',  # ★ s13 自动推 Type
                inserted_to_preplan=False,  # ★ 计划外默认不插入预排筛选（预警界面可切换）
                exported=False,    # ★ 计划外默认不纳入决议中心
                archived=True,     # ★ 同步进存档中心/预警
            ))
        elif str(ext.mtd_output or '').strip() != val or (ext.mtd_source or '').strip() != src:
            ext.mtd_output = val
            if src and (ext.mtd_source or '').strip() != src:
                ext.mtd_source = src  # ★ 补全来源：旧 SQL 无 source 列建的行，新 SQL 带 source 后补齐
            external_update.append(ext)
    # SQL 已消失的旧计划外行 → 删除
    for key, o in existing_ext.items():
        if key in seen_keys:
            continue
        # ★ 关键修复：仅清理「纯自动生成、用户从未触碰」的计划外行；
        #   凡用户已插入决议中心(inserted_to_preplan) / 已回填 Type / 已写备注(filter_reason) 的条目，
        #   即使本次 SQL 未返回也一律保留，绝不删除——确保执行 SQL 后用户完成的修改不丢失。
        if o.inserted_to_preplan or (o.type or '').strip() or (o.filter_reason or '').strip():
            continue
        external_stale.append(o)

    if external_update:
        # ★ 仅更新产量/来源；filter_reason（实时监控「原因」列的用户备注）保留，MTD 不覆盖不清空
        PreplanRow.objects.bulk_update(external_update, ['mtd_output', 'mtd_source', 'updated_at'])
    # ★ 存量计划外行若缺月份（历史同步建的行），按本次同步时刻补上；已有值的一律不覆盖。
    #   单独一条语句，不并入 external_update，避免污染「更新 N 行」的统计口径。
    PreplanRow.objects.filter(
        is_plan_external=True, plan_year=ext_year, plan_month_label=''
    ).update(plan_month_label=ext_month_label, plan_ym=ext_ym)
    # ★ 2026-09-20 补充：已有月份文本但 plan_ym 仍为 0 的历史计划外行（迁移回填不到），按 ext_ym 补齐。
    PreplanRow.objects.filter(
        is_plan_external=True, plan_year=ext_year, plan_ym=0
    ).update(plan_ym=ext_ym)
    if external_new:
        PreplanRow.objects.bulk_create(external_new, batch_size=1000)
    if external_stale:
        PreplanRow.objects.filter(id__in=[o.id for o in external_stale]).delete()

    external = external_new + external_update

    apply_cost = round(time.time() - _t0, 2)  # ★ 本地处理耗时（匹配/回填/计划外差异更新）

    print(f'[MTD-v5] 计划基准 kept {len(all_plan_rows)} 行（本月参与匹配 {len(rows)} 行）| SQL {len(raw_rows)} 条 | '
          f'回填 {len(to_update)} | 未生产置0 {len(not_produced)} | 计划外 新增{len(external_new)}/更新{len(external_update)}/清理{len(external_stale)} | '
          f'SQL {sql_cost}s 本地 {apply_cost}s')
    if unmatched_samples:
        print(f'[MTD-v5] 未匹配样本（计划有但SQL无，前5个 pn/model）：{unmatched_samples}')
    logger.info('MTD 回填 %d 行，未生产 %d 行，计划外新增 %d/更新 %d/清理 %d（抓取 %d 键，SQL %.2fs，本地 %.2fs）',
                len(to_update), len(not_produced), len(external_new), len(external_update),
                len(external_stale), len(raw_rows), sql_cost, apply_cost)
    return {
        'updated': len(to_update),
        'not_produced': len(not_produced),
        'external': len(external),
        'total_sql': len(raw_rows),
        'sql_cost': sql_cost,
        'apply_cost': apply_cost,
        'unmatched_samples': unmatched_samples,
    }
