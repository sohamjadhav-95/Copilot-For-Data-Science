# logger.py — Centralized logging for Data Science Copilot
# All logs written to logs_and_debug/ with rotating file handlers
import os
import json
import logging
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

# ═══════════════════════════════════════════════════════════════════════
# DIRECTORY SETUP
# ═══════════════════════════════════════════════════════════════════════

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs_and_debug")
os.makedirs(LOG_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════
# JSON FORMATTER
# ═══════════════════════════════════════════════════════════════════════

class JSONFormatter(logging.Formatter):
    """Structured JSON log format for machine parsing."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach extra fields if present
        for key in ("provider", "model", "latency_ms", "tokens", "status",
                     "intent", "query", "result_type", "error_type",
                     "error_detail", "stack_trace", "context"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class ReadableFormatter(logging.Formatter):
    """Human-readable console format."""
    def format(self, record):
        ts = datetime.now().strftime("%H:%M:%S")
        return f"[{ts}] {record.levelname:<7} {record.name}: {record.getMessage()}"


# ═══════════════════════════════════════════════════════════════════════
# LOGGER FACTORY
# ═══════════════════════════════════════════════════════════════════════

def _make_logger(name, filename, level=logging.DEBUG):
    """Create a logger with rotating file handler + console handler."""
    logger = logging.getLogger(name)
    if logger.handlers:  # already configured
        return logger
    logger.setLevel(level)
    logger.propagate = False

    # File handler (JSON, rotating 5MB x 3 backups)
    fh = RotatingFileHandler(
        os.path.join(LOG_DIR, filename),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(JSONFormatter())
    logger.addHandler(fh)

    # Console handler (readable, INFO+)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(ReadableFormatter())
    logger.addHandler(ch)

    return logger


# ═══════════════════════════════════════════════════════════════════════
# NAMED LOGGERS
# ═══════════════════════════════════════════════════════════════════════

api_logger = _make_logger("copilot.api", "api_calls.log")
interaction_logger = _make_logger("copilot.interaction", "user_interactions.log")
error_logger = _make_logger("copilot.errors", "errors.log")
app_logger = _make_logger("copilot.app", "app.log")


# ═══════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def log_api_call(provider, model, prompt_preview, response_preview,
                 latency_ms, tokens=None, status="success", error=None):
    """Log an API call with full context."""
    extra = {
        "provider": provider,
        "model": model,
        "latency_ms": round(latency_ms, 1),
        "tokens": tokens,
        "status": status,
    }
    msg = f"[{provider}/{model}] {status} ({latency_ms:.0f}ms)"
    if status == "success":
        # Truncate for log readability
        prompt_short = (prompt_preview[:120] + "...") if len(prompt_preview) > 120 else prompt_preview
        resp_short = (response_preview[:200] + "...") if len(response_preview) > 200 else response_preview
        api_logger.info(
            f"{msg} | prompt={prompt_short!r} | response={resp_short!r}",
            extra=extra,
        )
    else:
        extra["error_detail"] = str(error) if error else "unknown"
        api_logger.warning(f"{msg} | error={error}", extra=extra)


def log_interaction(query, intent, resolved_query, result_type, success, details=None):
    """Log a user interaction end-to-end."""
    extra = {
        "query": query,
        "intent": intent,
        "result_type": result_type,
        "status": "success" if success else "failure",
    }
    msg = (f"[{intent}] query={query!r}"
           f"{f' -> resolved={resolved_query!r}' if resolved_query != query else ''}"
           f" | result={result_type} | {'OK' if success else 'FAIL'}")
    if details:
        msg += f" | {details}"
    if success:
        interaction_logger.info(msg, extra=extra)
    else:
        interaction_logger.warning(msg, extra=extra)


def log_error(error, context="", include_traceback=True):
    """Log an error with full context and optional traceback."""
    extra = {
        "error_type": type(error).__name__,
        "error_detail": str(error),
        "context": context,
    }
    if include_traceback:
        extra["stack_trace"] = traceback.format_exc()

    error_logger.error(
        f"[{type(error).__name__}] {error} | context={context}",
        extra=extra,
    )


def log_app_event(event, details=None):
    """Log a general application event."""
    msg = f"[{event}]"
    if details:
        msg += f" {details}"
    app_logger.info(msg)
