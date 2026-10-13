#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
反诈卫士 v3.0 - 一键启动脚本
支持完全离线规则模式 / 语义NLP增强模式
"""
import os
import sys
import io
import webbrowser
import time
from threading import Timer

# Windows GBK 终端 UTF-8 兼容
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)


def open_browser():
    time.sleep(2)
    from config import Config
    print(f"\n🔗 正在打开浏览器: http://localhost:{Config.PORT}")
    webbrowser.open(f'http://localhost:{Config.PORT}')


if __name__ == '__main__':
    Timer(1, open_browser).start()

    from config import Config
    print("=" * 60)
    print("  🛡️  多模态智能反诈对话系统 v3.0")
    print("  Anti-Fraud Intelligent Dialogue System")
    print("=" * 60)
    print(f"  项目路径: {BASE_DIR}")
    print(f"  启动地址: http://localhost:{Config.PORT}")
    print(f"  🔒 加密存储: {'已启用' if Config.ENCRYPT_DATA else '未启用'}")
    print(f"  🤖 LLM: {'已连接' if os.getenv('LLM_API_KEY') else '规则引擎模式'}")
    print(f"  🧠 知识图谱: {'已加载' if os.path.exists(os.path.join(BASE_DIR, 'knowledge_base', 'fraud_types.json')) else '未加载'}")
    print(f"  📝 日志: {Config.LOG_FILE}")
    print(f"  按 Ctrl+C 停止服务")
    print("=" * 60)
    print("  功能快捷键:")
    print(f"  📊 管理后台: http://localhost:{Config.PORT}/admin")
    print(f"  📚 API文档: http://localhost:{Config.PORT}/api/docs/ui")
    print("  🔍 健康检查: /api/health")
    print("=" * 60)

    from app import app
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)
