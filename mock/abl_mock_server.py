# -*- coding: utf-8 -*-
"""
ABL 触发 Mock API 服务（模拟公司机器人 /api/byfab/abl/ 返回）
用途：公司内网机器人（<内网机器人地址>）不可达时，用本服务模拟真实拉取流程，
      验证 ABL 首屏缓存 / 每小时静默刷新 / 失败重试 / 单位次数 / W 编号等，不改动任何业务源码。

启动：  python mock/abl_mock_server.py        （默认 127.0.0.1:8001）
指向：  新建 frontend/.env.development.local 写入 VITE_API_BASE=http://127.0.0.1:8001/api
恢复：  删除该 .env.development.local 即回到真实后端 http://localhost:8000/api

返回结构（与后端 byfab_abl 视图一致）：{"success": true, "data": <echarts JSON>}
echarts JSON 形如机器人原始回复：title/xAxis(含 WoW 尾列)/yAxis.name=次数/series[2A-2D]
数值会随当前分钟轻微浮动，便于观察「重新查询 / 每小时刷新取到新数据才更新」。
"""
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8001

# 每周基线（各 FAB 每周 ABL 触发次数）；W 编号用 API 风格原始编号 W{年2位}{周2位}
WEEKS = ["W2634", "W2635", "W2636", "W2637"]
BASE = {
    "2A": [1, 0, 2, 1],
    "2B": [3, 2, 5, 4],
    "2C": [0, 1, 1, 0],
    "2D": [1, 2, 0, 1],
}
FAB_ORDER = ["2A", "2B", "2C", "2D"]


def build_abl_payload():
    """按当前分钟做一点确定性浮动，让连续请求能看到“新数据”。"""
    minute = int(time.time() // 60)          # 每分钟变一次
    drift = {fab: (minute + i) % 3 - 1 for i, fab in enumerate(FAB_ORDER)}  # -1/0/+1
    series = []
    for fab in FAB_ORDER:
        vals = list(BASE[fab])
        vals[-2] = max(0, vals[-2] + (0 if drift[fab] == 0 else drift[fab]))
        vals[-1] = max(0, vals[-1] + (-1 if drift[fab] == 0 else drift[fab]))
        # WoW 尾列 = 本周 − 上周（保持与折线图末两点一致）
        wow = vals[-1] - vals[-2]
        series.append({"name": fab, "data": vals + [wow]})
    return {
        "title": {"text": "OOS报警数"},
        "tooltip": {"trigger": "axis"},
        "legend": {"data": FAB_ORDER},
        "xAxis": {"type": "category", "name": "周别", "data": WEEKS + ["WoW"]},
        "yAxis": {"type": "value", "name": "次数"},
        "series": series,
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if re.search(r"/byfab/abl/?$", path) or "byfab/abl" in path:
            self._send(200, {"success": True, "data": build_abl_payload(), "mock": True})
        else:
            self._send(404, {"success": False, "error": "mock: 仅提供 /api/byfab/abl/ 接口"})


if __name__ == "__main__":
    print(f"[mock-abl] http://{HOST}:{PORT}/api/byfab/abl/  启动，Ctrl+C 停止", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
