"""
预警监控 API 视图（不依赖公司数据库，使用本地 SQLite）
"""
import logging
import random
import time
from django.db import models as dj_models
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import date, datetime, timedelta
from decimal import Decimal

from ..models import Product, ProductionPlan, WarningRecord, WarningRule, DailyProduction, SamplePlan

logger = logging.getLogger(__name__)


def _check_warning_logic(actual_qty, planned_qty, operator='>='):
    """统一的预警判断逻辑"""
    try:
        actual = Decimal(str(actual_qty))
        planned = Decimal(str(planned_qty))
    except Exception:
        return False, 0

    if planned <= 0:
        return False, 0

    achievement_rate = float(actual / planned * 100)

    if operator == '>=':
        has_warning = actual >= planned
    elif operator == '>':
        has_warning = actual > planned
    elif operator == '<=':
        has_warning = actual <= planned
    elif operator == '<':
        has_warning = actual < planned
    elif operator == '==':
        has_warning = actual == planned
    else:
        has_warning = actual >= planned

    return has_warning, round(achievement_rate, 2)


def _shift_month(year, month, offset):
    total = year * 12 + (month - 1) + offset
    return total // 12, total % 12 + 1


def _find_sample_plan_for_plan(plan):
    """
    按导入逻辑反查监控月份对应的每月计划行。
    多策略匹配（由严到宽）：
    1. (material_code_52, finished_product_code, customer) + (year, month) + mps
    2. (material_code_52, finished_product_code) + (year, month) + mps
    3. (material_code_52) + (year, month) + mps
    4. (material_code_52, finished_product_code) 不限月份
    5. (material_code_52) 不限月份
    返回最近创建的一条。
    """
    product = plan.product
    candidates_all = SamplePlan.objects.all()
    if not candidates_all.exists():
        return None

    prev_year, prev_month = _shift_month(plan.year, plan.month, -1)
    prev2_year, prev2_month = _shift_month(plan.year, plan.month, -2)

    def _by_keys_and_months(month_specs):
        """按指定 (year, month) 列表 + 物料关键字段查"""
        for (yr, mo) in month_specs:
            qs = candidates_all.filter(plan_year=yr, plan_month=mo)
            if not qs.exists():
                continue
            # 1) 完整三字段
            hit = qs.filter(
                material_code_52=product.material_code_52,
                finished_product_code=product.finished_product_code,
                customer=product.customer.name if product.customer else '',
            ).order_by('-created_at', '-id').first()
            if hit:
                return hit
            # 2) 物料 + 成品料号
            hit = qs.filter(
                material_code_52=product.material_code_52,
                finished_product_code=product.finished_product_code,
            ).order_by('-created_at', '-id').first()
            if hit:
                return hit
            # 3) 仅 52 阶料号
            hit = qs.filter(
                material_code_52=product.material_code_52,
            ).order_by('-created_at', '-id').first()
            if hit:
                return hit
        return None

    month_specs_with_mps = [
        (prev_year, prev_month),
        (prev2_year, prev2_month),
        (plan.year, plan.month),
    ]
    hit = _by_keys_and_months(month_specs_with_mps)
    if hit:
        return hit

    # 4/5 不限月份：按物料关键字段全局匹配
    hit = candidates_all.filter(
        material_code_52=product.material_code_52,
        finished_product_code=product.finished_product_code,
    ).order_by('-created_at', '-id').first()
    if hit:
        return hit

    hit = candidates_all.filter(
        material_code_52=product.material_code_52,
    ).order_by('-created_at', '-id').first()
    if hit:
        return hit

    return None


def _serialize_warning_item(plan, has_warning, achievement, matched_rule_names, record=None):
    sample_plan = _find_sample_plan_for_plan(plan)
    is_handled = bool(record and record.status == 'closed')
    return {
        'product_id': plan.product.id,
        'product_code': plan.product.code,
        'product_name': plan.product.name,
        'customer': plan.product.customer.name if plan.product.customer else '',
        'fab': plan.product.fab,
        'bu': plan.product.bu,
        'mode': plan.product.mode,
        'material_code_52': plan.product.material_code_52,
        'finished_product_code': plan.product.finished_product_code,
        'year': plan.year,
        'month': plan.month,
        'planned_quantity': float(plan.planned_quantity),
        'actual_quantity': float(plan.actual_quantity),
        'achievement_rate': achievement,
        'has_warning': has_warning,
        'is_handled': is_handled,
        'warning_record_id': record.id if record else None,
        'warning_status': record.status if record else '',
        'warning_status_display': record.get_status_display() if record else '',
        'handler': record.handler if record else '',
        'warning_remark': record.remark if record else '',
        'matched_rules': matched_rule_names,
        'sample_plan': {
            'id': sample_plan.id,
            'serial_number': sample_plan.serial_number,
            'month': sample_plan.month,
            'qe_decision': sample_plan.qe_decision,
            'gpc_decision': sample_plan.gpc_decision,
            'final_decision': sample_plan.final_decision,
            'sample_remark': sample_plan.sample_remark,
            'q_order': sample_plan.q_order,
            'box_number': sample_plan.box_number,
            'sample_date': sample_plan.sample_date.isoformat() if sample_plan.sample_date else '',
            'exception_note': sample_plan.exception_note,
        } if sample_plan else None,
    }


def _ensure_warning_record(plan, has_warning, achievement, threshold, operator, today=None):
    """
    收口函数：保证只要 is_warning 为 True，就一定有可用的 WarningRecord。
    返回 record 对象（含 id）；非预警时返回 None。
    关键点：
    - 用 (product, year, month) 作为业务主键查找；找不到再退回到 today
    - 已关闭 (status='closed') 的记录如果仍处于预警状态，**不重新打开**（保留处理结论）
    - 已有 pending/producing 的记录会被刷新 actual/achievement
    """
    if not has_warning:
        return None
    if today is None:
        today = date.today()

    # 优先按 (product, year, month) 查找；这样同一产品不同月份不会被合并
    record = WarningRecord.objects.filter(
        product=plan.product,
        warning_date__year=plan.year,
        warning_date__month=plan.month,
    ).order_by('-warning_date', '-id').first()

    if record is None:
        # 再退回到 (product, today)，兼容老数据
        record = WarningRecord.objects.filter(
            product=plan.product,
            warning_date=today,
        ).first()

    if record is None:
        record = WarningRecord.objects.create(
            product=plan.product,
            warning_date=date(plan.year, plan.month, 1) if (plan.year, plan.month) != (today.year, today.month) else today,
            planned_quantity=plan.planned_quantity,
            actual_quantity=plan.actual_quantity,
            achievement_rate=Decimal(str(achievement)),
            status='pending',
            handler='系统自动检测',
            remark=(
                f'累计产量 {plan.actual_quantity} 已达到规则阈值 {threshold}'
                if threshold is not None else
                f'累计产量 {plan.actual_quantity} 已达到月计划 {plan.planned_quantity}'
            ),
        )
    else:
        # 刷新关键字段，但**不**覆盖已关闭的结论
        record.planned_quantity = plan.planned_quantity
        record.actual_quantity = plan.actual_quantity
        record.achievement_rate = Decimal(str(achievement))
        if record.status == 'closed':
            # 已处理但又再次超阈值：追加到 remark 不覆盖
            extra = f'[{datetime.now().strftime("%Y-%m-%d %H:%M")}] 再次触发预警：累计 {plan.actual_quantity} ≥ 阈值 {threshold if threshold is not None else plan.planned_quantity}'
            if extra not in record.remark:
                record.remark = (record.remark + '\n' + extra).strip() if record.remark else extra
        record.save()

    return record


def _detect_and_create_unplanned_plans(year, month):
    """
    ★ 计划外产品自动加入
    业务逻辑：
    - 遍历指定 (year, month) 所有实际产量 > 0 的产品（来自 ProductionPlan）
    - 对每个产品，尝试在 SamplePlan 中按 (material_code_52, customer, fab, bu, mode) 匹配
    - 匹配不到但实际产量 > 0 → 自动创建 SamplePlan，is_unplanned=True
    - 已有 is_unplanned 标记的，刷新 detected_at 和备注

    返回：本次新创建/更新的计划外 SamplePlan 列表（用于前端展示）
    """
    from django.utils import timezone

    created_or_updated = []

    # 1. 找出 (year, month) 中所有实际产量 > 0 的生产计划
    plans_with_production = ProductionPlan.objects.filter(
        year=year, month=month, actual_quantity__gt=0
    ).select_related('product', 'product__customer')

    for plan in plans_with_production:
        product = plan.product
        if not product:
            continue

        # 2. 多策略匹配 SamplePlan
        # 优先用物料关键字段（material_code_52, finished_product_code, customer）
        mat52 = (product.material_code_52 or '').strip()
        fpc = (product.finished_product_code or '').strip()
        cust_name = product.customer.name if product.customer else ''
        fab = (product.fab or '').strip()
        bu = (product.bu or '').strip()
        mode = (product.mode or '').strip()

        match_qs = SamplePlan.objects.filter(plan_year=year, plan_month=month)
        match = None

        if mat52 and fpc and cust_name:
            match = match_qs.filter(
                material_code_52=mat52,
                finished_product_code=fpc,
                customer=cust_name,
            ).first()
        if match is None and mat52 and fpc:
            match = match_qs.filter(
                material_code_52=mat52,
                finished_product_code=fpc,
            ).first()
        if match is None and mat52:
            match = match_qs.filter(material_code_52=mat52).first()
        # 最后兜底：按客户+52阶料号
        if match is None and mat52 and cust_name:
            match = match_qs.filter(
                material_code_52=mat52, customer=cust_name
            ).first()

        if match is not None:
            # 已存在对应计划行 → 不创建
            continue

        # 3. 没找到匹配计划 → 自动创建一条计划外 SamplePlan
        try:
            # 序号 = 当前月最大序号 + 1
            max_serial = SamplePlan.objects.filter(
                plan_year=year, plan_month=month
            ).aggregate(max_sn=dj_models.Max('serial_number'))['max_sn'] or 0

            new_plan = SamplePlan.objects.create(
                plan_year=year,
                plan_month=month,
                month=f"{year}-{month:02d}",
                serial_number=max_serial + 1,
                fab=fab,
                bu=bu,
                customer=cust_name,
                material_code_52=mat52,
                mode=mode,
                finished_product_code=fpc,
                next_month_mps=0,
                next_next_month_mps=0,
                box_quantity=0,
                sample_request_qty=0,
                import_batch=f'AUTO_UNPLANNED_{year}{month:02d}',
                source_file_name='(由预警系统自动检测)',
                source_side='',
                is_unplanned=True,
                unplanned_reason=(
                    f'产品 {product.code} 在 {year}年{month}月 实际产量 '
                    f'{plan.actual_quantity} > 0，但未匹配到任何月度计划行，已自动加入'
                ),
                detected_at=timezone.now(),
            )
            created_or_updated.append({
                'id': new_plan.id,
                'product_code': product.code,
                'material_code_52': mat52,
                'reason': new_plan.unplanned_reason,
                'is_new': True,
            })
        except Exception as e:
            logger.warning('自动创建计划外 SamplePlan 失败 (%s): %s', product.code, e)

    return created_or_updated


@api_view(['POST'])
def check_warning(request):
    """检查单个产品的预警状态"""
    product_code = request.data.get('product_code')
    year = request.data.get('year')
    month = request.data.get('month')

    if not all([product_code, year, month]):
        return Response({'error': '缺少必要参数'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        year = int(year)
        month = int(month)

        product = Product.objects.filter(code=product_code).first()
        if not product:
            return Response({'error': f'产品不存在: {product_code}'}, status=status.HTTP_404_NOT_FOUND)

        plan = ProductionPlan.objects.filter(product=product, year=year, month=month).first()
        if not plan:
            return Response({'error': f'{year}年{month}月没有生产计划'}, status=status.HTTP_404_NOT_FOUND)

        has_warning, achievement = _check_warning_logic(plan.actual_quantity, plan.planned_quantity)

        return Response({
            'success': True,
            'data': {
                'product_code': product.code,
                'product_name': product.name,
                'year': year,
                'month': month,
                'planned_quantity': float(plan.planned_quantity),
                'actual_quantity': float(plan.actual_quantity),
                'achievement_rate': achievement,
                'has_warning': has_warning
            }
        })
    except ValueError:
        return Response({'error': '年份和月份必须是整数'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("check_warning 异常: %s", e)
        return Response({'error': f'检查失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def check_all_warnings(request):
    """
    检查所有产品的预警状态
    遍历所有启用的预警规则，使用 rule.matches(plan) 检查匹配
    """
    year = request.data.get('year')
    month = request.data.get('month')

    if not year or not month:
        now = datetime.now()
        year = int(year) if year else now.year
        month = int(month) if month else now.month

    try:
        year = int(year)
        month = int(month)
    except (TypeError, ValueError):
        return Response({'error': '年份和月份必须是整数'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        plans = ProductionPlan.objects.filter(
            year=year, month=month
        ).select_related('product').select_related('product__customer')

        # ★ 自动检测并创建计划外 SamplePlan（在计算预警前先收口）
        try:
            unplanned_created = _detect_and_create_unplanned_plans(year, month)
        except Exception as e:
            logger.warning('检测计划外产品失败（不影响主流程）: %s', e)
            unplanned_created = []

        # 获取所有启用的规则
        active_rules = list(WarningRule.objects.filter(is_active=True))

        results = []
        for plan in plans:
            has_warning, achievement = _check_warning_logic(
                plan.actual_quantity, plan.planned_quantity
            )

            # 找到所有匹配此计划的规则
            # ★ plan_a_middle_qty 类规则只在 effective_month 月份生效
            def _rule_matches_active_month(rule, plan_month):
                if rule.condition_type in ('plan_a_middle_qty', 'plan_a_second_last_qty'):
                    return rule.effective_month == plan_month
                return True
            matched_rules = [r for r in active_rules
                             if r.matches(plan) and _rule_matches_active_month(r, plan.month)]

            threshold = None
            operator = '>='
            if matched_rules:
                # 使用规则定义的阈值
                rule = matched_rules[0]
                threshold = rule.threshold
                operator = rule.operator
                if operator == '>=':
                    has_warning = Decimal(str(plan.actual_quantity)) >= threshold
                elif operator == '>':
                    has_warning = Decimal(str(plan.actual_quantity)) > threshold
                elif operator == '<=':
                    has_warning = Decimal(str(plan.actual_quantity)) <= threshold
                elif operator == '<':
                    has_warning = Decimal(str(plan.actual_quantity)) < threshold
                elif operator == '==':
                    has_warning = Decimal(str(plan.actual_quantity)) == threshold
                matched_rule_names = [r.name for r in matched_rules]
            else:
                matched_rule_names = []

            # ★ 收口：只要有预警，立刻确保 WarningRecord 存在
            record = _ensure_warning_record(
                plan, has_warning, achievement, threshold, operator
            )

            results.append({
                'product_id': plan.product.id,
                'product_code': plan.product.code,
                'product_name': plan.product.name,
                'customer': plan.product.customer.name if plan.product.customer else '',
                'fab': plan.product.fab,
                'bu': plan.product.bu,
                'mode': plan.product.mode,
                'material_code_52': plan.product.material_code_52,
                'finished_product_code': plan.product.finished_product_code,
                'year': year,
                'month': month,
                'planned_quantity': float(plan.planned_quantity),
                'actual_quantity': float(plan.actual_quantity),
                'achievement_rate': achievement,
                'has_warning': has_warning,
                'is_handled': bool(record and record.status == 'closed'),
                'warning_record_id': record.id if record else None,
                'warning_status': record.status if record else '',
                'warning_status_display': record.get_status_display() if record else '',
                'handler': record.handler if record else '',
                'warning_remark': record.remark if record else '',
                'matched_rules': matched_rule_names,
            })

        warning_count = sum(1 for r in results if r['has_warning'])
        normal_count = len(results) - warning_count

        return Response({
            'success': True,
            'year': year,
            'month': month,
            'count': len(results),
            'warning_count': warning_count,
            'normal_count': normal_count,
            'data': results,
            'unplanned_created': unplanned_created,
        })
    except Exception as e:
        logger.exception("check_all_warnings 异常: %s", e)
        return Response({'error': f'检查失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def detect_unplanned_products(request):
    """
    ★ 独立端点：手动触发"计划外产品检测"
    - 遍历 (year, month) 中所有实际产量 > 0 的产品
    - 对没有匹配 SamplePlan 的产品自动创建计划外记录
    - 返回新建/更新的列表
    """
    year = request.data.get('year')
    month = request.data.get('month')
    if not year or not month:
        now = datetime.now()
        year = int(year) if year else now.year
        month = int(month) if month else now.month
    try:
        year = int(year)
        month = int(month)
    except (TypeError, ValueError):
        return Response({'error': '年份和月份必须是整数'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        created = _detect_and_create_unplanned_plans(year, month)
        return Response({
            'success': True,
            'year': year,
            'month': month,
            'created_count': len(created),
            'created': created,
        })
    except Exception as e:
        logger.exception('detect_unplanned_products 异常: %s', e)
        return Response({'error': f'检测失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def ensure_warning_record(request):
    """
    ★ 关键接口
    接收 { product_code, year, month }（或 { plan_id }）
    如果该计划当前处于预警状态 → 确保 WarningRecord 存在并返回 warning_record_id
    如果不是预警状态 → 返回 has_warning=False + warning_record_id=null

    用途：前端卡片冒红但 warning_record_id 为空时（极端竞态 / 旧数据），
         点击"处理预警"时第一时间调此接口，拿到 ID 后立即打开处理弹窗，
         不会再提示"请等待下一次刷新"。
    """
    product_code = request.data.get('product_code')
    year = request.data.get('year')
    month = request.data.get('month')
    plan_id = request.data.get('plan_id')

    try:
        if plan_id:
            plan = (
                ProductionPlan.objects
                .select_related('product', 'product__customer')
                .filter(pk=plan_id)
                .first()
            )
        else:
            year = int(year)
            month = int(month)
            plan = (
                ProductionPlan.objects
                .select_related('product', 'product__customer')
                .filter(product__code=product_code, year=year, month=month)
                .first()
            )
    except (TypeError, ValueError):
        return Response({'error': '年份和月份必须是整数'}, status=status.HTTP_400_BAD_REQUEST)

    if not plan:
        return Response(
            {'error': f'未找到生产计划: {product_code} {year}-{month}'},
            status=status.HTTP_404_NOT_FOUND
        )

    active_rules = list(WarningRule.objects.filter(is_active=True))
    matched_rules = [r for r in active_rules if r.matches(plan)]
    has_warning, achievement = _check_warning_logic(
        plan.actual_quantity, plan.planned_quantity
    )
    threshold = None
    operator = '>='
    if matched_rules:
        rule = matched_rules[0]
        threshold = rule.threshold
        operator = rule.operator
        if operator == '>=':
            has_warning = Decimal(str(plan.actual_quantity)) >= threshold
        elif operator == '>':
            has_warning = Decimal(str(plan.actual_quantity)) > threshold
        elif operator == '<=':
            has_warning = Decimal(str(plan.actual_quantity)) <= threshold
        elif operator == '<':
            has_warning = Decimal(str(plan.actual_quantity)) < threshold
        elif operator == '==':
            has_warning = Decimal(str(plan.actual_quantity)) == threshold

    record = _ensure_warning_record(plan, has_warning, achievement, threshold, operator)

    return Response({
        'success': True,
        'data': {
            'product_code': plan.product.code,
            'product_name': plan.product.name,
            'year': plan.year,
            'month': plan.month,
            'planned_quantity': float(plan.planned_quantity),
            'actual_quantity': float(plan.actual_quantity),
            'achievement_rate': achievement,
            'has_warning': has_warning,
            'warning_record_id': record.id if record else None,
            'is_handled': bool(record and record.status == 'closed'),
            'warning_status': record.status if record else '',
            'warning_status_display': record.get_status_display() if record else '',
        }
    })


@api_view(['GET'])
def get_warning_summary(request):
    """获取预警汇总信息"""
    year = request.query_params.get('year')
    month = request.query_params.get('month')

    if not year or not month:
        now = datetime.now()
        year = int(year) if year else now.year
        month = int(month) if month else now.month

    try:
        year = int(year)
        month = int(month)
    except (TypeError, ValueError):
        return Response({'error': '年份和月份必须是整数'}, status=status.HTTP_400_BAD_REQUEST)

    plans = ProductionPlan.objects.filter(year=year, month=month).select_related('product')
    total = plans.count()
    warning_count = 0
    normal_count = 0
    for plan in plans:
        has_warning, _ = _check_warning_logic(plan.actual_quantity, plan.planned_quantity)
        if has_warning:
            warning_count += 1
        else:
            normal_count += 1

    return Response({
        'success': True,
        'data': {
            'year': year,
            'month': month,
            'total': total,
            'warning_count': warning_count,
            'normal_count': normal_count
        }
    })


@api_view(['GET'])
def test_company_db(request):
    """测试数据库连接"""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

        return Response({
            'success': True,
            'message': '数据库连接成功（本地SQLite）',
            'test_result': result[0] if result else 0
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': '数据库连接失败',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_warning_records(request):
    """获取预警记录列表"""
    qs = WarningRecord.objects.all().select_related('product')

    records = []
    for r in qs.order_by('-warning_date')[:200]:
        records.append({
            'id': r.id,
            'product_code': r.product.code,
            'product_name': r.product.name,
            'warning_date': r.warning_date.isoformat() if r.warning_date else None,
            'planned_quantity': float(r.planned_quantity),
            'actual_quantity': float(r.actual_quantity),
            'achievement_rate': float(r.achievement_rate),
            'status': r.status,
            'status_display': r.get_status_display(),
            'handler': r.handler,
            'remark': r.remark
        })

    return Response({'success': True, 'count': len(records), 'data': records})


@api_view(['PATCH'])
def update_warning_record(request, pk):
    """更新预警记录状态 + 同步 SamplePlan 字段（自动建行兜底）"""
    try:
        record = WarningRecord.objects.get(pk=pk)
    except WarningRecord.DoesNotExist:
        return Response({'error': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)

    new_status = request.data.get('status')
    handler = request.data.get('handler')
    remark = request.data.get('remark')
    sample_plan_data = request.data.get('sample_plan') or {}

    if new_status and new_status in ['pending', 'producing', 'closed']:
        record.status = new_status
    if handler is not None:
        record.handler = handler
    if remark is not None:
        record.remark = remark

    sample_plan = None
    sample_plan_id = sample_plan_data.get('id')
    editable_fields = [
        'qe_decision', 'gpc_decision', 'final_decision', 'sample_remark',
        'q_order', 'box_number', 'sample_date', 'exception_note'
    ]

    def _parse_date(val):
        if not val:
            return None
        try:
            return datetime.strptime(val, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError(f'date format error: {val}')

    if sample_plan_id:
        try:
            sample_plan = SamplePlan.objects.get(pk=sample_plan_id)
        except SamplePlan.DoesNotExist:
            return Response({'error': '对应每月计划记录不存在'}, status=status.HTTP_404_NOT_FOUND)
    else:
        # ★ 兜底：没传 sample_plan.id 时，尝试反查该预警对应 ProductionPlan 的 SamplePlan
        # 如果仍找不到 → 主动建一条新的（保证 Excel 导出能体现编辑结果）
        prod_plan = ProductionPlan.objects.filter(
            product=record.product, year=record.warning_date.year, month=record.warning_date.month
        ).first()
        if prod_plan:
            sample_plan = _find_sample_plan_for_plan(prod_plan)

        if sample_plan is None and record.product:
            product = record.product
            today = date.today()
            try:
                sample_plan = SamplePlan.objects.create(
                    serial_number=int(time.time()) % 100000,
                    month=f"{record.warning_date.year}-{record.warning_date.month:02d}",
                    plan_year=record.warning_date.year,
                    plan_month=record.warning_date.month,
                    fab=product.fab or '',
                    bu=product.bu or '',
                    customer=product.customer.name if product.customer else '',
                    material_code_52=product.material_code_52 or '',
                    mode=product.mode or '',
                    finished_product_code=product.finished_product_code or '',
                    next_month_mps=0,
                    next_next_month_mps=0,
                    box_quantity=0,
                    sample_request_qty=0,
                    import_batch=f'AUTO_FROM_WARNING_{today.strftime("%Y%m%d")}',
                    source_file_name='(由预警处理自动生成)',
                    source_side='',
                )
            except Exception as e:
                logger.warning('自动创建 SamplePlan 失败: %s', e)
                sample_plan = None

    if sample_plan is not None:
        try:
            for field in editable_fields:
                if field in sample_plan_data:
                    value = sample_plan_data[field]
                    if field == 'sample_date':
                        value = _parse_date(value)
                    setattr(sample_plan, field, value)
            sample_plan.save()
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    record.save()

    return Response({
        'success': True,
        'message': '更新成功',
        'data': {
            'id': record.id,
            'status': record.status,
            'status_display': record.get_status_display(),
            'handler': record.handler,
            'remark': record.remark,
            'sample_plan_id': sample_plan.id if sample_plan else None,
        }
    })


@api_view(['POST'])
def seed_demo_data(request):
    """
    为指定月份生成演示用的按日产量数据
    - 创建过去 7-30 天的 DailyProduction 记录
    - 每日的 actual_quantity 累积递增
    - 确保 DailyProduction 图表有数据可显示
    """
    year = request.data.get('year')
    month = request.data.get('month')
    days = int(request.data.get('days', 15))  # 默认生成 15 天数据

    if not year or not month:
        now = datetime.now()
        year = int(year) if year else now.year
        month = int(month) if month else now.month

    try:
        year = int(year)
        month = int(month)
    except (TypeError, ValueError):
        return Response({'error': '年份和月份必须是整数'}, status=status.HTTP_400_BAD_REQUEST)

    plans = ProductionPlan.objects.filter(
        year=year, month=month
    ).select_related('product')

    if not plans.exists():
        return Response({
            'success': False,
            'error': f'{year}年{month}月没有生产计划'
        }, status=status.HTTP_404_NOT_FOUND)

    from django.db import transaction
    from ..models import DailyProduction

    created_count = 0
    updated_count = 0

    with transaction.atomic():
        for plan in plans:
            # 计算每日的产量（模拟生产进度）
            # 假设生产从月初开始，累积到当前的某个比例
            today = date.today()
            days_in_month = 30  # 简化

            # 决定累积进度（已有 actual_quantity 决定的进度，或随机初始化）
            current_ratio = float(plan.actual_quantity) / float(plan.planned_quantity) if plan.planned_quantity > 0 else 0.3
            current_ratio = min(max(current_ratio, 0.05), 0.95)  # 限制在 5%-95%

            # 决定已生产的天数（今天之前）
            days_elapsed = min(days, days_in_month)

            # 计算每日的 daily_quantity（按递增曲线）
            cumulative = 0
            for day_offset in range(days_elapsed):
                production_date = date(today.year, today.month, today.day) - timedelta(days=days_elapsed - day_offset - 1)

                # 按天计算递增产量
                target_ratio = current_ratio * (day_offset + 1) / days_elapsed
                target_cumulative = float(plan.planned_quantity) * target_ratio
                daily_qty = max(0, int(target_cumulative - cumulative))
                cumulative += daily_qty

                # 写入或更新 DailyProduction
                obj, created = DailyProduction.objects.update_or_create(
                    product=plan.product,
                    production_date=production_date,
                    defaults={
                        'year': production_date.year,
                        'month': production_date.month,
                        'day': production_date.day,
                        'daily_quantity': Decimal(str(daily_qty)),
                        'cumulative_quantity': Decimal(str(cumulative)),
                    }
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

            # 同步 ProductionPlan 的 actual_quantity 为最后一天的累计
            plan.actual_quantity = Decimal(str(cumulative))
            plan.save()

    return Response({
        'success': True,
        'message': f'已生成演示数据：{created_count} 条新增，{updated_count} 条更新',
        'year': year,
        'month': month,
        'days': days,
        'created': created_count,
        'updated': updated_count
    })


@api_view(['POST'])
def simulate_realtime_production(request):
    """
    模拟实时产量增长（用于演示预警实时触发）

    每次调用时，所有生产计划都会增加一定的产量。
    演示场景：模拟产线持续生产，累计产量逐渐接近或超过计划值。

    Request Body (可选):
        year: 年份
        month: 月份
        min_increment: 每次最小增量（默认 10）
        max_increment: 每次最大增量（默认 50）
    """
    year = request.data.get('year')
    month = request.data.get('month')
    min_inc = int(request.data.get('min_increment', 10))
    max_inc = int(request.data.get('max_increment', 50))

    if not year or not month:
        now = datetime.now()
        year = int(year) if year else now.year
        month = int(month) if month else now.month

    try:
        year = int(year)
        month = int(month)
    except (TypeError, ValueError):
        return Response({'error': '年份和月份必须是整数'}, status=status.HTTP_400_BAD_REQUEST)

    plans = ProductionPlan.objects.filter(
        year=year, month=month
    ).select_related('product').select_related('product__customer')

    # 获取所有启用的规则
    active_rules = list(WarningRule.objects.filter(is_active=True))

    results = []
    warning_count = 0
    normal_count = 0

    for plan in plans:
        # 每次模拟增加一些产量（除非已经达到或超过计划的 1.2 倍）
        today = date.today()
        increment_value = 0
        if plan.actual_quantity < plan.planned_quantity * Decimal('1.2'):
            increment_value = random.randint(min_inc, max_inc)
            plan.actual_quantity += Decimal(str(increment_value))
            plan.save()

        # ========== 按日记录产量（用于每日趋势图）==========
        # 计算"今天已累计的产量"（同一天多次调用时累加）
        from ..models import DailyProduction as DP
        today_daily_record = DP.objects.filter(
            product=plan.product,
            production_date=today
        ).first()

        if today_daily_record:
            # 今天已有记录，累加 daily_quantity，更新 cumulative
            today_daily_record.daily_quantity = today_daily_record.daily_quantity + Decimal(str(increment_value))
            today_daily_record.cumulative_quantity = plan.actual_quantity
            today_daily_record.save()
        else:
            # 今天首次记录
            DP.objects.create(
                product=plan.product,
                production_date=today,
                year=today.year,
                month=today.month,
                day=today.day,
                daily_quantity=Decimal(str(increment_value)),
                cumulative_quantity=plan.actual_quantity
            )

        # 找到所有匹配此计划的规则
        matched_rules = [r for r in active_rules if r.matches(plan)]

        # 总是计算基础达成率
        has_warning, achievement = _check_warning_logic(
            plan.actual_quantity, plan.planned_quantity
        )

        if matched_rules:
            rule = matched_rules[0]
            threshold = rule.threshold
            operator = rule.operator
            if operator == '>=':
                has_warning = Decimal(str(plan.actual_quantity)) >= threshold
            elif operator == '>':
                has_warning = Decimal(str(plan.actual_quantity)) > threshold
            elif operator == '<=':
                has_warning = Decimal(str(plan.actual_quantity)) <= threshold
            elif operator == '<':
                has_warning = Decimal(str(plan.actual_quantity)) < threshold
            elif operator == '==':
                has_warning = Decimal(str(plan.actual_quantity)) == threshold
            matched_rule_names = [r.name for r in matched_rules]
        else:
            matched_rule_names = []
            threshold = None
            operator = '>='

        # ★ 收口：只要有预警，立刻确保 WarningRecord 存在
        record = _ensure_warning_record(
            plan, has_warning, achievement, threshold, operator, today=today
        )

        is_pending_warning = bool(has_warning and (not record or record.status != 'closed'))
        if is_pending_warning:
            warning_count += 1
        else:
            normal_count += 1

        results.append(_serialize_warning_item(
            plan,
            has_warning,
            achievement,
            matched_rule_names,
            record,
        ))

    return Response({
        'success': True,
        'year': year,
        'month': month,
        'count': len(results),
        'warning_count': warning_count,
        'normal_count': normal_count,
        'timestamp': datetime.now().isoformat(),
        'data': results
    })


@api_view(['POST'])
def reset_production(request):
    """重置所有生产计划到初始状态（用于演示）"""
    year = request.data.get('year')
    month = request.data.get('month')

    if not year or not month:
        now = datetime.now()
        year = int(year) if year else now.year
        month = int(month) if month else now.month

    try:
        year = int(year)
        month = int(month)
    except (TypeError, ValueError):
        return Response({'error': '年份和月份必须是整数'}, status=status.HTTP_400_BAD_REQUEST)

    plans = ProductionPlan.objects.filter(year=year, month=month)
    count = 0
    for plan in plans:
        # 重置为初始 50% 状态
        plan.actual_quantity = plan.planned_quantity * Decimal('0.5')
        plan.save()
        count += 1

    return Response({
        'success': True,
        'message': f'已重置 {count} 个生产计划',
        'year': year,
        'month': month
    })
