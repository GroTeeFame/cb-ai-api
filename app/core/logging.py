import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings

ReservedLogKeys = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
}

request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")
client_ip_ctx_var: ContextVar[str] = ContextVar("client_ip", default="-")
_logging_configured = False


def get_request_id() -> str:
    """Return the current request identifier stored in the context."""
    return request_id_ctx_var.get("-")


def bind_request_id(request_id: str) -> Token[str]:
    """Store the request id in the context variable and return the token."""
    return request_id_ctx_var.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    """Reset the context variable to the previous value."""
    request_id_ctx_var.reset(token)


def get_client_ip() -> str:
    """Return the current client IP stored in the context."""
    return client_ip_ctx_var.get("-")


def bind_client_ip(client_ip: str) -> Token[str]:
    """Store client IP in context."""
    return client_ip_ctx_var.set(client_ip)


def reset_client_ip(token: Token[str]) -> None:
    """Reset client IP context variable."""
    client_ip_ctx_var.reset(token)


class RequestContextFilter(logging.Filter):
    """Attach contextual information to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - thin shim
        record.request_id = get_request_id()
        record.environment = settings.environment
        record.client_ip = get_client_ip()
        return True


class JsonLogFormatter(logging.Formatter):
    """Render logs as JSON dictionaries to simplify ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "environment": getattr(record, "environment", settings.environment),
            "client_ip": getattr(record, "client_ip", "-"),
        }

        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_entry["stack"] = self.formatStack(record.stack_info)

        self._inject_extra_fields(record, log_entry)
        return json.dumps(log_entry, default=str, ensure_ascii=False)

    @staticmethod
    def _inject_extra_fields(
        record: logging.LogRecord, log_entry: Dict[str, Any]
    ) -> None:
        for key, value in record.__dict__.items():
            if key in ReservedLogKeys:
                continue
            if key.startswith("_"):
                continue
            log_entry.setdefault(key, value)


def configure_logging() -> None:
    """Initialize application-wide logging configuration."""
    global _logging_configured
    if _logging_configured:
        return

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = (
        JsonLogFormatter()
        if settings.log_json
        else logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(request_id)s | %(client_ip)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    stream_handler.addFilter(RequestContextFilter())
    stream_handler.setFormatter(formatter)

    file_handler = _build_file_handler(log_level, formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    handlers = [stream_handler]
    if file_handler:
        handlers.append(file_handler)
    root_logger.handlers = handlers
    root_logger.propagate = False

    logging.captureWarnings(True)
    _logging_configured = True


def _build_file_handler(
    log_level: int, formatter: logging.Formatter
) -> Optional[logging.Handler]:
    """Create a rotating file handler if configuration allows it."""
    log_path = Path(settings.log_file_path)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=settings.log_file_max_bytes,
            backupCount=settings.log_file_backup_count,
        )
    except OSError as exc:  # pragma: no cover - filesystem-specific
        logging.getLogger(__name__).warning(
            "Unable to set up file logging at %s: %s", log_path, exc
        )
        return None

    handler.setLevel(log_level)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(formatter)
    return handler
