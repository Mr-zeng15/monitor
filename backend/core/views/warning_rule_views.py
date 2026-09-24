from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from ..models import WarningRule
from ..serializers import WarningRuleSerializer


class WarningRuleViewSet(viewsets.ModelViewSet):
    """预警规则管理（rule_type=warning）/ 初步筛选规则（rule_type=plan_import）"""
    queryset = WarningRule.objects.all()
    serializer_class = WarningRuleSerializer

    def get_queryset(self):
        queryset = WarningRule.objects.all()

        # 按产品筛选
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(Q(product_id=product_id) | Q(product__isnull=True))

        # 按启用状态筛选
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        # ★ 按规则类型筛选（核心：warning 与 plan_import 互不混用）
        rule_type = self.request.query_params.get('rule_type')
        if rule_type in ('warning', 'plan_import'):
            queryset = queryset.filter(rule_type=rule_type)

        return queryset

    @action(detail=False, methods=['get'])
    def active_rules(self, request):
        """获取所有启用的规则（可按 rule_type 过滤）"""
        rules = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(rules, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """切换规则启用状态"""
        rule = self.get_object()
        rule.is_active = not rule.is_active
        rule.save()
        serializer = self.get_serializer(rule)
        return Response(serializer.data)
