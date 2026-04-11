import logging
import sys
from types import FrameType
from typing import cast

from loguru import logger
from app.configs.settings.settings import get_settings

class InterceptHandler(logging.Handler):
    """
    Intercepts standard Python logging messages and routes them to Loguru.
    This ensures FastAPI, Uvicorn, and LangChain logs all share the exact same format.
    """
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = "DEBUG"
            # level = str(record.levelno)

        # Find caller from where the logged message originated
        # This ensures Loguru prints the actual file/line number, not this interceptor file!
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            if frame.f_back:
                frame = cast(FrameType, frame.f_back)
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logging():
    """Configures Loguru and intercepts all standard logging."""
    settings = get_settings()
    log_level = settings.log_level.upper()

    # Remove the default Loguru handler
    logger.remove()

    # 1. Add our custom Loguru handler targeting standard output (Console)
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        enqueue=True,  # Thread-safe for FastAPI async operations
        colorize=True
    )

    # # 2. Add the File Logging handler
    # logger.add(
    #     "logs/app_{time:YYYY-MM-DD}.log",  # Creates a 'logs' folder and names file by date
    #     level=log_level,
    #     format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    #     rotation="10 MB",     # Create a new log file when the current one reaches 10 MB
    #     retention="30 days",  # Keep log files for 30 days, then delete them
    #     compression="zip",    # Compress older log files to save disk space
    #     enqueue=True,         # Thread-safe writing
    #     colorize=False        # Disable color codes for file logs so they are readable in text editors
    # )

    # Intercept everything at the root logger level
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Hijack stubborn third-party loggers (like Uvicorn and FastAPI)
    # Uvicorn creates its own loggers early, so we must overwrite them manually.
    loggers_to_hijack = (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "langchain",
        "langgraph",
        "asyncio",
        "starlette",
        "docling",
        "docling_core",
        "RapidOCR",
        "onnxruntime",
        "urllib3", # Catches those HTTP GET logs from RapidOCR
    )

    for logger_name in loggers_to_hijack:
        hijacked_logger = logging.getLogger(logger_name)
        hijacked_logger.handlers = [InterceptHandler()]
        hijacked_logger.propagate = False # Prevent double-logging
        
        # We let Loguru handle the filtering, so we set standard loggers to lowest level
        hijacked_logger.setLevel(logging.DEBUG)

    logger.success(f"Loguru successfully hijacked standard logging. Level: {log_level}")