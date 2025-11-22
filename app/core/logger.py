from functools import lru_cache
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger as loguru_logger
import logging
import sys
import time
from pathlib import Path

from app.core.config import settings


LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)


class PropagateToStandardLogger:
    def write(self, message):
        record = message.record
        level = record["level"].name

        standard_level = level
        if not isinstance(standard_level, int):
            standard_level = logging.INFO

        # Get the logger with the specific name so OTel can track the source
        target_logger = logging.getLogger(record["name"])

        # Log to standard python logger
        target_logger.log(
            standard_level,
            record["message"],
            exc_info=record["exception"],  # Pass exception info if present
        )


def setup_logger():
    # Remove any default handlers (avoid duplicate logs)
    loguru_logger.remove()
    # --- 1. Console Handler: simple human-readable output ---
    loguru_logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <7}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )
    # --- 2. OTel Bridge (The Fix) ---
    # We add the sink that forwards to standard logging. This allows OTel to capture logs correctly.
    loguru_logger.add(PropagateToStandardLogger(), format="{message}")
    logging.basicConfig(level=settings.log_level)

    if settings.debug:
        # --- 2. File Handler: structured JSON logs ---
        loguru_logger.add(
            "logs/app.log",
            serialize=True,
            rotation="10 MB",  # or "00:00" for daily rotation
            retention="20 days",
            compression="zip",
            level="DEBUG",
            enqueue=True,
        )

    return loguru_logger


# initializing logger from get_logger function with cache
@lru_cache(maxsize=1)
def get_logger():
    return setup_logger()


logger = get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Pre-request log
        logger.info(f"→ {request.method} {request.url.path}")

        try:
            response = await call_next(request)
        except Exception as e:
            # Log unhandled exceptions
            logger.exception(f"Unhandled error: {e}")
            raise
        finally:
            process_time = time.time() - start_time

            # Post-request log
            logger.info(
                f"← {request.method} {request.url.path} | "
                f"Status: {getattr(response, 'status_code', 'N/A')} | "
                f"{process_time:.4f}s"
            )

        return response
