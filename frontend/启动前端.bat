@echo off
chcp 65001 >nul 2>&1
title 产量监控预警系统 · 前端 v2.17.0
echo ============================================================
echo   产量监控预警系统 · 前端开发服务 v2.17.0
echo   内置 Node 运行时，无需安装 Node.js / 无需 npm install
echo ============================================================
cd /d "%~dp0"

REM ---------- 0. 内置便携 Node（frontend\runtime\node）----------
set "NODE_DIR=%~dp0runtime\node"
set "NODE_EXE=%NODE_DIR%\node.exe"
if not exist "%NODE_EXE%" (
    echo [X] 未找到内置 Node 运行时: %NODE_EXE%
    echo     请确认 frontend\runtime\node 目录已完整解压。
    pause
    exit /b 1
)
set "PATH=%NODE_DIR%;%PATH%"

echo [1/4] 内置 Node 运行时: %NODE_DIR%
"%NODE_EXE%" -v
if errorlevel 1 (
    echo [X] 内置 Node 无法执行，请检查解压完整性。
    pause
    exit /b 1
)

REM ---------- 1. 依赖完整性自检（IT 部署最常见的坑就是 node_modules 解压不全）----------
echo [2/4] 校验前端依赖完整性...
set "VITE_BIN=%~dp0node_modules\vite\bin\vite.js"
set "VITE_CLI=%~dp0node_modules\vite\dist\node\cli.js"
if not exist "%VITE_BIN%" (
    echo [X] 缺少 %VITE_BIN%
    echo     node_modules 解压不完整，请用 7-Zip / WinRAR 重新完整解压。
    pause
    exit /b 1
)
if not exist "%VITE_CLI%" (
    echo [X] 缺少 %VITE_CLI%
    echo     node_modules\vite 解压不完整，请用 7-Zip / WinRAR 重新完整解压。
    pause
    exit /b 1
)
echo   vite 入口 OK

REM ---------- 2. 启动 Vite ----------
REM ★ 2026-09-16：dev 代理目标（vite.config.js 读取 process.env.VITE_DEV_BACKEND）。
REM   后端端口不是 8000 时，在运行本脚本前 set VITE_DEV_BACKEND=http://127.0.0.1:<端口> 即可。
REM   注意：这只影响开发环境；生产构建的前端用相对路径 /api，由 Django 同源提供，与端口无关。
if not defined VITE_DEV_BACKEND set "VITE_DEV_BACKEND=http://localhost:8000"
set "DEV_BACKEND=%VITE_DEV_BACKEND%"
echo [3/4] 启动 Vite 开发服务器 ...
echo       地址: http://127.0.0.1:5173
echo       接口代理: /api  ->  %DEV_BACKEND%（可用 VITE_DEV_BACKEND 覆盖）
echo       提示: 后端需先运行 backend\start.bat（端口不同时先 set VITE_DEV_BACKEND=http://127.0.0.1:<端口>）
echo [4/4] 服务运行中，关闭本窗口即停止。
echo ------------------------------------------------------------
"%NODE_EXE%" "%VITE_BIN%" --host 0.0.0.0 --port 5173
echo.
echo 前端服务已停止。
pause
