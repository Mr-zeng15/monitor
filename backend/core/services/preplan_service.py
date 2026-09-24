# -*- coding: utf-8 -*-
"""
预排筛选服务（2026-08-07 修订）

需求说明 1.0：导入两份 Excel
  A = S13_DPS*.xlsx       → 第 2 个 sheet（DPS summary）
  B = Monthly input target*.xlsx → 第 2 个 sheet（MPS Detail）

关键修正：
  - 日期从文件名正则提取（YYYYMMDD 或 YYMMDD 格式）
  - MM 基准独立：S13_DPS 与 S11(Monthly) 各自从自身文件名解析月份，两份为独立判断逻辑
  - S13_DPS：找两个连续空表头列 → 其后第 1 列 = MM+1 / N+1 DPS，第 2 列 = MM+2 / N+2 DPS
    （需求说明 1.0：s13 的 dps 是两列空白之后的第二列）
  - Monthly input target：英文月份列按月份值匹配 MM+1 / MM+2
  - ★ S11（Monthly）只抓取 N+1（MM+1）的 DPS，每行输出 1 行；N+2 由 S13_DPS 提供
    （需求说明 1.0：N+2 DPS 来源文件 = S13_DPS）
"""
import calendar
import io
import json
import os
import re
import time
from datetime import date, datetime
from html.parser import HTMLParser

import pandas as pd
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ★ 2026-09-18 性能：优先用 python-calamine（Rust 实现）读 Excel —— xlsx/xls 都比 openpyxl 快约 5 倍。
#   未安装时自动回退 openpyxl，行为完全不变。
#   已实测两引擎「单元格值 100% 一致」（仅末尾空列的列标签 nan / 'Unnamed: N' 名称差异，不参与任何匹配）。
try:
    import python_calamine as _python_calamine  # noqa: F401
    _EXCEL_ENGINE = 'calamine'
except Exception:
    _EXCEL_ENGINE = None


OUTPUT_HEADERS = [
    '预排月份', '制表日期', 'Type', 'FAB', '52阶料号', 'Model', 'P/N', '客户',
    'N+1 DPS', 'N+2 DPS', '满箱量', '需求数量(PCS)', '领用数量-箱', '领用数量-零数片',
    '是否满足ORT量', 'QE需求', 'QERemark', 'RA REMARK', 'GPC回复', 'OQC Hold', 'Q工单',
    '箱号', '送样日期', 'MTD OUTPUT监控', 'Judge', '来源文件',
]
OUTPUT_KEYS = [
    'plan_month_label', 'table_date', 'type', 'fab', 'material_code_52', 'model', 'pn', 'customer',
    'n1_dps', 'n2_dps', 'box_quantity', 'request_qty', 'issue_qty_box', 'issue_qty_pcs',
    'ort_ok', 'qe_requirement', 'qe_remark', 'ra_remark', 'gpc_reply', 'oqc_hold', 'q_order',
    'box_number', 'sample_date', 'mtd_output', 'judge', 'source',
]
HEADER_KEY_PAIRS = list(zip(OUTPUT_HEADERS, OUTPUT_KEYS))

# ★ 导出 Excel 专用列：不含「来源文件」（内部字段，不导出）
EXPORT_HEADERS = [h for h in OUTPUT_HEADERS if h != '来源文件']
EXPORT_KEYS = [k for k in OUTPUT_KEYS if k != 'source']
EXPORT_KEY_PAIRS = list(zip(EXPORT_HEADERS, EXPORT_KEYS))

COLUMN_ALIASES = {
    'pn': ['P/N', 'PN', 'Input P/N & Grade WIP', 'Input PN', 'Input P/N', 'P/N料号', '料号', 'Part Number'],
    'model': ['Model', 'Model P/N', 'MODEL', '型号'],
    'fab': ['FAB', 'Fab', '工厂', '厂区', '晶圆厂'],
    'bu': ['BU', 'B U', '事业部', '业务单元'],
    'n1_dps': ['N+1 DPS', 'N1 DPS', 'N+1', 'DPS N+1', '下个月DPS'],
    'n2_dps': ['N+2 DPS', 'N2 DPS', 'N+2', 'DPS N+2', '下下个月DPS'],
    'request_qty': ['需求数量(PCS)', '需求数量（PCS）', '需求数量', '需求PCS', '需求量', 'Qty'],
    'issue_qty_box': ['领用数量-箱', '领用数量箱', '领用箱数', '箱数'],
    'issue_qty_pcs': ['领用数量-零数片', '领用数量零数片', '零数片', '领用数量(零数片)', '领用零数'],
    'qe_requirement': ['QE需求', 'QE 需求', 'QE需求数量'],
    'qe_remark': ['QERemark', 'QE Remark', 'QE备注'],
    'ra_remark': ['RA REMARK', 'RA Remark', 'RA备注'],
    'q_order': ['Q工单', 'Q工单号', '工单号', 'Q单号'],
    'box_number': ['箱号', 'Box Number'],
    'sample_date': ['送样日期', '送样时间', 'Sample Date'],
    'table_date': ['制表日期', '制定日期', '表格日期'],
}

MONTH_TOKENS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

DEFAULT_ORT_RULES = [
    ('S13', 'S13', '>=', 300),
    ('PD', 'ALL', '>=', 300),
    ('TV', 'ALL', '>=', 2000),
    ('DT', 'ALL', '>=', 2000),
]

RED_FILL = 'FFCCCC'


def _norm_header(v):
    if v is None:
        return ''
    s = str(v).strip().lower()
    s = re.sub(r'[\s_\-./\\()（）\[\]【】+&]', '', s)
    return s


def _to_str(v):
    if v is None:
        return ''
    s = str(v).strip()
    if s.lower() in ('nan', 'none', 'nat'):
        return ''
    return s


def _norm_decision(v):
    """★ 决议字段(qe_requirement/gpc_reply)归一化：严格收敛为 'Y' / 'N' / ''。
    解决导入 Excel 携带的 'YES'/'NO'/'是'/'否' 等自由文本导致 el-select 无法匹配、
    在单元格里原样显示成 "NO" 的问题（见审核决议中心「未选择却显示 NO」）。
    """
    s = _to_str(v).lower()
    if s in ('y', 'yes', '是', 'true', '1', 'ok'):
        return 'Y'
    if s in ('n', 'no', '否', 'false', '0'):
        return 'N'
    return ''


def _to_int(v):
    if v is None:
        return 0
    if isinstance(v, str):
        s = v.strip().replace(',', '')
        if not s:
            return 0
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return 0
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


def _is_blank_num(v):
    """★ 判定「无数据」→ True：None / 空串 / 纯空白 / 'nan' / '-' 等占位符。

    与 _to_int 的关键区别：_to_int('') 会返回 0，把「没有数据」混同为「产量为 0」。
    二者业务语义完全不同：
      · 0    = 一个真实产量值（可能确实未达标）
      · 空   = 上游 MTD 未同步 / 该料号本月无产出记录 → 没有任何依据参与阈值比较
    2026-09-23 修复：空 mtd_output 被当成 0 → `0 >= 阈值` 恒 False → 满屏假「预警」。
    """
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip().lower() in ('', 'nan', 'none', 'nat', 'null', '-', '--')
    return False


def _to_date_str(v):
    if v is None:
        return ''
    if isinstance(v, (datetime, date)):
        return v.strftime('%Y-%m-%d')
    s = _to_str(v)
    if not s:
        return ''
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return s


def _add_month(month, delta):
    """月份加 delta，1-12 循环"""
    return (month - 1 + delta) % 12 + 1


# ==================== 文件名日期提取 ====================

def _month_year_from_filename(file_obj, today=None, file_year=None):
    """
    从「文件名 + 文件属性」中提取基准年月和制表日期（2026-09-04 用户口径）：
       - 月份：只从【文件名】解析（YYYYMMDD / YYYYMM / YYMMDD / 尾部 MMDD 等月标识）
       - 年份：① 文件名显式写 20xx 年份（如 202608/20260803）→ 直接信任文件名；
               ② 文件名没年份（如 s110623）→ 取文件「修改日期」年份 file_year
                  （浏览器 file.lastModified 随上传传入，后端拿不到 mtime）；
               ③ 无 file_year 时：2 位年份且在当年 ±2 内 → 用该年；
               ④ 兜底当前年份。

    文件名示例：
      S13_DPS_20260803.xlsx        → year=2026, month=8   （YYYYMMDD：信任文件名年份）
      S13_DPS_202608.xlsx          → year=2026, month=8   （YYYYMM）
      Monthly input target s110623.xlsx → year=file_year(或当年), month=6 （代号+MMDD）
      Monthly input target s260823.xlsx → year=file_year(或当年±2内 2026), month=8（YYMMDD）
    """
    if today is None:
        today = date.today()
    if file_year is not None:
        try:
            file_year = int(file_year)
            if not 2000 <= file_year <= 2100:
                file_year = None
        except (TypeError, ValueError):
            file_year = None
    name = getattr(file_obj, 'name', '') or ''
    s = os.path.basename(name)

    # 年份兜底：文件属性年份优先，其次当年
    def _fallback_year(yy_guess=None):
        if file_year:
            return file_year
        if yy_guess and abs(yy_guess - today.year) <= 2:
            return yy_guess
        return today.year

    # 1. YYYYMMDD（20 开头的 8 位数字：文件名显式年份 → 直接信任）
    m8 = re.search(r'(20\d{2})(\d{2})(\d{2})', s)
    if m8:
        y, mo, d = int(m8.group(1)), int(m8.group(2)), int(m8.group(3))
        if 2000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
            return y, mo, f'{str(y)[-2:]}/{str(mo).zfill(2)}/{str(d).zfill(2)}'

    # 2. YYYYMM（20 开头的 6 位数字：文件名显式年份 → 直接信任）
    m6y = re.search(r'(20\d{2})(\d{2})(?!\d)', s)
    if m6y:
        y, mo = int(m6y.group(1)), int(m6y.group(2))
        if 2000 <= y <= 2100 and 1 <= mo <= 12:
            return y, mo, f'{str(y)[-2:]}/{str(mo).zfill(2)}/01'

    # 3. YYMMDD（6 位数字：月份/日取名字，年份优先文件属性）
    #    年份不合理（如 s110623 的 11 → 2011）同样视为「代号+MMDD」，月份照取
    m6 = re.search(r'(\d{2})(\d{2})(\d{2})', s)
    if m6:
        yy, mo, dd = int(m6.group(1)), int(m6.group(2)), int(m6.group(3))
        if 1 <= mo <= 12 and 1 <= dd <= 31:
            y = _fallback_year(2000 + yy)
            return y, mo, f'{str(y)[-2:]}/{str(mo).zfill(2)}/{str(dd).zfill(2)}'

    # 4. 兜底：取最后 4 位数字作为 MMDD（月份/日取名字，年份取文件属性/当年）
    md4 = re.search(r'(\d{2})(\d{2})(?!\d)\s*$', s)
    if md4:
        mo, dd = int(md4.group(1)), int(md4.group(2))
        if 1 <= mo <= 12 and 1 <= dd <= 31:
            y = _fallback_year()
            return y, mo, f'{str(y)[-2:]}/{str(mo).zfill(2)}/{str(dd).zfill(2)}'

    # 5. 最终兜底：月份取文件名失败 → 当前日期（年份仍优先文件属性）
    y = _fallback_year()
    return y, today.month, f'{str(y)[-2:]}/{str(today.month).zfill(2)}/{str(today.day).zfill(2)}'



# ==================== 列查找 ====================

def _find_column(df, key):
    """根据 COLUMN_ALIASES 在 df 中找到对应的列名"""
    aliases = [_norm_header(a) for a in COLUMN_ALIASES.get(key, [])]
    for col in df.columns:
        if _norm_header(col) in aliases:
            return col
    return None


def _find_header_row(raw):
    """
    在原始 DataFrame（header=None）中找到表头行索引。

    策略：不是简单地找第一个"有日期"的行（真实 S13 第 1 行是 'CX、CY列勿填'、
    '1/0' 等注释行，可能被误判），而是选择"别名命中数最多"的行；
    若没有任何别名命中，再退化为按日期命中判断。
    """
    all_aliases = set()
    for aliases in COLUMN_ALIASES.values():
        for a in aliases:
            all_aliases.add(_norm_header(a))

    best_row, best_hits = None, 0
    for i in range(min(12, len(raw))):
        vals = raw.iloc[i].values
        normed = [_norm_header(v) for v in vals]
        hits = sum(1 for n in normed if n and n in all_aliases)
        if hits > best_hits:
            best_hits, best_row = hits, i

    if best_row is not None and best_hits >= 2:
        return best_row

    # 退化：没有任何别名命中，找第一个含日期/月份的行
    for i in range(min(12, len(raw))):
        vals = raw.iloc[i].values
        date_hits = any(
            (_date_col_month(v) is not None or _month_from_header(v) is not None)
            for v in vals if v is not None
        )
        if date_hits:
            return i
    return None


def _pick_sheet_name(xls, hints, fallback_index=1):
    """
    从 ExcelFile 中按关键词选 sheet 名称。

    策略：hints 按优先级排列，依次用每个 hint 匹配所有 sheet，
    第一个命中的即返回。例如 S11 文件 hints=['mps detail', 'mps summary', 'mps']，
    'mps detail' 会先命中 'MPS Detail'（明细），而不是排在前面的 'MPS Summary'。
    """
    names = xls.sheet_names
    for h in hints:
        nh = _norm_header(h)
        if not nh:
            continue
        for n in names:
            if nh in _norm_header(n):
                return n
    if len(names) > fallback_index:
        return names[fallback_index]
    return names[0]


# ── ★ 2026-09-23：Excel「真实格式」嗅探 + 中文可操作报错 + 网页表格兜底 ────────────
#
#  背景（用户报「.xls 不能识别，好像只能改成 .xlsx」）：
#    公司系统导出的文件常把扩展名写成 .xls，**内容却不是** Excel 97-2003（BIFF）：
#      · HTML 表格（magic `<htm` / `<!doctype html`）—— 最常见，报表 / ERP / MES 导出；
#      · Excel 2003 XML 电子表格（magic `<?xml`）。
#    pandas 对这两类只会抛
#      ValueError: Excel file format cannot be determined, you must specify an engine manually.
#    纯英文、且完全没说该怎么办 → 只能猜「是不是不支持 xls」，把文件另存为 xlsx 绕过。
#    （实测：**真正的** BIFF .xls 是能读的 —— magic `d0 cf 11 e0 a1 b1 1a e1` → xlrd 引擎，
#      项目便携环境已装 xlrd 2.0.2 + calamine，两条路都通。）
#
#  现在：先按 magic 嗅探真实格式，
#    · html     → 用**标准库**自写的 _HtmlTableParser 兜底（便携环境无 lxml/bs4/html5lib，
#                 不能用 pd.read_html），读得出就照常导入（不必再另存为 xlsx）；
#    · xml2003  → 明确告知「这是 Excel 2003 XML」，并给「另存为 .xlsx」的指引；
#    · unknown  → 明确告知「文件头无法识别」（损坏 / 根本不是 Excel），附原始报错；
#    · xls/xlsx → 走原路径，行为与耗时**完全不变**。
_OLE2_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
_HTML_SHEET_LABEL = '网页表格'


def _sniff_excel_format(f):
    """按文件头判断真实格式：'xls' | 'xlsx' | 'html' | 'xml2003' | 'unknown'"""
    if hasattr(f, 'seek'):
        f.seek(0)
    try:
        head = f.read(8) or b''
    except Exception:
        head = b''
    if hasattr(f, 'seek'):
        f.seek(0)
    if head.startswith(_OLE2_MAGIC):
        return 'xls'                       # 真 Excel 97-2003（BIFF8）
    if head.startswith(b'PK\x03\x04'):
        return 'xlsx'                      # xlsx / xlsm（zip 容器）
    low = head.lower().lstrip()
    if low.startswith(b'<htm') or low.startswith(b'<!doctype html'):
        return 'html'
    if low.startswith(b'<?xml'):
        return 'xml2003'
    return 'unknown'


def _file_label(f):
    return (getattr(f, 'name', '') or '该文件')


def _unique_columns(values):
    """表头行规范化：**对齐 pd.read_excel 的行为**。

    ① 空表头 → `Unnamed: N`（N = 列号）—— 下游 `is_empty_header()` 就是靠
       `'' 或 'unnamed' 前缀` 来识别「两空列 + 月末日期列」结构的；
       若这里留成 `nan` → `_norm_header(nan)` = `'nan'` → 判定为*非空* → 月末列定位整个错位。
    ② 重名 → 第二个起加 `.1`（网页表格里同名列很常见，重复列名会让 pandas 取列出错）。
    """
    out = []
    for i, v in enumerate(values):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            out.append('Unnamed: %d' % i)
        else:
            out.append(v)
    seen, final = {}, []
    for c in out:
        key = str(c)
        if key in seen:
            seen[key] += 1
            final.append('%s.%d' % (key, seen[key]))
        else:
            seen[key] = 0
            final.append(c)
    return final


_NUM_ONLY_RE = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')


def _coerce_cell_text(txt):
    """把网页表格的单元格文本转成与 Excel 路径**同类型**的值。

    ★ 必需（实测踩过）：HTML 里所有单元格都是文本，而 Excel 路径下数字是 int/float。
      下游的过滤规则 / 数值比较按数字语义判断 —— 若拿到 `'0'`（truthy）、`'12.5'`
      （不能参与算术），规则会**静默失灵**。同一份 S13 数据实测：
        真 xlsx → 解析 112 行，通过 98 / 过滤 14
        纯文本 → 解析 112 行，通过 112 / 过滤 0   ← 过滤规则完全没生效
      空单元格统一成 `float('nan')`，与 pandas 读 Excel 的表现对齐。
    """
    s = (txt or '').strip()
    if not s:
        return float('nan')
    if _NUM_ONLY_RE.match(s):
        try:
            f = float(s)
            return int(f) if f.is_integer() else f
        except Exception:
            return s
    return s


class _HtmlTableParser(HTMLParser):
    """极简 HTML 表格解析器 —— **只用标准库**。

    为什么不用 `pd.read_html`：它需要 lxml / bs4 / html5lib，而本项目便携环境三者都没有
    （实测 `Import lxml failed`）。为一个兜底路径给离线部署包增加 C 扩展依赖，
    代价远大于收益，所以这里只用 stdlib 的 html.parser。

    支持：`<table>` / `<tr>` / `<td>` / `<th>`、`colspan`（展开为占位）、`<br>`（转空格）、
          HTML 实体（convert_charrefs 自动反转义）、**可省略的 `</td>`/`</tr>`**。
    不支持 `rowspan`：只保证列数补齐（不崩、不让错位扩散），典型导出场景够用。
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._table = None
        self._row = None
        self._cell = None
        self._colspan = 1

    # ---- 内部收尾（HTML 允许省略 </td> </tr>，所以两者都可能在 starttag 里被触发）----
    def _close_cell(self):
        if self._row is not None and self._cell is not None:
            self._row.append(_coerce_cell_text(''.join(self._cell)))
            for _ in range(self._colspan - 1):
                self._row.append(float('nan'))   # colspan 展开占位
        self._cell = None
        self._colspan = 1

    def _close_row(self):
        if self._table is not None and self._row is not None:
            self._close_cell()
            self._table.append(self._row)
        self._row = None

    # ---- 标签 ----
    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            if self._table is None:
                self._table = []
        elif tag == 'tr':
            self._close_row()
            self._row = []
        elif tag in ('td', 'th'):
            self._close_cell()
            self._cell = []
            try:
                self._colspan = max(1, int(dict(attrs).get('colspan') or 1))
            except Exception:
                self._colspan = 1
        elif tag == 'br' and self._cell is not None:
            self._cell.append(' ')

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag == 'td' or tag == 'th':
            self._close_cell()
        elif tag == 'tr':
            self._close_row()
        elif tag == 'table':
            self._close_row()
            if self._table is not None:
                self.tables.append(self._table)
                self._table = None


def _decode_html_bytes(raw):
    """HTML 编码嗅探：BOM → meta charset → utf-8 → gb18030 → big5。

    ★ 必需：公司系统导出的 HTML 表格常是 GBK/GB2312，直接按 utf-8 解会整片乱码，
      表头文字全认不出 → 反而更像"文件坏了"。（gb18030 是 gbk 的超集，优先用它兜底）
    """
    if not raw:
        return ''
    if raw[:3] == b'\xef\xbb\xbf':
        return raw[3:].decode('utf-8', 'replace')
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        try:
            return raw.decode('utf-16')
        except Exception:
            pass
    m = re.search(r'charset\s*=\s*["\']?\s*([\w\-]+)',
                  raw[:4096].decode('latin-1', 'ignore'), re.I)
    if m:
        try:
            return raw.decode(m.group(1).strip().lower())
        except Exception:
            pass
    for enc in ('utf-8', 'gb18030', 'big5'):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode('utf-8', 'replace')


def _read_html_tables(f):
    """把「HTML 伪装成的 .xls」读成原始行表（header=None、列已对齐的 DataFrame）。"""
    if hasattr(f, 'seek'):
        f.seek(0)
    try:
        raw = f.read()
    except Exception as e:
        raise ValueError(
            '%s 的扩展名虽是 .xls，但内容其实是「网页表格(HTML)」，读取失败：%s。'
            '请用 Excel / WPS 打开它，「另存为 .xlsx」后再导入。' % (_file_label(f), e)
        ) from None

    parser = _HtmlTableParser()
    try:
        parser.feed(_decode_html_bytes(raw))
        parser.close()
    except Exception as e:
        raise ValueError(
            '%s 内容其实是「网页表格(HTML)」，解析失败：%s。'
            '请用 Excel / WPS 打开它，「另存为 .xlsx」后再导入。' % (_file_label(f), e)
        ) from None

    tables = [t for t in parser.tables
              if t and any(any(c is not None for c in r) for r in t)]
    if not tables:
        raise ValueError(
            '%s 的扩展名虽是 .xls，但内容其实是「网页表格(HTML)」，里面没有可用的表格数据。'
            '请用 Excel / WPS 打开它，「另存为 .xlsx」后再导入。' % _file_label(f)
        )
    # 列数对齐（各行按本表最大列数补 None），再取「最像数据表」的那张
    norm = []
    for t in tables:
        w = max(len(r) for r in t)
        norm.append([list(r) + [float('nan')] * (w - len(r)) for r in t])
    best = max(norm, key=lambda t: len(t) * max(len(t[0]) if t else 0, 1))
    return pd.DataFrame(best, dtype=object)


def _read_sheet_df(file_obj, hints, fallback_index=1):
    """读取 Excel file_obj，自动定位 sheet 和表头行，返回 df 和 sheet 名"""
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)
    fmt = _sniff_excel_format(file_obj)

    if fmt == 'xml2003':
        raise ValueError(
            '%s 是「Excel 2003 XML 电子表格」，不是标准 Excel 工作簿（.xls 只是它的文件名后缀）。'
            '请用 Excel / WPS 打开它，「另存为 .xlsx」后再导入。' % _file_label(file_obj)
        )

    html_full = None
    if fmt == 'html':
        # ★ 网页表格兜底：读成「无表头」的全量表，表头行交给下方统一逻辑定位
        html_full = _read_html_tables(file_obj)
        sheet_name = _HTML_SHEET_LABEL
        raw = html_full.iloc[:12]
    else:
        try:
            xls = pd.ExcelFile(file_obj)
        except Exception as e:
            if fmt == 'unknown':
                raise ValueError(
                    '%s 无法识别为 Excel 文件：文件头既不是 xlsx(zip)、也不是 xls(OLE2 复合文档)，'
                    '也不是网页表格。可能文件已损坏，或它根本不是 Excel 文件。原始报错：%s'
                    % (_file_label(file_obj), e)
                ) from None
            raise ValueError('无法读取 Excel 文件: %s' % e) from None
        sheet_name = _pick_sheet_name(xls, hints, fallback_index)
        # ★ 2026-09-18 性能修复：表头探测只需前 12 行（_find_header_row 只扫 min(12, len(raw))）。
        #   原先这里用「全量」首读 → 同一个 sheet 被 openpyxl 完整解析了两遍，大文件上这是主要耗时。
        #   实测 1500 行 × 109 列：全量首读 1.54s → nrows=12 仅 0.02s（语义完全不变）。
        raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, dtype=object, nrows=12)

    header_row = _find_header_row(raw)
    if header_row is None:
        raise ValueError('无法定位表头行（%s: %s）' % ('sheet' if html_full is None else _HTML_SHEET_LABEL, sheet_name))

    if html_full is not None:
        # 网页表格只有一份数据，无法像 Excel 那样「按 header=N 重读」→ 手工切片。
        # 列名保持单元格**原值**（与 Excel 路径一致：日期列可能是字符串，交给 _date_col_ymd 解析）。
        df = html_full.iloc[header_row + 1:].copy()
        df.columns = _unique_columns(html_full.iloc[header_row].values)
        return df.reset_index(drop=True), sheet_name

    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)
    # ★ 2026-09-18 性能：全量读这一步用 calamine 引擎（若已安装）—— 大文件上这是主要耗时。
    _ekw = {'engine': _EXCEL_ENGINE} if _EXCEL_ENGINE else {}
    df = pd.read_excel(file_obj, sheet_name=sheet_name, header=header_row, dtype=object, **_ekw)
    return df, sheet_name


# ==================== 日期/月份辅助 ====================

def _month_from_header(v):
    """从表头值中提取月份（英文月份名或数字月），如 Aug-26 → 8"""
    if v is None:
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.month
    if isinstance(v, (int, float)):
        try:
            f = float(v)
            if f.is_integer() and 1 <= f <= 12:
                return int(f)
        except (ValueError, TypeError):
            return None
        return None
    s = str(v).strip().lower()
    m = re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b', s)
    if m:
        return MONTH_TOKENS[m.group(1)]
    m = re.search(r'(\d{1,2})\s*月', s)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 12:
            return n
    return None


def _date_col_month(v):
    """从表头值中提取月份：
    支持 M/D（8/31、12/1）、YYYY-MM-DD、YYYY-MM-DD HH:MM:SS(.n)、YYYYMMDD、datetime 等格式。
    无效日期（如 1/0）返回 None。
    """
    if v is None:
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.month
    s = str(v).strip()
    # M/D 格式如 8/31、12/1
    m = re.match(r'^(\d{1,2})/(\d{1,2})(?:\.\d+)?$', s)
    if m:
        n, d = int(m.group(1)), int(m.group(2))
        return n if 1 <= n <= 12 and 1 <= d <= 31 else None
    # YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS(.n) 格式
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ .]|$)', s)
    if m:
        mo = int(m.group(2))
        d = int(m.group(3))
        return mo if 1 <= mo <= 12 and 1 <= d <= 31 else None
    # YYYYMMDD 格式
    s2 = re.sub(r'\D', '', s)
    if len(s2) == 8:
        try:
            mo = int(s2[4:6])
            if 1 <= mo <= 12:
                return mo
        except ValueError:
            return None
    return None


def _pure_month_col(v):
    """
    判断表头是否为「纯月份列」：表头规范化后 = 月份缩写（可带 2~4 位年份），
    如 Jun、May-26、Aug26、6月。
    用于排除 Jun.Var / Jun L. / Jun T / ~Jan缺口 等变体列。
    """
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.month
    n = _norm_header(v)
    if not n:
        return None
    # 中文「8月」
    m = re.match(r'^(\d{1,2})月$', n)
    if m:
        mo = int(m.group(1))
        return mo if 1 <= mo <= 12 else None
    # 英文月份缩写 + 可选年份
    m = re.match(r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{2,4})?$', n)
    if m:
        return MONTH_TOKENS[m.group(1)]
    return None


# ==================== DPS 列定位 ====================

def _date_col_month_day(v):
    """从表头值中提取 (month, day)；支持 M/D、YYYY-MM-DD、YYYYMMDD、datetime 等格式。无效返回 None"""
    if v is None:
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.month, v.day
    s = str(v).strip()
    m = re.match(r'^(\d{1,2})/(\d{1,2})(?:\.\d+)?$', s)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return mo, d
        return None
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ .]|$)', s)
    if m:
        mo, d = int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return mo, d
        return None
    s2 = re.sub(r'\D', '', s)
    if len(s2) == 8:
        try:
            mo, d = int(s2[4:6]), int(s2[6:8])
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return mo, d
        except ValueError:
            return None
    return None


def _add_month_ym(year, month, delta):
    """年月加 delta（可为负），自动处理跨年/跨年号，返回 (year, month)"""
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def _date_col_ymd(v):
    """
    从表头值中提取 (year, month, day)，支持：
      YYYY-MM-DD / YYYY-MM-DD HH:MM:SS(.n) / YYYYMMDD / datetime / M/D(8/31)
    带年份格式返回完整年月日；M/D 格式无年份返回 (None, month, day)。无效返回 None。
    """
    if v is None:
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.year, v.month, v.day
    s = str(v).strip()
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ .]|$)', s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return y, mo, d
        return None
    s2 = re.sub(r'\D', '', s)
    if len(s2) == 8:
        try:
            y, mo, d = int(s2[0:4]), int(s2[4:6]), int(s2[6:8])
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return y, mo, d
        except ValueError:
            pass
        return None
    m = re.match(r'^(\d{1,2})/(\d{1,2})(?:\.\d+)?$', s)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return None, mo, d
        return None
    return None


def _is_month_end_day(y, mo, d):
    """
    判断 (y, mo, d) 是否为该月最后一天。
    按日历月真实天数判断（calendar.monthrange），不写死 28/29/30/31；
    无年份（M/D 表头）时退化为日 >= 28。
    """
    if y is None:
        return d >= 28
    return d == calendar.monthrange(y, mo)[1]


def _find_month_end_dps_cols_s13(df, year, month):
    """
    S13_DPS 的 DPS 列定位（业务规则，需求说明 1.0）：
      「s13 文件的 dps 是两列空白之后的第二列，这一列表头是日期，下面是 dps 的数据」

    完全自适应（不写死月份 / 天数 / 列数）：
      1. 结构定位：两个连续空表头 → 其后连续日期表头列 = 月末列候选组
         （每日列在前、两空列分隔，故候选组内都是月末汇总列）
      2. ★ 年月值匹配：从候选组中按 (year, month) 精确匹配 MM+1 / MM+2
         —— 候选组起点、列数随月份组合变化（123月 / 456月 / 跨年 11-12-1月）
         都能命中，不再依赖「第 1 列 / 第 2 列」的位置假设
      3. 退化：找不到两空列结构时，从全部列中识别「月末日」列（按日历月真实天数）再匹配
      4. 兜底：候选组非空但按值匹配不到时，按位置取第 1 / 2 列（防解析崩溃）

    返回：(n1_col, n2_col, all_month_end_cols)
      n1_col: (年,月) == MM+1 的列（N+1 DPS），找不到则 None
      n2_col: (年,月) == MM+2 的列（N+2 DPS，即需求说的「两列空白之后的第二列」），找不到则 None
      all_month_end_cols: 定位到的月末列组 [ (col, (y, mo, d)), ... ]
    """
    cols = list(df.columns)
    col_norms = [(i, col, _norm_header(col)) for i, col in enumerate(cols)]

    def is_empty_header(n):
        return n == '' or n.startswith('unnamed')

    # 1. 找两个连续空表头，跳过它们后的列是月末日期列组
    empty_indices = [i for i, col, n in col_norms if is_empty_header(n)]
    split_idx = None
    for i in range(len(empty_indices) - 1):
        if empty_indices[i + 1] - empty_indices[i] == 1:
            split_idx = empty_indices[i + 1] + 1  # 跳过这两个空表头
            break

    month_end_cols = []  # [(col, (y, mo, d)), ...]
    if split_idx is not None:
        for i in range(split_idx, len(cols)):
            col = cols[i]
            ymd = _date_col_ymd(col)
            if ymd:
                month_end_cols.append((col, ymd))
            elif month_end_cols:
                # 连续日期列中断（遇到非日期表头），不再向后收集
                break

    # 2. 退化：没有两空列结构 → 从全部列中识别「月末日」列
    if not month_end_cols:
        for col in cols:
            ymd = _date_col_ymd(col)
            if ymd and _is_month_end_day(*ymd):
                month_end_cols.append((col, ymd))

    # 3. ★ 年月值精确匹配 MM+1 / MM+2（核心，自适应月份组合与列数）
    y1, m1 = _add_month_ym(year, month, 1)
    y2, m2 = _add_month_ym(year, month, 2)
    n1_col = n2_col = None
    for col, (cy, cm, cd) in month_end_cols:
        # 带年份：年月都必须匹配（处理跨年）；M/D 无年份：只按月份匹配
        if n1_col is None and cm == m1 and (cy is None or cy == y1):
            n1_col = col
        if n2_col is None and cm == m2 and (cy is None or cy == y2):
            n2_col = col

    # 4. 兜底：匹配不到时按位置取第 1 / 2 列
    if not n1_col and len(month_end_cols) >= 1:
        n1_col = month_end_cols[0][0]
    if not n2_col and len(month_end_cols) >= 2:
        n2_col = month_end_cols[1][0]

    return n1_col, n2_col, month_end_cols


def _find_monthly_dps_cols(df, month):
    """
    Monthly input target 的 DPS 列定位：
      找出所有「纯月份列」（表头 = Jun/Jul/Aug 或 May-26 等，排除 Jun.Var / Jun L. /
      ~Jan缺口 等变体列）→ 按月份值精确匹配 MM+1 和 MM+2 对应的列。

    返回：(n1_col, n2_col)
    """
    cols = list(df.columns)
    month_cols = []
    for i, col in enumerate(cols):
        m = _pure_month_col(col)
        if m:
            month_cols.append((i, m, col))

    if not month_cols:
        # 退化：尝试匹配任何英文月份列（含变体），按位置取最后几个
        for i, col in enumerate(cols):
            m = _month_from_header(col)
            if m:
                month_cols.append((i, m, col))

    if not month_cols:
        raise ValueError('Monthly input target 未识别到月份列')

    m1 = _add_month(month, 1)
    m2 = _add_month(month, 2)

    n1_col = None
    n2_col = None

    # 优先精确匹配月份值
    for _, m, col in month_cols:
        if m == m1 and n1_col is None:
            n1_col = col
        if m == m2 and n2_col is None:
            n2_col = col

    # 位置兜底：纯月份列按出现顺序，第 2 个视为 MM+1、第 3 个视为 MM+2
    # （第 1 个视为 MM，即"当前月份列"在最前）
    if not n1_col and len(month_cols) >= 2:
        n1_col = month_cols[1][2]
    if not n2_col and len(month_cols) >= 3:
        n2_col = month_cols[2][2]
    if not n1_col and len(month_cols) >= 1:
        n1_col = month_cols[0][2]
    if not n2_col and n1_col:
        n2_col = n1_col

    return n1_col, n2_col


# ==================== S13_DPS 解析 ====================

def parse_s13_dps(file_obj, year=None, month=None, file_year=None):
    """
    解析 S13_DPS：DPS summary sheet，数字日期列，预排月份 MM+2。
    每行输出 1 行。

    列映射（MM 由文件名决定，如 202607 → MM=7）：
      - 两空列后第 1 列（8/31）= MM+1 月末
      - 两空列后第 2 列（9/30）= MM+2 月末 → N+2 DPS（n2_dps）
        （需求说明 1.0：s13 文件的 dps 是两列空白之后的第二列）

    file_year：文件「修改日期」年份（前端 file.lastModified 传入）——
    文件名无 20xx 显式年份时作为年份来源（2026-09-04）。

    ★ 业务规则：S13 只保留 N+2 的数据，N+1 全部放空（n1_dps=0，记录不删除）。
      与 S11（Monthly 只抓 N+1）配合：N+1 由 Monthly 提供，N+2 由 S13 提供。
    """
    today = date.today()
    if year is None or month is None:
        year, month, td = _month_year_from_filename(file_obj, today, file_year)
    table_date = _month_year_from_filename(file_obj, today, file_year)[2]

    df, sheet = _read_sheet_df(file_obj, ['dps summary', 'dps'])
    col_pn = _find_column(df, 'pn')
    col_model = _find_column(df, 'model')
    col_fab = _find_column(df, 'fab')
    col_bu = _find_column(df, 'bu')

    missing = []
    if not col_pn:
        missing.append('P/N')
    if not col_model:
        missing.append('Model')
    # ★ FAB 为可选列：缺失时不报错（可能被用户粘贴/整理导致该列缺失）
    if missing:
        raise ValueError(
            f'S13_DPS 缺少必要列: {", ".join(missing)}。'
            f'实际表头: {[str(c) for c in list(df.columns)[:25]]}'
        )

    n1_col, n2_col, month_end_cols = _find_month_end_dps_cols_s13(df, year, month)
    if not n2_col and not n1_col:
        raise ValueError('S13_DPS 未识别到月末 DPS 列（两空列后的日期列）')

    plan_month = _add_month(month, 2)
    # ★ 跨年时标注年份：如 12 月文件 → 预排次年 2 月，显示「2027年2月」
    plan_year_num = year + (1 if month + 2 > 12 else 0)
    plan_label = f'{plan_year_num}年{plan_month}月' if plan_year_num != year else f'{plan_month}月'

    col_request = _find_column(df, 'request_qty')
    col_box = _find_column(df, 'issue_qty_box')
    col_pcs = _find_column(df, 'issue_qty_pcs')
    col_qe = _find_column(df, 'qe_requirement')
    col_qer = _find_column(df, 'qe_remark')
    col_ra = _find_column(df, 'ra_remark')
    col_qo = _find_column(df, 'q_order')
    col_boxno = _find_column(df, 'box_number')
    col_sdate = _find_column(df, 'sample_date')

    rows = []
    for idx, row in df.iterrows():
        pn = _to_str(row.get(col_pn))
        model = _to_str(row.get(col_model))
        fab = _to_str(row.get(col_fab))
        bu = _to_str(row.get(col_bu)) if col_bu else ''
        if not (pn or model or fab):
            continue
        rows.append({
            'source': 'S13_DPS',
            'plan_year': year,
            # ★ 2026-09-20 预排年月（YYYYMM）：与 plan_month_label 同源（文件月+2，跨年取次年）
            'plan_ym': plan_year_num * 100 + plan_month,
            'serial_number': int(idx) + 1,
            'plan_month_label': plan_label,
            'table_date': table_date,
            'type': '',
            'fab': fab,
            'bu': bu,
            'material_code_52': '',
            'model': model,
            'pn': pn,
            'customer': '',
            # ★ S13 只保留 N+2 的数据，N+1 放空（不删除记录）
            'n1_dps': 0,
            'n2_dps': _to_int(row.get(n2_col)) if n2_col else 0,
            'box_quantity': 0,
            'request_qty': _to_int(row.get(col_request)) if col_request else 0,
            'issue_qty_box': _to_int(row.get(col_box)) if col_box else 0,
            'issue_qty_pcs': _to_int(row.get(col_pcs)) if col_pcs else 0,
            'ort_ok': '',
            'qe_requirement': _norm_decision(row.get(col_qe)) if col_qe else '',
            'qe_remark': _to_str(row.get(col_qer)) if col_qer else '',
            'ra_remark': _to_str(row.get(col_ra)) if col_ra else '',
            'gpc_reply': '',
            'q_order': _to_str(row.get(col_qo)) if col_qo else '',
            'box_number': _to_str(row.get(col_boxno)) if col_boxno else '',
            'sample_date': _to_date_str(row.get(col_sdate)) if col_sdate else '',
            'mtd_output': '',
            'judge': '',
            'source_file_name': getattr(file_obj, 'name', '') or '',
            'missing_fields': '',
            'filter_reason': '',
            'status': 'kept',
        })
    return rows


# ==================== Monthly input target 解析 ====================

def parse_monthly_input(file_obj, year=None, month=None, file_year=None):
    """
    解析 Monthly input target（S11）：MPS Detail sheet，英文月份列，Type 取自 BU。
    每行输出 1 行（MM+1 / N+1 DPS）。

    ★ 业务规则：S11 这份只抓取 N+1（MM+1）的 DPS；
      N+2（MM+2）由 S13_DPS 提供（需求说明 1.0：N+2 DPS 来源文件 = S13_DPS）。

    注意：S11(Monthly) 与 S13 是两份独立的判断逻辑，MM 基准各自从自身文件名解析
    （s110623 中的 0623 = 产品代号+制表日期，月份取自身文件）；
    年份：文件名无 20xx 显式年份时取 file_year（文件修改日期年份，2026-09-04）。
    """
    today = date.today()
    if year is None or month is None:
        year, month, td = _month_year_from_filename(file_obj, today, file_year)
    table_date = _month_year_from_filename(file_obj, today, file_year)[2]

    # S11（Monthly input target）优先读 MPS Detail（明细），兼容 MPS Summary
    df, sheet = _read_sheet_df(file_obj, ['mps detail', 'mps summary', 'mps'])
    col_pn = _find_column(df, 'pn')
    col_model = _find_column(df, 'model')
    col_fab = _find_column(df, 'fab')
    col_bu = _find_column(df, 'bu')

    missing = []
    if not col_pn:
        missing.append('P/N')
    if not col_model:
        missing.append('Model')
    # ★ FAB/BU 为可选列：缺失时不报错（可能被用户粘贴/整理导致该列缺失）
    if missing:
        raise ValueError(
            f'Monthly input target 缺少必要列: {", ".join(missing)}。'
            f'实际表头: {[str(c) for c in list(df.columns)[:25]]}'
        )

    # ★ 只取 MM+1（N+1）列；N+2 由 S13 提供，此处不抓
    n1_col, _ = _find_monthly_dps_cols(df, month)
    if not n1_col:
        raise ValueError('Monthly input target 未识别到英文月份列（提取 MM+1 对应列失败）')

    m1 = _add_month(month, 1)

    col_request = _find_column(df, 'request_qty')
    col_box = _find_column(df, 'issue_qty_box')
    col_pcs = _find_column(df, 'issue_qty_pcs')
    col_qe = _find_column(df, 'qe_requirement')
    col_qer = _find_column(df, 'qe_remark')
    col_ra = _find_column(df, 'ra_remark')
    col_qo = _find_column(df, 'q_order')
    col_boxno = _find_column(df, 'box_number')
    col_sdate = _find_column(df, 'sample_date')

    rows = []
    last_model = ''  # ★ 向下填充：连续多行同一 model 时，后续留空行继承上一个 model
    for idx, row in df.iterrows():
        pn = _to_str(row.get(col_pn))
        model = _to_str(row.get(col_model))
        fab = _to_str(row.get(col_fab))
        bu = _to_str(row.get(col_bu))
        if not (pn or model or fab or bu):
            continue
        # ★ Monthly 的 Model 按业务要求截取前 11 位
        if model:
            model = model[:11]
            last_model = model
        elif last_model:
            # ★ model 留空但属于同一 model 连续行 → 自动填充/识别为同一 model
            model = last_model

        n1_val = _to_int(row.get(n1_col)) if n1_col else 0

        base = {
            'source': 'Monthly_Input',
            'plan_year': year,
            'serial_number': int(idx) + 1,
            'table_date': table_date,
            'type': bu,
            'fab': fab,
            'bu': bu,
            'material_code_52': '',
            'model': model,
            'pn': pn,
            'customer': '',
            'box_quantity': 0,
            'request_qty': _to_int(row.get(col_request)) if col_request else 0,
            'issue_qty_box': _to_int(row.get(col_box)) if col_box else 0,
            'issue_qty_pcs': _to_int(row.get(col_pcs)) if col_pcs else 0,
            'ort_ok': '',
            'qe_requirement': _norm_decision(row.get(col_qe)) if col_qe else '',
            'qe_remark': _to_str(row.get(col_qer)) if col_qer else '',
            'ra_remark': _to_str(row.get(col_ra)) if col_ra else '',
            'gpc_reply': '',
            'q_order': _to_str(row.get(col_qo)) if col_qo else '',
            'box_number': _to_str(row.get(col_boxno)) if col_boxno else '',
            'sample_date': _to_date_str(row.get(col_sdate)) if col_sdate else '',
            'mtd_output': '',
            'judge': '',
            'source_file_name': getattr(file_obj, 'name', '') or '',
            'missing_fields': '',
            'filter_reason': '',
            'status': 'kept',
        }

        # ★ 业务规则：S11 只抓 N+1（MM+1）的 DPS，每行输出 1 行；N+2 由 S13 提供
        row = dict(base)
        # ★ 跨年时标注年份：如 12 月文件 → 预排次年 1 月，显示「2027年1月」
        m1_year = year + (1 if month + 1 > 12 else 0)
        row['plan_month_label'] = f'{m1_year}年{m1}月' if m1_year != year else f'{m1}月'
        # ★ 2026-09-20 预排年月（YYYYMM）：与 label 同源（文件月+1，跨年取次年）
        row['plan_ym'] = m1_year * 100 + m1
        row['n1_dps'] = n1_val
        row['n2_dps'] = 0  # S11 不提供 N+2 DPS（N+2 来自 S13_DPS）
        row['_ort_dps'] = n1_val  # ORT 用 N+1 DPS

        rows.append(row)

    return rows


# ==================== 合并 / 规则 ====================

def merge_sources(rows_s13, rows_monthly):
    return list(rows_s13) + list(rows_monthly)


def apply_type_rule_s13(rows):
    """规则七：S13 按 P/N 左 2 位判定 Type（97→BIM；93/99→SET）"""
    for r in rows:
        if r.get('source') != 'S13_DPS':
            continue
        left2 = (r.get('pn') or '').strip().upper()[:2]
        if left2 == '97':
            r['type'] = 'BIM'
        elif left2 in ('93', '99'):
            r['type'] = 'SET'
        else:
            r['type'] = ''


def apply_entry_table(rows, entry_map):
    """规则三：按 P/N 从基础资料表带入 52阶料号/满箱量/客户，查无标红"""
    for r in rows:
        key = (r.get('pn') or '').strip()
        e = entry_map.get(key)
        if e:
            r['material_code_52'] = e.material_code_52 or ''
            r['box_quantity'] = e.box_quantity or 0
            r['customer'] = e.customer or ''
            r['missing_fields'] = ''
        else:
            r['material_code_52'] = ''
            r['box_quantity'] = 0
            r['customer'] = ''
            r['missing_fields'] = json.dumps(['P/N', '52阶料号', '满箱量', '客户'], ensure_ascii=False)


def refresh_entry_backfill(year=None):
    """
    ★ 基础资料表变更后「刷新回填」：对已导入的 PreplanRow 按 P/N 重新从基础资料表
      带回 52阶料号/满箱量/客户，无需重新导入 Excel。
      ★ 2026-09-09：放开到【全部来源】（原仅 Monthly_Input/S11）——审核决议中心
        「基础资料比对回填」需覆盖 S13 行；命中则覆盖为权威主数据值，
        未命中时【保留该行已有值】（S13 Excel 自带料号不清空），仅当整行为空料号时标 missing。
      返回更新过的行数。
    """
    from ..models import EntryTable, PreplanRow
    from django.utils import timezone
    entry_map = {}
    for e in EntryTable.objects.all():
        if e.pn:
            entry_map[e.pn.strip()] = e
    qs = PreplanRow.objects.all()
    if year:
        qs = qs.filter(plan_year=year)
    missing = json.dumps(['P/N', '52阶料号', '满箱量', '客户'], ensure_ascii=False)
    # ★ 性能优化：bulk_update 批量写入（原逐行 save 在大数据量时耗时显著）
    changed = []
    now = timezone.now()
    for obj in qs.iterator():
        key = (obj.pn or '').strip()
        e = entry_map.get(key)
        if e:
            # ★ 2026-09-09：逐字段【仅非空才覆盖】——基础资料表为空的字段不覆盖，
            #   保留该行原有值（如 S13 Excel 自带客户/料号，或人工已填的箱量），避免空值冲掉已有信息
            m52 = (e.material_code_52 or '').strip()
            box = e.box_quantity or 0
            cust = (e.customer or '').strip()
            new_vals = (m52 if m52 else (obj.material_code_52 or ''),
                        box if box else (obj.box_quantity or 0),
                        cust if cust else (obj.customer or ''))
            if (obj.material_code_52 != new_vals[0] or obj.box_quantity != new_vals[1]
                    or obj.customer != new_vals[2] or (obj.missing_fields or '') != ''):
                obj.material_code_52, obj.box_quantity, obj.customer = new_vals
                obj.missing_fields = ''
                obj.updated_at = now
                changed.append(obj)
        else:
            # ★ 未命中：不清空已有值（S13 Excel 自带料号/客户原样保留）；
            #   仅当该行完全没有料号时才标 missing 提示补录
            if not (obj.material_code_52 or '').strip() and (obj.missing_fields or '') != missing:
                obj.missing_fields = missing
                obj.updated_at = now
                changed.append(obj)
    if changed:
        PreplanRow.objects.bulk_update(
            changed, ['material_code_52', 'box_quantity', 'customer', 'missing_fields', 'updated_at'],
            batch_size=1000)
    return len(changed)


def apply_basic_filters(rows):
    """
    规则一/二：P/N 90/9F、DPS=0 过滤，记录原因。

    - S13_DPS：N+1 已按要求放空（只保留 N+2），不参与 N+1 DPS=0 检查（否则会被误杀）；
      记录保留，仅按 P/N 90/9F 过滤。
    - Monthly_Input：只抓 N+1（MM+1），按 N+1 DPS 是否 0 过滤。
    """
    kept, filtered = [], []
    for r in rows:
        reasons = []
        pn = (r.get('pn') or '').strip().upper()
        if pn[:2] in ('90', '9F'):
            reasons.append('P/N左2码为90或9F')
        # ★ DPS=0 检查：S13 跳过（N+1 已放空，N+2 直接带入）；Monthly 检查 N+1
        if r.get('source') != 'S13_DPS':
            actual_dps = _to_int(r.get('_ort_dps', r.get('n1_dps')))
            if actual_dps == 0:
                reasons.append('N+1 DPS = 0')
        r['filter_reason'] = '；'.join(reasons)
        r['status'] = 'filtered' if reasons else 'kept'
        (filtered if reasons else kept).append(r)
    return kept, filtered


def _apply_operator(num, op, threshold):
    if op == '>=':
        return num >= threshold
    if op == '>':
        return num > threshold
    if op == '<=':
        return num <= threshold
    if op == '<':
        return num < threshold
    if op == '==':
        return num == threshold
    if op == '<>':
        return num != threshold
    return True


def _pick_ort_rule(r, rules):
    """按 Type/来源匹配 ORT 规则，返回命中的规则(或 None)。
    优先级：1) 具体 Type+精确来源 > 2) 具体 Type+ALL > 3) 空 Type+精确来源 > 4) 空 Type+ALL

    ★ 来源判定（s11/s13 规则分离）：
      - 计划行：source='S13_DPS' → S13 规则；Monthly_Input → MONTHLY 规则
      - 计划外行：按 mtd_source 判定 —— 's13' → S13 规则；'s11' 或空 → MONTHLY 规则
        （新 SQL 带 source 列后，s13 计划外不再被误套 Monthly 规则）
    """
    source = r.get('source')
    mtd_src = (r.get('mtd_source') or '').strip().lower()
    if source == 'S13_DPS' or mtd_src == 's13':
        rule_source = 'S13'
        key = 'S13'
    else:
        rule_source = 'MONTHLY'
        key = (r.get('type') or '').strip().upper()
    exact = [x for x in rules if x.type_name and x.type_name.upper() == key and x.source == rule_source]
    generic = [x for x in rules if x.type_name and x.type_name.upper() == key and x.source == 'ALL']
    global_src = [x for x in rules if not x.type_name and x.source == rule_source]
    global_all = [x for x in rules if not x.type_name and x.source == 'ALL']
    return key, (exact or generic or global_src or global_all or [None])[0]


def apply_ort(rows, rules):
    """
    规则四：ORT 量判断（★ 基线 = 【计划预测量 DPS】对比 ORT 规则阈值）

    ★ 语义归位（2026-09-15）：ort_ok 必须与「筛选结果」严格绑定 ——
      通过 ORT 规则留在「通过」清单 → Y；未通过被 filter_ort_n 移出 → N。
      因此这里统一采用与导入筛选完全相同的 DPS 预测量基线，
      ★ 不再用 mtd_output（实际产量）覆盖 ort_ok：
        否则 MTD 同步 / 改规则重算后会出现「行还在通过清单里、是否满足ORT量却显示 N」
        的矛盾（实测存量 38 行 kept + ort_ok='N'），且前端「通过」视图会
        按 ort_ok!=='N' 把这些行过滤掉 → 表现为「切个页面回来数据少了一截」。
      ★ 按「该行实际拥有的量」取基线：
      - 计划行（有 DPS 预测量）：S13_DPS → n2_dps（N+2 DPS）；
        Monthly_Input → _ort_dps（= N+1 DPS）或 n1_dps / n2_dps
      - 计划外行（实时监控抓来的，只有实际产量）→ mtd_output。
        （计划外行没有 DPS 预测量，套 DPS 基线会全部误判成 N）
      - ★ 计划外行：Type 未回填时不参与规则对比（阈值 0 导致误判达标）→ ort_ok=''
        （s13 来源的计划外行例外：S13 规则不依赖 Type，可直接判定）
    """
    for r in rows:
        if r.get('is_plan_external') and not (r.get('type') or '').strip() \
                and (r.get('mtd_source') or '').strip().lower() != 's13':
            r['ort_ok'] = ''
            if '_ort_dps' in r:
                del r['_ort_dps']
            continue
        key, rule = _pick_ort_rule(r, rules)
        if not key and rule is None:
            r['ort_ok'] = 'N/A'
        elif rule is None:
            # 没有匹配规则默认 Y
            r['ort_ok'] = 'Y'
        else:
            # ★ 计划外行只有实际产量 → mtd_output 基线；计划行 → DPS 预测量基线
            if r.get('is_plan_external'):
                num = _to_int(r.get('mtd_output'))
            elif r.get('source') == 'S13_DPS':
                num = _to_int(r.get('n2_dps'))
            else:
                num = _to_int(r.get('_ort_dps', r.get('n1_dps') or r.get('n2_dps')))
            r['ort_ok'] = 'Y' if _apply_operator(num, rule.operator, rule.threshold) else 'N'

        if '_ort_dps' in r:
            del r['_ort_dps']


def apply_ort_by_forecast(rows, rules):
    """
    ★ 向后兼容别名（2026-09-15）：ORT 筛选基线即 DPS 预测量基线，
      现已合并进 apply_ort，保留此名以免老调用点失效。
    """
    apply_ort(rows, rules)


def apply_judge_by_mtd(rows, rules):
    """
    ★ 实时预警判定（2026-09-15 语义拆分）：judge 由【实际产量 mtd_output】
      对比 ORT 规则决定，与 ort_ok（筛选基线，DPS 预测量）彻底解耦。

      两者职责不同，不可互相派生：
        - ort_ok 回答「是否满足 ORT 量 → 能否通过筛选」（DPS 预测量基线）
        - judge  回答「实际产量是否已达目标 → 能否处理」（mtd_output 基线）

      - mtd_output 未达阈值 → judge='预警'（绿灯，生产中）
      - 达标 / 无匹配规则 → judge 置空（不显示 'OK'，保留手动填写值）
      - ★ 计划外行 Type 未回填 → judge='待回填'（s13 来源例外）
    """
    for r in rows:
        if r.get('is_plan_external') and not (r.get('type') or '').strip() \
                and (r.get('mtd_source') or '').strip().lower() != 's13':
            r['judge'] = '待回填'
            continue
        _key, rule = _pick_ort_rule(r, rules)
        # ★ 2026-09-23 修复「空 mtd_output → 假预警」：
        #   mtd_output 为空表示 MTD 尚未同步 / 该料号无产出记录，没有任何实际产量依据，
        #   不能通过 _to_int 归 0 后去比阈值（`0 >= 2000` 恒 False → 恒判「预警」）。
        #   与「无匹配规则」同一处理：不预警，并清掉历史遗留的假「预警」值。
        if rule is None or _is_blank_num(r.get('mtd_output')):
            r['judge'] = '' if r.get('judge') in ('预警', 'OK') else (r.get('judge') or '')
            continue
        num = _to_int(r.get('mtd_output'))
        if _apply_operator(num, rule.operator, rule.threshold):
            r['judge'] = '' if r.get('judge') in ('预警', 'OK') else (r.get('judge') or '')
        else:
            r['judge'] = '预警'


def filter_ort_n(rows):
    """
    ★ ORT 过滤规则（S13 + Monthly 通用）：
      ORT 判定为 N（不满足对应规则阈值）的行过滤到被过滤清单（记录原因，不删除记录），
      不再显示在「通过」清单中。
      - S13：不论 P/N 类型，N+2 DPS >= 300 才保留
      - Monthly：按自身 Type 匹配的规则判断（如 PD/TV/DT 或空 Type 全局规则）
    """
    for r in rows:
        # ★ 计划外行不走「预排筛选」语义（由实时监控独立管理，无 DPS 预测量），跳过
        if r.get('is_plan_external'):
            continue
        if r.get('ort_ok') == 'N' and r.get('status') != 'filtered':
            parts = [x for x in [r.get('filter_reason') or '', 'ORT量不满足'] if x]
            r['filter_reason'] = '；'.join(parts)
            r['status'] = 'filtered'


def apply_judge_by_ort(rows):
    """
    ★ 预警判定（与 ORT 数量对比同一套逻辑）：
      - ORT 判定为 N（不满足规则阈值）→ judge = '预警'（冒红灯，在 Judge 列显示）
      - ORT 判定为 Y → judge 置空（不显示 'OK'，只保留手动填写的其他值）
      - 其余（N/A 等）保持原值
    - ★ 计划外行：Type 未回填 → judge='待回填'（不参与达标/生产对比，提示操作人员回填）；
      s13 来源计划外例外：直接按 S13 规则判定，不进入待回填
    """
    for r in rows:
        if r.get('is_plan_external') and not (r.get('type') or '').strip() \
                and (r.get('mtd_source') or '').strip().lower() != 's13':
            r['ort_ok'] = ''
            r['judge'] = '待回填'
            continue
        if r.get('ort_ok') == 'N':
            r['judge'] = '预警'
        elif r.get('ort_ok') == 'Y':
            if r.get('judge') in ('预警', 'OK'):
                r['judge'] = ''
            else:
                r['judge'] = r.get('judge') or ''


def recompute_judge(year=None, source=None, type_name=None, ym=None):
    """
    ★ 实时预警：按【当前 ORT 规则(OrtRule 表)】对已导入的预排数据重新判定 ort_ok 与 judge。
      与预排页的 ORT 判定严格同一套规则，改规则后无需重新导入即可更新。
      返回更新行数。

    ★ 2026-09-15 语义拆分（两者基线不同，不可互相派生）：
      - ort_ok ← apply_ort  ：DPS 预测量 vs 规则 → 「是否满足 ORT 量 / 能否通过筛选」
      - judge  ← apply_judge_by_mtd：mtd_output 实际产量 vs 规则 → 「是否已达标（预警）」

    ★ 增量筛选（性能优化）：支持按 source / type_name 收窄重算范围——
      删除或修改某条规则后，仅对该规则影响的数据范围重算，避免全量扫描+逐行 save()。
      - source='S13_DPS'|'Monthly_Input'：只重算该来源
      - type_name 不为 None（含 ''）：只重算该 Type 的行（'' 表示空 Type 的行）
      - ym（★ 2026-09-20）：'YYYYMM' 或 int，只重算该「预排年月」的行
      都不传 → 全量重算（兼容旧行为）
    """
    from ..models import OrtRule, PreplanRow
    from django.utils import timezone
    ensure_default_ort_rules()
    rules = list(OrtRule.objects.filter(is_active=True))
    # ★ 重算范围：通过(kept)的计划行 + 计划外行；
    #   并纳入「曾因 ORT 被过滤」的计划行——规则放宽后它们可能恢复为通过。
    #   （纯手动过滤、或因其它原因被过滤的行不在此范围，避免被误恢复）
    from django.db.models import Q as _Q
    qs = PreplanRow.objects.filter(
        _Q(status='kept') | _Q(is_plan_external=True)
        | _Q(is_plan_external=False, status='filtered', filter_reason__contains='ORT量不满足')
    )
    if year:
        qs = qs.filter(plan_year=year)
    if source:
        qs = qs.filter(source=source)
    # ★ 2026-09-20：可按「预排年月」收窄 —— 多月并存时只重算所选月份，不牵动其它月
    if ym:
        try:
            qs = qs.filter(plan_ym=int(ym))
        except (TypeError, ValueError):
            pass
    if type_name is not None:
        qs = qs.filter(type=type_name)
    # ★ 性能优化：收集变更后 bulk_update 一次性写入（原逐行 save = N 条 UPDATE，
    #   数据量大时占同步/刷新耗时的 99%+，改为批量后从分钟级降到秒级）
    ORT_REASON = 'ORT量不满足'
    changed = []
    now = timezone.now()
    for obj in qs.iterator():
        r = preplan_row_to_dict(obj)
        # ★ 2026-09-15：ort_ok 走 DPS 筛选基线、judge 走 mtd_output 实际产量基线，两者解耦
        apply_ort([r], rules)
        apply_judge_by_mtd([r], rules)
        dirty = False
        new_ort_ok = r.get('ort_ok') or ''
        # ★ 2026-09-18 修复：改规则后必须同步重算「通过/已过滤」状态，
        #   否则仅 ort_ok 列翻转、行集不变 → 预排筛选页面数据看似"不变"（用户报 bug）。
        #   仅对计划行生效（计划外行由实时监控独立管理，不套预排筛选语义）。
        if not obj.is_plan_external:
            reasons = [x for x in (obj.filter_reason or '').split('；') if x]
            was_ort_filtered = ORT_REASON in reasons
            if new_ort_ok == 'N':
                if obj.status != 'filtered':
                    obj.status = 'filtered'
                    dirty = True
                if ORT_REASON not in reasons:
                    reasons.append(ORT_REASON)
                    obj.filter_reason = '；'.join(reasons)
                    dirty = True
            else:  # Y / N/A / '' → 曾因 ORT 被过滤则恢复为通过
                if was_ort_filtered:
                    reasons = [x for x in reasons if x != ORT_REASON]
                    obj.filter_reason = '；'.join(reasons)
                    if not reasons:
                        obj.status = 'kept'
                    dirty = True
        if new_ort_ok != (obj.ort_ok or ''):
            obj.ort_ok = new_ort_ok
            dirty = True
        if (r.get('judge') or '') != (obj.judge or ''):
            obj.judge = r.get('judge') or ''
            dirty = True
        if dirty:
            obj.updated_at = now
            changed.append(obj)
    if changed:
        PreplanRow.objects.bulk_update(
            changed, ['ort_ok', 'judge', 'status', 'filter_reason', 'updated_at'], batch_size=1000)
    return len(changed)


def recompute_external_row(obj):
    """
    ★ 计划外单行回填后处理（操作人员在页面回填 Type 等字段后调用）：
      1) 按 P/N 从基础资料表带回 52阶料号/满箱量/客户（补基础资料）；
      2) 按当前 ORT 规则重算 ort_ok / judge（Type 已回填 → 正常匹配规则，
         未回填 → 保持「待回填」）。
      返回是否发生变更。
    """
    from ..models import EntryTable, OrtRule
    changed = False
    # 1) 基础资料表回填（按 P/N）
    e = None
    if (obj.pn or '').strip():
        e = EntryTable.objects.filter(pn=obj.pn.strip()).first()
    missing = json.dumps(['P/N', '52阶料号', '满箱量', '客户'], ensure_ascii=False)
    if e:
        new_vals = (e.material_code_52 or '', e.box_quantity or 0, e.customer or '')
        if (obj.material_code_52 != new_vals[0] or obj.box_quantity != new_vals[1]
                or obj.customer != new_vals[2] or (obj.missing_fields or '') != ''):
            obj.material_code_52, obj.box_quantity, obj.customer = new_vals
            obj.missing_fields = ''
            changed = True
    else:
        if (obj.missing_fields or '') != missing:
            obj.missing_fields = missing
            changed = True
    # 2) ORT / 预警重算（单行）
    rules = list(OrtRule.objects.filter(is_active=True))
    r = preplan_row_to_dict(obj)
    # ★ 2026-09-15：同上，ort_ok(DPS 筛选基线) 与 judge(mtd 产量基线) 解耦
    apply_ort([r], rules)
    apply_judge_by_mtd([r], rules)
    if (r.get('ort_ok') or '') != (obj.ort_ok or ''):
        obj.ort_ok = r.get('ort_ok') or ''
        changed = True
    if (r.get('judge') or '') != (obj.judge or ''):
        obj.judge = r.get('judge') or ''
        changed = True
    if changed:
        obj.save()
    return changed


def ensure_default_ort_rules():
    # ★ 默认规则已改为 data migration(0021) 在首次 migrate 时初始化；
    #   运行时不再自动补建，用户删除的规则(含默认规则)不会被弹回，删光后保持空。
    return


# ==================== 完整流程 ====================

def process_single_file(file_obj, source_type, year=None, task_id=None, file_year=None):
    """
    处理单个文件（导入 A 或 B），返回 {kept, filtered, stats}
    task_id：导入任务 id（可空）。传入后在解析/过滤阶段检查取消标志，
             用户点「取消导入」或清空数据时提前中止，不进入写入阶段。
    file_year：文件「修改日期」年份（前端 file.lastModified 传入）——
               S13/S11 基准年份在文件名无 20xx 显式年份时使用它（2026-09-04）。
    """
    from ..models import EntryTable, OrtRule
    from .import_task import ImportCancelled, is_cancelled

    def _check_cancel():
        if task_id and is_cancelled(task_id):
            raise ImportCancelled('导入已取消')

    today = date.today()
    if year is None:
        year = today.year

    # ★ 2026-09-18 性能：记录各阶段耗时（打印到终端，便于定位瓶颈）
    _t0 = time.time()

    # 1. 解析
    if source_type == 'S13_DPS':
        rows = parse_s13_dps(file_obj, year=year, file_year=file_year)
        apply_type_rule_s13(rows)
    else:
        rows = parse_monthly_input(file_obj, year=year, file_year=file_year)

    _check_cancel()

    if not rows:
        return {'kept': [], 'filtered': [], 'stats': {'parsed_total': 0, 'kept': 0, 'filtered': 0, 'ort_n_count': 0}}

    # 2. 基础资料表（按 P/N）—— ★ 仅 S11(Monthly_Input) 回填；S13 不回填
    entry_map = {}
    for e in EntryTable.objects.all():
        if e.pn:
            entry_map[e.pn.strip()] = e
    if source_type == 'Monthly_Input':
        apply_entry_table(rows, entry_map)

    _check_cancel()

    # 3. 规则一 + 规则二：基础过滤
    kept, filtered = apply_basic_filters(rows)

    # 4. 规则四：ORT 判断
    ensure_default_ort_rules()
    rules = list(OrtRule.objects.filter(is_active=True))
    apply_ort_by_forecast(kept, rules)

    # ★ ORT 过滤：S13 与 Monthly 中 ORT 判定为 N 的行全部移出「通过」清单
    filter_ort_n(rows)
    # ★ 预警判定：按 ORT 结果写入 Judge（N→预警 冒红灯，Y→OK）
    apply_judge_by_ort(rows)

    _check_cancel()

    # 重新分组
    kept, filtered = [], []
    for r in rows:
        (filtered if r.get('status') == 'filtered' else kept).append(r)

    # ★ 不重新编号 serial_number，保留源文件行号，确保「全部」视图顺序与原始 Excel 完全一致

    stats = {
        'parsed_total': len(rows),
        'kept': len(kept),
        'filtered': len(filtered),
        'ort_n_count': sum(1 for r in rows if r.get('ort_ok') == 'N'),
    }
    # ★ 2026-09-18 性能：解析 + 过滤/ORT 阶段耗时（不含写库，不含 MTD）
    print(f'[导入计时] {source_type} 解析+过滤+ORT {(time.time() - _t0):.2f}s'
          f' | 解析 {len(rows)} 行 → 通过 {len(kept)} / 过滤 {len(filtered)}')
    return {'kept': kept, 'filtered': filtered, 'stats': stats}


def process_preplan(file_a, file_b, year=None, drop_ort_n=False):
    """
    完整流程（向后兼容旧端点）：解析 A+B → 合并 → 规则筛选 → 返回结果
    """
    today = date.today()
    if not year:
        year = today.year

    a_year, a_month, _ = _month_year_from_filename(file_a, today)
    b_year, b_month, _ = _month_year_from_filename(file_b, today)

    rows_s13 = parse_s13_dps(file_a, a_year, a_month)
    # ★ S11(Monthly) 与 S13 是两份独立的判断逻辑：MM 基准各自从自身文件名解析，
    #   不跟随 S13。Monthly 只抓 N+1(MM+1)，S13 只留 N+2(MM+2)。
    rows_monthly = parse_monthly_input(file_b, b_year, b_month)
    rows = merge_sources(rows_s13, rows_monthly)

    apply_type_rule_s13(rows)

    from ..models import EntryTable, OrtRule
    entry_map = {}
    for e in EntryTable.objects.all():
        if e.pn:
            entry_map[e.pn.strip()] = e
    # ★ 基础资料表仅针对 S11(Monthly_Input) 回填；S13 行保持解析原始值（不回填）
    apply_entry_table(rows_monthly, entry_map)

    kept, filtered = apply_basic_filters(rows)
    ensure_default_ort_rules()
    rules = list(OrtRule.objects.filter(is_active=True))
    apply_ort_by_forecast(kept, rules)

    # ★ ORT 过滤：S13 与 Monthly 中 ORT 判定为 N 的行全部移出「通过」清单
    filter_ort_n(rows)
    # ★ 预警判定：按 ORT 结果写入 Judge（N→预警 冒红灯，Y→OK）
    apply_judge_by_ort(rows)

    if drop_ort_n:
        for r in rows:
            if r.get('ort_ok') == 'N' and r.get('status') != 'filtered':
                parts = [x for x in [r.get('filter_reason') or '', 'ORT量不满足'] if x]
                r['filter_reason'] = '；'.join(parts)
                r['status'] = 'filtered'

    kept, filtered = [], []
    for r in rows:
        (filtered if r.get('status') == 'filtered' else kept).append(r)
    # ★ 不重新编号 serial_number，保留源文件行号

    stats = {
        's13_total': len(rows_s13),
        'monthly_total': len(rows_monthly),
        'parsed_total': len(rows),
        'kept': len(kept),
        'filtered': len(filtered),
        'ort_n_count': sum(1 for r in rows if r.get('ort_ok') == 'N'),
    }
    return {'kept': kept, 'filtered': filtered, 'stats': stats}


# ==================== Excel 导出 ====================

def _cell_value(v):
    if v is None:
        return ''
    if isinstance(v, (datetime, date)):
        return v.strftime('%Y-%m-%d')
    return v


def _missing_set(r):
    raw = r.get('missing_fields') or ''
    if not raw:
        return set()
    try:
        return set(json.loads(raw))
    except Exception:
        return set()


def _style_sheet(ws, row_count, red_cells):
    header_font = Font(name='Microsoft YaHei', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='003D80', end_color='003D80', fill_type='solid')
    center = Alignment(horizontal='center', vertical='center')
    thin = Side(style='thin', color='0A2D48')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    red_fill = PatternFill(start_color=RED_FILL, end_color=RED_FILL, fill_type='solid')
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border
    data_font = Font(name='Microsoft YaHei', size=10)
    for row in ws.iter_rows(min_row=2, max_row=row_count + 1):
        for cell in row:
            cell.font = data_font
            cell.alignment = center
            cell.border = border
            if (cell.row, cell.column) in red_cells:
                cell.fill = red_fill
    widths = (12, 10, 10, 10, 16, 16, 18, 14, 12, 12, 10, 14, 14, 14, 12, 12, 16, 16, 12, 14, 12, 14, 16, 12, 16, 16, 12)
    # ★ 2026-09-16 修正：旧写法 `chr(64 + idx) if idx <= 26 else 'A'` 在第 27 列会退化成 'A'，
    #   把 A 列（预排月份）的宽度覆盖掉。改用 get_column_letter，支持任意列数。
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.freeze_panes = 'A2'


def _safe_sheet_title(title):
    """Excel sheet 名约束：≤31 字符，且不能含 [ ] : * ? / \\（2026-09-14 按月分 Sheet 用）"""
    name = re.sub(r'[\[\]:*?/\\]', '-', str(title or '').strip()) or 'Sheet'
    return name[:31]


def build_preplan_excel(kept, filtered, split_by_month=False, sheet_title='通过筛选', include_longlife=False):
    """导出预排筛选结果.xlsx：通过筛选 + 被过滤清单两个 sheet（不含「来源文件」列，无分组分割线）
    filtered 为空时不生成「被过滤清单」sheet

    ★ 2026-09-14：新增 split_by_month / sheet_title 两个可选参数（默认值 = 原有行为，老调用方零影响）。
      split_by_month=True 时，kept 按「年份+月份」拆成多个 sheet（存档中心导出用），
      月份顺序遵循首次出现顺序，与页面视图顺序一致。分组 key 为「年+月」复合，跨年同名不冲突。

    ★ 2026-09-16：新增 include_longlife（默认 False = 原有行为，老调用方零影响）。
      True 时在末尾追加「LongLife」列 —— 审核决议中心导出用（LongLife 只加在决议页），
      预排页 / 存档中心导出保持原样，不会多出这一列。
      注意：LongLife=Y 的「副本行」是页面上的填写便利，**不进导出**；
      副本里填的 Q工单会自动用 '/' 并入原行（本函数内完成，调用方无需关心）。
    """
    if include_longlife:
        # ★ LongLife 导出模式 = 带 LongLife 列 + 不导出副本行 + 副本 Q工单并回原行。
        #   在这里统一处理（而不是让调用方记得先合并），避免漏调 / 重复调用导致
        #   'A/B/B' 这类叠加。作用在浅拷贝上，不污染调用方传入的 dict。
        kept = merge_longlife_q_order([dict(r) for r in kept])
        if filtered:
            filtered = merge_longlife_q_order([dict(r) for r in filtered])

    headers = EXPORT_HEADERS + (['LongLife'] if include_longlife else [])
    wb = Workbook()
    if split_by_month:
        groups, seen = [], {}
        for r in kept:
            # ★ 跨年健壮性：plan_month_label 真实不带年份（如 '9月'），按它单独分组会让
            #   2026年9月 与 2027年9月 撞到同一个 sheet → sheet 名冲突、文件被覆盖。
            #   复合 key「2026年9月」使跨年同名天然分离，sheet 名也含年份便于阅读。
            ym = f"{r.get('plan_year') or '未知年份'}年{r.get('plan_month_label') or '未标注月份'}"
            if ym not in seen:
                seen[ym] = []
                groups.append((ym, seen[ym]))
            seen[ym].append(r)
    else:
        groups = [(sheet_title, list(kept))]

    for idx, (title, rows) in enumerate(groups):
        ws = wb.active if idx == 0 else wb.create_sheet()
        ws.title = _safe_sheet_title(title)
        ws.append(headers)
        red_cells = set()
        for r_i, r in enumerate(rows, start=2):
            missing = _missing_set(r)
            values = []
            for col_i, (header, key) in enumerate(EXPORT_KEY_PAIRS, start=1):
                values.append(_cell_value(r.get(key)))
                if header in missing or (key == 'ort_ok' and r.get('ort_ok') == 'N'):
                    red_cells.add((r_i, col_i))
            if include_longlife:
                values.append(_cell_value(r.get('longlife')))
            ws.append(values)
        _style_sheet(ws, len(rows), red_cells)

    if not groups:  # 理论上不会走到，兜底保证至少一个空表头 sheet
        ws = wb.active
        ws.title = _safe_sheet_title(sheet_title)
        ws.append(headers)
        _style_sheet(ws, 0, set())

    if filtered:
        ws2 = wb.create_sheet('被过滤清单')
        ws2.append(headers + ['过滤原因'])
        for r in filtered:
            row_vals = [_cell_value(r.get(k)) for k in EXPORT_KEYS]
            if include_longlife:
                row_vals.append(_cell_value(r.get('longlife')))
            ws2.append(row_vals + [r.get('filter_reason') or ''])
        _style_sheet(ws2, len(filtered), set())

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def parse_longlife_copy(raw):
    """★ 2026-09-16：LongLife 副本行数据（DB 里的 JSON 文本 ↔ dict）

    - 只存「副本行被改过的字段」（覆盖值），未改的字段跟随原行 → 前端 `{...原行, ...覆盖}`
    - 容错：空串 / 非法 JSON / 非 dict → 返回 {}（绝不让脏数据把接口带崩）
    """
    if not raw:
        return {}
    try:
        v = json.loads(raw)
    except Exception:
        return {}
    return v if isinstance(v, dict) else {}


def merge_longlife_q_order(rows):
    """★ 2026-09-16：LongLife 导出前置处理 —— 把「副本行」的内容并回原行。

    背景：LongLife=Y 的行在审核决议页会在下方派生一份一模一样的副本行，
    那是**给员工填写方便**用的（页面行为），不是一条独立数据。
    导出 Excel 时只出一行：把副本里填的 Q工单用 '/' 接到原行上，副本行本身不导出。

    规则：
      · 原行 'A123'  + 副本 'B456' → 'A123/B456'
      · 原行 'A123'  + 副本 空     → 'A123'（原样，不出现多余的 '/'）
      · 原行 空      + 副本 'B456' → 'B456'（不出现前导 '/'）
      · 原行 空      + 副本 空     → ''（保持空）
    仅处理 longlife=='Y' 的行；就地修改传入的 dict 列表并返回。
    """
    for r in rows:
        if str(r.get('longlife') or '').strip().upper() != 'Y':
            continue
        cp = r.get('longlife_copy')
        if not isinstance(cp, dict):
            continue
        extra = str(cp.get('q_order') or '').strip()
        if not extra:
            continue
        base = str(r.get('q_order') or '').strip()
        r['q_order'] = f'{base}/{extra}' if base else extra
    return rows


def preplan_row_to_dict(obj):
    """PreplanRow 对象 → 前端展示 dict"""
    try:
        missing = json.loads(obj.missing_fields or '[]')
    except Exception:
        missing = []
    return {
        'id': obj.id,
        'batch_id': obj.batch_id,
        'plan_year': obj.plan_year,
        # ★ 2026-09-20 预排年月（YYYYMM，0=未归类）：前端「月份」维度的筛选/分组键
        'plan_ym': obj.plan_ym,
        'serial_number': obj.serial_number,
        'status': obj.status,
        'source': obj.source,
        'plan_month_label': obj.plan_month_label,
        'table_date': obj.table_date,
        'type': obj.type,
        'fab': obj.fab,
        'material_code_52': obj.material_code_52,
        'model': obj.model,
        'pn': obj.pn,
        'customer': obj.customer,
        'n1_dps': obj.n1_dps,
        'n2_dps': obj.n2_dps,
        'box_quantity': obj.box_quantity,
        'request_qty': obj.request_qty,
        'issue_qty_box': obj.issue_qty_box,
        'issue_qty_pcs': obj.issue_qty_pcs,
        'ort_ok': obj.ort_ok,
        'qe_requirement': obj.qe_requirement,
        'qe_remark': obj.qe_remark,
        'ra_remark': obj.ra_remark,
        'gpc_reply': obj.gpc_reply,
        'oqc_hold': obj.oqc_hold or '',
        # ★ 2026-09-16：LongLife 标记 + 副本行（决议页在 LongLife=Y 时于下方复制一行）
        #   longlife_copy 以 dict 下发；未出现过的字段表示"跟随原行"，前端不做覆盖。
        'longlife': obj.longlife or '',
        'longlife_copy': parse_longlife_copy(obj.longlife_copy),
        'q_order': obj.q_order,
        'box_number': obj.box_number,
        'sample_date': obj.sample_date.strftime('%Y-%m-%d') if obj.sample_date else '',
        'mtd_output': obj.mtd_output,
        'is_plan_external': obj.is_plan_external,
        'mtd_source': obj.mtd_source or '',
        'inserted_to_preplan': obj.inserted_to_preplan,
        'exported': obj.exported,
        'archived': obj.archived,
        # ★ 2026-09-14：定版时间（存档中心「定版时间」列）。
        # USE_TZ=True 下直接 strftime 会输出 UTC，故显式 localtime 转成北京时间展示。
        'archived_at': timezone.localtime(obj.archived_at).strftime('%Y-%m-%d %H:%M:%S') if obj.archived_at else '',
        'judge': obj.judge,
        'filter_reason': obj.filter_reason,
        'missing_fields': missing,
        'source_file_name': obj.source_file_name,
        'created_at': obj.created_at.strftime('%Y-%m-%d %H:%M:%S') if obj.created_at else '',
        'updated_at': obj.updated_at.strftime('%Y-%m-%d %H:%M:%S') if obj.updated_at else '',
    }
