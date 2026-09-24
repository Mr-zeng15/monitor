// 预排筛选表格列定义（共享）
// ★ 预排筛选页与审核决议页(方案2)共用同一份列定义，保证表格字段/表头/数据完全一致
export const TABLE_COLUMNS = [
  { key: 'plan_month_label', label: '预排月份', width: 90 }, { key: 'table_date', label: '制表日期', width: 90 },
  { key: 'type', label: 'Type', width: 70 }, { key: 'fab', label: 'FAB', width: 60 },
  { key: 'material_code_52', label: '52阶料号', width: 130 }, { key: 'model', label: 'Model', width: 160 },
  { key: 'pn', label: 'P/N', width: 130 }, { key: 'customer', label: '客户', width: 80 },
  { key: 'n1_dps', label: 'N+1 DPS', width: 90 }, { key: 'n2_dps', label: 'N+2 DPS', width: 90 },
  { key: 'box_quantity', label: '满箱量', width: 80 }, { key: 'request_qty', label: '需求数量(PCS)', width: 110 },
  { key: 'issue_qty_box', label: '领用数量-箱', width: 100 }, { key: 'issue_qty_pcs', label: '领用数量-零数片', width: 110 },
  { key: 'ort_ok', label: '是否满足ORT量', width: 100 }, { key: 'qe_requirement', label: 'QE需求', width: 80 },
  { key: 'qe_remark', label: 'QERemark', width: 100 }, { key: 'ra_remark', label: 'RA REMARK', width: 100 },
  { key: 'gpc_reply', label: 'GPC回复', width: 80 }, { key: 'oqc_hold', label: 'OQC Hold', width: 80 }, { key: 'q_order', label: 'Q工单', width: 100 },
  { key: 'box_number', label: '箱号', width: 80 }, { key: 'sample_date', label: '送样日期', width: 140 },
  { key: 'mtd_output', label: 'MTD OUTPUT监控', width: 120 }, { key: 'judge', label: 'Judge', width: 80 },
  // ★ 2026-09-23：来源文件名较长（如 `Monthly input target s110623.xlsx` / `S13_DPS_202608.xlsx`），
  //   原 width:100 太窄 → 单元格折成 2~3 行，把整行行高撑高。
  //   这里加宽 + 两页对 `.col-source` 做单行省略（配合单元格 title 悬停看全名）。
  { key: 'source', label: '来源文件', width: 160 },
]

// 决议相关字段（审核决议页(方案2) 与预排页共用）
// ★ judge 不参与决议（judge 用于预警显示），仅 QE需求/GPC回复 可决议
export const DECISION_FIELDS = [
  { key: 'qe_requirement', label: 'QE需求' },
  { key: 'gpc_reply', label: 'GPC回复' },
]
