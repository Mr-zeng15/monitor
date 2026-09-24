# -*- coding: utf-8 -*-
"""DPPM 回覆形状回归探针（纯逻辑，不碰网络/DB）。

验证「解析拿到的回复只取最近 4 周」这条契约，以及轴/数值长度不一致时的**尾部对齐**。

用 manage.py shell 跑：
  python manage.py shell -c "exec(open('_probe_dppm_shape.py',encoding='utf-8').read())"

契约（2026-09-24 定稿）：
  · `_extract_dppm_fab` 产出的 xAxis / values：
      - 长度相等；
      - 长度 ≤ DPPM_RECENT_WEEKS(4)；
      - 保留的是【最新】那几周（末尾对齐）；
      - 数值里不出现"凭空补出来的空位"（不足时补在最旧端）。
  · 兜底种子两厂同构（都 4 周）。
"""
from core.views import byfab_views as V

N = V.DPPM_RECENT_WEEKS
W6 = ['W2634', 'W2635', 'W2636', 'W2637', 'W2638', 'W2639']
W4 = ['W2636', 'W2637', 'W2638', 'W2639']
_fail = []


def check(ok, msg):
    print('   %s %s' % ('[PASS]' if ok else '[FAIL]', msg))
    if not ok:
        _fail.append(msg)


def case(tag, raw, fab, want_axis, want_values):
    print('-' * 78)
    print('%s' % tag)
    out = V._extract_dppm_fab(raw, fab)
    if out is None:
        check(False, '%s -> None（会回退种子）' % fab)
        return
    axis, values = out['xAxis'], out['values']
    print('   xAxis  = %s  (len=%d)' % (axis, len(axis)))
    print('   values = %s  (len=%d)' % (values, len(values)))
    check(len(axis) == len(values) or len(axis) == 0,
          'xAxis 与 values 等长；轴完全缺失时允许为空（不编造标签）（%d / %d）' % (len(axis), len(values)))
    check(len(values) <= N, '周数 ≤ %d（实际 %d）' % (N, len(values)))
    check(axis == want_axis, 'xAxis == %s' % want_axis)
    check(values == want_values, 'values == %s' % want_values)


print('=' * 78)
print('DPPM_RECENT_WEEKS = %d' % N)
print('=' * 78)

# ① 上游给 6 周 → 必须裁到最新 4 周
case('C1 · 上游 6 周（2A / 2B 都可能这样回） → 裁到最近 4 周',
     {'title': {'text': 'DPPM'}, 'xAxis': {'data': W6},
      'series': [{'data': [1180.5, 1320.0, 980.2, 760.4, 690.5, 640.2]}]},
     '2A', W4, [980.2, 760.4, 690.5, 640.2])

# ② 上游给 4 周 → 原样保留（现在的 2A 就是这条）
case('C2 · 上游 4 周 → 原样保留',
     {'title': {'text': 'DPPM'}, 'xAxis': {'data': W4},
      'series': [{'data': [1180.5, 1320.0, 980.2, 760.4]}]},
     '2A', W4, [1180.5, 1320.0, 980.2, 760.4])

# ③ 上游 6 周 + 末尾 WoW 列（7 格） → 先剥 WoW、再裁到 4 周
case('C3 · 6 周 + 末尾 WoW 列 → 剥列后裁到 4 周',
     {'title': {'text': '抽检量'}, 'xAxis': {'data': W6 + ['WoW']},
      'series': [{'data': [3200, 4500, 4100, 3600, 4800, 5200, 400]}]},
     '2B', W4, [4100, 3600, 4800, 5200])

# ④ 轴 6 格 / 值只有 4 个（缺的是【最新】那两周）→ 缺位补在最旧端，保留 4 个真实点
case('C4 · 轴 6 / 值 4 → 尾部对齐，不留空点',
     {'title': {'text': '抽检量'}, 'xAxis': {'data': W6},
      'series': [{'data': [3200, 4500, 4100, 3600]}]},
     '2B', W4, [3200, 4500, 4100, 3600])

# ⑤ 轴 4 格 / 值 6 个 → 不得编造 "W5"/"W6" 假周别
case('C5 · 轴 4 / 值 6 → 不得出现 W5/W6 假周别',
     {'title': {'text': '抽检量'}, 'xAxis': {'data': W4},
      'series': [{'data': [3200, 4500, 4100, 3600, 4800, 5200]}]},
     '2B', W4, [4100, 3600, 4800, 5200])

# ⑥ 行表回吐（LLM 把原始表原样吐回）6 周 → 同样裁到 4 周
case('C6 · 行表回吐 6 周 → 裁到 4 周',
     {'data': [{'week': w, 'count_value': v} for w, v in
               zip(W6, [3200, 4500, 4100, 3600, 4800, 5200])],
      'message': '您没有提出具体问题'},
     '2B', W4, [4100, 3600, 4800, 5200])

print('-' * 78)
print('C9 · 裸数值数组（上游只吐数值、不带 series 包装）')
case('C9 · {"data":[6 个数]} → 裁到 4 周（无周别标签）',
     {'data': [1180.5, 1320.0, 980.2, 760.4, 690.5, 640.2]},
     '2A', [], [980.2, 760.4, 690.5, 640.2])

print('-' * 78)
print('C10 · 多折线且名字都匹配不上 → 认领「数值最多的一条」（不再要求只有一条）')
case('C10 · 2 条无名折线 → 取数值多的那条',
     {'xAxis': {'data': W6},
      'series': [{'name': '抽检量', 'data': [3200, 4500, 4100, 3600, 4800, 5200]},
                 {'name': '不良数', 'data': [12, None, None, None, None, None]}]},
     '2B', W4, [4100, 3600, 4800, 5200])

print('-' * 78)
print('C11 · 「周别 → 数值」对象映射（键序乱序，必须按周排回来）')
case('C11 · 乱序 week-map → 按周排序后取最近 4 周',
     {'data': {'W2638': 4800, 'W2636': 4100, 'W2639': 5200, 'W2637': 3600,
               'W2635': 4500, 'W2634': 3200}},
     '2B', W4, [4100, 3600, 4800, 5200])

print('-' * 78)
print('C12 · 反例守卫：厂别→数值 的映射不得被当成周别（应判失败，交给缓存/种子）')
_out = V._extract_dppm_fab({'2A': 8, '2B': 3, '2C': 5, '2D': 4}, '2A')
print('   {"2A":8,"2B":3,"2C":5,"2D":4} -> %s' % ('None（已拒绝，正确）' if _out is None else _out))
check(_out is None, '厂别→数值 映射被拒绝，不会排出假折线')

print('-' * 78)
print('C8 · `_trim_recent_fab`（「沿用上次缓存值」回退分支也会走它）')
_old6 = {'title': '抽检量', 'unit': '', 'seeded': True,
         'xAxis': W6, 'values': [3200, 4500, 4100, 3600, 4800, 5200]}
_t = V._trim_recent_fab(_old6)
print('   6 周旧值 -> xAxis=%s values=%s' % (_t['xAxis'], _t['values']))
check(_t['xAxis'] == W4 and _t['values'] == [4100, 3600, 4800, 5200], '老库 6 周旧值裁到最近 4 周')
check(_t['seeded'] is True and _t['title'] == '抽检量', '裁剪不丢 seeded / title 等字段')
check(V._trim_recent_fab(_t) == _t, '重复裁幂等')

print('-' * 78)
print('C7 · 兜底种子两厂同构（都 %d 周）' % N)
for fab in ('2A', '2B'):
    s = V._dppm_seed_fab(fab)
    print('   %s: xAxis=%s values=%s seeded=%s' % (fab, s['xAxis'], s['values'], s['seeded']))
    check(len(s['xAxis']) == len(s['values']) == N, '%s 种子 = %d 周且轴值等长' % (fab, N))

print('=' * 78)
if _fail:
    print('结果：%d 项失败' % len(_fail))
    for m in _fail:
        print('  · ' + m)
else:
    print('结果：全部通过（契约：解析即只取最近 %d 周、轴值等长、保留最新）' % N)
print('=' * 78)
