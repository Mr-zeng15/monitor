# -*- coding: utf-8 -*-
"""★ 2026-09-16：QC_AI_TEAM · AI Agent 专案登记（前后端版）

原版是单文件纯前端页（`QC_AI_TEAM V4.txt`），台账存在浏览器 localStorage：
  `qcat_p4` 专案列表 / `qcat_c4` 分类配置
-> 换电脑、换浏览器就看不到，也没有备份与并发控制。

本模块把数据搬到服务端，**功能与原版逐项对齐**：
  · bootstrap            一次取回 项目 + 分类 + 内建项 + 前缀映射（等价原版启动时的 loadCats/loadProjects）
  · projects/save        新增/修改（等价 saveRecord，含必填校验、工作英文校验、名称唯一校验、名称服务端生成）
  · projects/status      废除 / 恢复（等价 chStatus）
  · projects/delete      永久删除（等价 askDel）
  · next-seq             流水码自动分配（等价 autoAssign）
  · cats/add|remove      分类项增删（等价 addCatItem/removeCat，内建项不可删）
  · export / import      JSON 备份与汇入（兼容原版导出的 JSON 结构，可直接互相导入）

★ 所有写操作都返回「最新全量状态」(projects + cats)，前端直接整体替换即可，
  不做增量合并 —— 数据量小，且能保证界面与服务端永远一致（原版也是 saveProjects 后整体 refresh）。
"""
import json
import random
import time as _time

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..models import QcAgentCategory, QcAgentProject

# ── 与原版一致的常量（原版 script 顶部 CONFIG 段）──
PREFIX_MAP = {'风控卫士': 'QCWF', '问答型': 'QCRG', '流程自动化': 'QCAF', '邮件自动化': 'QCMF'}
BUILTIN_CATS = {
    'group': ['风控卫士', '问答型', '流程自动化', '邮件自动化'],
    'subtype': ['IPQC', 'OQC', 'SQC', 'ORT'],
    'arch': ['Sagent', 'myagent', 'python'],
    'dev': ['Shinya', 'Taibin', 'Huifang', 'Ling', 'Jason'],
}
CAT_KINDS = ('group', 'subtype', 'arch', 'dev')
STATUSES = ('开发中', '使用中', '废除')
BTYPES = ('', '耗时', '人力')

WORK_RE = r'^[A-Za-z0-9_]+$'


# ════════════════════════════════════════════════════════════
#  兼容工具
# ════════════════════════════════════════════════════════════
def _post_data(request):
    """兼容 JSON body 与表单 POST（前端 axios 默认发 JSON）"""
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or b'{}')
        except Exception:
            return {}
    return request.POST


def _s(v, limit=None):
    """统一转字符串并 strip（None → ''），可选截断。"""
    s = '' if v is None else str(v).strip()
    return s[:limit] if limit else s


def _gen_qc_id():
    """沿用原版 id 生成口味：毫秒时间戳 36 进制 + 随机后缀（仅需唯一，不承载语义）。"""
    base = ''
    n = int(_time.time() * 1000)
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    while n:
        base = alphabet[n % 36] + base
        n //= 36
    suffix = ''.join(random.choice(alphabet) for _ in range(10))
    return (base + suffix)[:32]


def _make_name(group, subtype, work, seq):
    """Agent 名称规则：{前缀}_{3位流水码}_{子类型}_{工作}（与原版 updateName 一致）。

    ★ 2026-09-21（用户）：流水码为空时**不再塞 '___' 占位** ——
      原写法 `f"{prefix}_{'___'}_…"` 会把「分隔符 + 占位 + 分隔符」连成 5 个下划线
      （QCWF_____FUNCTION_XXX），看起来像名称坏了。现在空段直接跳过，只留一个分隔符：
      QCWF_FUNCTION_XXX。流水码填了仍旧 3 位补零，格式不变。
      （注：保存接口本就强制 seq 必填，这条主要影响预览/兜底路径，与前端 genName 逐字对齐。）
    """
    prefix = PREFIX_MAP.get(group)
    if not prefix:
        return ''
    seq_s = (seq or '').zfill(3) if seq else ''
    seg = [prefix, seq_s, subtype or 'FUNCTION', work or 'XXX']
    return '_'.join([s for s in seg if s])


def _ensure_builtin_cats():
    """首次访问时把内建分类落库（等价原版 loadCats 的默认值）。"""
    existing = set(QcAgentCategory.objects.values_list('kind', 'name'))
    to_create = []
    for kind, names in BUILTIN_CATS.items():
        for i, nm in enumerate(names):
            if (kind, nm) not in existing:
                to_create.append(QcAgentCategory(kind=kind, name=nm, is_builtin=True, sort=i))
    if to_create:
        QcAgentCategory.objects.bulk_create(to_create, ignore_conflicts=True)


def _cats_dict():
    """{'group': [...], 'subtype': [...], ...}（顺序：sort, id）"""
    out = {k: [] for k in CAT_KINDS}
    for c in QcAgentCategory.objects.all():
        if c.kind in out:
            out[c.kind].append(c.name)
    return out


def _project_dict(p):
    """与原版 rec 字段逐项对齐（含 id / updatedAt，前端逻辑零改动）。"""
    return {
        'id': p.qc_id,
        'group': p.group,
        'subtype': p.subtype,
        'work': p.work,
        'seq': p.seq,
        'name': p.name,
        'arch': p.arch,
        'status': p.status,
        'dev': p.dev or '',
        'desc': p.desc or '',
        'success': p.success or '',
        'accuracy': p.accuracy or '',
        'token': p.token or '',
        'time': p.time or '',
        'btype': p.btype or '',
        'bval': p.bval or '',
        'updatedAt': timezone.localtime(p.updated_at).isoformat() if p.updated_at else '',
    }


def _projects_list():
    return [_project_dict(p) for p in QcAgentProject.objects.all()]


def _state(extra=None):
    """写操作统一回包：最新全量状态。"""
    body = {'success': True, 'projects': _projects_list(), 'cats': _cats_dict()}
    if extra:
        body.update(extra)
    return body


def _err(msg, status=400):
    return Response({'success': False, 'error': msg}, status=status)


# ════════════════════════════════════════════════════════════
#  读取
# ════════════════════════════════════════════════════════════
@api_view(['GET'])
@permission_classes([AllowAny])
def qc_bootstrap(request):
    """一次取回全部初始数据（等价原版启动时的 loadCats + loadProjects）。

    额外下发 prefix_map / builtins / statuses / btypes，让前端的
    「命名原则说明」「分类管理内建标记」「下拉选项」都取自服务端单一来源。
    """
    _ensure_builtin_cats()
    return Response({
        'success': True,
        'projects': _projects_list(),
        'cats': _cats_dict(),
        'prefix_map': PREFIX_MAP,
        'builtins': BUILTIN_CATS,
        'statuses': list(STATUSES),
        'btypes': list(BTYPES),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def qc_next_seq(request):
    """流水码自动分配（等价原版 autoAssign）。

    规则：在【同 group + subtype】范围内取最小未用正整数（1~999），
    与工作后缀无关 —— 群组和子类型一致时流水码一律向后顺延，
    避免 QCWF_001_FUNCTION_A / QCWF_001_FUNCTION_B 重号。
    已废除的专案号码保留、不参与重新分配（原版注释即如此）。
    参数：group / subtype / exclude_id（编辑时排除自身）；work 仅作兼容保留，不参与范围。
    """
    g = _s(request.GET.get('group'))
    s = _s(request.GET.get('subtype'))
    exclude_id = _s(request.GET.get('exclude_id'))
    if not (g and s):
        return _err('请先填写：功能群组、子类型')

    qs = QcAgentProject.objects.filter(group=g, subtype=s)
    if exclude_id:
        qs = qs.exclude(qc_id=exclude_id)
    used = set()
    for sq in qs.values_list('seq', flat=True):
        try:
            used.add(int(str(sq)))
        except (TypeError, ValueError):
            continue
    n = 1
    while n in used and n <= 999:
        n += 1
    if n > 999:
        return _err('编号已用尽 (001~999)')
    return Response({'success': True, 'seq': str(n).zfill(3)})


# ════════════════════════════════════════════════════════════
#  写入：专案
# ════════════════════════════════════════════════════════════
@api_view(['POST'])
@permission_classes([AllowAny])
def qc_project_save(request):
    """新增 / 修改专案（等价原版 saveRecord）。

    校验与原版逐条对齐：
      ① 必填：group / subtype / work / seq / arch / status
      ② work 仅限英文字母与数字（原版 enforceEn + 保存前再校验）
      ③ Agent 名称唯一（排除自身）
    ★ 名称由服务端按命名规则生成（原版该输入框是 readonly，永远是生成值），
      忽略前端传来的 name，避免绕过规则写进不一致的名称。
    """
    d = _post_data(request)
    qc_id = _s(d.get('id'))
    group = _s(d.get('group'), 32)
    subtype = _s(d.get('subtype'), 32)
    work = _s(d.get('work'), 30)
    seq = _s(d.get('seq'), 3)
    arch = _s(d.get('arch'), 32)
    status = _s(d.get('status'), 8) or '开发中'

    if not (group and subtype and work and seq and arch and status):
        return _err('请填写所有必填栏位（*）并确认 Agent 名称已生成。')
    if not group in PREFIX_MAP:
        return _err(f'功能群组「{group}」没有对应的命名前缀，请在分类管理中维护。')
    import re
    if not re.match(WORK_RE, work):
        return _err('工作栏位仅限英文字母与数字。')
    if status not in STATUSES:
        return _err(f'状态只能是：{" / ".join(STATUSES)}')
    btype = _s(d.get('btype'), 8)
    if btype not in BTYPES:
        return _err('效益类型只能是：耗时 / 人力 / 空')

    seq = seq.zfill(3)
    name = _make_name(group, subtype, work, seq)

    # 名称唯一（排除自身）
    dup = QcAgentProject.objects.filter(name=name)
    if qc_id:
        dup = dup.exclude(qc_id=qc_id)
    if dup.exists():
        return _err(f'名称「{name}」已存在，请更换流水码或工作名称。')

    fields = dict(
        group=group, subtype=subtype, work=work, seq=seq, name=name, arch=arch,
        status=status, dev=_s(d.get('dev'), 32), desc=_s(d.get('desc'), 255),
        success=_s(d.get('success'), 16), accuracy=_s(d.get('accuracy'), 16),
        token=_s(d.get('token'), 16), time=_s(d.get('time'), 16),
        btype=btype, bval=_s(d.get('bval'), 16),
    )

    with transaction.atomic():
        if qc_id:
            obj = QcAgentProject.objects.filter(qc_id=qc_id).first()
            if obj is None:
                return _err('要修改的专案不存在（可能已被他人删除），请刷新后重试。', status=404)
            for k, v in fields.items():
                setattr(obj, k, v)
            obj.save()
        else:
            obj = QcAgentProject.objects.create(qc_id=_gen_qc_id(), **fields)

    return Response(_state({'id': obj.qc_id, 'name': obj.name}))


@api_view(['POST'])
@permission_classes([AllowAny])
def qc_project_status(request):
    """改变状态：废除 / 恢复（等价原版 chStatus）。

    ★ 废除只改状态，流水码保留、不会被重新分配（原版语义）。
    """
    d = _post_data(request)
    qc_id = _s(d.get('id'))
    status = _s(d.get('status'), 8)
    if status not in STATUSES:
        return _err(f'状态只能是：{" / ".join(STATUSES)}')
    obj = QcAgentProject.objects.filter(qc_id=qc_id).first()
    if obj is None:
        return _err('专案不存在（可能已被他人删除），请刷新后重试。', status=404)
    obj.status = status
    obj.save(update_fields=['status', 'updated_at'])
    return Response(_state({'id': obj.qc_id, 'status': obj.status}))


@api_view(['POST'])
@permission_classes([AllowAny])
def qc_project_delete(request):
    """永久删除（等价原版 askDel）。"""
    d = _post_data(request)
    qc_id = _s(d.get('id'))
    obj = QcAgentProject.objects.filter(qc_id=qc_id).first()
    if obj is None:
        return _err('专案不存在（可能已被他人删除），请刷新后重试。', status=404)
    obj.delete()
    return Response(_state({'deleted': qc_id}))


# ════════════════════════════════════════════════════════════
#  写入：分类项
# ════════════════════════════════════════════════════════════
@api_view(['POST'])
@permission_classes([AllowAny])
def qc_cat_add(request):
    """新增分类项（等价原版 addCatItem）。"""
    d = _post_data(request)
    kind = _s(d.get('kind'), 16)
    name = _s(d.get('name'), 64)
    if kind not in CAT_KINDS:
        return _err('分类类型不正确')
    if not name:
        return _err('请输入要新增的项目名称')
    if QcAgentCategory.objects.filter(kind=kind, name=name).exists():
        return _err('项目已存在')
    max_sort = QcAgentCategory.objects.filter(kind=kind).order_by('-sort').values_list('sort', flat=True).first() or 0
    QcAgentCategory.objects.create(kind=kind, name=name, is_builtin=False, sort=max_sort + 1)
    return Response(_state())


@api_view(['POST'])
@permission_classes([AllowAny])
def qc_cat_remove(request):
    """删除分类项（等价原版 removeCat）—— 内建项不可删除。"""
    d = _post_data(request)
    kind = _s(d.get('kind'), 16)
    name = _s(d.get('name'), 64)
    if kind not in CAT_KINDS:
        return _err('分类类型不正确')
    obj = QcAgentCategory.objects.filter(kind=kind, name=name).first()
    if obj is None:
        return _err('项目不存在', status=404)
    if obj.is_builtin:
        return _err('内建项目无法删除')
    obj.delete()
    return Response(_state())


# ════════════════════════════════════════════════════════════
#  备份 / 汇入（与原版 JSON 结构完全兼容，可双向互导）
# ════════════════════════════════════════════════════════════
@api_view(['GET'])
@permission_classes([AllowAny])
def qc_export(request):
    """备份 JSON：结构与原版 exportJSON 完全一致 {projects, cats, exportedAt}。"""
    return Response({
        'projects': _projects_list(),
        'cats': _cats_dict(),
        'exportedAt': timezone.localtime(timezone.now()).isoformat(),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def qc_import(request):
    """汇入 JSON：覆盖现有数据（等价原版 importJSON 的"将覆盖现有数据"）。

    - 兼容原版导出的备份：项目按 id 去重、缺 name 时按命名规则补算
    - cats 里出现的分类项会自动落库（内建项保持 is_builtin，不可删）
    - 整个过程在一个事务里，任一条失败则整体回滚（原版是整块覆盖，语义一致）
    """
    d = _post_data(request)
    projects = d.get('projects')
    if not isinstance(projects, list):
        return _err('格式错误：缺少 projects 数组')
    cats_in = d.get('cats') if isinstance(d.get('cats'), dict) else {}

    _ensure_builtin_cats()
    ok_cnt = 0
    with transaction.atomic():
        QcAgentProject.objects.all().delete()

        # 分类：先补进不在库里的项（含内建标记）
        if cats_in:
            exists = set(QcAgentCategory.objects.values_list('kind', 'name'))
            new_cats = []
            for kind in CAT_KINDS:
                items = cats_in.get(kind) or []
                if not isinstance(items, list):
                    continue
                for i, nm in enumerate(items):
                    nm = _s(nm, 64)
                    if nm and (kind, nm) not in exists:
                        new_cats.append(QcAgentCategory(
                            kind=kind, name=nm,
                            is_builtin=(nm in BUILTIN_CATS.get(kind, [])), sort=i + 100,
                        ))
                        exists.add((kind, nm))
            if new_cats:
                QcAgentCategory.objects.bulk_create(new_cats, ignore_conflicts=True)

        seen_names, seen_ids = set(), set()
        objs = []
        for i, raw in enumerate(projects):
            if not isinstance(raw, dict):
                continue
            group = _s(raw.get('group'), 32)
            subtype = _s(raw.get('subtype'), 32)
            work = _s(raw.get('work'), 30)
            seq = _s(raw.get('seq'), 3).zfill(3) if _s(raw.get('seq'), 3) else ''
            name = _s(raw.get('name'), 120) or _make_name(group, subtype, work, seq)
            qc_id = _s(raw.get('id'), 32) or _gen_qc_id()
            if not name or name in seen_names or qc_id in seen_ids:
                continue                     # 跳过重名/重 id 的脏行，避免整包失败
            status = _s(raw.get('status'), 8)
            if status not in STATUSES:
                status = '开发中'
            btype = _s(raw.get('btype'), 8)
            if btype not in BTYPES:
                btype = ''
            seen_names.add(name)
            seen_ids.add(qc_id)
            objs.append(QcAgentProject(
                qc_id=qc_id, group=group, subtype=subtype, work=work, seq=seq, name=name,
                arch=_s(raw.get('arch'), 32), status=status,
                dev=_s(raw.get('dev'), 32), desc=_s(raw.get('desc'), 255),
                success=_s(raw.get('success'), 16), accuracy=_s(raw.get('accuracy'), 16),
                token=_s(raw.get('token'), 16), time=_s(raw.get('time'), 16),
                btype=btype, bval=_s(raw.get('bval'), 16),
            ))
            ok_cnt += 1
        if objs:
            QcAgentProject.objects.bulk_create(objs, batch_size=200)

    return Response(_state({'imported': ok_cnt, 'skipped': len(projects) - ok_cnt}))
