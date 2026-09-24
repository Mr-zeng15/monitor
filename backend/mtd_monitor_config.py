# -*- coding: utf-8 -*-
"""
============================================================
 MTD OUTPUT 实时抓取 · 用户配置文件
============================================================
你只需要修改本文件里的 2 处即可使用：

  1. PG_CONFIG   → 公司 PostgreSQL 数据库连接信息
  2. MTD_SQL     → 你的 MTD OUTPUT 查询 SQL（★ 核心）

------------------------------------------------------------
★ MTD_SQL 规则（已适配你的 3 列 SQL）：
  - 值列：取「最后一列」（例如 total_input_qty）
  - 匹配键：自动识别 model 列（列名含 model）与 p/n 列（列名含 part 或 pn）


  示例（按 model_no + part_no 汇总当月产出）：
    SELECT model_no, part_no, SUM(output_qty) AS total_qty
    FROM ...
    GROUP BY model_no, part_no

  抓取后会把「最后一列」的值回填预排表格的「MTD OUTPUT监控」列，
  并在「实时预警监控」中使用；计划里没有的料号会自动标记为「计划外」。
------------------------------------------------------------
"""

# ==================== 1. 公司 PostgreSQL 数据库连接 ====================
# ★ 2026-09-24 公开仓库化：凭据不再写死在本文件。
#   读取顺序：环境变量 > backend/local_secrets.py 的 SECRETS > 空（连接会报错属预期）。
#   键名：MTD_PG_HOST / MTD_PG_PORT / MTD_PG_DBNAME / MTD_PG_USER / MTD_PG_PASSWORD
try:
    from backend.settings import _secret as _s
except Exception:
    import os as _os
    def _s(name, default=''):
        return _os.environ.get(name) or default

PG_CONFIG = {
 'host': _s('MTD_PG_HOST'),           # ← 数据库主机（IP 或域名）
 'port': int(_s('MTD_PG_PORT', '80')), #
 'dbname': _s('MTD_PG_DBNAME'),       # ← 数据库名
 'user': _s('MTD_PG_USER'),           # ← 用户名
 'password': _s('MTD_PG_PASSWORD'),   # ← 密码
}

# ==================== 2. ★ 在这里填写你的 MTD OUTPUT SQL ====================
# ★ 已按你的新 SQL 更新：s11 / s13 各带 source 标记列，外层 GROUP BY 含 source，
#   保证两种来源的数据在处理时保持分离（预警规则按来源分别匹配 S13 / MONTHLY 规则）。
#   代码已适配：自动识别 source 列（s13 / s11 / 空），计划行按来源匹配、计划外行记录 mtd_source。
MTD_SQL = '''
WITH s13_agg AS (
    -- S13：PALLET 工序实体产出（按月汇总）
    SELECT
        model_no,
        part_no,
        SUM(output_qty) AS s13_qty
    FROM s13brisarpt.h_dax_output
    WHERE op_id = 'PALLET'
      AND SUBSTRING(wo_id, 5, 1) = 'M'
      AND mfg_day >= DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY model_no, part_no
),
s11_agg AS (
    -- S11：STOCK-IN 工序入库 lot 数（按月汇总）
    SELECT
        model_no,
        part_no,
        COUNT(lot_no) AS s11_qty
    FROM s11lcmpis2rpt.p_lot_oper
    WHERE op = 'STOCK-IN'
      AND LEFT(part_no, 2) = '91'
      AND SUBSTRING(wo_id, 5, 1) = 'M'
      AND shift_date >= DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY model_no, part_no
)
SELECT
    -- ★ COALESCE：s13 / s11 各自可能为 NULL（FULL OUTER JOIN），取非空的那边
    COALESCE(s13.model_no, s11.model_no)  AS model_no,
    COALESCE(s13.part_no,  s11.part_no)   AS part_no,

    -- ★ source 优先级：只要 s13 有产出，source = 's13'；否则 = 's11'
    --   Python 的 _pick_ort_rule 用 source 来判断套 S13 规则还是 MONTHLY 规则
    CASE
        WHEN s13.part_no IS NOT NULL THEN 's13'
        ELSE 's11'
    END AS source,

    -- ★ 两来源分量（保留，便于调试 / 核对数据）
    COALESCE(s13.s13_qty, 0) AS s13_qty,
    COALESCE(s11.s11_qty, 0) AS s11_qty,

    -- ★ 合并总量 = s13 + s11（回填预排表的 MTD OUTPUT 监控列）
    COALESCE(s13.s13_qty, 0) + COALESCE(s11.s11_qty, 0) AS total_input_qty

FROM      s13_agg AS s13
FULL OUTER JOIN s11_agg AS s11
    ON  s13.model_no = s11.model_no
    AND s13.part_no  = s11.part_no

ORDER BY
    COALESCE(s13.model_no, s11.model_no),
    COALESCE(s13.part_no,  s11.part_no)
;
'''
