from rest_framework import serializers
from .models import WarningRule, EntryTable, OrtRule, PreplanRow


class WarningRuleSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, allow_null=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, allow_null=True)

    # 字符串字段：把 None 归一为 ''，避免 NOT NULL 约束
    _NULL_TO_EMPTY_FIELDS = ('fab', 'bu', 'mode', 'material_code_52', 'finished_product_code')

    class Meta:
        model = WarningRule
        fields = [
            'id', 'name', 'rule_type',
            'product', 'product_name',
            'customer', 'customer_name',
            'fab', 'bu', 'mode', 'material_code_52', 'finished_product_code',
            'condition_type', 'operator', 'threshold',
            'target_month_day',          # ★ 2026-08-06 新增（其他月份条件用）
            'effective_month',           # ★ 2026-08-06 新增（中间月条件用，1-12）
            'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'product':     {'required': False, 'allow_null': True},
            'customer':    {'required': False, 'allow_null': True},
            'fab':         {'required': False, 'allow_null': True, 'allow_blank': True},
            'bu':          {'required': False, 'allow_null': True, 'allow_blank': True},
            'mode':        {'required': False, 'allow_null': True, 'allow_blank': True},
            'material_code_52':    {'required': False, 'allow_null': True, 'allow_blank': True},
            'finished_product_code': {'required': False, 'allow_null': True, 'allow_blank': True},
            'rule_type':   {'required': True},
            'target_month_day': {'required': False, 'allow_blank': True},
            'effective_month': {'required': False, 'allow_null': True},
        }

    def validate_target_month_day(self, value):
        """
        校验 target_month_day 格式 M/D（如 4/30、11/30）
        当 condition_type=plan_a_other_qty 时必填，其他场景留空
        """
        ct = self.initial_data.get('condition_type') if hasattr(self, 'initial_data') else None
        v = (value or '').strip()
        if ct == 'plan_a_other_qty':
            if not v:
                raise serializers.ValidationError('当条件类型=其他月份月底数量 时，目标月日必填（如 4/30）')
            import re
            if not re.match(r'^\d{1,2}/\d{1,2}$', v):
                raise serializers.ValidationError('目标月日格式必须为 M/D（如 4/30、11/30）')
        return v

    def validate_effective_month(self, value):
        """
        校验 effective_month 范围 1-12
        当 condition_type=plan_a_middle_qty 时必填，其他场景可空
        """
        ct = self.initial_data.get('condition_type') if hasattr(self, 'initial_data') else None
        if value is not None and (value < 1 or value > 12):
            raise serializers.ValidationError('生效月份必须在 1-12 之间')
        if ct in ('plan_a_middle_qty', 'plan_a_second_last_qty') and not value:
            raise serializers.ValidationError('当条件类型=计划A中间月/倒数第二个月底数量 时，生效月份必填（1-12）')
        return value

    def _null_to_empty(self, validated_data):
        """把 None 归一为 ''，避免数据库 NOT NULL 约束失败"""
        for f in self._NULL_TO_EMPTY_FIELDS:
            if validated_data.get(f) is None:
                validated_data[f] = ''
        return validated_data

    def validate_rule_type(self, value):
        """强制 rule_type 只能是 'warning' 或 'plan_import'"""
        if value not in ('warning', 'plan_import'):
            raise serializers.ValidationError(
                f'规则类型只能是 warning 或 plan_import，收到了：{value}'
            )
        return value

    def create(self, validated_data):
        # ★ 兜底：如果没传 rule_type，默认 'warning'
        if not validated_data.get('rule_type'):
            validated_data['rule_type'] = 'warning'
        validated_data = self._null_to_empty(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._null_to_empty(validated_data)
        return super().update(instance, validated_data)


class EntryTableSerializer(serializers.ModelSerializer):
    """基础资料表 序列化器（P/N 唯一键）"""
    class Meta:
        model = EntryTable
        fields = ['id', 'pn', 'model', 'material_code_52', 'box_quantity', 'customer', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'pn': {'required': True, 'allow_blank': False},
            'model': {'required': False, 'allow_blank': True},
            'material_code_52': {'required': False, 'allow_blank': True},
            'customer': {'required': False, 'allow_blank': True},
        }

    def validate_pn(self, value):
        v = (value or '').strip()
        if not v:
            raise serializers.ValidationError('P/N 不能为空')
        return v


class OrtRuleSerializer(serializers.ModelSerializer):
    """ORT 量判断规则序列化器"""
    class Meta:
        model = OrtRule
        fields = ['id', 'type_name', 'source', 'operator', 'threshold', 'is_active', 'remark', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_type_name(self, value):
        # ★ Type 可选：留空表示该规则对所有 Type 生效（不做 type 过滤）
        v = (value or '').strip().upper()
        return v


class PreplanRowSerializer(serializers.ModelSerializer):
    """预排筛选结果序列化器"""
    class Meta:
        model = PreplanRow
        fields = [
            'id', 'batch_id', 'plan_year', 'serial_number', 'status', 'source',
            'plan_month_label', 'table_date', 'type', 'fab',
            'material_code_52', 'model', 'pn', 'customer',
            'n1_dps', 'n2_dps', 'box_quantity', 'request_qty',
            'issue_qty_box', 'issue_qty_pcs', 'ort_ok',
            'qe_requirement', 'qe_remark', 'ra_remark', 'gpc_reply',
            'q_order', 'box_number', 'sample_date', 'mtd_output', 'judge',
            'filter_reason', 'missing_fields', 'source_file_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'batch_id', 'plan_year', 'serial_number', 'status', 'source',
            'plan_month_label', 'table_date', 'type', 'fab',
            'material_code_52', 'model', 'pn', 'customer',
            'n1_dps', 'n2_dps', 'box_quantity', 'request_qty',
            'issue_qty_box', 'issue_qty_pcs', 'ort_ok',
            'qe_requirement', 'qe_remark', 'ra_remark',
            'filter_reason', 'missing_fields', 'source_file_name',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'sample_date': {'required': False, 'allow_null': True},
        }