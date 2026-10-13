@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================
echo   反诈卫士 v3.0 - 本地一键启动
echo ================================================
echo.

REM 必须使用项目自带 .venv 的解释器：所有依赖（flask/torch/faiss/easyocr 等）
REM 都装在 .venv 里，系统 Python 没有这些包，直接用 py 会报 ModuleNotFoundError。
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo [错误] 未找到虚拟环境解释器：
    echo        %PY%
    echo.
    echo   请先在本目录下重建虚拟环境：
    echo        py -3.11 -m venv .venv
    echo        .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

"%PY%" run.py

if errorlevel 1 (
    echo.
    echo [提示] 服务异常退出（错误码 %errorlevel%）。常见原因：
    echo   - 5000 端口被占用：改 .env 里的 PORT
    echo   - 依赖缺失：.venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
)

pause
