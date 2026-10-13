"""
日志系统 - 统一日志配置，支持文件轮转、结构化日志
"""
import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime
from typing import Optional


class JSONFormatter(logging.Formatter):
    """结构化 JSON 日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/antifraud.log",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    use_json: bool = False
):
    """统一配置日志系统"""
    level = getattr(logging, log_level.upper(), logging.INFO)

    # 确保日志目录存在
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # 根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除已有处理器避免重复
    root_logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_fmt = logging.Formatter(
        '[%(asctime)s] %(levelname)-7s %(name)s:%(lineno)d - %(message)s',
        datefmt='%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_fmt)
    root_logger.addHandler(console_handler)

    # 文件处理器（带轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    if use_json:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(levelname)-7s %(name)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
    root_logger.addHandler(file_handler)

    # 设置第三方库日志级别
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"📝 日志系统初始化完成: level={log_level}, file={log_file}")
    logger.info(f"   控制台日志 {'已启用' if console_handler else '未启用'}")
    logger.info(f"   文件日志 {'已启用' if file_handler else '未启用'}")

    return root_logger


class RequestLogger:
    """HTTP 请求日志记录"""

    @staticmethod
    def log_request(environ, response):
        logger = logging.getLogger("access")
        logger.info(
            f"{environ.get('REMOTE_ADDR', '-')} "
            f"{environ.get('REQUEST_METHOD', '-')} "
            f"{environ.get('PATH_INFO', '-')} "
            f"{response.status_code}"
        )
        return response
