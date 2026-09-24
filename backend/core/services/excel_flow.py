# -*- coding: utf-8 -*-
"""★ 2026-09-24 Excel 处理测试 · Dify workflow 中继服务

链路：前端上传 Excel → 本服务后台线程
  ① POST {BASE}/files/upload      （multipart + Bearer Key）→ upload_file_id
  ② POST {BASE}/workflows/run     （streaming SSE，inputs.input_file=local_file）
  ③ workflow_finished.outputs 里「找数据不认形状」：任意层级里 type==document 且带 url 的对象
  ④ 立即把结果下载到本地 <backend>/excel_flow/（Dify 的 URL 是带签名的临时链接，会过期）
  ⑤ 前端经 /api/excel-flow/download/ 由后端代理取回，永不过期。

状态：单任务内存态（测试页，无历史任务）。整体 try/except，失败记 error 供前端展示；
      并发用 _lock 互斥（同一时刻只允许一个任务在跑）。
"""
import json
import mimetypes
import os
import re
import threading
import time
import uuid

import requests
from django.conf import settings

# 工作流文件输入变量名（Dify workflow 侧定义；换工作流时改这里）
INPUT_FILE_KEY = 'input_file'
ALLOWED_EXT = {'.xlsx', '.xls', '.csv'}
ACTIVE_STATUSES = ('queued', 'uploading', 'running', 'downloading')

_lock = threading.Lock()
_STATE = {}   # 内存单任务：{} 或最后一个任务的快照


def _workdir():
    d = os.path.join(str(settings.BASE_DIR), 'excel_flow')
    os.makedirs(d, exist_ok=True)
    return d


def _safe_name(name, default='input.xlsx'):
    """只留 basename，去掉路径分隔与控制字符；限制长度。"""
    name = os.path.basename(str(name or '')).replace('\\', '_').replace('/', '_')
    name = re.sub(r'[\x00-\x1f\x7f]', '', name).strip() or default
    return name[:120]


def current():
    """当前/最后一个任务快照（副本，避免调用方改内存态）。"""
    with _lock:
        return dict(_STATE) if _STATE else None


def _set(**kw):
    with _lock:
        _STATE.update(kw)


def start(tmp_path, filename):
    """受理任务。返回任务快照 dict；已有任务在跑则返回 None（视图层回 409）。"""
    with _lock:
        if _STATE.get('status') in ACTIVE_STATUSES:
            return None
        task = {
            'task_id': uuid.uuid4().hex[:16],
            'filename': _safe_name(filename),
            'status': 'queued',
            'progress': '排队中',
            'error': '',
            'result_name': '',
            'result_path': '',
            'created_at': time.time(),
            'finished_at': 0,
        }
        _STATE.clear()
        _STATE.update(task)
    t = threading.Thread(target=_run, args=(task['task_id'], tmp_path, task['filename']),
                         daemon=True, name=f'excel-flow-{task["task_id"]}')
    t.start()
    return dict(task)


def _fail(task_id, err):
    _set(task_id=task_id, status='failed', error=str(err)[:500],
         progress='失败', finished_at=time.time())


def _run(task_id, tmp_path, filename):
    base = str(getattr(settings, 'EXCEL_FLOW_BASE_URL', '')).rstrip('/')
    key = str(getattr(settings, 'EXCEL_FLOW_API_KEY', ''))
    user = str(getattr(settings, 'EXCEL_FLOW_USER_ID', 'user-001'))
    timeout = int(getattr(settings, 'EXCEL_FLOW_TIMEOUT', 680))
    headers = {'Authorization': f'Bearer {key}'}
    try:
        if not key or not base:
            raise RuntimeError('EXCEL_FLOW_API_KEY / BASE_URL 未配置')
        if not os.path.isfile(tmp_path):
            raise RuntimeError('临时上传文件丢失')

        # ① 上传文件到 Dify
        _set(task_id=task_id, status='uploading', progress='上传文件中…')
        mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        with open(tmp_path, 'rb') as f:
            r = requests.post(f'{base}/files/upload', headers=headers,
                              files={'file': (filename, f, mime)},
                              data={'user': user}, timeout=120)
        if r.status_code not in (200, 201):
            raise RuntimeError(f'文件上传失败 HTTP {r.status_code}: {r.text[:200]}')
        file_id = (r.json() or {}).get('id')
        if not file_id:
            raise RuntimeError('上传成功但未返回 file_id')

        # ② 启动工作流（SSE 流式）
        _set(task_id=task_id, status='running', progress='工作流运行中…')
        payload = {
            'inputs': {INPUT_FILE_KEY: {
                'transfer_method': 'local_file',
                'upload_file_id': file_id,
                'type': 'document',
            }},
            'response_mode': 'streaming',
            'user': user,
        }
        deadline = time.time() + timeout
        file_url = None
        with requests.post(f'{base}/workflows/run', headers={**headers, 'Content-Type': 'application/json'},
                           json=payload, stream=True, timeout=timeout) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f'工作流启动失败 HTTP {resp.status_code}: {resp.text[:200]}')
            for line in resp.iter_lines():
                if time.time() > deadline:
                    raise RuntimeError(f'工作流超时（>{timeout}s）')
                if not line:
                    continue
                s = line.decode('utf-8', 'ignore').strip()
                if not s.startswith('data:'):
                    continue
                js = s[5:].strip()
                if js == '[DONE]':
                    break
                try:
                    data = json.loads(js)
                except ValueError:
                    continue
                ev = data.get('event')
                if ev == 'workflow_started':
                    _set(task_id=task_id, progress='工作流已开始')
                elif ev == 'node_finished':
                    title = ((data.get('data') or {}).get('title') or '')[:24]
                    if title:
                        _set(task_id=task_id, progress=f'节点完成：{title}')
                elif ev == 'workflow_finished':
                    wdata = data.get('data') or {}
                    if wdata.get('status') == 'failed':
                        raise RuntimeError(f"工作流内部失败: {str(wdata.get('error'))[:200]}")
                    file_url = _find_doc_url(wdata.get('outputs') or {})
                elif ev == 'error':
                    raise RuntimeError(f"工作流错误: {str(data.get('message'))[:200]}")

        # ③④ 抓结果（Dify URL 带签名会过期，立刻下载落本地）
        if not file_url:
            raise RuntimeError('工作流输出里未找到文件（请确认结束节点输出了 document 类型变量）')
        _set(task_id=task_id, status='downloading', progress='下载结果文件…')
        stem = re.sub(r'\.[^.]+$', '', filename) or 'result'
        out_ext = os.path.splitext(str(file_url.split('?')[0]))[1][:8].lower() or '.xlsx'
        result_name = _safe_name(f'{stem}_processed{out_ext}')
        result_path = os.path.join(_workdir(), f'{task_id}_{result_name}')
        with requests.get(file_url, stream=True, timeout=180) as dl:
            if dl.status_code != 200:
                raise RuntimeError(f'结果下载失败 HTTP {dl.status_code}')
            with open(result_path, 'wb') as f:
                for chunk in dl.iter_content(8192):
                    f.write(chunk)
        if os.path.getsize(result_path) <= 0:
            raise RuntimeError('结果文件为空')
        _set(task_id=task_id, status='done', progress='完成', result_name=result_name,
             result_path=result_path, finished_at=time.time())
        _prune_old()
    except Exception as e:
        try:
            _fail(task_id, e)
        except Exception:
            pass
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _find_doc_url(obj, _depth=0):
    """在 outputs 里递归找 type==document 且带 url/remote_url 的对象（不认死形状）。"""
    if _depth > 6:
        return None
    if isinstance(obj, dict):
        if obj.get('type') == 'document':
            u = obj.get('url') or obj.get('remote_url')
            if u:
                return str(u)
        for v in obj.values():
            u = _find_doc_url(v, _depth + 1)
            if u:
                return u
    elif isinstance(obj, list):
        for v in obj:
            u = _find_doc_url(v, _depth + 1)
            if u:
                return u
    return None


def _prune_old():
    """新任务成功落盘时顺带清理超期结果文件（无历史任务概念，只留最近的）。"""
    keep = int(getattr(settings, 'EXCEL_FLOW_KEEP_HOURS', 24)) * 3600
    now = time.time()
    try:
        for fn in os.listdir(_workdir()):
            p = os.path.join(_workdir(), fn)
            if os.path.isfile(p) and now - os.path.getmtime(p) > keep:
                os.remove(p)
    except OSError:
        pass
