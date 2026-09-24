from django.db import models
from django.contrib.auth.models import User


class Customer(models.Model):
    """客户表"""
    name = models.CharField('客户名称', max_length=100, unique=True)
    code = models.CharField('客户代码', max_length=50, blank=True, default='')
    contact = models.CharField('联系人', max_length=50, blank=True, default='')
    email = models.EmailField('邮箱', blank=True, default='')
    phone = models.CharField('电话', max_length=20, blank=True, default='')
    is_active = models.BooleanField('启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'customer'
        verbose_name = '客户'
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """产品表"""
    code = models.CharField('产品代码', max_length=100, unique=True)
    name = models.CharField('产品名称', max_length=200)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='客户'
    )
    # 关键匹配字段（从 Excel 导入）
    fab = models.CharField('Fab', max_length=50, blank=True, default='')
    bu = models.CharField('BU', max_length=50, blank=True, default='')
    mode = models.CharField('Mode', max_length=50, blank=True, default='')
    material_code_52 = models.CharField('52阶料号', max_length=100, blank=True, default='')
    finished_product_code = models.CharField('成品料号', max_length=100, blank=True, default='')
    specification = models.CharField('规格', max_length=200, blank=True, default='')
    unit = models.CharField('单位', max_length=20, default='pcs')
    is_active = models.BooleanField('启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'product'
        verbose_name = '产品'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class ProductionPlan(models.Model):
    """生产计划表"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='产品')
    year = models.IntegerField('年份')
    month = models.IntegerField('月份')
    planned_quantity = models.DecimalField('计划产量', max_digits=12, decimal_places=2)
    actual_quantity = models.DecimalField('实际产量', max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'production_plan'
        verbose_name = '生产计划'
        verbose_name_plural = verbose_name
        unique_together = [['product', 'year', 'month']]
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.product.code} - {self.year}/{self.month}: {self.planned_quantity}"


class WarningRecord(models.Model):
    """预警记录表"""
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('producing', '生产中'),
        ('closed', '已处理'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='产品')
    warning_date = models.DateField('预警日期')
    planned_quantity = models.DecimalField('计划产量', max_digits=12, decimal_places=2, default=0)
    actual_quantity = models.DecimalField('实际产量', max_digits=12, decimal_places=2, default=0)
    achievement_rate = models.DecimalField('达成率(%)', max_digits=6, decimal_places=2, default=0)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    handler = models.CharField('处理人', max_length=50, blank=True, default='')
    remark = models.TextField('备注', blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'warning_record'
        verbose_name = '预警记录'
        verbose_name_plural = verbose_name
        ordering = ['-warning_date']

    def __str__(self):
        return f"{self.product.code} - {self.warning_date} - {self.status}"


class WarningRule(models.Model):
    """预警规则配置 / 初步筛选规则（同一套模型，两端独立使用，互不混用）"""
    # ★ 计划 A 月底数量（精准匹配 8/31 9/30 10/31 列）
    CONDITION_TYPE_CHOICES = [
        ('cumulative_vs_plan', '实际产量累计值 vs 计划值'),
        ('request_qty',        '需求送片量 vs 阈值'),
        ('next_month_mps',     '下个月MPS vs 阈值'),
        ('next_next_month_mps', '下下个月MPS vs 阈值'),
        ('box_quantity',       '每箱数量 vs 阈值'),
        # ★ 计划 A 月底数量（2026-08-06 新增，用于初步筛选）
        ('plan_a_8_31_qty',    '8/31 月底数量 vs 阈值'),
        ('plan_a_9_30_qty',    '9/30 月底数量 vs 阈值'),
        ('plan_a_10_31_qty',   '10/31 月底数量 vs 阈值'),
        ('plan_a_other_qty',   '其他月份月底数量 vs 阈值（搭配 target_month_day）'),
        # ★ 计划 A 中间月月底数量（2026-08-06 新增）
        # 三个日期列里中间那个的数字，对 effective_month 月份生效
        ('plan_a_middle_qty',  '计划A中间月月底数量 vs 阈值（对下个月生效，搭配 effective_month）'),
        ('plan_a_second_last_qty', '计划A倒数第二个月底数量 vs 阈值（对下个月生效，搭配 effective_month）'),
    ]

    OPERATOR_CHOICES = [
        ('>=', '大于等于'),
        ('>',  '大于'),
        ('<=', '小于等于'),
        ('<',  '小于'),
        ('==', '等于'),
        ('<>', '不等于'),
    ]

    # ★ 规则类型（单选枚举，不可混用）
    # - warning     : 仅用于预警监控（WarningRulesView 创建/管理）
    # - plan_import : 仅用于 Excel 计划导入筛选（PlanImportView 创建/管理）
    RULE_TYPE_CHOICES = [
        ('warning',     '预警监控'),
        ('plan_import', '初步筛选'),
    ]

    name = models.CharField('规则名称', max_length=100)

    # ★ 规则类型（单选，决定规则归属，互不混用）
    rule_type = models.CharField(
        '规则类型',
        max_length=20,
        choices=RULE_TYPE_CHOICES,
        default='warning',
        db_index=True,
        help_text='warning=预警规则（预警监控用）；plan_import=筛选规则（Excel导入用）'
    )

    # 匹配目标（多字段组合筛选，留空 = 不限制）
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='具体产品',
        help_text='指定特定产品（可选）'
    )
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='客户',
        help_text='指定客户（可选）'
    )
    fab = models.CharField('Fab', max_length=50, blank=True, default='', help_text='匹配 Fab 字段，留空不限制')
    bu = models.CharField('BU', max_length=50, blank=True, default='', help_text='匹配 BU 字段，留空不限制')
    mode = models.CharField('Model', max_length=50, blank=True, default='', help_text='匹配 Model 字段，留空不限制')
    material_code_52 = models.CharField('52阶料号', max_length=100, blank=True, default='', help_text='匹配 52阶料号，留空不限制')
    finished_product_code = models.CharField('成品料号', max_length=100, blank=True, default='', help_text='匹配 成品料号，留空不限制')

    # 触发条件
    condition_type = models.CharField(
        '条件类型',
        max_length=32,
        choices=CONDITION_TYPE_CHOICES,
        default='cumulative_vs_plan'
    )
    operator = models.CharField('运算符', max_length=2, choices=OPERATOR_CHOICES, default='>=')
    threshold = models.DecimalField('阈值', max_digits=10, decimal_places=2, default=0)
    # ★ 目标月日（2026-08-06 新增）：当 condition_type=plan_a_other_qty 时必填，例 '4/30'、'11/30'
    target_month_day = models.CharField(
        '目标月日',
        max_length=10,
        blank=True,
        default='',
        help_text='当条件类型=其他月份月底数量 时必填，如 4/30、11/30；其他场景留空'
    )
    # ★ 生效月份（2026-08-06 新增）：当 condition_type=plan_a_middle_qty 时必填，例 6（表示 6 月）
    # 表示该规则仅在监控 (year, effective_month) 月份时生效
    effective_month = models.IntegerField(
        '生效月份',
        null=True,
        blank=True,
        help_text='当条件类型=计划A中间月/倒数第二个月底数量 时必填，1-12；表示对哪个月份生效'
    )
    is_active = models.BooleanField('是否启用', default=True)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='创建人'
    )

    class Meta:
        db_table = 'warning_rule'
        verbose_name = '预警规则'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def matches(self, plan):
        """
        检查生产计划是否匹配此规则的所有筛选条件
        所有非空字段都必须匹配
        """
        product = plan.product

        # 1. 客户匹配
        if self.customer_id and (not product.customer_id or product.customer_id != self.customer_id):
            return False

        # 2. 产品匹配
        if self.product_id and product.id != self.product_id:
            return False

        # 3. Fab 匹配（精确匹配）
        if self.fab and product.fab != self.fab:
            return False

        # 4. BU 匹配
        if self.bu and product.bu != self.bu:
            return False

        # 5. Mode 匹配
        if self.mode and product.mode != self.mode:
            return False

        # 6. 52阶料号匹配
        if self.material_code_52 and product.material_code_52 != self.material_code_52:
            return False

        # 7. 成品料号匹配
        if self.finished_product_code and product.finished_product_code != self.finished_product_code:
            return False

        return True

    def __str__(self):
        product_name = self.product.name if self.product else '所有产品'
        return f"{self.name} - {product_name}"


class SamplePlan(models.Model):
    """每月计划 - 双 Excel 合并后的月度计划表"""
    DECISION_CHOICES = [
        ('是', '是'),
        ('否', '否'),
        ('待定', '待定'),
        ('', '未填写'),
    ]

    SOURCE_SIDE_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('A+B', 'A+B'),
        ('', '未指定'),
    ]

    # 基础信息（从Excel导入，不可编辑）
    serial_number = models.IntegerField('序号', default=0)
    month = models.CharField('月份', max_length=20)
    # 标准化月份字段（用于按月筛选和排序）
    plan_year = models.IntegerField('计划年份', default=2026)
    plan_month = models.IntegerField('计划月份', default=1)
    fab = models.CharField('Fab', max_length=50)
    bu = models.CharField('BU', max_length=50)
    customer = models.CharField('客户', max_length=100)
    material_code_52 = models.CharField('52阶料号', max_length=100)
    mode = models.CharField('Model', max_length=50)
    finished_product_code = models.CharField('成品料号', max_length=100)
    next_month_mps = models.IntegerField('下个月MPS数量', default=0)
    next_next_month_mps = models.IntegerField('下下个月MPS数量', default=0)
    box_quantity = models.IntegerField('每箱数量', default=0)
    sample_request_qty = models.IntegerField('需求送片量', default=0)

    # ★ 计划 A 月底数量（2026-08-06 新增，对应 Excel 最后 N 列：M/D 格式的"月最后一天"列）
    # 用于按月筛选规则，例如"8/31 月底数量 > 1000 则保留"
    # - plan_a_8_31_qty 等固定 3 个：常用月份的快速访问字段（也是规则 condition_type 选项）
    # - plan_a_other_monthly_qty JSONField：其他月份的灵活存储，如 {"4/30": 100, "11/30": 200}
    plan_a_8_31_qty = models.IntegerField('8/31月底数量', default=0, help_text='计划A表8月最后一天列的值')
    plan_a_9_30_qty = models.IntegerField('9/30月底数量', default=0, help_text='计划A表9月最后一天列的值')
    plan_a_10_31_qty = models.IntegerField('10/31月底数量', default=0, help_text='计划A表10月最后一天列的值')
    # ★ 其他月份月底数量（2026-08-06 新增）
    # SQLite 3.35 < 3.38 不支持 JSONField，所以用 TextField 存 JSON 字符串
    # 格式: '{"4/30": 100, "11/30": 200}'
    plan_a_other_monthly_qty = models.TextField(
        '其他月份月底数量',
        default='{}',
        blank=True,
        help_text='所有月份的月底数量（含8/9/10月），JSON 字符串 {"4/30": 100, "8/31": 200, "11/30": 300}'
    )
    # ★ 计划 A 中间月月底数量（2026-08-06 新增）
    # 导入计划 A 时，如果 Excel 有 N 个月底列，自动取中间那一列（如 4/30/5/31/6/30 → 取 5/31）的数字
    # 配套 plan_a_middle_month_day 记录中间那一列的月日（如 "5/31"）
    plan_a_middle_qty = models.IntegerField(
        '中间月月底数量',
        default=0,
        help_text='导入计划A时自动取三个日期列里中间那个的底下的数字（如 4/30/5/31/6/30 → 取 5/31）'
    )
    plan_a_middle_month_day = models.CharField(
        '中间月月日',
        max_length=10,
        blank=True,
        default='',
        help_text='中间那一列的月日，如 5/31、9/30；空表示导入时未识别到月底列'
    )
    # ★ 计划 A 倒数第二个月底数量（2026-08-06 新增）
    # 取某月最后一天列的倒数第二列（如 8/31、9/30、10/31 → 9/30）的数字
    plan_a_second_last_qty = models.IntegerField(
        '倒数第二个月底数量',
        default=0,
        help_text='导入计划A时自动取某月最后一天列的倒数第二列（如 8/31、9/30、10/31 → 取 9/30）的数字'
    )
    plan_a_second_last_month_day = models.CharField(
        '倒数第二个月底月日',
        max_length=10,
        blank=True,
        default='',
        help_text='倒数第二个月底列的月日，如 9/30、7/31；空表示导入时未识别到月底列'
    )

    # 可编辑字段 - 决议相关
    qe_decision = models.CharField('QE决议是否送样', max_length=20, choices=DECISION_CHOICES, default='', blank=True)
    gpc_decision = models.CharField('GPC决议是否送样', max_length=20, choices=DECISION_CHOICES, default='', blank=True)
    final_decision = models.CharField('最终决议是否送样', max_length=20, choices=DECISION_CHOICES, default='', blank=True)
    sample_remark = models.TextField('需求数量备注', blank=True, default='')

    # 可编辑字段 - ORT填写
    q_order = models.CharField('Q工单', max_length=100, blank=True, default='')
    box_number = models.CharField('箱号', max_length=50, blank=True, default='')
    sample_date = models.DateField('送样日期', null=True, blank=True)
    exception_note = models.TextField('异常确认说明', blank=True, default='')

    # 元数据
    import_batch = models.CharField('导入批次', max_length=100, blank=True, default='')
    source_file_name = models.CharField('源文件名', max_length=200, blank=True, default='', help_text='导入时的原始 Excel 文件名')
    source_side = models.CharField(
        '来源',
        max_length=10,
        choices=SOURCE_SIDE_CHOICES,
        default='',
        blank=True,
        help_text='双 Excel 合并时此行来自哪个文件：A(仅A) / B(仅B) / A+B(两边都有)'
    )
    # ★ 计划外产品标记：实际生产中存在，但月度计划中未包含的产品
    is_unplanned = models.BooleanField(
        '计划外产品',
        default=False,
        help_text='由预警系统自动加入：原本不在计划中但已实际生产的产品。'
    )
    unplanned_reason = models.CharField(
        '计划外原因',
        max_length=200,
        blank=True,
        default='',
        help_text='自动加入时的原因描述，例如"实际产量 > 0 但未匹配到任何月度计划"'
    )
    detected_at = models.DateTimeField('检测时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'sample_plan'
        verbose_name = '每月计划'
        verbose_name_plural = verbose_name
        # 按 (年,月) 倒序，序号升序
        ordering = ['-plan_year', '-plan_month', 'serial_number', 'id']

    def __str__(self):
        return f"{self.plan_year}-{self.plan_month:02d} #{self.serial_number} {self.material_code_52}"


class DailyProduction(models.Model):
    """按日实际产量记录（用于预警监控的每日趋势图）"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='产品')
    year = models.IntegerField('年份')
    month = models.IntegerField('月份')
    day = models.IntegerField('日', default=1)
    production_date = models.DateField('生产日期')
    daily_quantity = models.DecimalField('当日产量', max_digits=12, decimal_places=2, default=0)
    cumulative_quantity = models.DecimalField('累计产量', max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'daily_production'
        verbose_name = '按日产量'
        verbose_name_plural = verbose_name
        # 每天每个产品只有一条记录
        unique_together = [['product', 'production_date']]
        ordering = ['-production_date', 'product']

    def __str__(self):
        return f"{self.product.code} {self.production_date}: {self.daily_quantity}"


class EntryTable(models.Model):
    """基础资料表：P/N 主数据，预排导入时按 P/N 自动带出 52阶料号/满箱量/客户"""
    pn = models.CharField('P/N', max_length=100, unique=True)
    model = models.CharField('Model', max_length=100, blank=True, default='')
    material_code_52 = models.CharField('52阶料号', max_length=100, blank=True, default='')
    box_quantity = models.IntegerField('满箱量', default=0)
    customer = models.CharField('客户', max_length=100, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'entry_table'
        verbose_name = '基础资料表'
        verbose_name_plural = verbose_name
        ordering = ['pn']

    def __str__(self):
        return self.pn or self.model


class OrtRule(models.Model):
    """ORT 量判断规则：按 Type 设置最低需求阈值，可启用/停用"""
    SOURCE_CHOICES = [
        ('ALL', '全部'),
        ('S13', 'S13_DPS'),
        ('MONTHLY', 'Monthly input target'),
    ]
    OPERATOR_CHOICES = [
        ('>=', '大于等于'),
        ('>', '大于'),
        ('<=', '小于等于'),
        ('<', '小于'),
        ('==', '等于'),
        ('<>', '不等于'),
    ]
    type_name = models.CharField('Type', max_length=20, blank=True, default='',
                                 help_text='如 PD/TV/DT/MIB/SET；S13 专用可填 S13；留空表示对所有 Type 生效')
    source = models.CharField('来源', max_length=10, choices=SOURCE_CHOICES, default='ALL')
    operator = models.CharField('运算符', max_length=2, choices=OPERATOR_CHOICES, default='>=')
    threshold = models.IntegerField('最低需求数量阈值', default=0)
    is_active = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'ort_rule'
        verbose_name = 'ORT规则'
        verbose_name_plural = verbose_name
        ordering = ['source', 'type_name']

    def __str__(self):
        return f'{self.type_name} {self.operator} {self.threshold}'


class PreplanRow(models.Model):
    """预排筛选结果：S13_DPS + Monthly input target 合并筛选后的持久化行"""
    STATUS_CHOICES = [
        ('kept', '通过筛选'),
        ('filtered', '被过滤'),
    ]
    SOURCE_CHOICES = [
        ('S13_DPS', 'S13_DPS'),
        ('Monthly_Input', 'Monthly_Input'),
        ('MTD_EXTERNAL', '计划外'),
    ]

    batch_id = models.CharField('导入批次', max_length=64, db_index=True)
    plan_year = models.IntegerField('计划年份', default=2026, db_index=True)
    # ★ 2026-09-20：「预排年月」一级维度（YYYYMM；0 = 未归类，兼容加字段前的旧数据）。
    #   为什么存 YYYYMM 而不是裸月份：S13 的预排月 = 文件月+2、S11 = +1，11/12 月的文件会跨到次年
    #   （如 2026-12 的文件 → 预排 2027-02）；裸 1..12 会让「2026年9月」与「2027年9月」撞到同一个桶。
    #   归属月份在【导入时由用户确认】（默认用文件名/表格列推算的预排月份预填，可改），
    #   并且覆盖范围改为按本字段收窄 → 同名文件只在本月桶内覆盖，换月导入不再顶掉上个月的未导出行。
    plan_ym = models.IntegerField('预排年月(YYYYMM)', default=0, db_index=True)
    serial_number = models.IntegerField('序号', default=0)
    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default='kept', db_index=True)
    source = models.CharField('来源文件', max_length=20, choices=SOURCE_CHOICES, default='S13_DPS')

    plan_month_label = models.CharField('预排月份', max_length=20, blank=True, default='')
    table_date = models.CharField('制表日期', max_length=20, blank=True, default='')
    type = models.CharField('Type', max_length=20, blank=True, default='')
    fab = models.CharField('FAB', max_length=50, blank=True, default='')
    material_code_52 = models.CharField('52阶料号', max_length=100, blank=True, default='')
    model = models.CharField('Model', max_length=100, blank=True, default='')
    pn = models.CharField('P/N', max_length=100, blank=True, default='')
    customer = models.CharField('客户', max_length=100, blank=True, default='')
    n1_dps = models.IntegerField('N+1 DPS', default=0)
    n2_dps = models.IntegerField('N+2 DPS', default=0)
    box_quantity = models.IntegerField('满箱量', default=0)
    request_qty = models.IntegerField('需求数量(PCS)', default=0)
    issue_qty_box = models.IntegerField('领用数量-箱', default=0)
    issue_qty_pcs = models.IntegerField('领用数量-零数片', default=0)
    ort_ok = models.CharField('是否满足ORT量', max_length=4, blank=True, default='')
    qe_requirement = models.CharField('QE需求', max_length=100, blank=True, default='')
    qe_remark = models.CharField('QERemark', max_length=200, blank=True, default='')
    ra_remark = models.CharField('RA REMARK', max_length=200, blank=True, default='')
    gpc_reply = models.CharField('GPC回复', max_length=20, blank=True, default='')
    oqc_hold = models.CharField('OQC Hold', max_length=4, blank=True, default='', help_text='OQC Hold 标记，仅允许 Y / N / 空')
    # ★ 2026-09-16：LongLife 标记（审核决议中心专用列，仅允许 Y / N / 空）
    #   语义：LongLife=Y → 决议页在该行【下方】再渲染一份一模一样的行（序号与被复制行相同，
    #   KPI/总项数按"条目"计保持不变），两份数据各自独立可编辑。
    longlife = models.CharField('LongLife', max_length=4, blank=True, default='', help_text='LongLife 标记，仅允许 Y / N / 空；为 Y 时决议页在下方复制一行')
    # ★ 2026-09-16：复制行（副本）的独立字段值，JSON 字典（仅存被改过的字段，未改的跟随原行）。
    #   存这里而不另建一行，是为了满足「序号不变、总项数不变」——一份记录仍是一个条目。
    #   仅审核决议中心读写；预排/预警/存档/导出均忽略。
    longlife_copy = models.TextField('LongLife复制行数据', blank=True, default='', help_text='JSON：副本行相对原行被覆盖的字段值')
    q_order = models.CharField('Q工单', max_length=100, blank=True, default='')
    box_number = models.CharField('箱号', max_length=50, blank=True, default='')
    sample_date = models.DateField('送样日期', null=True, blank=True)
    mtd_output = models.CharField('MTD OUTPUT监控', max_length=50, blank=True, default='')
    is_plan_external = models.BooleanField('计划外', default=False, help_text='MTD SQL 查到但预排计划中不存在的料号，标记为计划外')
    mtd_source = models.CharField('MTD来源', max_length=10, blank=True, default='', help_text='MTD SQL 的 source 列（s13/s11），计划外行用于区分预警规则来源')
    inserted_to_preplan = models.BooleanField(
        '插入预排筛选',
        default=False,
        db_index=True,
        help_text='计划外实时监控项是否插入预排筛选（默认不插入；预警界面可切换）',
    )
    judge = models.CharField('Judge', max_length=50, blank=True, default='')
    filter_reason = models.TextField('过滤原因', blank=True, default='')
    missing_fields = models.TextField('缺失字段', blank=True, default='')
    source_file_name = models.CharField('源文件名', max_length=300, blank=True, default='')
    exported = models.BooleanField('是否导出到审核决议', default=False)
    archived = models.BooleanField('已存档定版', default=False, help_text='决议中心保存到存档中心后置 True，表示数据已最终定版')
    archived_at = models.DateTimeField('定版时间', null=True, blank=True, help_text='保存到存档中心的时间；撤销存档时清空（2026-09-14）')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'preplan_row'
        verbose_name = '预排筛选结果'
        verbose_name_plural = verbose_name
        ordering = ['-plan_year', 'serial_number', 'id']

    def __str__(self):
        return f'{self.plan_year} #{self.serial_number} {self.pn} ({self.status})'


class BotDataCache(models.Model):
    """★ 2026-09-16：公司机器人（Dify）返回数据的【服务端持久缓存】

    为什么需要它（部署到服务器后暴露的问题）：
      原实现里 `/api/byfab/abl/`（和 `/api/byfab/data/`）每收到一次请求，
      就现场向机器人发一次 workflow 查询，而该查询可能阻塞到 680 秒；
      前端又是「失败后每 1.5 秒重试一次，直到拿到为止」。
      两者叠加 → 服务器线程被几分钟级的请求占满 → 浏览器侧表现为
      `ERR_CONNECTION_RESET`（连接被重置）、随后大量 500；页面因为两条通道都拿不到
      数据，`DATA_ONLINE=false` → 整页压暗（用户看到的"ABL 面板灰色"）。
      另外缓存只存在浏览器 localStorage，换个浏览器或服务器重启就全没了。

    现在：服务端持久化「最后一次成功取到的真值」+「一份永久兜底种子」；
      接口**立即**返回缓存，绝不阻塞在机器人上；后台静默刷新，取到真值再覆盖。
      这样机器人临时不可达 / 服务器重启，页面依旧有数据可显示。
    """
    key = models.CharField('缓存键', max_length=32, unique=True)
    payload = models.TextField('数据(JSON)', blank=True, default='')
    is_seed = models.BooleanField('是否兜底种子', default=False, help_text='True=尚未取到真值，当前是内置兜底数据')
    fetched_at = models.DateTimeField('取到真值时间', null=True, blank=True, help_text='最近一次成功从机器人取到真值的时间')
    last_attempt_at = models.DateTimeField('最近尝试时间', null=True, blank=True)
    last_error = models.CharField('最近错误', max_length=300, blank=True, default='')
    fail_count = models.IntegerField('连续失败次数', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bot_data_cache'
        verbose_name = '机器人数据缓存'
        verbose_name_plural = verbose_name
        ordering = ['key']

    def __str__(self):
        src = '兜底种子' if self.is_seed else '真值'
        return f'{self.key} ({src})'


class QcAgentProject(models.Model):
    """★ 2026-09-16：QC_AI_TEAM · AI Agent 专案登记（原纯前端 localStorage 版迁到服务端）

    原版把台账存在浏览器 localStorage（`qcat_p4`），换电脑/换浏览器就看不到，
    也没有备份与并发控制。现改为服务端持久化，**功能与原版保持一致**：
      · 字段与前端 `saveRecord()` 生成的 rec 结构逐项对应（数值类刻意保留字符串形态，
        以维持原版"空值显示 —"的语义不变）
      · 流水码 seq 在【同一 群组+子类型+工作】下唯一，废除的号码保留不重新分配
      · Agent 名称 name 全局唯一（原版在保存前做重名校验）
    """
    qc_id = models.CharField('原前端ID', max_length=32, unique=True, help_text='沿用原版 id 生成规则，便于汇入旧备份')
    group = models.CharField('功能群组', max_length=32)
    subtype = models.CharField('子类型(Function)', max_length=32)
    work = models.CharField('工作(英文)', max_length=30)
    seq = models.CharField('流水码', max_length=3)
    name = models.CharField('Agent 名称', max_length=120, unique=True)
    arch = models.CharField('技术架构', max_length=32)
    status = models.CharField('状态', max_length=8, default='开发中', help_text='开发中 / 使用中 / 废除')
    dev = models.CharField('开发者', max_length=32, blank=True, default='')
    desc = models.CharField('专案说明', max_length=255, blank=True, default='')
    # 评估指标：原前端为 <input type="number"> 的字符串值，空串表示未填（显示 —）
    success = models.CharField('成功率(%)', max_length=16, blank=True, default='')
    accuracy = models.CharField('准确率(%)', max_length=16, blank=True, default='')
    token = models.CharField('Token消耗', max_length=16, blank=True, default='')
    time = models.CharField('单次耗时(s)', max_length=16, blank=True, default='')
    # 效益评估
    btype = models.CharField('效益类型', max_length=8, blank=True, default='', help_text='耗时 / 人力 / 空')
    bval = models.CharField('效益数值', max_length=16, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'qc_agent_project'
        verbose_name = 'QC_AI_TEAM Agent 专案'
        verbose_name_plural = verbose_name
        ordering = ['group', 'subtype', 'work', 'seq', 'id']

    def __str__(self):
        return f'{self.name} [{self.status}]'


class QcAgentCategory(models.Model):
    """★ 2026-09-16：QC_AI_TEAM 分类下拉项（功能群组 / 子类型 / 技术架构 / 开发者）

    原版存 localStorage `qcat_c4`，有内建默认值且内建项不可删除。
    这里用 is_builtin 标记内建项，行为保持一致。
    """
    KIND_CHOICES = [
        ('group', '功能群组'),
        ('subtype', '子类型(Function)'),
        ('arch', '技术架构'),
        ('dev', '开发者'),
    ]
    kind = models.CharField('分类类型', max_length=16, choices=KIND_CHOICES)
    name = models.CharField('项目名称', max_length=64)
    is_builtin = models.BooleanField('内建', default=False, help_text='内建项不可删除（与原版一致）')
    sort = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'qc_agent_category'
        verbose_name = 'QC_AI_TEAM 分类项'
        verbose_name_plural = verbose_name
        unique_together = [('kind', 'name')]
        ordering = ['kind', 'sort', 'id']

    def __str__(self):
        return f'{self.get_kind_display()}:{self.name}'