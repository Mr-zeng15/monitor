# -*- coding: utf-8 -*-
"""★ 2026-09-24 Excel 处理测试 · 视图层

  · POST /api/excel-flow/upload     接收前端拖拽的 Excel，受理后台任务（忙则 409）
  · GET  /api/excel-flow/status/    当前/最后任务状态（前端 2s 轮询）
  · GET  /api/excel-flow/download/  后端代理下载结果文件（本地落盘，Dify 临时 URL 过期也不影响）
"""
import os

from django.http import FileResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings

from ..services import excel_flow


def _err(msg, code=400):
    return Response({'success': False, 'error': msg}, status=code)


@api_view(['POST'])
@permission_classes([AllowAny])
def excel_flow_upload(request):
    f = request.FILES.get('file')
    if not f:
        return _err('未收到文件')
    name = os.path.basename(f.name or '')
    ext = os.path.splitext(name)[1].lower()
    if ext not in excel_flow.ALLOWED_EXT:
        return _err(f'仅支持 {"/".join(sorted(excel_flow.ALLOWED_EXT))} 文件')
    max_mb = int(getattr(settings, 'EXCEL_FLOW_MAX_UPLOAD_MB', 20))
    if f.size > max_mb * 1024 * 1024:
        return _err(f'文件超过 {max_mb}MB 上限')

    tmp = os.path.join(excel_flow._workdir(), f'tmp_{os.getpid()}_{int(__import__("time").time()*1000)}{ext}')
    with open(tmp, 'wb') as out:
        for chunk in f.chunks():
            out.write(chunk)

    task = excel_flow.start(tmp, name)
    if task is None:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return _err('已有任务在处理中，请等待完成后再上传', code=409)
    return Response({'success': True, 'task': task})


@api_view(['GET'])
@permission_classes([AllowAny])
def excel_flow_status(request):
    return Response({'success': True, 'task': excel_flow.current()})


@api_view(['GET'])
@permission_classes([AllowAny])
def excel_flow_download(request):
    task = excel_flow.current()
    if not task or task.get('status') != 'done':
        return _err('结果尚未就绪', code=404)
    path = task.get('result_path') or ''
    # 只允许下载服务自己落盘的结果文件（task_id 命名的白名单目录内文件）
    if not path or not os.path.isfile(path) or os.path.dirname(path) != excel_flow._workdir():
        return _err('结果文件已清理，请重新上传处理', code=404)
    return FileResponse(open(path, 'rb'), as_attachment=True,
                        filename=task.get('result_name') or 'result.xlsx')
