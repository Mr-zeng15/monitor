# -*- mode: python ; coding: utf-8 -*-
# ============================================================
# 产量监控预警系统 - PyInstaller 打包配置
# ============================================================
# 用法：
#   cd D:\产量监控系统\backend
#   pyinstaller 产量监控系统.spec --noconfirm
# 输出：
#   backend\dist\产量监控系统\产量监控系统.exe
# ============================================================

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ===== 路径 =====
BACKEND_DIR = Path(SPECPATH).resolve().parent  # backend/ 目录
STATIC_SRC = BACKEND_DIR / 'static'             # 前端 dist 拷贝目录

block_cipher = None

# ===== 收集所有 hiddenimports =====
# 精简模式：只保留必需的包（其它由 PyInstaller 自动发现）
hiddenimports = [
    # 我们的核心 app（必须显式列出，因为不是 package __init__ 暴露的形式）
    'core',
    'core.views',
    'core.models',
    'core.serializers',
    'core.urls',
    'core.migrations',
    'backend',
    'backend.settings',
    'backend.urls',
    'backend.wsgi',
]

# ===== 收集 data files =====
datas = []

# 1) 前端 dist（整个 static 目录，含 frontend/）
if STATIC_SRC.exists():
    datas.append((str(STATIC_SRC), 'static'))
    print(f'[spec] 包含前端静态文件: {STATIC_SRC}')

# 2) 我们的 core app 的 templates（如有）
core_templates = BACKEND_DIR / 'core' / 'templates'
if core_templates.exists():
    datas.append((str(core_templates), 'core/templates'))
    print(f'[spec] 包含 core/templates')

# 3) collect_data_files 自动找 data 目录
for pkg in ('openpyxl', 'pandas', 'rest_framework', 'django'):
    try:
        for src, dst in collect_data_files(pkg):
            datas.append((src, dst))
    except Exception:
        pass

# ===== Analysis =====
a = Analysis(
    ['run_server.py'],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 不必要的包
        'tkinter', 'unittest', 'pydoc', 'doctest',
        'matplotlib', 'pytest', 'IPython', 'jupyter',
        'scipy', 'sklearn', 'torch', 'tensorflow',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ===== 单目录模式（onefolder，启动更快、占空间小） =====
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='产量监控系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # 关闭 UPX 压缩（兼容性更好）
    console=True,              # 显示控制台（方便看日志）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='产量监控系统',
)
