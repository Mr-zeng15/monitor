# -*- coding: utf-8 -*-
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import models
from ..models import Product, ProductionPlan

@api_view(['GET'])
def production_plan_months(request):
    """
    返回所有有 ProductionPlan 数据的月份列表（用于预警监控）
    自动合并：当前月 + 未来3个月 + 数据库中已有数据的月份
    """
    from datetime import date

    # 1. 从数据库查询所有有计划的月份
    months = (
        ProductionPlan.objects
        .values('year', 'month')
        .annotate(count=models.Count('id'))
        .order_by('-year', '-month')
    )

    db_months = set()
    for m in months:
        db_months.add((m['year'], m['month']))

    # 2. 添加当前月 + 未来 3 个月
    today = date.today()
    for offset in range(0, 4):
        y = today.year + (today.month - 1 + offset) // 12
        m = (today.month - 1 + offset) % 12 + 1
        db_months.add((y, m))

    # 3. 添加前 6 个月（如果不存在）
    for offset in range(1, 7):
        y = today.year + (today.month - 1 - offset) // 12
        m = (today.month - 1 - offset) % 12 + 1
        db_months.add((y, m))

    # 4. 按时间倒序
    sorted_months = sorted(db_months, key=lambda x: (x[0], x[1]), reverse=True)

    data = []
    for y, m in sorted_months:
        # 计算该月的计划数
        count = ProductionPlan.objects.filter(year=y, month=m).count()
        data.append({
            'year': y,
            'month': m,
            'period': f"{y}-{m:02d}",
            'count': count,
        })

    return Response({
        'success': True,
        'data': data
    })


@api_view(['GET'])
def daily_production_list(request):
    """
    按日产量列表（用于预警监控的每日趋势图）
    支持按年/月/产品筛选
    """
    from datetime import date
    from ..models import DailyProduction

    year = request.query_params.get('year')
    month = request.query_params.get('month')

    queryset = DailyProduction.objects.all()
    if year:
        queryset = queryset.filter(year=int(year))
    if month:
        queryset = queryset.filter(month=int(month))

    queryset = queryset.order_by('production_date', 'product_id')

    data = []
    for item in queryset:
        data.append({
            'id': item.id,
            'product_id': item.product_id,
            'product_code': item.product.code,
            'product_name': item.product.name,
            'customer_name': item.product.customer.name if item.product.customer else '',
            'fab': item.product.fab,
            'production_date': item.production_date.strftime('%Y-%m-%d'),
            'year': item.year,
            'month': item.month,
            'day': item.day,
            'daily_quantity': float(item.daily_quantity),
            'cumulative_quantity': float(item.cumulative_quantity),
        })

    return Response({
        'success': True,
        'total': len(data),
        'data': data
    })


@api_view(['GET'])
def daily_production_grouped(request):
    """
    按日产量分组聚合 API（用于 ECharts 图表）
    支持按 mode / fab / customer / product 分组

    Query Params:
        year: 必填
        month: 必填
        group_by: 必填（mode/fab/customer/product）

    Response:
        {
            success: true,
            year, month, group_by,
            dates: ["2026-07-17", ...],       // 所有日期（升序）
            groups: [
                {name: "Mode1", data: [50, 60, ...]},   // 每天的产量
                ...
            ],
            cumulative: [50, 110, 190, ...],  // 全部产品合计的累计产量
            planned_total: 4500               // 该月总计划产量
        }
    """
    from collections import defaultdict
    from ..models import DailyProduction, Product, Customer

    year = request.query_params.get('year')
    month = request.query_params.get('month')
    group_by = request.query_params.get('group_by', 'mode')

    if not year or not month:
        return Response({
            'success': False,
            'error': 'year 和 month 必填'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        year = int(year)
        month = int(month)
    except (TypeError, ValueError):
        return Response({
            'success': False,
            'error': 'year/month 必须是整数'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 1. 查出该月所有按日产量
    queryset = DailyProduction.objects.filter(
        year=year, month=month
    ).select_related('product', 'product__customer').order_by('production_date')

    if not queryset.exists():
        return Response({
            'success': True,
            'year': year,
            'month': month,
            'group_by': group_by,
            'dates': [],
            'groups': [],
            'cumulative': [],
            'planned_total': 0
        })

    # 2. 提取所有唯一的日期（升序）
    all_dates = sorted(set(item.production_date.strftime('%Y-%m-%d') for item in queryset))
    date_index = {d: i for i, d in enumerate(all_dates)}

    # 3. 决定分组字段
    def get_group_key(item):
        if group_by == 'mode':
            return item.product.mode or '未指定Mode'
        elif group_by == 'fab':
            return item.product.fab or '未指定Fab'
        elif group_by == 'customer':
            return item.product.customer.name if item.product.customer else '未指定客户'
        elif group_by == 'product':
            return item.product.code
        else:
            return item.product.mode or '未指定'

    # 4. 按分组聚合
    group_data = defaultdict(lambda: [0.0] * len(all_dates))
    daily_total = [0.0] * len(all_dates)  # 每天所有产品合计

    for item in queryset:
        key = get_group_key(item)
        idx = date_index[item.production_date.strftime('%Y-%m-%d')]
        dq = float(item.daily_quantity)
        group_data[key][idx] += dq
        daily_total[idx] += dq

    # 5. 计算累计产量（每天所有产品合计的累计）
    cumulative = []
    running = 0.0
    for d in daily_total:
        running += d
        cumulative.append(round(running, 2))

    # 6. 整理分组数据
    groups = []
    # 按组合 key 名称排序（空值排最后）
    sorted_keys = sorted(group_data.keys(), key=lambda k: (k.startswith('未指定'), k))
    for key in sorted_keys:
        groups.append({
            'name': key,
            'data': [round(v, 2) for v in group_data[key]]
        })

    # 7. 计算该月总计划产量
    from ..models import ProductionPlan
    planned_total = ProductionPlan.objects.filter(
        year=year, month=month
    ).aggregate(total=models.Sum('planned_quantity'))['total'] or 0

    return Response({
        'success': True,
        'year': year,
        'month': month,
        'group_by': group_by,
        'dates': all_dates,
        'groups': groups,
        'cumulative': cumulative,
        'planned_total': float(planned_total),
        'total_actual': round(sum(daily_total), 2)
    })
