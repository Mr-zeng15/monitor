"""
URL configuration for backend project.

- /admin/         Django 后台
- /api/           REST API 接口
- /static/        Django 静态资源
- /assets/        前端打包的 chunk 资源
- /favicon.ico    前端图标
- 其它路径        返回前端 index.html（Vue Router 接管）
"""
import os
from pathlib import Path
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.views.decorators.clickjacking import xframe_options_exempt

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / 'static' / 'frontend'
FRONTEND_INDEX = FRONTEND_DIR / 'index.html'


@xframe_options_exempt
def frontend_index(request):
    """返回前端 index.html（用于 Vue Router History 模式）"""
    if not FRONTEND_INDEX.exists():
        return HttpResponse(
            f'<h1>前端资源未找到</h1>'
            f'<p>请确认 {FRONTEND_INDEX} 存在</p>'
            f'<p>如果是首次部署，请将 <code>frontend/dist/</code> 复制到 <code>backend/static/frontend/</code></p>',
            status=500
        )
    resp = FileResponse(open(FRONTEND_INDEX, 'rb'), content_type='text/html')
    # ★ index.html 禁止强缓存（2026-09-15）：原先没有任何缓存头，浏览器会启发式缓存
    #   这个文件，导致前端重新构建后页面仍引用旧的 assets/*.js|css —— 表现为
    #   「代码明明改了、刷新了还是老样子」。assets 带内容哈希可长期缓存，index.html
    #   每次校验即可（文件仅 1KB 左右，开销可忽略）。
    resp['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp['Pragma'] = 'no-cache'
    resp['Expires'] = '0'
    return resp


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),

    # Django 静态资源（/static/...）
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'static'}),

    # 前端 assets 目录直接访问
    re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': FRONTEND_DIR / 'assets'}),

    # favicon
    re_path(r'^favicon\.ico$', serve, {'document_root': str(FRONTEND_DIR), 'path': 'favicon.ico'}),

    # 前端路由兜底 - 只匹配非 API / 非 admin / 非 static / 非 assets 的路径
    re_path(r'^(?!api/|admin/|static/|assets/|favicon\.ico$).*$', frontend_index, name='frontend'),
]
