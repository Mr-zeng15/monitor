@echo off
chcp 65001 >nul
title 关闭产量监控预警系统
echo 正在关闭所有后端服务...
taskkill /IM python.exe /F 2>nul
if errorlevel 1 (
    echo 没有运行中的服务
) else (
    echo 已关闭
)
timeout /t 2 /nobreak >nul
