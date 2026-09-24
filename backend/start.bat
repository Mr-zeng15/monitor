@echo off
chcp 65001 >nul 2>&1
title 产量监控预警系统 v2.19.0
echo ============================================================
echo   产量监控预警系统 v2.19.0
echo ============================================================
cd /d "%~dp0"
set "PYEXE="

REM ---------- 服务端口（★ 2026-09-16 新增，便于换端口）----------
REM   8000 端口被别的程序占用时，改这一行即可（例如改成 8065）。
REM   前端已改为【相对路径 /api】，由 Django 同源提供 ——
REM   换端口不需要重新构建前端、也不需要改前端代码。
REM   也可在运行本脚本前临时覆盖：  set YM_PORT=8065
if not defined YM_PORT set "YM_PORT=8000"

REM ---------- 0. 便携内置 Python（runtime\python：自带解释器+全部依赖，第三方开发包免安装/离线可跑）----------
if exist "runtime\python\python.exe" (
    set "PYEXE=runtime\python\python.exe"
    echo [0/5] 便携内置 Python: %PYEXE%
    goto :init_db
)

REM ---------- 1. 优先复用已有虚拟环境（公司电脑已装过 → 秒启动，不联网）----------
if exist "venv\Scripts\python.exe" (
    set "PYEXE=venv\Scripts\python.exe"
    goto :checkdeps
)

REM ---------- 2. 常见 Python 安装路径 / 系统 PATH ----------
for %%p in (
    "C:\Users\haibozeng\AppData\Local\Programs\Python\Python38\python.exe"
    "C:\Users\haibozeng\AppData\Local\Programs\Python\Python310\python.exe"
    "C:\Users\haibozeng\AppData\Local\Programs\Python\Python312\python.exe"
    "C:\Python38\python.exe"
    "C:\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Program Files\Python38\python.exe"
    "C:\Program Files\Python310\python.exe"
    "C:\Program Files\Python312\python.exe"
) do (
    if exist %%p ( set "PYEXE=%%p" & goto :found )
)
where python >nul 2>&1
if not errorlevel 1 (for /f %%i in ('where python 2^>nul') do set "PYEXE=%%i" & goto :found)
echo [X] 未找到 Python，请安装 Python 3.8~3.12（安装时勾选 Add Python to PATH）
pause
exit /b 1

:found
set "PYEXE=%PYEXE%"

REM ---------- 3. 检查依赖（与 requirements.txt 对齐；已装则跳过下载，内网友好）----------
:checkdeps
echo [1/5] Python: %PYEXE%
echo [2/5] 检查依赖（已安装则跳过下载）...
"%PYEXE%" -c "import django,rest_framework,openpyxl,pandas,corsheaders" >nul 2>&1
if not errorlevel 1 (
    echo   依赖已就绪，跳过安装
    goto :init_db
)
echo   依赖不完整，尝试安装（内网屏蔽外网时会失败，见下方提示）...
if not exist "venv\Scripts\python.exe" (
    echo   正在创建虚拟环境...
    python -m venv venv
    if errorlevel 1 goto :deps_fail
    set "PYEXE=venv\Scripts\python.exe"
)
"%PYEXE%" -m pip install --quiet --disable-pip-version-check --timeout 20 -r requirements.txt
if errorlevel 1 "%PYEXE%" -m pip install --quiet --disable-pip-version-check --timeout 20 -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
if errorlevel 1 goto :deps_fail
goto :init_db

:deps_fail
echo.
echo [X] 依赖安装失败
echo     公司内网可能屏蔽了 PyPI 下载。请任选其一：
echo       1. 直接复用旧版本的 venv 目录（复制 旧backend\venv 到本目录）
echo       2. 或手动执行: "%PYEXE%" -m pip install -r requirements.txt
echo       3. 或确认能联网后再运行本脚本
echo.
pause
exit /b 1

REM ---------- 4. 初始化数据库（种子库兜底：有旧库直接用，绝不覆盖）----------
:init_db
echo [3/5] 备份数据库（保留最近 10 份）...
"%PYEXE%" backup_db.py
echo [4/5] 初始化数据库...
if not exist "db.sqlite3" (
    if exist "db.sqlite3.seed" (
        echo   首次部署：从种子库生成数据库...
        copy /Y "db.sqlite3.seed" "db.sqlite3" >nul
    )
)
"%PYEXE%" manage.py migrate --noinput
if errorlevel 1 (
    echo [X] 数据库迁移失败
    pause
    exit /b 1
)

REM ---------- 5. 启动服务 ----------
echo [5/5] 启动服务...  端口 %YM_PORT%
start "" "http://127.0.0.1:%YM_PORT%/"
"%PYEXE%" manage.py runserver 0.0.0.0:%YM_PORT% --noreload
echo.
echo 服务已停止。关闭本窗口或按 Ctrl+C 可退出。
pause
