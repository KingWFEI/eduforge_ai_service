import logging
import os
from logging.handlers import RotatingFileHandler

# 日志目录和文件配置
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "server.log")
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> logging.Logger:
    """
    配置并返回应用级日志记录器。
    同时输出到控制台和文件（带轮转）。
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 文件输出（10MB 轮转，保留 5 个备份）
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
