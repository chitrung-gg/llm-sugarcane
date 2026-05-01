import logging
import sys
from types import FrameType
from typing import cast

from loguru import logger
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import set_tracer_provider
from opentelemetry.semconv.attributes import service_attributes

from app.configs.settings.settings import get_settings

# class StreamToLogger:
#     """Fake file-like stream object that redirects writes to a logger instance."""
#     def __init__(self, logger, log_level=logging.INFO):
#         self.logger = logger
#         self.log_level = log_level

#     def write(self, buf):
#         for line in buf.rstrip().splitlines():
#             self.logger.log(self.log_level, line.rstrip())

#     def flush(self):
#         pass  # Standard stdout has a flush method

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
            level = record.levelno

        # Find caller from where the logged message originated
        # This ensures Loguru prints the actual file/line number, not this interceptor file!
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def init_opentelemetry():
    """Initializes the OpenTelemetry SDK Tracer Provider."""
    resource = Resource(attributes={
        service_attributes.SERVICE_NAME: "sugarcane-agent"
    })
    provider = TracerProvider(resource=resource)
    # Note: In production, you'd add a BatchSpanProcessor and an Exporter here 
    # (like OTLP or Jaeger). For local logs, the provider itself is enough to generate IDs.
    set_tracer_provider(provider)

def patch_opentelemetry(record):
    """
    Injects OpenTelemetry trace_id and span_id into the log record.
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        ctx = span.get_span_context()
        record["extra"]["trace_id"] = format(ctx.trace_id, "032x")
        record["extra"]["span_id"] = format(ctx.span_id, "016x")
    else:
        record["extra"]["trace_id"] = "0" * 32
        record["extra"]["span_id"] = "0" * 16

def setup_logging():
    """Configures Loguru and intercepts all standard logging."""
    settings = get_settings()
    log_level = settings.LOG_LEVEL.upper()

    # Remove the default Loguru handler
    logger.remove()

    # Define a format that includes trace_id and span_id
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<magenta>{extra[trace_id]}</magenta>:<magenta>{extra[span_id]}</magenta> | "
        "<level>{level: <8}</level> | "

        # Use on production
        # "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - " 

        # Use on development
        "<cyan>{file.path}:{line}</cyan> in <cyan>{function}</cyan> - "   
        "<level>{message}</level>"
    )

    # Add handler with the patcher
    logger.configure(patcher=patch_opentelemetry)

    # 1. Add our custom Loguru handler targeting standard output (Console)
    logger.add(
        sys.stdout,
        level=log_level,
        format=log_format,
        enqueue=True,  # Set to False to prevent pickling errors with complex objects
        colorize=True
    )

    # # 2. Add the File Logging handler
    # logger.add(
    #     "logs/app_{time:YYYY-MM-DD}.log",  # Creates a 'logs' folder and names file by date
    #     level=log_level,
    #     format=log_format,
    #     rotation="10 MB",     # Create a new log file when the current one reaches 10 MB
    #     retention="30 days",  # Keep log files for 30 days, then delete them
    #     compression="zip",    # Compress older log files to save disk space
    #     enqueue=True,         # Thread-safe writing
    #     colorize=False        # Disable color codes for file logs so they are readable in text editors
    # )

    # Redirect all print() to logger
    # sys.stdout = StreamToLogger(logger, logging.INFO)

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
        "deepeval",
    )
    
    for logger_name in loggers_to_hijack:
        hijacked_logger = logging.getLogger(logger_name)
        hijacked_logger.handlers = [InterceptHandler()]
        hijacked_logger.propagate = False # Prevent double-logging

       
        # We let Loguru handle the filtering, so we set standard loggers to lowest level
        hijacked_logger.setLevel(logging.DEBUG)
    
    for logger_name in ["neo4j", "boto3", "botocore", "s3transfer", "urllib3", "aioboto3"]:
        logging.getLogger(logger_name).setLevel(logging.INFO)

    logger.success(f"Loguru successfully hijacked standard logging. Level: {log_level}")