# logging_config.py
import logging
import logging.config
import os
from datetime import datetime

# 创建logs目录
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# 全局变量，存储当前会话的日志文件名
_current_session_log_file = None
_session_handlers = {}

# 基础格式化器配置
FORMATTERS = {
    "standard": {
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S"
    },
    "detailed": {
        "format": "%(asctime)s - [%(levelname)s] - %(name)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S"
    },
    "json_like": {
        "format": "%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-15s | %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S"
    }
}

def setup_logging():
    """初始化基础日志配置（仅控制台输出）"""
    # 基础配置，只配置控制台输出
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": FORMATTERS,
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "json_like",
            }
        },
        "loggers": {
            "agent": {
                "handlers": ["console"],
                "level": "DEBUG",
                "propagate": False
            },
            "api": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False
            },
            "utils": {
                "handlers": ["console"],
                "level": "DEBUG",
                "propagate": False
            }
        },
        "root": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    }

    logging.config.dictConfig(logging_config)
    logger = logging.getLogger(__name__)
    logger.info("基础日志系统已初始化（控制台输出）")
    return logger

def setup_session_logging(session_id: str):
    """
    为新的会话创建专属的日志文件

    Args:
        session_id: 会话ID

    Returns:
        日志文件路径
    """
    global _current_session_log_file

    # 生成日志文件名：travel_时间戳_短session_id.log
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    short_session_id = session_id[:8]  # 只取session_id的前8位
    log_filename = os.path.join(LOGS_DIR, f"travel_{timestamp}_{short_session_id}.log")

    _current_session_log_file = log_filename

    # 创建文件处理器
    file_formatter = logging.Formatter(
        fmt="%(asctime)s - [%(levelname)s] - %(name)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_filename, encoding='utf-8', mode='w')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # 错误日志文件
    error_log_filename = os.path.join(LOGS_DIR, f"error_{timestamp}_{short_session_id}.log")
    error_handler = logging.FileHandler(error_log_filename, encoding='utf-8', mode='w')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)

    # 将处理器添加到所有相关的logger
    loggers_to_update = ['agent.amusement', 'api.trival', 'utils', 'root']

    for logger_name in loggers_to_update:
        if logger_name == 'root':
            logger = logging.getLogger()
        else:
            logger = logging.getLogger(logger_name)

        # 移除之前会话的文件处理器（如果有）
        if session_id in _session_handlers:
            old_handlers = _session_handlers[session_id]
            for h in old_handlers:
                if h in logger.handlers:
                    logger.removeHandler(h)

        # 添加新的文件处理器
        logger.addHandler(file_handler)
        logger.addHandler(error_handler)

    # 保存处理器引用，以便后续清理
    _session_handlers[session_id] = [file_handler, error_handler]

    # 记录日志文件创建信息
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info(f"【新会话日志】会话ID: {session_id}")
    logger.info(f"日志文件: {log_filename}")
    logger.info(f"错误日志: {error_log_filename}")
    logger.info("=" * 80)

    return log_filename

def cleanup_session_logging(session_id: str):
    """
    清理会话的日志处理器

    Args:
        session_id: 会话ID
    """
    if session_id not in _session_handlers:
        return

    handlers = _session_handlers[session_id]

    # 从所有logger中移除处理器
    loggers_to_update = ['agent.amusement', 'api.trival', 'utils', 'root']
    for logger_name in loggers_to_update:
        if logger_name == 'root':
            logger = logging.getLogger()
        else:
            logger = logging.getLogger(logger_name)

        for h in handlers:
            if h in logger.handlers:
                logger.removeHandler(h)
            h.close()

    # 删除引用
    del _session_handlers[session_id]

def get_current_log_file():
    """获取当前会话的日志文件路径"""
    return _current_session_log_file

