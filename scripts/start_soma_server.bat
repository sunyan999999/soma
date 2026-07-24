@echo off
REM === SOMA Server 后台启动脚本 ===
REM 使用 pythonw.exe 无窗口运行，确保 SOMA HTTP 服务在后台持续运行
REM 端口: 8766 | 日志: soma_server.log

cd /d %~dp0..\..

echo [%date% %time%] Starting SOMA Server...

REM 检查是否已在运行
netstat -ano 2>nul | findstr ":8766" >nul
if %errorlevel% equ 0 (
    echo SOMA Server 已在运行 (端口 8766)
    exit /b 0
)

REM 后台启动（无窗口）
start "" /B pythonw -m soma.server --port 8766 > soma_server.log 2>&1

timeout /t 3 /nobreak >nul

REM 验证启动
netstat -ano 2>nul | findstr ":8766" >nul
if %errorlevel% equ 0 (
    echo SOMA Server 启动成功 [http://localhost:8766]
) else (
    echo SOMA Server 启动失败，检查 soma_server.log
    exit /b 1
)
